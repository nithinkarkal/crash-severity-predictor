"""
ASP global frontend settings
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# type stricts streamlit set_page_config
LayoutType = Literal["centered", "wide"]
SidebarStateType = Literal["auto", "collapsed", "expanded", "locked"]


class Settings(BaseSettings):
    """frontend configuration"""

    model_config = SettingsConfigDict(
        env_file=".env.frontend",
        extra="ignore",
    )

    # backend
    backend_url: str = "http://localhost:8000"
    api_prefix: str = "/api/v1"

    # grafana (for embedded dashboards on the monitoring page)
    grafana_url: str = "https://asp.local:8081/grafana"

    # app
    app_name: str = "Accident Severity Predictor"
    app_short_name: str = "ASP"
    page_title: str = "ASP - Accident Severity Predictor"
    page_icon: str = "🚗"
    layout: LayoutType = "wide"
    sidebar_state: SidebarStateType = "collapsed"

    # theme
    primary_color: str = "#599191"
    background_color: str = "#192E36"

    # deployment — when true (public cloud demo), the login page shows/pre-fills
    # demo credentials. Predict + explain only; the demo `user` role never sees
    # Monitoring or Training. Driven by env vars CLOUD_DEMO / DEMO_USERNAME / DEMO_PASSWORD.
    cloud_demo: bool = False
    demo_username: str = "demo"
    demo_password: str = "demo1234"


settings = Settings()
