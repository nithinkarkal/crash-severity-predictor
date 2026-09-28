"""
Metric card component.
"""

import streamlit as st
from pydantic import BaseModel, ConfigDict


class MetricCard(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str
    value: str | None = "N/A"
    delta: str | None = None


def render_metric_card(card: MetricCard) -> None:

    st.metric(
        label=card.title,
        value=card.value or "N/A",
        delta=card.delta,
    )
