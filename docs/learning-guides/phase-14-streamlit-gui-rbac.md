# Phase 14 — The GUI: a role-based Streamlit app (predict · explain · train · monitor)

> **Goal of this phase:** turn the standalone API into a usable product — one Streamlit web app
> that ties together prediction, explanation, admin-only training, and embedded live monitoring,
> behind **two logins** (admin = full access, user = prediction only). You'll see how the frontend
> talks to the backend, how role-based access works end to end, and how the whole thing runs as one
> container stack.

This is the first of the **closing "product" phases** (14 GUI → 15 Kubernetes → 16 cloud). The
frontend scaffold already existed; this phase finishes and wires it.

---

## 14.1 The shape of it

```
   browser ──▶ Streamlit GUI (:8501) ──▶ FastAPI backend (asp-backend:8000, internal network)
      │                                        └── /login /predict /explain /train /model/info /health
      └────────▶ nginx TLS (:8081) ──▶ Grafana (embedded dashboards, read-only)
```

Two important design choices:

- The **GUI → backend** calls go over the **internal Docker network** as plain HTTP
  (`http://asp-backend:8000`) — no TLS/cert pain inside the cluster. The browser only meets TLS at
  nginx (`:8081`), which is where Grafana is embedded from.
- The backend stays **authoritative for authorization**. The frontend reads the role from the JWT
  only to decide *what to show*; every protected action is still enforced by the backend.

## 14.2 Authentication & role-based access (2 logins)

Login posts to the backend `/login`, which returns a **JWT** whose payload carries a `role`
(`admin` or `user`). The frontend:

- decodes the role from the token (`session_service.get_role_from_token`) — for **navigation
  visibility only**;
- gates pages in `app.py` (`enforce_page_access`): `Prediction` / `Model Insights` need any login;
  `Monitoring` / `Training` are **admin-only**;
- shows/hides sidebar links by role (`is_admin()`).

| Login | Sees |
|---|---|
| **admin** | Prediction · Explain · **Training** · **Monitoring** (+ Grafana) |
| **user** (`datascientest`) | Prediction · Explain · Model Insights only |

Because backend endpoints like `/train` use `require_admin`, a `user` who somehow called them still
gets a **403** — defence in depth.

## 14.3 Prediction + explanation

The Prediction page builds the feature form, calls `/predict`, then calls `/explain` (Phase 13) as a
**secondary, non-fatal** step. The result card shows the predicted severity, the confidence gauge,
the **plain-language summary**, and a **per-prediction SHAP bar chart** ("Why this prediction"). If
`/explain` is unavailable it silently falls back to the global importance radar — the prediction is
never blocked by the explanation.

## 14.4 Training trigger (admin only)

A dedicated **Training** page lets an admin launch a retraining run via `POST /train` (which runs the
training container in the background on the server). A **confirmation checkbox** guards the button so
an expensive run can't be launched by an accidental click — a small but real piece of the
public-demo hardening.

## 14.5 Monitoring + embedded Grafana

The Monitoring page pulls `/health` and `/model/info` for status, active-model facts, and **real
performance metrics** (read from `artifacts/metrics/` — accuracy, precision, recall, F1). Below that,
it **embeds the four live Grafana dashboards** (API Health, Model, Drift & Gate, Infrastructure) in
tabs via `st.components.v1.iframe`.

For the embed to work, Grafana is configured (in `docker-compose.yaml`) with:

- `GF_SECURITY_ALLOW_EMBEDDING=true` — allow being shown inside an `<iframe>`;
- `GF_AUTH_ANONYMOUS_ENABLED=true` + `GF_AUTH_ANONYMOUS_ORG_ROLE=Viewer` — render read-only without a
  separate Grafana login. (Admin actions in Grafana still require the admin login.)

> Locally, a self-signed cert means a panel may be blank until you open
> `https://asp.local:8081/grafana/` once to accept it. On a real cloud TLS domain this is seamless.

## 14.6 Containerizing the frontend

`services/frontend/Dockerfile.frontend` installs only the `frontend` dependency group, copies the
code, sets `PYTHONPATH=/app` (so the absolute `services.frontend...` imports resolve), and runs
Streamlit headless on `:8501`. The `frontend` service in `docker-compose.yaml` publishes `:8501`,
sets `BACKEND_URL=http://asp-backend:8000` and `GRAFANA_URL=https://asp.local:8081/grafana` via env
(read by `pydantic-settings`), and waits for the backend to be healthy.

## 14.7 Reproduce it yourself

```powershell
docker compose up -d --build      # backend, nginx, prometheus, node-exporter, grafana, frontend
docker compose ps                 # all healthy
```

Open **http://localhost:8501**:

1. **admin / admin123** → run a prediction (see summary + SHAP), open **Training** (confirm → start),
   open **Monitoring** (real metrics + Grafana tabs).
2. **datascientest / user123** → only Prediction / Model Insights; Training & Monitoring are hidden
   and blocked.

## 14.8 Phase 14 checkpoint

You understand Phase 14 when you can explain:

- Why the GUI calls the backend over the **internal network** (HTTP) but embeds Grafana over **nginx
  TLS** (browser).
- How the **JWT role** drives frontend visibility while the **backend stays authoritative** (403 on
  `/train` for non-admins).
- How the prediction result composes `/predict` + a **non-fatal** `/explain`.
- Why the training trigger has a **confirmation gate**.
- What Grafana settings make **embedding** possible, and the local self-signed-cert caveat.
- How the frontend is containerized and wired into the compose stack.

---

### Next up — Phase 15: Kubernetes

We'll translate this compose stack into Kubernetes (Deployments, Services, ConfigMap, Secret,
Ingress — or a small Helm chart), tested locally on `kind`/`minikube`, on the way to a cloud deploy
(Phase 16).
