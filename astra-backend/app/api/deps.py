"""
Shared FastAPI dependencies: DB session + current authenticated user.
Har protected endpoint me `user: User = Depends(get_current_user)` likho.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # DEV CONVENIENCE: agar frontend abhi token nahi bhej raha (Home page
    # demo/local dev), to hum seeded demo user "Aisha" wapas kar dete hain.
    # Production me yeh fallback hata dena — sirf valid JWT accept hoga.
    if token is None:
        if settings.APP_ENV == "production":
            # The demo-user fallback is a dev convenience only — never allow
            # unauthenticated requests to silently become "Aisha" in prod.
            raise credentials_error
        demo_user = db.query(User).filter(User.email == "aisha@astra.ai").first()
        if demo_user:
            return demo_user
        raise credentials_error

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_error

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_error
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
