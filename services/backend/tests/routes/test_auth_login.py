"""Integration tests for authentication routes."""

import pytest
from fastapi.testclient import TestClient

from services.backend.src.config.settings import Settings, get_settings
from services.backend.src.main import app


@pytest.fixture
def override_settings(fake_settings: Settings):
    app.dependency_overrides[get_settings] = lambda: fake_settings
    yield
    app.dependency_overrides.clear()


class TestLogin:
    def test_login_admin_success(self, client: TestClient, override_settings) -> None:
        response = client.post(
            "/api/v1/login",
            data={"username": "admin", "password": "admin_pwd"},
        )
        assert response.status_code == 200
        json_data = response.json()
        assert "access_token" in json_data
        assert json_data["token_type"] == "bearer"

    def test_login_user_success(self, client: TestClient, override_settings) -> None:
        response = client.post(
            "/api/v1/login",
            data={"username": "datascientest", "password": "user_pwd"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_invalid_credentials(self, client: TestClient, override_settings) -> None:
        response = client.post(
            "/api/v1/login",
            data={"username": "admin", "password": "wrong_password"},
        )
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
