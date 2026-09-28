# Phase 13 — Explainability & Model Transparency

> **Goal of this phase:** understand the "why did the model say that, and can I trust it?" layer we
> added on top of the API. You'll read the `/explain` endpoint (per-prediction **SHAP** attributions),
> the **plain-language summary** built from those attributions, the `/model/info` endpoint, and the
> **model card** (`MODEL_CARD.md`). These are the second batch of **post-defense enhancements**.

A model that only outputs `severity=1` is a black box. For a *safety* model, "why?" matters as much
as "what?". This phase makes each prediction explainable, readable by a non-expert, and pairs it with
honest documentation of the model's limits.

---

## 13.1 SHAP in one paragraph

**SHAP** (SHapley Additive exPlanations) borrows an idea from game theory: treat each feature as a
"player" that contributes to moving the prediction away from a baseline. For one prediction it gives
a **signed number per feature** — positive = pushed toward the predicted class, negative = pushed
away. The neat property:

```
   base_value  +  Σ(shap_value for every feature)  ≈  the model's predicted probability
```

For a tree model like our RandomForest, `shap.TreeExplainer` computes these exactly and fast.

---

## 13.2 The `/explain` endpoint

Same input as `/predict`, same JWT auth, plus a `top_n` query param:

```python
@router.post("/explain", response_model=ExplanationResponse)
def explain(request: PredictionRequest,
            current_user: Annotated[UserCredentials, Depends(get_current_user)],
            top_n: Annotated[int, Query(ge=1, le=30)] = 10) -> ExplanationResponse:
    return explain_accident(request, top_n=top_n)
```

The service function `explain_accident()` reuses the cached model and the **shared** input builder
(`_build_input_frame`, also used by `/predict` — no duplication), then:

```python
import shap                                   # imported lazily — /predict never pays for it
explainer = shap.TreeExplainer(model)
explanation = explainer(df)
contribs, base_value = _class_contributions(explanation.values, explanation.base_values, prediction)
```

### The shape gotcha (`_class_contributions`)

Modern SHAP returns, for a binary tree classifier, an array shaped **`(1, n_features, 2)`** for
`.values` and **`(1, 2)`** for `.base_values` — i.e. per-sample, per-feature, **per-class**. A very
common bug is assuming a flat 2-D array. `_class_contributions` selects the predicted class and
degrades sensibly for other shapes:

```python
if values.ndim == 3:            # (n_samples, n_features, n_classes)
    contribs = values[0, :, cls]
    base_value = float(base[0, cls] if base.ndim == 2 else base[cls])
elif values.ndim == 2:          # single-output fallback
    contribs = values[0]
    ...
```

Features are then ranked by **absolute** SHAP value (biggest movers first), each tagged
`increases`/`decreases`.

---

## 13.3 Plain-language summary (no LLM)

Raw SHAP numbers are for engineers. A recruiter or road-safety officer wants a sentence. We generate
one **deterministically** from the same contributions — no LLM, no API key, no network:

```python
def _plain_language_summary(severity_code, probability, top_features, n=3) -> str:
    def phrase(fc):
        label = FEATURE_LABELS.get(fc.feature, fc.feature)      # "vma" -> "speed limit"
        value = int(fc.value) if float(fc.value).is_integer() else round(fc.value, 2)
        return f"{label} ({fc.feature}={value})"
    verdict = "Likely a severe or fatal injury" if severity_code == 1 else "Likely a light injury"
    increasing = [phrase(f) for f in top_features if f.shap_value > 0][:n]
    lowering   = [phrase(f) for f in top_features if f.shap_value < 0][:n]
    ...
```

Output:

> *Likely a severe or fatal injury (83% confidence). Main factors increasing this risk: speed limit
> (vma=110), safety equipment (secu1=0). Factors lowering the risk: lighting conditions (lum=1).*

Two deliberate choices:

- **`FEATURE_LABELS`** maps raw BAAC codes to human words — the summary reads naturally but still
  shows the raw `code=value` so it stays verifiable.
- **Template, not LLM.** For a portfolio/safety context this is *better*: deterministic (same input →
  same sentence, so it's testable), free, offline, and CI-safe. An LLM hook can be added later
  without changing the contract — the `summary` field stays the same.

The summary is returned as a first-class field on `ExplanationResponse` (`summary: str`), alongside
`top_features`, `base_value`, `probability`.

---

## 13.4 The `/model/info` endpoint

A read-only metadata endpoint — "what model am I actually talking to?"

```python
def get_model_info() -> dict[str, Any]:
    ...
    feature_importance = {}
    if hasattr(model, "feature_importances_"):
        ranked = sorted(zip(features, model.feature_importances_, strict=False), key=lambda t: t[1], reverse=True)
        feature_importance = {str(f): round(float(v), 6) for f, v in ranked}
    return {"registry_name": ..., "alias": ..., "version": ..., "algorithm": type(model).__name__,
            "dataset": "BAAC 2021-2023", "features_count": len(features),
            "parameters": MODEL_CONFIG["model_parameters"], "feature_importance": feature_importance, ...}
```

Note the distinction from `/explain`: `/model/info` reports **global** feature importance (the
model's overall ranking, straight from `feature_importances_`), while `/explain` reports **local**
SHAP attributions for *one* prediction. Global = "what matters in general"; local = "what mattered
*here*". Both, with no MLflow round-trip — the values come from the already-loaded model.

> Implementation note: this route existed as a scaffold that imported a missing `get_model_info`;
> wiring it up (function + `include_router`) both fixed a broken import *and* turned dead code into a
> working, tested endpoint — a small lesson in not leaving half-built routes in a repo.

---

## 13.5 The model card — `MODEL_CARD.md`

Code explains a single prediction; a **model card** explains the model as a whole. Following Mitchell
et al. (2019), `MODEL_CARD.md` documents:

- **Intended use** and, crucially, **out-of-scope / prohibited use** (no decisions about identifiable
  individuals; not medical triage).
- **Data** (BAAC 2021–2023, ~182k records, 2024 held out) and **performance** (F1 ≈ 0.69, 0.65 gate).
- **Limitations & biases** (class imbalance, reporting bias, quasi-identifiers, no causality).
- **Ethics & GDPR** — anonymised open data, data-minimisation, no Art. 22 automated individual
  decisions, TLS/JWT security, and what a full personal-data setup *would* add (DPIA, pseudonymisation,
  retention/erasure, audit logging).
- **Reproducibility** — points back to the Phase 12 lineage tags.

Why it matters: it's the honest-limits document a reviewer, teammate, or recruiter looks for. It says
"I know what this model *shouldn't* be used for," which is a senior signal.

---

## 13.6 Reproduce it yourself

```powershell
# Unit tests for /explain + the summary wording + /model/info:
uv run pytest services/backend/tests/routes/test_explain.py services/backend/tests/routes/test_model_info.py -q --no-cov
```

Live (needs the stack up and a model loaded — see `docs/explain-endpoint.md` for the full curl):

```powershell
$token = (curl.exe -sk -X POST https://asp.local:8081/api/v1/login -d "username=admin&password=admin123" | ConvertFrom-Json).access_token
curl.exe -sk -X POST "https://asp.local:8081/api/v1/explain?top_n=5" -H "Authorization: Bearer $token" -H "Content-Type: application/json" --data "@severe.json"
curl.exe -sk https://asp.local:8081/api/v1/model/info
```

**Expected:** `/explain` returns `severity`, `probability`, a `summary` sentence, and ranked
`top_features`; `/model/info` returns the algorithm, version, parameters, and global feature
importances.

---

## 13.7 Phase 13 checkpoint

You understand Phase 13 when you can explain:

- The SHAP identity `base_value + Σ(shap) ≈ predicted probability`, and local vs global explanations.
- Why SHAP is imported **lazily** (keeps the `/predict` path lean) and why `_class_contributions`
  has to handle the `(1, n_features, 2)` shape.
- Why the plain-language summary is **template-based** (deterministic, testable, no keys) and how
  `FEATURE_LABELS` keeps it readable yet verifiable.
- The difference between `/model/info` (global importance) and `/explain` (local attribution).
- What a **model card** is for and the main sections of `MODEL_CARD.md` — especially out-of-scope use
  and GDPR.

---

### Where this leaves the project

Phases 12–13 add the reproducibility + transparency layer on top of the end-to-end MLOps system from
Phases 0–9: lineage-tagged runs, explainable predictions, human-readable summaries, a model-info
endpoint, and an honest model card — all green in CI. The remaining roadmap item is **Kubernetes**
(autoscaling + canary), noted in the README.
