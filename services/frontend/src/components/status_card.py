"""
status card component
"""

from dataclasses import dataclass

import streamlit as st


@dataclass(slots=True)
class StatusCard:
    title: str
    value: str
    icon: str


def render_status_card(card: StatusCard) -> None:

    st.metric(label=f"{card.icon} {card.title}", value=card.value)
