"""ASP Home dashboard."""

from datetime import UTC, datetime

import streamlit as st

from services.frontend.src.models.health_model import HealthResponse
from services.frontend.src.models.model_info import ModelInfo
from services.frontend.src.services.health_service import get_health
from services.frontend.src.services.model_info_service import get_model_info


def _format_trained_at(value: str) -> str:
    """format ISO timestamp for human-readable display."""

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

        # Example:
        # Mon, 25 Aug 2026 – 16:46 UTC
        return dt.strftime("%a, %d %b %Y – %H:%M UTC")

    except (TypeError, ValueError):
        return value


def _system_status_card(health: HealthResponse) -> None:
    """render the system status card."""

    backend_ok = health.status.lower() == "healthy"
    model_ok = health.model_loaded

    backend_status = "Running" if backend_ok else "Offline"
    model_status = "Loaded" if model_ok else "Unavailable"
    api_status = "Ready" if backend_ok and model_ok else "Unavailable"

    backend_class = "status-ok" if backend_ok else "status-danger"
    model_class = "status-ok" if model_ok else "status-danger"
    api_class = "status-ok" if backend_ok and model_ok else "status-danger"

    st.html(
        f"""
        <div class="asp-card asp-system-card">

            <div class="asp-card-title">
                SYSTEM STATUS
            </div>

            <div class="asp-status-row">
                <span>Backend API</span>
                <span class="{backend_class}">
                    ● {backend_status}
                </span>
            </div>

            <div class="asp-status-row">
                <span>Prediction Model</span>
                <span class="{model_class}">
                    ● {model_status}
                </span>
            </div>

            <div class="asp-status-row">
                <span>Prediction API</span>
                <span class="{api_class}">
                    ● {api_status}
                </span>
            </div>

        </div>
        """
    )


def _model_card(model: ModelInfo) -> None:
    """Render the active model card."""

    trained_at = _format_trained_at(model.trained_at)

    st.html(
        f"""
        <div class="asp-card asp-model-card">

            <div class="asp-card-title">
                ACTIVE MODEL
            </div>

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


def _metric_card(
    label: str,
    value: str,
    description: str,
) -> None:
    """Render a model metric card."""

    st.html(
        f"""
        <div class="asp-metric-card">

            <div class="asp-metric-label">
                {label}
            </div>

            <div class="asp-metric-value">
                {value}
            </div>

            <div class="asp-metric-description">
                {description}
            </div>

        </div>
        """
    )


def home_page() -> None:
    """Render the ASP home dashboard."""

    health: HealthResponse = get_health()
    model: ModelInfo | None = get_model_info()

    # ------------------------------------------------------------
    # PAGE HEADER
    # ------------------------------------------------------------

    st.html(
        """
        <div class="asp-page-header">

            <div class="asp-eyebrow">
                MLOPS DASHBOARD
            </div>

            <h1>
                Accident Severity Predictor
            </h1>

            <p>
                AI-powered predictions for French road accident severity
            </p>

        </div>
        """
    )

    # ------------------------------------------------------------
    # SYSTEM STATUS + ACTIVE MODEL
    # ------------------------------------------------------------

    left, right = st.columns(
        [1, 1],
        gap="medium",
    )

    with left:
        _system_status_card(health)

    with right:
        if model:
            _model_card(model)
        else:
            st.html(
                """
                <div class="asp-card asp-model-card">

                    <div class="asp-card-title">
                        ACTIVE MODEL
                    </div>

                    <div class="asp-model-unavailable">
                        Model metadata is currently unavailable.
                    </div>

                </div>
                """
            )

    # ------------------------------------------------------------
    # MODEL PERFORMANCE
    # ------------------------------------------------------------

    st.html(
        """
        <div class="asp-section-title">
            MODEL PERFORMANCE
        </div>
        """
    )

    if model:
        metrics = model.metrics

        accuracy = metrics.get("accuracy", 0.0)
        f1_score = metrics.get("f1_score", 0.0)
        precision = metrics.get("precision", 0.0)
        recall = metrics.get("recall", 0.0)

        c1, c2, c3, c4 = st.columns(
            4,
            gap="medium",
        )

        with c1:
            _metric_card(
                "ACCURACY",
                f"{accuracy * 100:.1f}%",
                "Test set",
            )

        with c2:
            _metric_card(
                "F1 SCORE",
                f"{f1_score * 100:.1f}%",
                "Test set",
            )

        with c3:
            _metric_card(
                "PRECISION",
                f"{precision * 100:.1f}%",
                "Test set",
            )

        with c4:
            _metric_card(
                "RECALL",
                f"{recall * 100:.1f}%",
                "Test set",
            )

    else:
        st.warning("Model performance metrics are unavailable.")

    # ------------------------------------------------------------
    # ACTIONS
    # ------------------------------------------------------------

    st.html('<div class="asp-action-spacer"></div>')

    c1, c2 = st.columns(
        [1, 1],
        gap="medium",
    )

    with c1:
        if st.button(
            "🚀  Try Prediction",
            use_container_width=True,
            key="home_try_prediction",
        ):
            st.session_state.page = "Prediction"
            st.rerun()

    with c2:
        if st.button(
            "📈  Go to Monitoring",
            use_container_width=True,
            key="home_go_monitoring",
        ):
            st.session_state.page = "Monitoring"
            st.rerun()
