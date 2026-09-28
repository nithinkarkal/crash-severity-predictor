"""Tests for settings configuration."""

from services.backend.src.config.settings import Settings, get_settings


class TestVerifyAdmin:
    """Tests for admin verification."""

    def test_empty_hash_returns_false(self) -> None:
        settings = Settings(admin_password_hash_b64="")
        assert settings.verify_admin("any_password") is False


class TestVerifyUser:
    """Tests for user verification."""

    def test_empty_hash_returns_false(self) -> None:
        settings = Settings(user_password_hash_b64="")
        assert settings.verify_user("any_password") is False

    def test_valid_password(self, fake_settings: Settings) -> None:
        """b64decode + bcrypt.checkpw for verify_user."""
        assert fake_settings.verify_user("user_pwd") is True


class TestGetSettings:
    def test_returns_settings_instance(self) -> None:
        result = get_settings()
        assert isinstance(result, Settings)

    def test_uses_lru_cache(self) -> None:
        """return settings and verify cache"""
        result1 = get_settings()
        result2 = get_settings()
        assert result1 is result2  # same instance
