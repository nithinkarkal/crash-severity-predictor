"""Prediction probability and model-factor visualizations."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from services.frontend.src.models.model_info import ModelInfo
from services.frontend.src.models.prediction_model import ExplanationResponse, PredictionResponse


def _probability_color(
    probability: float,
    *,
    severity_code: int,
) -> str:
    """Return a severity-aware color for the predicted probability."""

    if severity_code == 1:
        if probability >= 0.70:
            return "#ef4444"
        if probability >= 0.40:
            return "#f59e0b"
        return "#22c55e"

    if probability >= 0.70:
        return "#22c55e"
    if probability >= 0.40:
        return "#f59e0b"

    return "#ef4444"


def _build_combined_gauge(
    *,
    severe_probability: float,
) -> go.Figure:
    """Build a single gauge representing the predicted severity probability."""

    value = severe_probability * 100

    color = _probability_color(
        severe_probability,
        severity_code=1,
    )

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=value,
            number={
                "suffix": "%",
                "font": {
                    "size": 34,
                },
            },
            title={
                "text": "Injured / Killed",
                "font": {
                    "size": 15,
                },
            },
            gauge={
                "axis": {
                    "range": [0, 100],
                    "ticksuffix": "%",
                    "tickwidth": 1,
                    "dtick": 25,
                },
                "bar": {
                    "color": color,
                    "thickness": 0.65,
                },
                "bgcolor": "rgba(128, 128, 128, 0.12)",
                "borderwidth": 0,
            },
        )
    )

    fig.update_layout(
        height=280,
        margin={
            "l": 25,
            "r": 25,
            "t": 50,
            "b": 10,
        },
        paper_bgcolor="rgba(0,0,0,0)",
        font={
            "color": "#E5E7EB",
        },
    )

    return fig


def render_prediction_confidence(
    result: PredictionResponse,
) -> None:
    """Render one combined gauge with both class probabilities."""

    # The backend returns a single `probability` for the PREDICTED class (+ severity_code).
    # Derive both class probabilities from it (fall back to a full dict if ever provided).
    probabilities = result.probabilities

    if probabilities:
        unharmed_probability = float(probabilities.get(0, 0.0))
        severe_probability = float(probabilities.get(1, 0.0))
    else:
        predicted = float(result.probability) if result.probability is not None else 0.0
        severe_probability = predicted if result.severity_code == 1 else 1.0 - predicted
        unharmed_probability = 1.0 - severe_probability

    gauge_column, summary_column = st.columns(
        [1.15, 0.85],
        gap="medium",
    )

    # ================================================================
    # GAUGE
    # ================================================================

    with gauge_column:
        fig = _build_combined_gauge(
            severe_probability=severe_probability,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "displayModeBar": False,
            },
        )

    # ================================================================
    # PROBABILITY SUMMARY
    # ================================================================

    with summary_column:
        st.html(
            f"""
            <div style="
                padding: 1.25rem 0.75rem;
                margin-top: 2.2rem;
            ">
                <div style="
                    font-size: 0.75rem;
                    text-transform: uppercase;
                    letter-spacing: 0.08em;
                    opacity: 0.60;
                    margin-bottom: 0.75rem;
                ">
                    Prediction confidence
                </div>

                <div style="
                    display: flex;
                    justify-content: space-between;
                    align-items: baseline;
                    margin-bottom: 0.45rem;
                ">
                    <span style="
                        font-size: 0.82rem;
                        opacity: 0.75;
                    ">
                        Unharmed / Lightly injured
                    </span>

                    <strong style="
                        font-size: 1.05rem;
                    ">
                        {unharmed_probability:.0%}
                    </strong>
                </div>

                <div style="
                    height: 7px;
                    border-radius: 999px;
                    background: rgba(128,128,128,0.18);
                    overflow: hidden;
                    margin-bottom: 1rem;
                ">
                    <div style="
                        width: {unharmed_probability * 100:.2f}%;
                        height: 100%;
                        background: #22c55e;
                        border-radius: 999px;
                    "></div>
                </div>

                <div style="
                    display: flex;
                    justify-content: space-between;
                    align-items: baseline;
                    margin-bottom: 0.45rem;
                ">
                    <span style="
                        font-size: 0.82rem;
                        opacity: 0.75;
                    ">
                        Injured / Killed
                    </span>

                    <strong style="
                        font-size: 1.05rem;
                    ">
                        {severe_probability:.0%}
                    </strong>
                </div>

                <div style="
                    height: 7px;
                    border-radius: 999px;
                    background: rgba(128,128,128,0.18);
                    overflow: hidden;
                ">
                    <div style="
                        width: {severe_probability * 100:.2f}%;
                        height: 100%;
                        background: #ef4444;
                        border-radius: 999px;
                    "></div>
                </div>
            </div>
            """
        )


def render_local_factors(explanation: ExplanationResponse, top_n: int = 6) -> None:
    """Render the top per-prediction SHAP factors as a signed horizontal bar chart.

    Positive contributions (push toward severe/fatal) are red; negative (push toward
    light) are green — matching the risk semantics of the confidence gauge.
    """

    factors = explanation.top_features[:top_n]

    if not factors:
        return

    # smallest |shap| at top so the biggest bar sits at the bottom of the chart
    ordered = sorted(factors, key=lambda f: abs(f.shap_value))

    names = [f.feature for f in ordered]
    values = [f.shap_value for f in ordered]
    colors = ["#ef4444" if v >= 0 else "#22c55e" for v in values]
    hover = [f"{f.feature} = {f.value:g}<br>{'increases' if f.shap_value >= 0 else 'lowers'} risk by {abs(f.shap_value):.3f}" for f in ordered]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=names,
            orientation="h",
            marker={"color": colors},
            text=hover,
            hovertemplate="%{text}<extra></extra>",
        )
    )

    fig.update_layout(
        height=330,
        margin={"l": 10, "r": 20, "t": 35, "b": 25},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#E5E7EB"},
        xaxis={
            "title": "SHAP contribution (→ severe)",
            "zeroline": True,
            "zerolinecolor": "rgba(128,128,128,0.4)",
            "gridcolor": "rgba(128,128,128,0.12)",
        },
        yaxis={"tickfont": {"size": 11}},
    )

    st.html(
        """
        <div style="margin-top: 0.25rem; margin-bottom: 0.15rem; font-size: 0.95rem; font-weight: 600;">
            Why this prediction
        </div>
        <div style="margin-bottom: 0.25rem; font-size: 0.78rem; opacity: 0.65;">
            Top factors for this specific case (SHAP)
        </div>
        """
    )

    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_key_factors(model_info: ModelInfo) -> None:
    """Render the top global model factors as a radar chart."""

    feature_importance = getattr(
        model_info,
        "feature_importance",
        None,
    )

    if not feature_importance:
        return

    top_features = sorted(
        feature_importance.items(),
        key=lambda item: item[1],
        reverse=True,
    )[:6]

    if not top_features:
        return

    names = [name for name, _ in top_features]

    importances = [float(value) for _, value in top_features]

    max_importance = max(importances)

    if max_importance <= 0:
        return

    # Normalize values so the most important feature reaches 100.
    normalized = [(value / max_importance) * 100 for value in importances]

    # Close the radar polygon.
    radar_names = names + [names[0]]
    radar_values = normalized + [normalized[0]]

    actual_percentages = [value * 100 for value in importances]

    hover_values = [
        f"{name}<br>Global importance: {value:.2f}%"
        for name, value in zip(
            names,
            actual_percentages,
            strict=True,
        )
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=radar_values,
            theta=radar_names,
            fill="toself",
            name="Model factors",
            text=hover_values + [hover_values[0]],
            hovertemplate="%{text}<extra></extra>",
            line={
                "width": 2,
            },
            marker={
                "size": 6,
            },
        )
    )

    fig.update_layout(
        height=330,
        margin={
            "l": 65,
            "r": 65,
            "t": 35,
            "b": 35,
        },
        paper_bgcolor="rgba(0,0,0,0)",
        polar={
            "radialaxis": {
                "visible": True,
                "range": [0, 100],
                "showticklabels": False,
                "gridwidth": 1,
            },
            "angularaxis": {
                "tickfont": {
                    "size": 10,
                },
            },
        },
        showlegend=False,
    )

    st.html(
        """
        <div style="
            margin-top: 0.25rem;
            margin-bottom: 0.15rem;
            font-size: 0.95rem;
            font-weight: 600;
        ">
            Key Model Factors
        </div>

        <div style="
            margin-bottom: 0.25rem;
            font-size: 0.78rem;
            opacity: 0.65;
        ">
            Top global feature importances
        </div>
        """
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": False,
        },
    )
