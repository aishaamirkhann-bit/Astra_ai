"""
Auth flow, now with dynamic role + email-OTP 2FA:

  1. POST /auth/register  {name,email,password,role}  -> OtpRequiredResponse
  2. POST /auth/login     {email,password}             -> OtpRequiredResponse
  3. POST /auth/verify-otp {otp_token, code}            -> TokenResponse  (real session starts here)
  4. POST /auth/resend-otp {otp_token}                  -> OtpRequiredResponse

A password alone never issues a session token anymore — every login/register
must be completed with the emailed code. `otp_token` is a short-lived,
privilege-less JWT that just says "this OTP attempt belongs to user X";
it cannot be used to call any protected endpoint.
"""
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import secrets
import smtplib
import time
from typing import Literal
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_otp_token,
    decode_otp_token,
    generate_otp_code,
    hash_otp,
    hash_password,
    verify_otp,
    verify_password,
)
from app.models.user import User
from app.models.seller_profile import SellerProfile
from app.models.seller_wallet import SellerWallet
from app.models.wallet import Wallet
from app.schemas.user import (
    ForgotPasswordRequest,
    ChangeRoleRequest,
    LoginRequest,
    OtpRequiredResponse,
    RegisterRequest,
    ResendOtpRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserOut,
    VerifyOtpRequest,
)
from app.services.email_service import send_otp_email, send_password_reset_email
from app.utils.helpers import as_aware_utc
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Auth"])

# Local-development convenience: this code is accepted as a valid OTP only
# when APP_ENV != "production". Email delivery is unreliable in dev, so this
# keeps the login flow testable. Never enabled in production.
DEV_OTP_CODE = "123456"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_STATE_COOKIE = "astra_google_state"


class GoogleLoginRequest(BaseModel):
    id_token: str
    role: Literal["buyer", "seller"] = "buyer"


def verify_google_id_token(token: str) -> dict:
    """Verify a Google-issued ID token against this app's configured audience."""
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token

    return id_token.verify_oauth2_token(token, GoogleRequest(), settings.GOOGLE_CLIENT_ID)


def _google_user(db: Session, profile: dict, role: Literal["buyer", "seller"]) -> User:
    email = profile.get("email")
    if not isinstance(email, str) or not email.strip() or profile.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Google did not provide a verified email address")
    email = email.strip().lower()
    user = db.query(User).filter(User.email.ilike(email)).first()
    if user is None:
        display_name = profile.get("name")
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = email.split("@", 1)[0]
        user = User(
            name=display_name.strip(),
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            preferred_language="Roman Urdu",
            role=role,
        )
        try:
            db.add(user)
            db.flush()
            db.add(Wallet(user_id=user.id, available_balance=0))
            if role == "seller":
                db.add(SellerProfile(user_id=user.id, role="seller", compliance_status="pending", total_revenue=0))
                db.flush()
                db.add(SellerWallet(seller_id=user.id))
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            user = db.query(User).filter(User.email.ilike(email)).first()
            if user is None:
                raise
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
    return user


def _google_error_redirect(error: str) -> RedirectResponse:
    query = urlencode({"oauth_error": error})
    redirect = RedirectResponse(f"{settings.primary_frontend_url}/login?{query}")
    redirect.delete_cookie(
        GOOGLE_STATE_COOKIE,
        path="/api/v1/auth/google/callback",
        secure=settings.APP_ENV == "production",
        samesite="lax",
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    return redirect


def _google_state(role: Literal["buyer", "seller"] = "buyer") -> str:
    issued_at = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)
    payload = f"{issued_at}.{nonce}.{role}"
    signature = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{payload}.{encoded}"


def _valid_google_state(state: str) -> bool:
    parts = state.split(".")
    if len(parts) != 4 or parts[2] not in {"buyer", "seller"}:
        return False
    issued_at, nonce, role, signature = parts
    try:
        if abs(time.time() - int(issued_at)) > 600:
            return False
    except ValueError:
        return False
    payload = f"{issued_at}.{nonce}.{role}"
    expected = base64.urlsafe_b64encode(hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return hmac.compare_digest(signature, expected)


def _google_state_role(state: str) -> Literal["buyer", "seller"]:
    parts = state.split(".")
    if len(parts) == 4 and parts[2] == "seller":
        return "seller"
    return "buyer"


def _issue_otp(db: Session, user: User) -> OtpRequiredResponse:
    code = generate_otp_code()
    now = datetime.now(timezone.utc)
    user.otp_code_hash = hash_otp(code)
    user.otp_expires_at = now + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    user.otp_sent_at = now
    user.otp_attempts = 0
    try:
        db.flush()
        send_otp_email(to_email=user.email, name=user.name, code=code)
        db.commit()
    except (OSError, RuntimeError, smtplib.SMTPException) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We could not send the verification email. Check the email settings or try again.",
        ) from exc

    message = f"Verification code sent to {user.email}."
    if settings.EMAIL_PROVIDER.lower() == "console" and settings.APP_ENV.lower() in {"test", "development"}:
        message = "Local development email is not configured. Use 123456 to verify; the generated code is also printed in the backend terminal."

    return OtpRequiredResponse(
        otp_token=create_otp_token(user.id),
        email=user.email,
        expires_in_minutes=settings.OTP_EXPIRE_MINUTES,
        message=message,
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.AUTH_COOKIE_NAME,
        path="/",
        secure=settings.APP_ENV == "production",
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )


@router.get("/google/start")
def google_start(role: Literal["buyer", "seller"] = "buyer"):
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return _google_error_redirect("not_configured")
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": _google_state(role),
        "access_type": "online",
        "prompt": "select_account",
    }
    redirect = RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
    redirect.set_cookie(
        key=GOOGLE_STATE_COOKIE,
        value=params["state"],
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite="lax",
        max_age=600,
        path="/api/v1/auth/google/callback",
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    return redirect


@router.post("/google", response_model=TokenResponse)
def google_login(payload: GoogleLoginRequest, response: Response, db: Session = Depends(get_db)):
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="Google login not configured")
    try:
        profile = verify_google_id_token(payload.id_token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Google ID token is invalid or expired") from exc
    user = _google_user(db, profile, payload.role)
    token = create_access_token(subject=str(user.id), extra_claims={"role": user.role})
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return _google_error_redirect("not_configured")
    if error:
        return _google_error_redirect("cancelled")
    browser_state = request.cookies.get(GOOGLE_STATE_COOKIE)
    if (
        not code
        or not state
        or not browser_state
        or not hmac.compare_digest(state, browser_state)
        or not _valid_google_state(state)
    ):
        return _google_error_redirect("invalid_state")
    try:
        with httpx.Client(timeout=10) as client:
            token_response = client.post(GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            })
            token_response.raise_for_status()
            access_token = token_response.json()["access_token"]
            if not isinstance(access_token, str) or not access_token:
                raise ValueError("Google token response did not contain an access token")
            user_response = client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
            user_response.raise_for_status()
            profile = user_response.json()
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return _google_error_redirect("exchange_failed")

    if not isinstance(profile, dict):
        return _google_error_redirect("unverified_email")
    email = profile.get("email")
    if not isinstance(email, str) or not email.strip() or profile.get("email_verified") is not True:
        return _google_error_redirect("unverified_email")
    email = email.strip().lower()
    user = db.query(User).filter(User.email.ilike(email)).first()
    if user is None:
        display_name = profile.get("name")
        if not isinstance(display_name, str) or not display_name.strip():
            display_name = email.split("@", 1)[0]
        user = User(
            name=display_name.strip(),
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
            preferred_language="Roman Urdu",
            role=_google_state_role(state),
        )
        try:
            db.add(user)
            db.flush()
            db.add(Wallet(user_id=user.id, available_balance=0))
            if user.role == "seller":
                db.add(SellerProfile(user_id=user.id, role="seller", compliance_status="pending", total_revenue=0))
                db.flush()
                db.add(SellerWallet(seller_id=user.id))
            db.commit()
            db.refresh(user)
        except IntegrityError:
            db.rollback()
            user = db.query(User).filter(User.email.ilike(email)).first()
            if user is None:
                raise

    token = create_access_token(subject=str(user.id), extra_claims={"role": user.role})
    redirect = RedirectResponse(f"{settings.primary_frontend_url}/auth/callback")
    redirect.delete_cookie(
        GOOGLE_STATE_COOKIE,
        path="/api/v1/auth/google/callback",
        secure=settings.APP_ENV == "production",
        samesite="lax",
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    redirect.set_cookie(
        key=settings.AUTH_COOKIE_NAME, value=token, httponly=True,
        secure=settings.APP_ENV == "production", samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/",
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    return redirect


@router.post("/register", response_model=OtpRequiredResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    _clear_auth_cookie(response)
    email = payload.email.strip().lower()
    existing = db.query(User).filter(User.email.ilike(email)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        name=payload.name,
        email=email,
        hashed_password=hash_password(payload.password),
        preferred_language=payload.preferred_language,
        role=payload.role,
    )
    db.add(user)
    db.flush()

    # Every new user gets an empty wallet immediately so /goals and /wallet
    # endpoints have something to attach to on first login.
    db.add(Wallet(user_id=user.id, available_balance=0))
    if payload.role == "seller":
        db.add(SellerProfile(user_id=user.id, role="seller", compliance_status="pending", total_revenue=0))
        db.flush()
        db.add(SellerWallet(seller_id=user.id, available_balance=0, pending_payouts=0))

    return _issue_otp(db, user)


@router.post("/login", response_model=OtpRequiredResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    _clear_auth_cookie(response)
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None and settings.APP_ENV != "production" and payload.email.lower().endswith("@gmail.com") and len(payload.password) >= 6:
        display_name = payload.email.split("@", 1)[0].replace(".", " ").replace("_", " ").replace("-", " ").title()
        user = User(
            name=display_name or "Astra Buyer",
            email=payload.email,
            hashed_password=hash_password(payload.password),
            preferred_language="Roman Urdu",
            role="buyer",
        )
        db.add(user)
        db.flush()
        db.add(Wallet(user_id=user.id, available_balance=0))
        db.commit()
        db.refresh(user)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

    return _issue_otp(db, user)


@router.post("/verify-otp", response_model=TokenResponse)
def verify_otp_code(payload: VerifyOtpRequest, response: Response, db: Session = Depends(get_db)):
    token_data = decode_otp_token(payload.otp_token)
    if token_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OTP session expired — please log in again")

    user = db.query(User).filter(User.id == int(token_data["sub"])).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending verification for this account")

    dev_bypass = settings.APP_ENV.lower() in {"test", "development"} and payload.code == DEV_OTP_CODE

    if not dev_bypass:
        if user.otp_code_hash is None or user.otp_expires_at is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending verification for this account")

        if datetime.now(timezone.utc) > as_aware_utc(user.otp_expires_at):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Code expired — request a new one")

        if user.otp_attempts >= settings.OTP_MAX_ATTEMPTS:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts — request a new code")

        if not verify_otp(payload.code, user.otp_code_hash):
            user.otp_attempts += 1
            db.commit()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect code")

    # Success — clear the OTP so it can't be replayed, then issue the real session.
    user.otp_code_hash = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    db.commit()
    db.refresh(user)

    access_token = create_access_token(subject=str(user.id), extra_claims={"role": user.role})
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME, value=access_token, httponly=True,
        secure=settings.APP_ENV == "production", samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, path="/",
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    return TokenResponse(access_token=access_token, user=UserOut.model_validate(user))


@router.post("/resend-otp", response_model=OtpRequiredResponse)
def resend_otp(payload: ResendOtpRequest, db: Session = Depends(get_db)):
    token_data = decode_otp_token(payload.otp_token)
    if token_data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OTP session expired — please log in again")

    user = db.query(User).filter(User.id == int(token_data["sub"])).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.otp_sent_at and settings.OTP_RESEND_COOLDOWN_SECONDS > 0:
        elapsed = (datetime.now(timezone.utc) - as_aware_utc(user.otp_sent_at)).total_seconds()
        remaining = settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed
        if remaining > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {int(remaining) + 1} seconds before requesting another code",
            )

    return _issue_otp(db, user)


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is not None:
        code = generate_otp_code()
        user.reset_code_hash = hash_otp(code)
        user.reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
        user.reset_attempts = 0
        db.commit()
        send_password_reset_email(user.email, user.name, code)
    # Same response either way so account existence is never leaked.
    return {"message": f"If that email is registered, a reset code has been sent to {payload.email}."}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if user is None or user.reset_code_hash is None or user.reset_expires_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending reset request for this account")

    if datetime.now(timezone.utc) > as_aware_utc(user.reset_expires_at):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset code expired — request a new one")

    if user.reset_attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many attempts — request a new code")

    dev_bypass = settings.APP_ENV.lower() in {"test", "development"} and payload.code == DEV_OTP_CODE
    if not dev_bypass and not verify_otp(payload.code, user.reset_code_hash):
        user.reset_attempts += 1
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect reset code")

    user.hashed_password = hash_password(payload.new_password)
    user.reset_code_hash = None
    user.reset_expires_at = None
    user.reset_attempts = 0
    # A password change invalidates any half-finished login OTP as well.
    user.otp_code_hash = None
    user.otp_expires_at = None
    user.otp_attempts = 0
    db.commit()
    return {"message": "Password updated — sign in with your new password."}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/role", response_model=TokenResponse)
def change_role(
    payload: ChangeRoleRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.role = payload.role
    if payload.role == "seller" and db.query(SellerProfile).filter(SellerProfile.user_id == current_user.id).first() is None:
        db.add(SellerProfile(user_id=current_user.id))
        db.flush()
    if payload.role == "seller" and db.query(SellerWallet).filter(SellerWallet.seller_id == current_user.id).first() is None:
        db.add(SellerWallet(seller_id=current_user.id))
    db.commit()
    db.refresh(current_user)

    access_token = create_access_token(
        subject=str(current_user.id),
        extra_claims={"role": current_user.role},
    )
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=settings.APP_ENV == "production",
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    return TokenResponse(access_token=access_token, user=UserOut.model_validate(current_user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    _clear_auth_cookie(response)
    return response
