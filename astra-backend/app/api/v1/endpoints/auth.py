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

from fastapi import APIRouter, Depends, HTTPException, Response, status
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
from app.models.wallet import Wallet
from app.schemas.user import (
    ForgotPasswordRequest,
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


def _issue_otp(db: Session, user: User) -> OtpRequiredResponse:
    code = generate_otp_code()
    user.otp_code_hash = hash_otp(code)
    user.otp_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)
    user.otp_attempts = 0
    db.commit()

    send_otp_email(to_email=user.email, name=user.name, code=code)

    return OtpRequiredResponse(
        otp_token=create_otp_token(user.id),
        email=user.email,
        expires_in_minutes=settings.OTP_EXPIRE_MINUTES,
        message=f"Verification code sent to {user.email}.",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.AUTH_COOKIE_NAME,
        path="/",
        secure=settings.APP_ENV == "production",
        samesite=settings.AUTH_COOKIE_SAMESITE,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )


@router.post("/register", response_model=OtpRequiredResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    _clear_auth_cookie(response)
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        preferred_language=payload.preferred_language,
        role=payload.role,
    )
    db.add(user)
    db.flush()

    # Every new user gets an empty wallet immediately so /goals and /wallet
    # endpoints have something to attach to on first login.
    db.add(Wallet(user_id=user.id, available_balance=0))
    db.commit()
    db.refresh(user)

    return _issue_otp(db, user)


@router.post("/login", response_model=OtpRequiredResponse)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    _clear_auth_cookie(response)
    user = db.query(User).filter(User.email == payload.email).first()
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

    dev_bypass = settings.APP_ENV != "production" and payload.code == DEV_OTP_CODE

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

    dev_bypass = settings.APP_ENV != "production" and payload.code == DEV_OTP_CODE
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


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    _clear_auth_cookie(response)
    return response
