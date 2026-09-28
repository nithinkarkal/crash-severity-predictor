"""
Backend settings loaded from .env.backend or environment
"""

import base64
from functools import lru_cache

import bcrypt
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Backend settings loaded from .env.backend or environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env.backend",
        extra="ignore",
    )

    # jwt
    jwt_secret_key: str = Field(default="")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expire_minutes: int = Field(default=180)

    # users
    admin_username: str = Field(default="admin")
    admin_password_hash_b64: str = Field(default="")

    user_username: str = Field(default="datascientest")
    user_password_hash_b64: str = Field(default="")

    def verify_admin(self, password: str) -> bool:
        """verify admin password against bcrypt hash (base64 encoded)."""

        if not self.admin_password_hash_b64:
            return False

        hashed = base64.b64decode(self.admin_password_hash_b64)

        return bcrypt.checkpw(password.encode(), hashed)

    def verify_user(self, password: str) -> bool:
        """verify user password against bcrypt hash (base64 encoded)."""

        if not self.user_password_hash_b64:
            return False

        hashed = base64.b64decode(self.user_password_hash_b64)

        return bcrypt.checkpw(password.encode(), hashed)


@lru_cache
def get_settings() -> Settings:
    return Settings()
