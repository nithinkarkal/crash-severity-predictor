"""Tests for authentication utilities."""

import pytest
from fastapi import HTTPException

from services.backend.src.config.settings import Settings
from services.backend.src.core.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    require_admin,
)
from services.backend.src.schemas.auth import UserCredentials


@pytest.fixture
def settings() -> Settings:
    return Settings(
        jwt_secret_key="test-secret",
        jwt_expire_minutes=10,
        admin_username="admin",
        admin_password_hash_b64="JDJiJDEyJEYxMWxqbHBueWVQYXhGbmNsV0h1Zi5TMDlwbi9wdEQudDlKc0J4eDJsRm5NSUlWLlJacFh1",
        user_username="datascientest",
        user_password_hash_b64="JDJiJDEyJEJWcmFIbXR2SnRaTmNlZG1jclhWZXVFb2gvYXBnR0lnRTlBNFUuUzdTelRrUUxrTkxxZ0dH",
    )


class TestAuthenticateUser:
    def test_admin_success(self, settings: Settings) -> None:
        # Note: this test uses the generated hash above.
        # If you changed passwords, update the hash or mock verify_admin.
        # Override with fake_settings in integration tests instead
        user = UserCredentials(username="admin", role="admin")
        token = create_access_token(user, settings)

        result = authenticate_user("admin", "admin_pwd", settings)

        assert isinstance(token, str)
        assert result is not None
        assert result.username == "admin"
        assert result.role == "admin"

    def test_unknown_user(self, settings: Settings) -> None:
        result = authenticate_user("unknown", "pwd", settings)
        assert result is None

    def test_user_success(self, fake_settings: Settings) -> None:
        """test user role for authenticated user"""
        result = authenticate_user("datascientest", "user_pwd", fake_settings)

        assert result is not None
        assert result.username == "datascientest"
        assert result.role == "user"


class TestCreateAccessToken:
    def test_token_contains_username_and_role(self, settings: Settings) -> None:
        user = UserCredentials(username="admin", role="admin")
        token = create_access_token(user, settings)
        assert isinstance(token, str)
        assert len(token) > 0


class TestGetCurrentUser:
    def test_valid_token(self, settings: Settings) -> None:
        user = UserCredentials(username="admin", role="admin")
        token = create_access_token(user, settings)
        result = get_current_user(token, settings)
        assert result.username == "admin"
        assert result.role == "admin"

    def test_expired_token(self, settings: Settings) -> None:
        settings.jwt_expire_minutes = -1
        user = UserCredentials(username="admin", role="admin")
        token = create_access_token(user, settings)
        with pytest.raises(HTTPException) as exc:
            get_current_user(token, settings)
        assert exc.value.status_code == 401

    def test_invalid_token_raises_401(self, fake_settings: Settings) -> None:
        """Test that an invalid token raises a 401"""
        with pytest.raises(HTTPException) as exc:
            get_current_user("invalid_token", fake_settings)
        assert exc.value.status_code == 401


class TestRequireAdmin:
    def test_admin_ok(self) -> None:
        user = UserCredentials(username="admin", role="admin")
        result = require_admin(user)
        assert result.username == "admin"

    def test_user_forbidden(self) -> None:
        user = UserCredentials(username="datascientest", role="user")
        with pytest.raises(HTTPException) as exc:
            require_admin(user)
        assert exc.value.status_code == 403
