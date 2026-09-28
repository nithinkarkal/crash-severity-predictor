"""
Tests for home page
"""

from unittest.mock import MagicMock, patch

import streamlit as st

from services.frontend.src.models.health_model import HealthResponse
from services.frontend.src.models.model_info import ModelInfo
from services.frontend.src.pages.home import home_page


def test_home_page_success() -> None:
    """Test home page with successful health and model info."""

    # Mock health response
    mock_health = MagicMock(spec=HealthResponse)
    mock_health.status = "healthy"
    mock_health.model_loaded = True

    # Mock model info
    mock_model = MagicMock(spec=ModelInfo)
    mock_model.registry_name = "accident-models"
    mock_model.alias = "severity-predictor"
    mock_model.version = "1.0.0"
    mock_model.algorithm = "RandomForest"
    mock_model.trained_at = "2023-01-01T00:00:00Z"
    mock_model.dataset = "accident_data_v1"
    mock_model.features_count = 15
    mock_model.metrics = {"accuracy": 0.92, "precision": 0.89, "recall": 0.87, "f1_score": 0.88}

    with (
        patch("services.frontend.src.pages.home.get_health", return_value=mock_health),
        patch("services.frontend.src.pages.home.get_model_info", return_value=mock_model),
    ):
        # Capture the st.html calls to verify content
        with patch.object(st, "html") as mock_html:
            home_page()

            # Verify that html was called at least once (for header)
            assert mock_html.called


def test_home_page_with_unavailable_model() -> None:
    """Test home page with unavailable model."""

    # Mock health response
    mock_health = MagicMock(spec=HealthResponse)
    mock_health.status = "healthy"
    mock_health.model_loaded = False

    with (
        patch("services.frontend.src.pages.home.get_health", return_value=mock_health),
        patch("services.frontend.src.pages.home.get_model_info", return_value=None),
    ):
        # Capture the st.html calls to verify content
        with patch.object(st, "html") as mock_html:
            home_page()

            # Verify that html was called at least once (for header)
            assert mock_html.called


def test_home_page_with_unhealthy_backend() -> None:
    """Test home page with unhealthy backend."""

    # Mock health response
    mock_health = MagicMock(spec=HealthResponse)
    mock_health.status = "offline"
    mock_health.model_loaded = True

    # Mock model info
    mock_model = MagicMock(spec=ModelInfo)
    mock_model.registry_name = "accident-models"
    mock_model.alias = "severity-predictor"
    mock_model.version = "1.0.0"
    mock_model.algorithm = "RandomForest"
    mock_model.trained_at = "2023-01-01T00:00:00Z"
    mock_model.dataset = "accident_data_v1"
    mock_model.features_count = 15
    mock_model.metrics = {"accuracy": 0.92, "precision": 0.89, "recall": 0.87, "f1_score": 0.88}

    with (
        patch("services.frontend.src.pages.home.get_health", return_value=mock_health),
        patch("services.frontend.src.pages.home.get_model_info", return_value=mock_model),
    ):
        # Capture the st.html calls to verify content
        with patch.object(st, "html") as mock_html:
            home_page()

            # Verify that html was called at least once (for header)
            assert mock_html.called
