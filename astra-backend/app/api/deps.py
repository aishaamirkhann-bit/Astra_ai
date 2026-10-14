"""
Shared FastAPI dependencies: DB session + current authenticated user.
Har protected endpoint me `user: User = Depends(get_current_user)` likho.
"""
import time

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    response: Response,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    cookie_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    access_token = token or cookie_token
    if access_token is None:
        raise credentials_error

    payload = decode_access_token(access_token)
    if payload is None:
        raise credentials_error

    user_id = payload.get("sub")
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
    except (TypeError, ValueError):
        user = None
    if user is None:
        raise credentials_error

    expires_at = payload.get("exp")
    if cookie_token and isinstance(expires_at, (int, float)) and expires_at <= time.time() + 15 * 60:
        refreshed_token = create_access_token(str(user.id), {"role": user.role})
        response.set_cookie(
            key=settings.AUTH_COOKIE_NAME,
            value=refreshed_token,
            httponly=True,
            secure=settings.APP_ENV == "production",
            samesite=settings.AUTH_COOKIE_SAMESITE,
            max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            domain=settings.AUTH_COOKIE_DOMAIN,
        )
    return user


def require_role(*allowed_roles: str):
    """
    Route-level role gate, e.g.:

        @router.post("/products")
        def create_product(
            payload: ProductCreate,
            current_user: User = Depends(require_role("seller")),
        ): ...

    Raises 403 if the authenticated user's role isn't in `allowed_roles`.
    """

    def _checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {', '.join(allowed_roles)}",
            )
        return current_user

    return _checker


def get_current_active_seller(current_user: User = Depends(require_role("seller"))) -> User:
    """Require an authenticated, active seller account for seller workspace APIs."""
    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller account is inactive")
    return current_user
