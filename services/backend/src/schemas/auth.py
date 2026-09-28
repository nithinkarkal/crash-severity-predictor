"""
User schemas for authentication and authorization.
"""

from pydantic import BaseModel


class UserCredentials(BaseModel):
    """User credentials model for Basic Auth."""

    username: str
    role: str


class Token(BaseModel):
    """Token response model."""

    access_token: str
    token_type: str = "bearer"
