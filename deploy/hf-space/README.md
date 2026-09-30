---
title: Crash Severity Predictor
emoji: 🚗
colorFrom: teal
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Predict French road-accident injury severity, with SHAP explanations.
---

# Crash Severity Predictor — live demo

End-to-end MLOps project that predicts whether a road-accident casualty is **lightly**
vs **severely / fatally** injured, from French open government data (ONISR / BAAC).

This Space runs a single container with:

- a **FastAPI** backend (internal) that loads the champion model from an **MLflow Model
  Registry on DagsHub** at startup, and
- a **Streamlit** GUI (public) for interactive predictions with **plain-language** and
  **SHAP** explanations.

**Demo login:** `demo` / `demo1234` (prediction + explanation access).

> This is the cloud demo (Phase 16 / Track B) of a larger project — the full stack adds
> Airflow retraining, drift-gated promotion, Prometheus/Grafana monitoring, and a
> Kubernetes deployment. Source & docs:
> https://github.com/nithinkarkal/crash-severity-predictor
