# ASP Learning Guides

A phase-by-phase, beginner-friendly walkthrough of the Accident Severity Predictor codebase —
what each part does, *why* it's built that way, and do-it-yourself steps (with Windows/Docker notes).

Read them in order, or jump to the phase you're working on.

| Phase | Topic | Location |
|-------|-------|----------|
| 0 | Foundations & tooling (uv, ruff, mypy, pre-commit) | [phase-0](phase-0-foundations-and-tooling.md) |
| 1 | Data & DVC pipeline | [phase-1](phase-1-data-and-dvc-pipeline.md) |
| 2 | Data processing modules | [phase-2](phase-2-data-processing-modules.md) |
| 3 | Training service + MLflow registry | [phase-3](phase-3-training-service.md) |
| 4 | Backend API + JWT auth | [phase-4](phase-4-backend-api.md) |
| 5 | Containerization + Nginx reverse proxy | [phase-5](phase-5-containerization.md) |
| 6 | CI/CD workflows | [phase-6](phase-6-cicd.md) |
| 7 | Frontend & wrap-up | [phase-7](phase-7-frontend-and-wrapup.md) |
| 8 | Airflow orchestration (retraining DAG) | [../../infra/airflow/docs/phase-8-airflow-orchestration.md](../../infra/airflow/docs/phase-8-airflow-orchestration.md) |
| 9 | Drift detection + F1 gate | [../../infra/airflow/docs/phase-9-drift-detection.md](../../infra/airflow/docs/phase-9-drift-detection.md) |
| 10–11 | Monitoring (visualization; Prometheus + Grafana) | *maintained locally, not in this repo* |
| 12 | Dataset & code lineage (reproducible MLflow runs) | [phase-12](phase-12-dataset-lineage.md) |
| 13 | Explainability & model transparency (`/explain` + plain-language, `/model/info`, model card) | [phase-13](phase-13-explainability-and-model-info.md) |
| 14 | The GUI — role-based Streamlit app (predict · explain · train · monitor) | [phase-14](phase-14-streamlit-gui-rbac.md) |
| 15 | Kubernetes — serving + monitoring on kind (Deployments/Services/Ingress) | [phase-15](phase-15-kubernetes.md) |
| — | Airflow how-to-verify checklist | [../../infra/airflow/docs/HOW-TO-VERIFY.md](../../infra/airflow/docs/HOW-TO-VERIFY.md) |

> **Where the guides live (single source of truth).** Phases 0–7 and the post-defense phases 12–13
> live here in `docs/learning-guides/`.
> Phases 8–9 and the how-to-verify checklist live under `infra/airflow/docs/` (next to the Airflow
> code the team edits directly) and are linked above — they are **not** duplicated here, so the two
> sets can't drift apart.
> Phases **10–11** (monitoring) are kept in the personal learning set on disk (they cover the
> standalone monitoring sandbox); the numbering is reserved here so both sets agree.

> A personal, standalone monitoring/visualization sandbox (Prometheus + Grafana) with its own guide
> lives under `sandbox/nk-monitoring/` — that's a learning/prototype copy, separate from the team's
> production monitoring in `infra/monitoring/`.
