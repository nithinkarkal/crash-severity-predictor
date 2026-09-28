"""ASP Prediction Lab page."""

import requests
import streamlit as st

from services.frontend.src.components.prediction_chart import (
    render_key_factors,
    render_prediction_confidence,
)
from services.frontend.src.config.features_mapping import (
    FEATURE_MAPS,
    FEATURE_RANGES,
    FEATURES_LABELS,
)
from services.frontend.src.models.prediction_model import PredictionResponse
from services.frontend.src.services.model_info_service import get_model_info
from services.frontend.src.services.prediction_service import predict


def _mapped_selectbox(
    feature: str,
    *,
    default_value: int | None = None,
) -> int:
    """Render a human-readable selectbox and return the API value."""

    mapping = FEATURE_MAPS[feature]
    label = FEATURES_LABELS[feature]

    values = list(mapping.keys())

    if default_value is not None and default_value in values:
        default_index = values.index(default_value)
    else:
        default_index = 0

    selected_value = st.selectbox(
        label,
        options=values,
        index=default_index,
        format_func=lambda value: mapping[value],
        key=f"prediction_{feature}",
    )

    return selected_value


def _number_input(
    feature: str,
    *,
    value: int | float,
    step: int | float = 1,
) -> int | float:
    """Render a constrained numeric input using FEATURE_RANGES."""

    label = FEATURES_LABELS[feature]
    min_value, max_value = FEATURE_RANGES[feature]

    return st.number_input(
        label,
        min_value=min_value,
        max_value=max_value,
        value=value,
        step=step,
        key=f"prediction_{feature}",
    )


def _prediction_result_card(
    result: PredictionResponse,
) -> None:
    """Render the prediction result section."""

    # st.html(
    #     """
    #     <div class="asp-card-title">
    #         PREDICTION RESULT
    #     </div>
    #     """
    # )

    # ================================================================
    # RESULT SUMMARY
    # ================================================================

    st.html(
        f"""
        <div style="
            margin-top: 0.5rem;
            padding-top: 0.85rem;
            border-top: 1px solid rgba(128,128,128,0.18);
        ">
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                gap: 1rem;
            ">
                <div>
                    <div style="
                        font-size: 0.72rem;
                        text-transform: uppercase;
                        letter-spacing: 0.08em;
                        opacity: 0.55;
                        margin-bottom: 0.2rem;
                    ">
                        Predicted severity
                    </div>

                    <div style="
                        font-size: 1.35rem;
                        font-weight: 700;
                    ">
                        {result.severity}
                    </div>
                </div>

                <div style="
                    text-align: right;
                ">
                    <div style="
                        font-size: 0.72rem;
                        text-transform: uppercase;
                        letter-spacing: 0.08em;
                        opacity: 0.55;
                        margin-bottom: 0.2rem;
                    ">
                        Model
                    </div>

                    <div style="
                        font-size: 0.82rem;
                        font-weight: 600;
                        opacity: 0.85;
                    ">
                        {result.model_used}
                    </div>
                </div>
            </div>
        </div>
        """
    )

    # ================================================================
    # RESULT VISUALIZATION
    # ================================================================

    visualization_left, visualization_right = st.columns(
        [1, 1],
        gap="large",
    )

    with visualization_left:
        render_prediction_confidence(result)

    with visualization_right:
        model_info = get_model_info()

        if model_info is not None:
            render_key_factors(model_info)


def _prediction_form() -> None:
    """Render the prediction input form."""

    st.html(
        """
        <div class="asp-card-title">
            ACCIDENT INFORMATION
        </div>
        """
    )

    col1, col2 = st.columns(2)

    # ================================================================
    # LEFT COLUMN - VICTIM / VEHICLE / ROAD
    # ================================================================

    with col1:
        place = _mapped_selectbox(
            "place",
            default_value=1,
        )

        catu = _mapped_selectbox(
            "catu",
            default_value=1,
        )

        sexe = _mapped_selectbox(
            "sexe",
            default_value=1,
        )

        secu1 = _mapped_selectbox(
            "secu1",
            default_value=1,
        )

        victim_age = _number_input(
            "victim_age",
            value=30,
        )

        nb_victim = _number_input(
            "nb_victim",
            value=1,
        )

        catv = _mapped_selectbox(
            "catv",
            default_value=2,
        )

        obsm = _mapped_selectbox(
            "obsm",
            default_value=0,
        )

        motor = _mapped_selectbox(
            "motor",
            default_value=0,
        )

        nb_vehicles = _number_input(
            "nb_vehicles",
            value=1,
        )

        catr = _mapped_selectbox(
            "catr",
            default_value=3,
        )

        circ = _mapped_selectbox(
            "circ",
            default_value=2,
        )

        surf = _mapped_selectbox(
            "surf",
            default_value=1,
        )

        situ = _mapped_selectbox(
            "situ",
            default_value=1,
        )

    # ================================================================
    # RIGHT COLUMN - CONDITIONS / LOCATION
    # ================================================================

    with col2:
        vma = _number_input(
            "vma",
            value=50,
        )

        jour = _number_input(
            "jour",
            value=15,
        )

        mois = _number_input(
            "mois",
            value=8,
        )

        lum = _mapped_selectbox(
            "lum",
            default_value=1,
        )

        dep = _number_input(
            "dep",
            value=75,
        )

        com = _number_input(
            "com",
            value=1,
        )

        agg = _mapped_selectbox(
            "agg",
            default_value=1,
        )

        int_value = _mapped_selectbox(
            "int",
            default_value=1,
        )

        atm = _mapped_selectbox(
            "atm",
            default_value=0,
        )

        col = _mapped_selectbox(
            "col",
            default_value=1,
        )

        lat = _number_input(
            "lat",
            value=48.8566,
            step=0.0001,
        )

        longitude = _number_input(
            "long",
            value=2.3522,
            step=0.0001,
        )

        hour = _number_input(
            "hour",
            value=12,
        )

        year_acc = _number_input(
            "year_acc",
            value=2024,
        )

    st.html("<div style='height: 12px;'></div>")

    predict_clicked = st.button(
        "🔮  Predict Severity",
        use_container_width=True,
        type="primary",
    )

    if not predict_clicked:
        return

    # ================================================================
    # AUTHENTICATION
    # ================================================================

    token = st.session_state.get("token")

    if not token:
        st.error("Authentication required. Please log in first.")
        return

    # ================================================================
    # API PAYLOAD
    # ================================================================

    payload = {
        "place": place,
        "catu": catu,
        "sexe": sexe,
        "secu1": secu1,
        "year_acc": year_acc,
        "victim_age": victim_age,
        "nb_victim": nb_victim,
        "catv": catv,
        "obsm": obsm,
        "motor": motor,
        "nb_vehicles": nb_vehicles,
        "catr": catr,
        "circ": circ,
        "surf": surf,
        "situ": situ,
        "vma": vma,
        "jour": jour,
        "mois": mois,
        "lum": lum,
        "dep": dep,
        "com": com,
        "agg": agg,
        "int": int_value,
        "atm": atm,
        "col": col,
        "lat": lat,
        "long": longitude,
        "hour": hour,
    }

    with st.spinner("Running prediction..."):
        try:
            result = predict(
                payload,
                token,
            )

        except requests.exceptions.HTTPError as exc:
            response = exc.response

            if response is not None:
                status_code = response.status_code

                try:
                    detail = response.json().get("detail")
                except ValueError:
                    detail = None

                if status_code == 401:
                    st.error("Authentication failed. Please log in again.")

                elif status_code == 403:
                    st.error("You are not authorized to perform predictions.")

                elif status_code == 422:
                    st.error(f"Invalid prediction input: {detail or 'please verify the provided values.'}")

                elif status_code >= 500:
                    st.error("The prediction backend encountered an internal error.")

                else:
                    st.error(f"Prediction request failed (HTTP {status_code}).")

            else:
                st.error("Prediction request failed.")

            return

        except requests.exceptions.RequestException:
            st.error("Unable to reach the prediction backend. Please verify that the backend is available.")
            return

        except ValueError:
            st.error("The backend returned an invalid prediction response.")
            return

    st.session_state.prediction_result = result


def prediction_page() -> None:
    """Render the ASP Prediction Lab."""

    st.html(
        """
        <div class="asp-page-header">
            <div>
                <div class="asp-eyebrow">
                    MACHINE LEARNING
                </div>

                <h1>
                    Prediction Lab
                </h1>

                <p>
                    Configure accident characteristics and predict
                    road accident severity.
                </p>
            </div>
        </div>
        """
    )

    # ================================================================
    # PREDICTION RESULT - TOP
    # ================================================================

    result = st.session_state.get("prediction_result")

    st.html(
        """
        <div class="asp-card">
            <div class="asp-card-title">
                PREDICTION RESULT
            </div>
        """
    )

    if result is not None:
        _prediction_result_card(result)

    else:
        st.html(
            """
            <div class="asp-prediction-empty-content">
                <div class="asp-prediction-empty-icon">
                    ◎
                </div>

                <div class="asp-prediction-empty-title">
                    Ready for prediction
                </div>

                <div class="asp-prediction-empty-text">
                    Configure the accident information below
                    and click <strong>Predict Severity</strong>.
                </div>
            </div>
            """
        )

    st.html("</div>")

    # ================================================================
    # PREDICTION INPUT - BOTTOM
    # ================================================================

    st.html("<div style='height: 1.25rem;'></div>")

    st.html(
        """
        <div class="asp-card">
            <div class="asp-card-title">
                PREDICTION INPUT
            </div>
        """
    )

    _prediction_form()

    st.html("</div>")
