# Monitoring & Visualization — Learning Guide (Prometheus + Grafana)

> A beginner-friendly walkthrough of the **NK monitoring sandbox**. It explains *what* each piece
> is, *why* it exists, and gives you *do-it-yourself* steps to run it on a Windows laptop with
> Docker Desktop. This is a personal/learning copy — the team's real stack is in `infra/monitoring/`.

---

## 1. The big picture (what we're building and why)

Once a model is serving predictions, we need to answer three questions continuously:

1. **Is the service healthy?** (Is the API up? Are requests failing? Are they slow?)
2. **Is the model behaving?** (How many predictions, of which class, how confident, how fast?)
3. **Is the data still like training?** (Has the input drifted? Is the model's F1 still above the gate?)

Two open-source tools answer these:

- **Prometheus** — a database that *pulls* ("scrapes") numeric metrics from your services every few
  seconds and stores them as time series. It also evaluates **alert rules**.
- **Grafana** — the dashboard tool that *queries* Prometheus and draws the graphs.

```
your services  ──expose /metrics──►  Prometheus  ──queried by──►  Grafana
(backend, demo-exporter, node)        (stores + alerts)            (dashboards)
```

The backend already exposes a `/metrics` endpoint (your teammates instrumented it). Prometheus
scrapes it; Grafana visualizes it. In this sandbox we add a **demo exporter** that fakes those same
metrics, so you can learn the whole flow without running the full application.

---

## 2. What a "metric" looks like

A service exposes plain text at `/metrics`, e.g.:

```
http_requests_total{method="POST",path="/api/v1/predict",status_code="200"} 1834
model_f1_score{model_version="asp-model-demo-2024"} 0.70
```

- The **name** (`http_requests_total`) is the measurement.
- The **labels** in `{...}` slice it (by path, status, model version…).
- The **number** is the current value. Counters only go up; gauges go up/down.

The metrics we monitor (same names as the real backend):

| Group | Metric | Meaning |
|-------|--------|---------|
| API | `http_requests_total` | request count by method/path/status |
| API | `http_request_duration_seconds` | latency histogram |
| Model | `predictions_total` | predictions by class |
| Model | `prediction_confidence` | predicted-probability histogram |
| Model | `prediction_duration_seconds` | inference time histogram |
| Model | `model_loaded`, `model_reload_total` | is a model live; reload attempts |
| **Drift** | `model_f1_score` | F1 of the promoted model (from your drift contract) |
| **Drift** | `model_drift_share` | share of features that drifted |
| **Drift** | `model_dataset_drift_detected` | 1 if dataset drift was flagged |

The last three come from *your* drift work: the backend reads `latest_metrics.json` (the drift
contract) on each scrape and publishes those numbers. So this dashboard literally visualizes the
output of the drift PR.

---

## 3. The pieces in this folder

- **`docker-compose.monitoring.yml`** — starts five containers on their own network:
  Prometheus, Grafana, node-exporter (host CPU/RAM/disk), **cAdvisor** (per-container Docker
  metrics), and the demo exporter.
- **`prometheus/prometheus.yml`** — tells Prometheus *what to scrape* (the demo exporter by default).
- **`prometheus/alert_rules.yml`** — conditions that turn into alerts (backend down, high error rate,
  high latency, F1 below the gate, dataset drift).
- **`grafana/provisioning/`** — on boot, Grafana auto-connects to Prometheus and auto-loads the
  dashboards (no clicking through setup).
- **`grafana/dashboards/*.json`** — the three dashboards (API health, model, drift).
- **`demo-exporter/`** — a ~90-line Python script that emits the metric names above with random but
  realistic values, nudged every 3 seconds so the graphs move.

---

## 4. Do it yourself (run the stack)

**Prerequisite:** Docker Desktop running.

1. Open a terminal **inside** `sandbox/nk-monitoring/`:

   ```powershell
   cd C:\Users\<you>\Documents\GitHub\accident-severity-predictor\sandbox\nk-monitoring
   ```

2. Start everything:

   ```powershell
   docker compose -f docker-compose.monitoring.yml up -d --build
   ```

   First run pulls images + builds the tiny exporter (~1–2 min).

3. Check Prometheus sees its targets: open **http://localhost:9091** → *Status → Targets*.
   `asp-demo`, `node-exporter`, and `prometheus` should all be **UP** (green).

4. Open **Grafana: http://localhost:3001** → login `admin` / `admin` (it'll ask you to change it).
   Go to **Dashboards** — you'll see three pre-loaded boards tagged `asp`:
   - **ASP · API Health** — request rate, 5xx %, latency, requests by path.
   - **ASP · Model** — predictions/s by class, confidence, inference time, reloads.
   - **ASP · Drift & Quality Gate** — F1 gauge vs the 0.65 gate, drift share, dataset-drift flag.
   - **ASP · Docker Containers** — CPU / memory / network **per container** (see §4a).

   Set the time range (top right) to *Last 30 minutes* and the refresh to *10s* — you'll watch the
   demo data move.

5. Stop when done (keeps the stored data + your Grafana login):

   ```powershell
   docker compose -f docker-compose.monitoring.yml down
   ```

---

## 4a. Host metrics vs Docker (container) metrics

Two different exporters answer two different "how's the machine doing?" questions:

- **node-exporter** → the **whole host** (your laptop): total CPU, RAM, disk. One number for the
  machine.
- **cAdvisor** → **each container** separately: how much CPU/memory/network `nk-grafana`,
  `nk-prometheus`, `asp-backend`, etc. are each using. This is the "Docker metrics" view.

cAdvisor reads Docker's own stats (via the cgroup mounts and the Docker socket declared in the
compose file) and exposes them at `/metrics`; Prometheus scrapes it just like any other target.
The **ASP · Docker Containers** dashboard then breaks it down per container. Useful PromQL:

- CPU per container (in cores): `sum by (name)(rate(container_cpu_usage_seconds_total{name=~".+"}[5m]))`
- Memory per container: `sum by (name)(container_memory_usage_bytes{name=~".+"})`

> On Docker Desktop (Windows/Mac), cAdvisor runs `privileged` with read-only mounts of `/sys`,
> `/var/lib/docker`, and the Docker socket — the standard setup. If a metric looks missing, check
> cAdvisor is **UP** under Prometheus → Targets, and that Docker Desktop allowed the socket mount.

---

## 5. Do it yourself (read a query)

Every panel is a **PromQL** query. Two you'll see a lot:

- **Rate of a counter** — `sum(rate(http_requests_total[5m]))` = requests per second, averaged over
  the last 5 minutes. `rate()` turns an ever-increasing counter into a per-second speed.
- **A percentile from a histogram** —
  `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))` = the p95
  latency. Histograms bucket observations; `histogram_quantile` reads a percentile back out.

Try them yourself: Prometheus (http://localhost:9091) → *Graph* tab → paste a query → *Execute*.

---

## 6. Switching to real numbers (optional)

The demo exporter is only so the dashboards have something to show. To point at the **real backend**:

1. In `prometheus/prometheus.yml`, comment out the `asp-demo` job and uncomment the `asp-backend`
   job (it targets `host.docker.internal:8000` on Docker Desktop).
2. Run the team's backend (main compose) so `/metrics` is reachable.
3. `docker compose -f docker-compose.monitoring.yml restart prometheus`.

Because the metric names are identical, **the dashboards don't change** — they just show real data.

---

## 7. Windows / Docker Desktop notes

- **Run commands from inside the `sandbox/nk-monitoring/` folder** — the compose file uses relative
  paths (`./prometheus`, `./grafana`) that are resolved against your current directory.
- **Ports 3001 / 9091 / 9101 / 8010 must be free.** If one is taken, change the left side of the
  `"3001:3000"` mapping in the compose file (e.g. `"3002:3000"`).
- **`host.docker.internal`** (for the real-backend option) works on Docker Desktop for Windows/Mac.
  On plain Linux you'd use the host IP or a shared Docker network instead.
- If Grafana shows "no data", check Prometheus *Targets* first (step 3) — a red target means the
  scrape URL/port is wrong, not the dashboard.

---

## 8. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Grafana dashboards empty / "No data" | Prometheus target down — open http://localhost:9091 → *Status → Targets*. Fix the scrape target before touching the dashboard. |
| `port is already allocated` on `up` | Another service (maybe the team's stack) uses 3000/9090/9100. This sandbox already uses 3001/9091/9101; if still clashing, bump the host port in the compose file. |
| Grafana login won't accept `admin`/`admin` | You changed it on a previous run and the volume persisted it. Use your changed password, or `docker compose ... down -v` to reset (wipes stored data). |
| Dashboards not showing up | They're auto-loaded from `grafana/dashboards/`. Confirm the JSON is valid and the `grafana/provisioning/dashboards/dashboards.yml` path matches the mount. |
| Demo graphs are flat | The exporter nudges values every 3s but `rate()` needs ~a minute of data — give it 1–2 minutes after start. |

---

## 9. How this relates to the team's work

The team owns the production stack in `infra/monitoring/` and the backend instrumentation, now
**merged into `develop` (PR #15)** — Prometheus, node-exporter, the Grafana *service*, and the
backend `/metrics` endpoint. This sandbox is deliberately separate so you can **learn and prototype
dashboards** without touching theirs. The main thing it adds that the team **hasn't done yet** is
**provisioned Grafana dashboards** (and alert rules) — if useful, the dashboard JSONs here can be
copied into `infra/monitoring/grafana/` and contributed back. Because the team's `/metrics` is now
on `develop`, the "real backend" option (§6) works against a plain `develop` checkout.
