"""Admin monitoring page."""

from __future__ import annotations

import requests
import streamlit as st
import streamlit.components.v1 as components

from services.frontend.src.config.settings import settings
from services.frontend.src.services.api import api_client

# Grafana dashboards to embed (uid -> label), matching infra/monitoring/grafana/dashboards/.
GRAFANA_DASHBOARDS = {
    "nk-asp-api": "API Health",
    "nk-asp-model": "Model",
    "nk-asp-drift": "Drift & Quality Gate",
    "asp-infra": "Infrastructure",
}


def _render_grafana_dashboards() -> None:
    """Embed the live Grafana dashboards (read-only) in tabs."""

    st.divider()
    st.subheader("Live Dashboards (Grafana)")
    st.caption(f"Live Prometheus-backed dashboards, embedded read-only. [Open Grafana in a new tab]({settings.grafana_url}/).")

    tabs = st.tabs(list(GRAFANA_DASHBOARDS.values()))

    for tab, uid in zip(tabs, GRAFANA_DASHBOARDS.keys(), strict=True):
        with tab:
            src = f"{settings.grafana_url}/d/{uid}?orgId=1&kiosk&theme=dark&refresh=10s"
            components.iframe(src, height=620, scrolling=True)

    st.caption(
        "If a panel is blank locally, open the Grafana link above once to accept the "
        "self-signed certificate, then reload this page. (On a real cloud TLS domain this "
        "is seamless.)"
    )


def _status_badge(
    label: str,
    status: str,
    healthy: bool,
) -> None:
    """Render a compact status badge."""

    color = "#22c55e" if healthy else "#ef4444"
    icon = "●" if healthy else "●"

    st.html(
        f"""
        <div style="
            padding: 1rem 1.1rem;
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            background: rgba(255,255,255,0.025);
        ">
            <div style="
                font-size: 0.78rem;
                opacity: 0.65;
                margin-bottom: 0.4rem;
            ">
                {label}
            </div>

            <div style="
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 1.05rem;
                font-weight: 600;
            ">
                <span style="color: {color};">
                    {icon}
                </span>

                {status}
            </div>
        </div>
        """
    )


def _metric_card(
    label: str,
    value: str,
) -> None:
    """Render a model metric card."""

    st.html(
        f"""
        <div style="
            padding: 1rem;
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 12px;
            background: rgba(255,255,255,0.025);
            text-align: center;
        ">
            <div style="
                font-size: 0.75rem;
                opacity: 0.6;
                margin-bottom: 0.35rem;
            ">
                {label}
            </div>

            <div style="
                font-size: 1.35rem;
                font-weight: 700;
            ">
                {value}
            </div>
        </div>
        """
    )


def _load_health() -> dict | None:
    """Fetch backend health information."""

    try:
        response = api_client.get("/health")
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    except requests.exceptions.RequestException as exc:
        st.error(f"Unable to reach backend: {exc}")
        return None


def _load_model_info() -> dict | None:
    """Fetch active model information."""

    try:
        response = api_client.get("/model/info")
        response.raise_for_status()
        return response.json()  # type: ignore[no-any-return]

    except requests.exceptions.RequestException as exc:
        st.error(f"Unable to load model information: {exc}")
        return None


def monitoring_page() -> None:
    """Render the admin monitoring dashboard."""

    st.title("System Monitoring")

    st.caption("Backend health, active model status and performance overview.")

    if st.button(
        "↻ Refresh",
        use_container_width=False,
    ):
        st.rerun()

    with st.spinner("Checking system status..."):
        health = _load_health()
        model_info = _load_model_info()

    st.divider()

    # ---------------------------------------------------------
    # System status
    # ---------------------------------------------------------

    st.subheader("System Status")

    col1, col2 = st.columns(2)

    with col1:
        if health:
            backend_healthy = health.get("status") == "healthy"

            _status_badge(
                "Backend API",
                "Healthy" if backend_healthy else "Unhealthy",
                backend_healthy,
            )
        else:
            _status_badge(
                "Backend API",
                "Unavailable",
                False,
            )

    with col2:
        if health:
            model_loaded = bool(health.get("model_loaded", False))

            _status_badge(
                "Model",
                "Loaded" if model_loaded else "Not loaded",
                model_loaded,
            )
        else:
            _status_badge(
                "Model",
                "Unknown",
                False,
            )

    # ---------------------------------------------------------
    # Active model
    # ---------------------------------------------------------

    if model_info:
        st.divider()
        st.subheader("Active Model")

        model_col1, model_col2, model_col3 = st.columns(3)

        with model_col1:
            st.metric(
                "Model",
                model_info.get(
                    "registry_name",
                    "Unknown",
                ),
            )

        with model_col2:
            st.metric(
                "Version",
                str(
                    model_info.get(
                        "version",
                        "Unknown",
                    )
                ),
            )

        with model_col3:
            st.metric(
                "Algorithm",
                model_info.get(
                    "algorithm",
                    "Unknown",
                ),
            )

        trained_at = model_info.get("trained_at")

        if trained_at:
            st.caption(f"Trained at: {trained_at}")

    # ---------------------------------------------------------
    # Model performance
    # ---------------------------------------------------------

    if model_info:
        metrics = model_info.get(
            "metrics",
            {},
        )

        if metrics:
            st.divider()
            st.subheader("Model Performance")

            metric_columns = st.columns(len(metrics))

            for column, (name, value) in zip(
                metric_columns,
                metrics.items(),
                strict=False,
            ):
                with column:
                    if isinstance(value, (int, float)):
                        formatted = f"{value:.1%}"
                    else:
                        formatted = str(value)

                    _metric_card(
                        name.replace("_", " ").title(),
                        formatted,
                    )

    # ---------------------------------------------------------
    # Configuration
    # ---------------------------------------------------------

    if model_info:
        parameters = model_info.get(
            "parameters",
            {},
        )

        if parameters:
            st.divider()
            st.subheader("Training Configuration")

            st.json(parameters)

    # ---------------------------------------------------------
    # Embedded live Grafana dashboards
    # ---------------------------------------------------------

    _render_grafana_dashboards()
