# NK Monitoring Sandbox (Prometheus + Grafana)

> **Personal sandbox — not the team's production monitoring.** The team's stack (Prometheus +
> backend `/metrics` instrumentation) is now **merged into `develop`** (PR #15) under
> `infra/monitoring/`. This folder is a self-contained copy on its **own ports and network** so the
> two can even run side by side. The team merged Prometheus + backend metrics but **not** Grafana
> dashboards/alerts yet — those are what this sandbox adds.

A standalone Prometheus + Grafana stack that visualizes the ASP metrics — API health, model, and
**drift/quality-gate** — with a built-in demo exporter so it runs without the rest of the app.

## Ports

| Service | This sandbox | (Team's `infra/monitoring`) |
|---------|--------------|------------------------------|
| Grafana | **3001** | 3000 |
| Prometheus | **9091** | 9090 |
| node-exporter (host metrics) | **9101** | 9100 |
| cAdvisor (per-container metrics) | **8082** | — |
| demo-exporter | **8010** | — |

## Files

| Path | Purpose |
|------|---------|
| `docker-compose.monitoring.yml` | The stack: prometheus + grafana + node-exporter + cAdvisor + demo-exporter |
| `prometheus/prometheus.yml` | Scrape config (demo by default; real backend optional) |
| `prometheus/alert_rules.yml` | Availability / API / model-health alert rules |
| `grafana/provisioning/` | Auto-wires the datasource + auto-loads dashboards |
| `grafana/dashboards/*.json` | API-health, model, drift, and Docker-containers dashboards |
| `demo-exporter/` | Tiny exporter emitting sample ASP metrics |
| `docs/monitoring-visualization-guide.md` | Beginner walkthrough (what/why + do-it-yourself) |

## Quickstart

From inside `sandbox/nk-monitoring/`:

```bash
docker compose -f docker-compose.monitoring.yml up -d --build
```

- **Grafana:** http://localhost:3001 (login `admin` / `admin` → change on first login).
  Three dashboards are pre-loaded under **Dashboards** (tagged `asp`).
- **Prometheus:** http://localhost:9091 → *Status → Targets* should show `asp-demo`,
  `node-exporter`, `prometheus` all **UP**.

Stop (keeps data): `docker compose -f docker-compose.monitoring.yml down`

## Real numbers instead of the demo

Edit `prometheus/prometheus.yml`: comment the `asp-demo` job, uncomment the `asp-backend` job, and
make sure the team's backend is reachable. The dashboards use the **same metric names** as the real
backend (`http_requests_total`, `predictions_total`, `model_f1_score`, …), so they work unchanged.

See `docs/monitoring-visualization-guide.md` for the full walkthrough and Windows notes.
