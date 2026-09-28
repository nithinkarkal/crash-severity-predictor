"""
Tests for prediction chart component
"""

from unittest.mock import MagicMock, patch

import pytest
import streamlit as st

from services.frontend.src.components.prediction_chart import (
    _build_combined_gauge,
    _probability_color,
    render_key_factors,
    render_prediction_confidence,
)
from services.frontend.src.models.model_info import ModelInfo
from services.frontend.src.models.prediction_model import PredictionResponse


class TestProbabilityColor:
    """Tests for the severity-aware color helper."""

    def test_severe_high_probability(self) -> None:
        assert (
            _probability_color(
                0.85,
                severity_code=1,
            )
            == "#ef4444"
        )

    def test_severe_mid_probability(self) -> None:
        assert (
            _probability_color(
                0.55,
                severity_code=1,
            )
            == "#f59e0b"
        )

    def test_severe_low_probability(self) -> None:
        assert (
            _probability_color(
                0.20,
                severity_code=1,
            )
            == "#22c55e"
        )

    def test_non_severe_high_probability(self) -> None:
        assert (
            _probability_color(
                0.90,
                severity_code=0,
            )
            == "#22c55e"
        )

    def test_non_severe_mid_probability(self) -> None:
        assert (
            _probability_color(
                0.50,
                severity_code=0,
            )
            == "#f59e0b"
        )

    def test_non_severe_low_probability(self) -> None:
        assert (
            _probability_color(
                0.10,
                severity_code=0,
            )
            == "#ef4444"
        )


class TestBuildCombinedGauge:
    """Tests for the single gauge builder."""

    @pytest.mark.parametrize(
        ("probability", "expected_color"),
        [
            (0.85, "#ef4444"),
            (0.55, "#f59e0b"),
            (0.20, "#22c55e"),
        ],
    )
    def test_gauge_color_follows_severity(
        self,
        probability: float,
        expected_color: str,
    ) -> None:
        from typing import cast

        import plotly.graph_objects as go

        fig = _build_combined_gauge(
            severe_probability=probability,
        )

        indicator = cast(go.Indicator, fig.data[0])
        assert indicator.mode == "gauge+number"
        assert float(indicator.value) == pytest.approx(probability * 100)
        assert indicator.gauge["bar"]["color"] == expected_color


class TestRenderPredictionConfidence:
    """Tests for the combined gauge rendering."""

    def test_renders_gauge_and_summary(self) -> None:
        result = PredictionResponse(
            severity="Injured / Killed",
            severity_code=1,
            probability=0.72,
            probabilities={0: 0.28, 1: 0.72},
            model_used="severity-predictor",
        )

        plotly = MagicMock()
        columns = (MagicMock(), MagicMock())

        with patch.object(st, "plotly_chart", plotly), patch.object(st, "columns", return_value=columns) as stub_columns:
            render_prediction_confidence(result)

        assert stub_columns.call_args.args == ([1.15, 0.85],)
        plotly.assert_called_once()
        gauge_fig = plotly.call_args.args[0]
        assert gauge_fig.data[0].mode == "gauge+number"


class TestRenderKeyFactors:
    """Tests for the feature-importance radar chart."""

    def _build_model(
        self,
        feature_importance: dict[str, float] | None,
    ) -> ModelInfo:
        return ModelInfo(
            registry_name="accident-models",
            alias="severity-predictor",
            version="1.0.0",
            algorithm="RandomForest",
            trained_at="2023-01-01T00:00:00Z",
            dataset="accident_data_v1",
            features_count=15,
            metrics={"accuracy": 0.92},
            parameters={"n_estimators": 300},
            feature_importance=(feature_importance if feature_importance is not None else {}),
        )

    def test_renders_radar_chart(self) -> None:
        model = self._build_model(
            {
                "hour": 0.18,
                "day": 0.12,
                "weather": 0.09,
                "road": 0.05,
                "age": 0.03,
                "sex": 0.02,
                "irrelevant": 0.01,
            }
        )

        with (
            patch.object(st, "plotly_chart") as plotly,
            patch.object(st, "html") as html,
        ):
            render_key_factors(model)

        html.assert_called()
        plotly.assert_called_once()

        fig = plotly.call_args.args[0]
        trace = fig.data[0]
        assert trace.name == "Model factors"
        assert len(trace.theta) == 7
        assert trace.theta[0] == "hour"

    def test_no_feature_importance_is_noop(self) -> None:
        model = self._build_model(None)

        with (
            patch.object(st, "plotly_chart") as plotly,
            patch.object(st, "html") as html,
        ):
            render_key_factors(model)

        plotly.assert_not_called()
        html.assert_not_called()

    def test_zero_importance_is_noop(self) -> None:
        model = self._build_model({"hour": 0.0, "day": 0.0})

        with (
            patch.object(st, "plotly_chart") as plotly,
            patch.object(st, "html") as html,
        ):
            render_key_factors(model)

        plotly.assert_not_called()
        html.assert_not_called()
