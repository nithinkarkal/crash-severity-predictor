"""Authentication and authorization utilities (JWT)."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from services.backend.src.config.settings import Settings, get_settings
from services.backend.src.schemas.auth import UserCredentials

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/login")


def authenticate_user(username: str, password: str, settings: Settings) -> UserCredentials | None:
    """verify username/password and return UserCredentials."""

    if username == settings.admin_username and settings.verify_admin(password):
        return UserCredentials(username=username, role="admin")

    if username == settings.user_username and settings.verify_user(password):
        return UserCredentials(username=username, role="user")
    return None


def create_access_token(user: UserCredentials, settings: Settings) -> str:
    """create a JWT access token for the authenticated user"""

    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user.username, "role": user.role, "exp": expire}

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> UserCredentials:
    """get the current user based on the JWT token."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str | None = payload.get("sub")
        role: str | None = payload.get("role")

        if username is None or role is None:
            raise credentials_exception

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired") from None
    except jwt.PyJWTError:
        raise credentials_exception from None

    return UserCredentials(username=username, role=role)


def require_admin(
    user: Annotated[UserCredentials, Depends(get_current_user)],
) -> UserCredentials:
    """require admin privileges for the current user."""

    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")

    return user
