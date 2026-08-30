"""
Shared FastAPI dependencies: DB session + current authenticated user.
Har protected endpoint me `user: User = Depends(get_current_user)` likho.
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = token or request.cookies.get(settings.AUTH_COOKIE_NAME)
    if token is None:
        raise credentials_error

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_error

    user_id = payload.get("sub")
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
    except (TypeError, ValueError):
        user = None
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
