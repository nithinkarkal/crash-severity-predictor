"""ASP frontend entrypoint."""

from pathlib import Path

import streamlit as st

from services.frontend.src.components.sidebar import render_sidebar
from services.frontend.src.config.settings import settings
from services.frontend.src.pages.home import home_page
from services.frontend.src.pages.login import login_page
from services.frontend.src.pages.model_insights import model_insights_page
from services.frontend.src.pages.monitoring import monitoring_page
from services.frontend.src.pages.prediction import prediction_page
from services.frontend.src.services.session_service import (
    initialize_session,
    is_admin,
    is_authenticated,
)


def load_css() -> None:
    """load application CSS."""

    css = Path(__file__).parent / "assets" / "style.css"

    with open(css, encoding="utf-8") as file:
        st.markdown(
            f"<style>{file.read()}</style>",
            unsafe_allow_html=True,
        )


def enforce_page_access() -> None:
    """ensure the requested page is accessible."""

    page = st.session_state.get(
        "page",
        "Home",
    )

    protected_pages = {
        "Prediction",
        "Model Insights",
        "Monitoring",
    }

    if page not in protected_pages:
        return

    if not is_authenticated():
        st.session_state.post_login_page = page
        st.session_state.page = "Login"
        return

    if page == "Monitoring" and not is_admin():
        st.session_state.page = "Home"


def main() -> None:
    """run the ASP frontend."""

    initialize_session()

    st.set_page_config(
        page_title=settings.page_title,
        page_icon=settings.page_icon,
        layout=settings.layout,
        initial_sidebar_state=settings.sidebar_state,
    )

    load_css()

    enforce_page_access()

    render_sidebar()

    page = st.session_state.get(
        "page",
        "Home",
    )

    if page == "Home":
        home_page()

    elif page == "Prediction":
        prediction_page()

    elif page == "Monitoring":
        monitoring_page()

    elif page == "Login":
        login_page()

    elif page == "Model Insights":
        model_insights_page()


if __name__ == "__main__":
    main()
