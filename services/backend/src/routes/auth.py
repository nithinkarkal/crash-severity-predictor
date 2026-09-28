"""
Authentication routes for the backend.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from services.backend.src.config.settings import Settings, get_settings
from services.backend.src.core.auth import authenticate_user, create_access_token
from services.backend.src.schemas.auth import Token

router = APIRouter(prefix="/api/v1", tags=["Auth"])


@router.post("/login", response_model=Token)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Token:
    """
    authenticate user and return a JWT token.
    """

    user = authenticate_user(form_data.username, form_data.password, settings)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user, settings)
    return Token(access_token=token)
