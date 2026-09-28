"""
Tests for prediction page
"""

from unittest.mock import MagicMock, patch

import requests
import streamlit as st

from services.frontend.src.models.prediction_model import PredictionResponse
from services.frontend.src.pages.prediction import (
    _prediction_form,
    _prediction_result_card,
    prediction_page,
)

COLS = (MagicMock(), MagicMock())


def test_prediction_page_renders_result_card() -> None:
    """Test prediction_page renders the result card when a result exists."""

    mock_result = MagicMock(spec=PredictionResponse)
    mock_result.severity = "high"
    mock_result.probability = 0.85
    mock_result.model_used = "accident_model_v1"

    with (
        patch.object(st, "columns", return_value=COLS),
        patch.object(st, "html") as mock_html,
        patch.object(st, "selectbox", return_value=1),
        patch.object(st, "number_input", return_value=10),
        patch.object(st, "button", return_value=False),
        patch.object(st, "spinner"),
        patch(
            "services.frontend.src.pages.prediction.st.session_state",
            new=MagicMock(get=MagicMock(side_effect=lambda key: None if key == "access_token" else mock_result)),
        ),
        patch("services.frontend.src.pages.prediction._prediction_result_card") as mock_card,
    ):
        prediction_page()

        mock_card.assert_called_once_with(mock_result)
        assert mock_html.called


def test_prediction_page_renders_empty_state() -> None:
    """Test prediction_page renders the empty placeholder when no result."""

    with (
        patch.object(st, "columns", return_value=COLS),
        patch.object(st, "html") as mock_html,
        patch.object(st, "selectbox", return_value=1),
        patch.object(st, "number_input", return_value=10),
        patch.object(st, "button", return_value=False),
        patch.object(st, "spinner"),
        patch(
            "services.frontend.src.pages.prediction.st.session_state",
            new=MagicMock(get=MagicMock(return_value=None)),
        ),
        patch("services.frontend.src.pages.prediction._prediction_result_card") as mock_card,
    ):
        prediction_page()

        mock_card.assert_not_called()
        assert mock_html.called


def test_prediction_form_not_clicked() -> None:
    """Test form does nothing when Predict button is not clicked."""

    messages: list[str] = []
    with (
        patch.object(st, "columns", return_value=COLS),
        patch.object(st, "html"),
        patch.object(st, "selectbox", return_value=1),
        patch.object(st, "number_input", return_value=10),
        patch.object(st, "button", return_value=False),
        patch.object(st, "spinner"),
        patch.object(st, "session_state"),
        patch.object(st, "error", side_effect=lambda msg: messages.append(msg)),
        patch("services.frontend.src.pages.prediction.predict") as mock_predict,
    ):
        _prediction_form()

        mock_predict.assert_not_called()
        assert messages == []


def test_prediction_form_requires_token() -> None:
    """Test form blocks prediction when no access token is set."""

    messages: list[str] = []
    with (
        patch.object(st, "columns", return_value=COLS),
        patch.object(st, "html"),
        patch.object(st, "selectbox", return_value=1),
        patch.object(st, "number_input", return_value=10),
        patch.object(st, "button", return_value=True),
        patch.object(st, "spinner"),
        patch.object(st, "session_state", new=MagicMock(get=MagicMock(return_value=None))),
        patch.object(st, "error", side_effect=lambda msg: messages.append(msg)),
        patch("services.frontend.src.pages.prediction.predict") as mock_predict,
    ):
        _prediction_form()

        mock_predict.assert_not_called()
        assert "Authentication required. Please log in first." in messages


def test_prediction_form_success() -> None:
    """Test form calls predict and stores the result on success."""

    expected = MagicMock(spec=PredictionResponse)
    expected.severity = "high"
    expected.severity_code = 3
    expected.probability = 0.85
    expected.model_used = "accident_model_v1"

    session = MagicMock()
    session.get.return_value = "test-token"

    with (
        patch.object(st, "columns", return_value=COLS),
        patch.object(st, "html"),
        patch.object(st, "selectbox", return_value=1),
        patch.object(st, "number_input", return_value=10),
        patch.object(st, "button", return_value=True),
        patch.object(st, "spinner"),
        patch.object(st, "session_state", new=session),
        patch(
            "services.frontend.src.pages.prediction.predict",
            return_value=expected,
        ) as mock_predict,
    ):
        _prediction_form()

        mock_predict.assert_called_once()
        call_args = mock_predict.call_args_list[0]
        payload, token = call_args.args
        assert token == "test-token"
        assert payload["place"] == 1
        assert payload["catu"] == 1
        assert payload["sexe"] == 1
        assert payload["year_acc"] == 10
        assert payload["long"] == 10
        assert session.prediction_result is expected


def test_prediction_form_failed() -> None:
    """Test form shows an error and skips the session when predict fails."""

    messages: list[str] = []
    session = MagicMock()
    session.get.return_value = "test-token"

    with (
        patch.object(st, "columns", return_value=COLS),
        patch.object(st, "html"),
        patch.object(st, "selectbox", return_value=1),
        patch.object(st, "number_input", return_value=10),
        patch.object(st, "button", return_value=True),
        patch.object(st, "spinner"),
        patch.object(st, "session_state", new=session),
        patch.object(st, "error", side_effect=lambda msg: messages.append(msg)),
        patch(
            "services.frontend.src.pages.prediction.predict",
            side_effect=requests.exceptions.RequestException("down"),
        ) as mock_predict,
    ):
        _prediction_form()

        mock_predict.assert_called_once()
        assert "Unable to reach the prediction backend. Please verify that the backend is available." in messages


def test_prediction_result_card_renders() -> None:
    """Test _prediction_result_card renders the severity and probability."""

    result = MagicMock(spec=PredictionResponse)
    result.severity = "high"
    result.severity_code = 1
    result.probability = 0.85
    result.probabilities = {1: 0.85}
    result.model_used = "accident_model_v1"

    with (
        patch.object(st, "html") as mock_html,
        patch.object(st, "plotly_chart") as mock_chart,
    ):
        _prediction_result_card(result)

        html_arg = mock_html.call_args_list[0].args[0]
        assert "high" in html_arg
        assert "accident_model_v1" in html_arg

        fig = mock_chart.call_args.args[0]
        assert fig.data[0].value == 85.0
        assert fig.data[0].number["suffix"] == "%"
