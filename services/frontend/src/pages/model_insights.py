"""ASP Model Insights page."""

from datetime import UTC, datetime

import streamlit as st

from services.frontend.src.components.model_insights_charts import (
    render_feature_importance,
    render_model_metrics,
)
from services.frontend.src.models.model_info import ModelInfo
from services.frontend.src.services.model_info_service import get_model_info


def _format_trained_at(value: str) -> str:
    """Format model training timestamp."""

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        return dt.strftime("%a, %d %b %Y – %H:%M UTC")

    except (TypeError, ValueError):
        return value


def _metadata_card(model: ModelInfo) -> None:
    """Render active model metadata."""

    trained_at = _format_trained_at(model.trained_at)

    st.html(
        f"""
        <div class="asp-card">
            <div class="asp-card-title">ACTIVE MODEL</div>

            <div class="asp-model-name">
                {model.registry_name}
            </div>

            <div class="asp-model-meta">

                <div class="asp-model-meta-item">
                    <span>Version</span>
                    <strong>v{model.version}</strong>
                </div>

                <div class="asp-model-meta-item">
                    <span>Alias</span>
                    <strong>{model.alias}</strong>
                </div>

                <div class="asp-model-meta-item">
                    <span>Algorithm</span>
                    <strong>{model.algorithm}</strong>
                </div>

                <div class="asp-model-meta-item">
                    <span>Features</span>
                    <strong>{model.features_count}</strong>
                </div>

            </div>

            <div class="asp-model-details">
                <span>Trained</span>
                <strong>{trained_at}</strong>
            </div>

            <div class="asp-model-details">
                <span>Dataset</span>
                <strong>{model.dataset}</strong>
            </div>
        </div>
        """
    )


def _parameters_card(model: ModelInfo) -> None:
    """Render model parameters."""

    parameters = model.parameters

    st.html(
        """
        <div class="asp-card">
            <div class="asp-card-title">MODEL PARAMETERS</div>
        """
    )

    columns = st.columns(3)

    items = list(parameters.items())

    for index, (key, value) in enumerate(items):
        with columns[index % 3]:
            st.metric(
                label=key.replace("_", " ").title(),
                value=str(value),
            )

    st.html("</div>")


def model_insights_page() -> None:
    """Render Model Insights."""

    st.html(
        """
        <div class="asp-page-header">
            <div>
                <div class="asp-eyebrow">MODEL ANALYTICS</div>
                <h1>Model Insights</h1>
                <p>
                    Model performance, configuration and feature importance.
                </p>
            </div>
        </div>
        """
    )

    model = get_model_info()

    if model is None:
        st.error("Model metadata is currently unavailable.")
        return

    _metadata_card(model)

    st.html(
        """
        <div class="asp-section-title">
            MODEL PERFORMANCE
        </div>
        """
    )

    render_model_metrics(model)

    st.html(
        """
        <div class="asp-section-title">
            FEATURE IMPORTANCE
        </div>
        """
    )

    if model.feature_importance:
        render_feature_importance(model)
    else:
        st.info("Feature importance is not available for the active model.")

    st.html(
        """
        <div class="asp-section-title">
            TRAINING CONFIGURATION
        </div>
        """
    )

    _parameters_card(model)
