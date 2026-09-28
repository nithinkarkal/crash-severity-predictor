"""Model Insights Plotly charts."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from services.frontend.src.models.model_info import ModelInfo

METRIC_LABELS = {
    "accuracy": "Accuracy",
    "precision": "Precision",
    "recall": "Recall",
    "f1_score": "F1 Score",
}


def render_model_metrics(model: ModelInfo) -> None:
    """Render model evaluation metrics."""

    metrics = [(label, model.metrics[key] * 100) for key, label in METRIC_LABELS.items() if key in model.metrics]

    if not metrics:
        return

    labels = [item[0] for item in metrics]
    values = [item[1] for item in metrics]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            text=[f"{value:.1f}%" for value in values],
            textposition="inside",
            hovertemplate=("<b>%{y}</b><br>Score: %{x:.1f}%<extra></extra>"),
        )
    )

    fig.update_layout(
        height=220,
        margin=dict(l=0, r=0, t=5, b=5),
        xaxis=dict(
            range=[0, 100],
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            fixedrange=True,
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            fixedrange=True,
            automargin=True,
        ),
        showlegend=False,
    )

    st.plotly_chart(
        fig,
        width="stretch",
        config={"displayModeBar": False, "responsive": True},
    )


def render_feature_importance(model: ModelInfo) -> None:
    """Render top feature importances."""

    if not model.feature_importance:
        return

    top_features = sorted(
        model.feature_importance.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:10]

    top_features.reverse()

    labels = [item[0] for item in top_features]
    values = [item[1] * 100 for item in top_features]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            text=[f"{value:.1f}%" for value in values],
            textposition="inside",
            hovertemplate=("<b>%{y}</b><br>Importance: %{x:.2f}%<extra></extra>"),
        )
    )

    fig.update_layout(
        height=420,
        margin=dict(l=0, r=0, t=5, b=5),
        xaxis=dict(
            showgrid=False,
            showticklabels=False,
            zeroline=False,
            fixedrange=True,
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            fixedrange=True,
            automargin=True,
        ),
        showlegend=False,
    )

    st.plotly_chart(
        fig,
        width="stretch",
        config={"displayModeBar": False, "responsive": True},
    )
