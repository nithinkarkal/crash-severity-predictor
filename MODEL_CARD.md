# Model Card — Crash Severity Predictor

A model card documenting the intended use, performance, limitations, and ethical
considerations of the accident-severity model served by this project. Format follows the
spirit of Mitchell et al., *"Model Cards for Model Reporting"* (2019).

## Model details

| | |
|---|---|
| **Task** | Binary classification of road-accident casualty injury severity |
| **Target** | `grav` — `0` = light (unharmed / slight), `1` = severe (hospitalized / killed) |
| **Algorithm** | `RandomForestClassifier` (scikit-learn) |
| **Key hyperparameters** | `n_estimators=100`, `max_depth=20`, `min_samples_leaf=2`, `min_samples_split=5`, `random_state=42` |
| **Features** | Top-20 features selected from the engineered BAAC fields (road, vehicle, user, environment, location, time) |
| **Preprocessing** | None required at inference (RandomForest is scale-invariant; no feature scaling) |
| **Registry** | MLflow Model Registry on DagsHub, alias-based (`@production` / `@fallback`) |
| **Serving** | FastAPI (JWT auth) behind an NGINX TLS reverse proxy; endpoints `/predict`, `/explain`, `/model/info` |
| **Owner** | Nithin R. Karkal (continued from a 4-person MLOps capstone) |

## Intended use

- **Primary use:** aggregate, decision-support analysis for road-safety stakeholders — e.g.
  estimating the share of severe outcomes under given road/environment conditions to help
  prioritise interventions (signage, speed management, infrastructure).
- **Intended users:** analysts, researchers, and engineers studying road safety; and as an
  end-to-end **MLOps reference implementation**.

### Out-of-scope / prohibited use

- **Not** for making or influencing decisions about identifiable individuals (insurance,
  liability, policing, triage). The model is not designed or validated for that.
- **Not** a real-time emergency-response or medical-triage tool.
- Predictions are **probabilistic and population-level**; they must not be read as a verdict
  about any specific person or accident.

## Training & evaluation data

- **Source:** French national road-accident database (ONISR / BAAC), published as **open data**
  on [data.gouv.fr](https://www.data.gouv.fr/). Four tables joined on `Num_Acc`.
- **Volume:** ~**182,680** accident records.
- **Split:** trained on **2021–2023**; **2024 is held out** as an unseen "future" year for
  out-of-time validation and drift monitoring (never used for training).
- **Class balance:** ~65% light / ~35% severe.

## Performance

| Metric | Value |
|---|---|
| **Binary F1 (severe class)** | **≈ 0.69** |
| Promotion quality gate | **0.65** (a retrained model is promoted only if F1 ≥ 0.65 **and** it beats the current champion) |

F1 (not accuracy) is the headline metric because the data is imbalanced and the cost of
missing a severe outcome is high — accuracy would be inflated by the majority "light" class.
Per-prediction explanations are available via the `/explain` endpoint (SHAP).

## Limitations & biases

- **Imbalance:** the minority "severe" class is harder to predict; recall/precision on it is
  the real constraint, not overall accuracy.
- **Reporting bias:** BAAC records only *reported* accidents; unreported or differently-coded
  events are absent, and coding practices vary across regions and years.
- **Temporal/geographic scope:** trained on France, 2021–2023. Performance on other countries,
  periods, or after distribution shift is not guaranteed — hence the drift monitoring.
- **Quasi-identifiers:** fields such as precise latitude/longitude combined with date, age, and
  sex carry a small theoretical re-identification risk (see GDPR note); the model does not use
  or expose direct identifiers.
- **Not causal:** feature contributions (SHAP) describe the model's associations, not causation.

## Ethical & GDPR considerations

- **Data protection basis:** the source is **anonymised open government data** with **no direct
  identifiers** (no names, IDs, or home addresses). Truly anonymised data falls outside GDPR's
  scope; even so, the project follows **data-protection-by-design**.
- **Data minimisation:** only features needed for the model; identifier-like fields are dropped.
- **No automated decisions about individuals** (GDPR Art. 22): outputs inform aggregate policy,
  not decisions about named people.
- **Security (integrity & confidentiality):** access via tokens kept in git-ignored env files;
  the API is served over **TLS with JWT auth and rate limiting**.
- **Residual risk:** the quasi-identifier point above; if the system were ever extended to
  *personal* data, a DPIA, pseudonymisation, retention/erasure, and audit logging would be added.

## Reproducibility & maintenance

- **Lineage:** every training run is tagged in MLflow with the **DVC data hash** and **git
  commit SHA** (`dvc_processed_data_md5`, `git_commit`), so any model is traceable to the exact
  data and code that produced it. See [`docs/dataset-lineage.md`](docs/dataset-lineage.md).
- **Retraining:** an Airflow DAG runs the full pipeline (ingest → validate → version → train →
  drift/quality-gate → compare → promote → reload) on the annual BAAC release.
- **Drift monitoring:** Evidently compares each new batch against the 2021–2023 baseline;
  Prometheus + Grafana expose model/service metrics with Slack alerting.

## How to reproduce a specific model

```bash
git checkout <git_commit>     # from the run's MLflow tags
dvc checkout                  # restores data/ to the md5 recorded in that commit's dvc.lock
uv run python -m services.training.train
```

---

*This card describes a portfolio/education project built on public data. It is not a validated
production system for decisions about individuals.*
