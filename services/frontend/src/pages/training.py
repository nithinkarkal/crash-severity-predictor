"""Admin model-training page."""

import time

import requests
import streamlit as st

from services.frontend.src.models.training_model import TrainStatusResponse
from services.frontend.src.services.session_service import is_admin
from services.frontend.src.services.training_service import get_training_status, trigger_training

_STATE_STYLE = {
    "idle": ("⚪", "#6b7280", "Idle"),
    "running": ("🟡", "#f59e0b", "Running"),
    "succeeded": ("✅", "#22c55e", "Succeeded"),
    "failed": ("❌", "#ef4444", "Failed"),
}


def _render_status(status: TrainStatusResponse) -> None:
    """Render the latest training run's status."""

    icon, color, label = _STATE_STYLE.get(status.state, ("⚪", "#6b7280", status.state))

    st.html(
        f"""
        <div style="padding:1rem 1.1rem; border:1px solid rgba(255,255,255,0.08);
             border-radius:12px; background:rgba(255,255,255,0.025);">
            <div style="font-size:0.78rem; opacity:0.6; margin-bottom:0.35rem;">LATEST RUN</div>
            <div style="font-size:1.15rem; font-weight:700; color:{color};">{icon} {label}</div>
            <div style="font-size:0.9rem; opacity:0.85; margin-top:0.4rem;">{status.message}</div>
        </div>
        """
    )

    cols = st.columns(3)
    cols[0].metric("Started", (status.started_at or "—")[:19].replace("T", " "))
    cols[1].metric("Finished", (status.finished_at or "—")[:19].replace("T", " "))
    cols[2].metric("Duration", f"{status.duration_seconds:.0f}s" if status.duration_seconds else "—")

    if status.state == "succeeded":
        info_cols = st.columns(2)
        info_cols[0].metric("Model", status.model_name or "—")
        info_cols[1].metric("Production version", status.version or "—")

        if status.metrics:
            metric_cols = st.columns(len(status.metrics))
            for col, (name, value) in zip(metric_cols, status.metrics.items(), strict=True):
                col.metric(name.replace("_", " ").title(), f"{value:.1%}")

    if status.state == "failed" and status.error:
        st.error(f"Error: {status.error}")


def training_page() -> None:
    """Render the admin-only training trigger + live status."""

    st.title("Model Training")
    st.caption("Trigger a new model training run on the server (admin only).")

    # Defence in depth: page access is already gated in app.py, but re-check here.
    if not is_admin():
        st.error("You are not authorized to trigger training.")
        return

    token = st.session_state.get("token")

    st.info(
        "Training runs in the background on the server (in a Docker container). It reads the "
        "processed dataset, trains a new model, logs it to MLflow, and — if it beats the current "
        "champion and clears the F1 quality gate (0.65) — promotes it and hot-reloads the API."
    )

    model_name = st.text_input(
        "Model name (optional)",
        placeholder="leave blank to auto-resolve the latest",
    )

    # A confirmation gate so a real, expensive run can't be launched by an accidental click.
    confirm = st.checkbox("I understand this launches a real training run on the server.")

    if st.button("🏋️  Start training", type="primary", disabled=not confirm):
        with st.spinner("Requesting training run..."):
            try:
                result = trigger_training(model_name.strip() or None, token)

            except requests.exceptions.HTTPError as exc:
                code = exc.response.status_code if exc.response is not None else None
                if code == 403:
                    st.error("You are not authorized to trigger training.")
                elif code == 401:
                    st.error("Authentication failed. Please log in again.")
                else:
                    st.error(f"Training request failed (HTTP {code}).")
                return

            except requests.exceptions.RequestException:
                st.error("Unable to reach the training backend.")
                return

            except ValueError:
                st.error("The backend returned an invalid training response.")
                return

        st.success(f"{result.message}")

    # ---------------------------------------------------------
    # Live status of the latest run
    # ---------------------------------------------------------

    st.divider()

    header_col, refresh_col, auto_col = st.columns([2, 1, 1])
    header_col.subheader("Training Status")
    refresh = refresh_col.button("🔄 Refresh")
    auto = auto_col.checkbox("Auto (4s)")

    if refresh:
        st.rerun()

    status = get_training_status(token)

    if status is None:
        st.warning("Could not fetch training status.")
        return

    _render_status(status)

    # While a run is in progress, auto-poll every few seconds if enabled.
    if auto and status.state == "running":
        time.sleep(4)
        st.rerun()
