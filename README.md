# Crash Severity Predictor

**End-to-end MLOps pipeline that predicts road-accident injury severity from French open government data (ONISR / BAAC).**

### 🌐 [**Live demo → crash-severity.duckdns.org**](https://crash-severity.duckdns.org/)

Running on real Kubernetes (k3s) in the cloud, with HTTPS. Sign in with **`demo`** / **`demo1234`** to try a prediction and its SHAP explanation. *(First load may take a few seconds to wake.)*

[![Live demo](https://img.shields.io/badge/live%20demo-crash--severity.duckdns.org-brightgreen)](https://crash-severity.duckdns.org/)
![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Model](https://img.shields.io/badge/model-RandomForest-2f8a53)
![F1](https://img.shields.io/badge/F1-0.69%20(gate%200.65)-success)
![Tests](https://img.shields.io/badge/tests-185%20passing-brightgreen)
![Lint](https://img.shields.io/badge/lint-ruff%20%2B%20mypy-000000)
![Docker](https://img.shields.io/badge/Docker-compose-2496ED?logo=docker&logoColor=white)
![Kubernetes](https://img.shields.io/badge/Kubernetes-manifests-326CE5?logo=kubernetes&logoColor=white)
![GUI](https://img.shields.io/badge/GUI-Streamlit-FF4B4B?logo=streamlit&logoColor=white)
[![CI](https://github.com/nithinkarkal/crash-severity-predictor/actions/workflows/asp-ci.yaml/badge.svg)](https://github.com/nithinkarkal/crash-severity-predictor/actions/workflows/asp-ci.yaml)

> **Origin & credit:** This project began as a 4-person MLOps capstone. This repository is my
> continued, independently-maintained version. On the original build, my ownership was **workflow
> orchestration (Airflow), drift detection & the F1 quality gate, and monitoring & alerting
> (Prometheus / Grafana / Slack)**. Ongoing improvements here are my own — see the
> [Roadmap](#roadmap).
>
> **Built solo (post-capstone):** dataset lineage tagging (DVC hash + git SHA into every MLflow
> run), the `/explain` SHAP endpoint with plain-language rationale, the [model card](MODEL_CARD.md),
> a role-based **Streamlit GUI** (predict · explain · admin training · embedded Grafana, 2 logins),
> **Kubernetes** deployment (serving + monitoring via Ingress), and migration to my **own MLflow
> model registry** (env-configurable DagsHub).

---

## What it does

Given the circumstances of a road accident (road type, speed limit, lighting, safety equipment,
road-user type, location, …), the service predicts whether a casualty is **lightly** vs
**severely / fatally** injured — and wraps that model in a full production stack: automated
retraining, drift-gated promotion, a registry-backed API, and live monitoring.

| | |
|---|---|
| **Data** | ONISR / BAAC open data, ~**182,680** accident records, **2021–2023** (2024 held out for drift) |
| **Target** | Binary injury severity — `0` light · `1` severe/fatal (≈ 65/35 imbalance) |
| **Model** | `RandomForestClassifier` (100 trees, depth 20), top-20 predictive features |
| **Headline metric** | **F1 ≈ 0.69** on the severe class · promotion **quality gate at 0.65** |
| **Tests** | **185** automated tests · ruff + mypy + 80% coverage gate in CI |

## Web interface

A **Streamlit GUI** (containerized) ties the whole system together behind **two logins**:

- **Prediction Lab** — enter accident details, get a severity prediction with a **plain-language
  explanation** and a per-prediction **SHAP** chart ("why this prediction").
- **Model Insights / Monitoring** — live model metadata and **embedded Grafana dashboards**.
- **Training** (admin only) — trigger a retraining run with a live status panel.
- **Roles:** `admin` = full access · `user` = prediction + explanation only (backend-enforced JWT).

## Architecture

![Architecture](docs/architecture.png)

The pipeline is orchestrated by a single Airflow DAG and runs each step as an isolated container:

```
ingest → build dataset → validate → version (DVC) → train + log (MLflow)
       → drift & F1 gate (Evidently) → compare champion → promote → reload API
```

## Key design decisions

- **Drift-gated promotion.** A retrained model is promoted to `@production` **only if** it beats the
  current champion **and** clears an absolute F1 floor of **0.65** — relative progress *and* absolute
  quality, so "better than a degraded champion" can never ship an unsafe model.
- **Registry over files.** MLflow on my **own DagsHub** (`nithinkarkal/crash-severity-predictor`)
  with alias-based versioning (`@production` / `@fallback`) enables champion/challenger comparison
  and one-step rollback. The registry repo is configurable via env (`DAGSHUB_REPO_OWNER/NAME`).
- **Role-based GUI.** A Streamlit front-end with JWT auth and two roles (admin / user); the backend
  is authoritative for authorization.
- **Reproducible data.** DVC versions each dataset; the pipeline records the exact data state used
  for every training run.
- **Secure serving.** FastAPI with JWT auth behind an NGINX TLS reverse proxy + rate limiting;
  hot model reload without downtime.
- **Observability.** Prometheus scrapes model + service metrics; 4 Grafana dashboards (API health,
  model, drift & quality gate, infrastructure); Slack alerting on backend-down, high 5xx, and low F1.

## Tech stack

`Python` · `scikit-learn` · `Airflow` · `MLflow` · `Evidently` · `DVC` · `FastAPI` · `Streamlit` ·
`Docker` · `Kubernetes` · `NGINX` · `Prometheus` · `Grafana` · `GitHub Actions`

## Quickstart

```bash
# 1. environment (uv)
uv sync

# 2. secrets — copy the examples and fill in your own values
cp infra/airflow/.env.example infra/airflow/.env
#   create .env / .env.backend / .env.grafana with your DagsHub token, admin hash, Slack webhook

# 3. bring up the stack
docker compose up -d --build
docker compose ps            # wait for healthy

# 4. try the API
curl -sk https://asp.local:8081/api/v1/health
```

The GUI is at `http://localhost:8501`, monitoring at `https://asp.local:8081/grafana/`. See
[`docs/`](docs/) for the full walkthrough.

### Run on Kubernetes

The serving + monitoring stack also runs on Kubernetes (Deployments/Services/Ingress, tested on
`kind`) — see [`k8s/`](k8s/):

```bash
kubectl apply -f k8s/          # or: ./k8s/deploy.ps1   (creates secrets/config + applies)
# then open http://asp.local/  (GUI), /grafana/, /api/v1/health
```

## Roadmap

- [x] **Dataset lineage** — stamp the DVC hash + git SHA into every MLflow run for one-click reproducibility. ([docs](docs/dataset-lineage.md))
- [x] **`/explain` endpoint** — per-prediction SHAP explanations. ([docs](docs/explain-endpoint.md))
- [x] **Plain-language predictions** — turn SHAP output into a human-readable rationale (template-based; LLM upgrade optional). ([docs](docs/explain-endpoint.md))
- [x] **Model card** — intended use, performance, limitations, and GDPR/ethics. ([MODEL_CARD.md](MODEL_CARD.md))
- [x] **Role-based Streamlit GUI** — predict + explain + admin training + embedded Grafana, 2 logins. ([docs](docs/learning-guides/phase-14-streamlit-gui-rbac.md))
- [x] **Kubernetes** — serving + monitoring on k8s via Ingress (tested on kind). ([k8s/](k8s/))
- [x] **Independent model registry** — own DagsHub repo, configurable via env.
- [x] **Cloud deployment** — live public HTTPS URL on **k3s** (Oracle Cloud Always Free), images from GHCR (ARM64), TLS via cert-manager / Let's Encrypt. ([demo](https://crash-severity.duckdns.org/) · [docs](docs/learning-guides/phase-16-cloud-deployment.md))
- [ ] **Kubernetes autoscaling + canary/shadow** deployment.

## License & credits

See [`LICENSE`](LICENSE). Built on French government open data published by ONISR / BAAC via
[data.gouv.fr](https://www.data.gouv.fr/). Originally a collaborative capstone; this fork is
maintained by **Nithin R. Karkal** — *Simulation Engineer × ML Engineer*.
