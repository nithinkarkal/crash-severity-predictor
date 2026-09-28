# Monitoring — Dashboards & Alerts

Grafana dashboards and Slack alerting on top of the Prometheus stack. Prometheus + the backend
`/metrics` instrumentation are documented in `infra/monitoring/README.md`; this covers the
**Grafana** layer added on top.

## Stack

| Service | Role | Port |
|---------|------|------|
| Prometheus | scrapes metrics (backend, node-exporter), evaluates rules | 9090 (internal) |
| node-exporter | host CPU/memory/disk/network metrics | 9100 (internal) |
| Grafana | dashboards + alerting | behind Nginx at `https://asp.local:8081/grafana/` |

Everything runs from the root `docker compose`. Grafana config is provisioned from
`infra/monitoring/grafana/` (datasource, dashboards, alerting) — no manual UI setup.

## Setup

1. One-time (see [Reverse Proxy](reverse_proxy.md)): add `127.0.0.1 asp.local` to your hosts file
   and run `infra/nginx/generate-dev-cert.sh`.
2. Create **`.env.grafana`** in the repo root:
   ```
   GF_SECURITY_ADMIN_USER=admin
   GF_SECURITY_ADMIN_PASSWORD=<choose>
   GF_SERVER_ROOT_URL=https://asp.local:8081/grafana/
   GF_SERVER_SERVE_FROM_SUB_PATH=true
   SLACK_WEBHOOK_URL=<slack incoming webhook>   # optional, for alerts
   ```
3. `docker compose up -d --build`, then open `https://asp.local:8081/grafana/`
   (login = `GF_SECURITY_ADMIN_*`; accept the self-signed-cert warning).

## Dashboards

Auto-loaded on boot (tag `asp`), backed by the Prometheus datasource (uid `prometheus`):

- **ASP · API Health** — request rate, 5xx error rate, p95 latency, requests by status/path.
- **ASP · Model** — predictions/s by class, confidence (p50/p95), inference time, reloads.
- **ASP · Drift & Quality Gate** — F1 gauge vs the 0.65 gate, drift share, dataset-drift flag.
- **ASP · Infrastructure** — CPU, memory, load, root-FS free, network I/O (node-exporter).

Files: `infra/monitoring/grafana/dashboards/*.json` (edit and Grafana reloads within 30s).

## Alerts (Grafana → Slack)

Provisioned under `infra/monitoring/grafana/provisioning/alerting/` — a Slack contact point, a
notification policy, and three rules:

| Rule | Fires when | Severity |
|------|-----------|----------|
| ASP backend is down | `up{job="asp-backend"} < 1` for 2m | critical |
| ASP high 5xx error rate | 5xx share > 5% for 2m | warning |
| ASP model F1 below gate | `model_f1_score < 0.65` for 5m | warning |

**Enable:** set `SLACK_WEBHOOK_URL` in `.env.grafana` (webhook read via `$__env{}`, never committed),
then `docker compose up -d --force-recreate grafana`. Verify in Grafana → **Alerting** (contact point
`slack-asp` → *Test*). Alertmanager is not used — Grafana handles evaluation and delivery.

## Config (`.env.grafana`)

| Var | For |
|-----|-----|
| `GF_SECURITY_ADMIN_USER` / `_PASSWORD` | Grafana login |
| `GF_SERVER_ROOT_URL` / `GF_SERVER_SERVE_FROM_SUB_PATH` | serving under the `/grafana/` sub-path via Nginx |
| `SLACK_WEBHOOK_URL` | Slack alerting (optional) |
