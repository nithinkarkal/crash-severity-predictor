# `/explain` — Per-Prediction SHAP Explanations

**Goal:** move beyond *"the model says severe"* to *"the model says severe **because** the road speed limit was high and the casualty was unbelted."* Every prediction becomes explainable — a big trust win for a safety model, and a strong portfolio feature.

## What it does

`POST /api/v1/explain` takes the **same input as `/predict`** and returns the predicted class plus the features that pushed the model toward that class, ranked by impact (SHAP values).

- Auth: same JWT as `/predict` (`get_current_user`).
- Query param: `top_n` (default 10, 1–30) — how many features to return.
- Model: reuses the cached RandomForest — no extra model load.

## How it works

[`explain_accident()`](../services/backend/src/services/prediction_service.py) builds the input row exactly like `/predict` (shared `_build_input_frame`), predicts the class, then uses `shap.TreeExplainer` to compute per-feature contributions. SHAP returns values shaped `(1, n_features, n_classes)`; `_class_contributions()` selects the predicted class, and the features are ranked by `|SHAP value|`. `shap` is imported **lazily**, so the normal `/predict` path never pays for it.

Sanity property: `base_value + Σ(shap_value) ≈ predicted probability`.

## Example

```bash
TOKEN=$(curl -sk -X POST https://asp.local:8081/api/v1/login -d "username=admin&password=..." | jq -r .access_token)

curl -sk -X POST "https://asp.local:8081/api/v1/explain?top_n=5" \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  --data '{"place":1,"catu":1,"sexe":1,"secu1":0,"year_acc":2023,"victim_age":78,"nb_victim":1,"catv":2,"obsm":0,"motor":1,"nb_vehicles":2,"catr":1,"circ":2,"surf":2,"situ":1,"vma":110,"jour":1,"mois":1,"lum":5,"dep":75,"com":101,"agg":1,"int":1,"atm":1,"col":6,"lat":48.85,"long":2.35,"hour":3}'
```

Response (shape):

```json
{
  "severity": "Injured (hospitalized) / Killed",
  "severity_code": 1,
  "probability": 0.83,
  "base_value": 0.35,
  "summary": "Likely a severe or fatal injury (83% confidence). Main factors increasing this risk: speed limit (vma=110). Factors lowering the risk: safety equipment (secu1=0).",
  "top_features": [
    {"feature": "vma",   "value": 110.0, "shap_value": 0.12,  "direction": "increases"},
    {"feature": "secu1", "value": 0.0,   "shap_value": -0.07, "direction": "decreases"}
  ],
  "model_used": "accident-severity-predictor@production (v10)"
}
```

## Dependency

Adds `shap` to the `backend` dependency group (the backend image already installs `numpy`/`pandas`/`scikit-learn` via the `training` group).
