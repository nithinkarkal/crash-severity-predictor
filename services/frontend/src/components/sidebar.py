"""ASP sidebar navigation."""

import streamlit as st

from services.frontend.src.services.session_service import (
    clear_authenticated_session,
    is_admin,
    is_authenticated,
    request_page,
)


def _nav_button(
    label: str,
    page: str,
) -> None:
    """render a navigation button."""

    if st.button(
        label,
        key=f"nav-{page.lower().replace(' ', '-')}",
        use_container_width=True,
    ):
        request_page(page)
        st.rerun()


def render_sidebar() -> None:
    """render role-aware sidebar navigation."""

    with st.sidebar:
        st.html(
            """
            <div class="asp-sidebar-brand">
                <div class="asp-sidebar-logo">ASP</div>
                <div>
                    <div class="asp-sidebar-title">
                        Accident Severity
                    </div>
                    <div class="asp-sidebar-subtitle">
                        Predictor
                    </div>
                </div>
            </div>
            """
        )

        st.markdown("")

        _nav_button("🏠  Home", "Home")

        if is_authenticated():
            _nav_button(
                "🧪  Prediction Lab",
                "Prediction",
            )

            _nav_button(
                "🧠  Model Insights",
                "Model Insights",
            )

            if is_admin():
                _nav_button(
                    "📊  Monitoring",
                    "Monitoring",
                )

            st.html(
                """
                <div class="asp-sidebar-divider"></div>
                """
            )

            username = st.session_state.get(
                "username",
                "User",
            )

            role = st.session_state.get(
                "role",
                "user",
            )

            role_label = "Administrator" if role == "admin" else "Data Scientist"

            st.html(
                f"""
                <div class="asp-sidebar-user">
                    <div class="asp-sidebar-user-name">
                        {username}
                    </div>
                    <div class="asp-sidebar-user-role">
                        {role_label}
                    </div>
                </div>
                """
            )

            if st.button(
                "🚪  Logout",
                key="nav-logout",
                use_container_width=True,
            ):
                clear_authenticated_session()
                st.rerun()

        else:
            st.html(
                """
                <div class="asp-sidebar-divider"></div>
                """
            )

            _nav_button(
                "🔐  Login",
                "Login",
            )
