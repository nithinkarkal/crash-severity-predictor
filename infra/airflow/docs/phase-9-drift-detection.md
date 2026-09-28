# Phase 9 — Drift Detection & the Quality Gate (Evidently)

> **Goal of this phase:** before a freshly retrained model is promoted, automatically check
> whether the **new year's data has drifted** from the baseline, whether the **target mix has
> shifted**, and whether the model's **F1 is still above a floor** — and *stop the pipeline* if the
> model would degrade. You'll learn what drift is, read the new `services/monitoring/drift.py`, and
> run it locally on Windows/Docker Desktop.
>
> This is an **additive** phase (like Phase 8): new files + one tiny, guarded edit to
> `make_dataset`. No training, backend, or DVC-logic changes.

---

## 9.1 What & why — drift in plain terms

A model is trained on the *past*. Every new year of accident data can differ from what the model
learned. Three things can go wrong:

- **Data drift** — the *inputs* change. e.g. more accidents in rain (`atm`), a different mix of
  collision types (`col`), new road categories (`catr`). The model may not generalise to the new mix.
- **Target drift** — the *answer* changes. e.g. the proportion of severe/fatal accidents (`grav`)
  shifts. Even a good model can look worse (or dangerously optimistic) if the base rate moved.
- **Performance decay** — the model's **F1 on the new batch** drops below what we consider safe.

If any of these is bad, we should **not** silently promote the new model. Phase 9 adds a step that
measures all three and **fails (blocks promotion)** when F1 is below a threshold — the same
"fail-the-task-to-stop-the-pipeline" idea as `validate_data` in Phase 8.

We use **[Evidently](https://www.evidentlyai.com/)**, a popular open-source library that produces a
polished **HTML** drift report (for humans) and a **JSON** report (for machines).

---

## 9.2 The approach — reference vs current

**Reference vs current is already in your project.** `split_data` uses `exclusive_test_year=2024`, so:

```
reference = training years (2021–2023)   -> the "baseline"
current   = the new annual batch (2024)  -> what we compare against the baseline
```

Phase 9 adds a tiny export in `make_dataset` that snapshots the
**raw, pre-normalization** frames:

```
data/processed/reference_raw.csv   # 2021–2023, raw category codes + grav
data/processed/current_raw.csv     # 2024,      raw category codes + grav
```

Evidently runs on those, so categorical drift stays interpretable.

**Isolated dependency.** Evidently pulls a big, version-sensitive dependency tree that can clash with
the project's pinned `pandas`/`numpy`. So — exactly like the `dvc` runner image — Evidently lives
**only** in a tiny dedicated image, `asp-drift` (`infra/airflow/Dockerfile.drift`). Your main `uv`
environment is never touched, and the unit tests **mock** Evidently, so CI needs no heavy install.

---

## 9.3 The files (a guided read)

```
common/data/merge_data.py         # + save_drift_frames()  (writes reference_raw / current_raw)
common/data/make_dataset.py       # calls it before normalization; adds the 2 files to the guard
services/monitoring/drift.py      # the drift step: report + gate + metrics contract
services/monitoring/tests/test_drift.py   # unit tests (Evidently mocked)
infra/airflow/Dockerfile.drift    # tiny image: python:3.12-slim + evidently
infra/airflow/dags/asp_retraining_dag.py  # + detect_drift task (after train, before compare)
```

### `save_drift_frames()` (in `merge_data.py`)

It takes the split frames **before** scaling, re-attaches the `grav` target, and writes the two CSVs.
`make_dataset` calls it right after `split_data` and before `process_features` — the only moment the
data is both split *and* still raw. The two files are also added to `PROCESSED_FILES`, so if they're
missing a rebuild recreates them.

### `services/monitoring/drift.py` — the heart of the phase

Read it in four parts:

**(a) Config + the categorical list.** `TARGET="grav"`, `DEFAULT_F1_THRESHOLD=0.65` (override with
`ASP_F1_THRESHOLD`), and `CATEGORICAL_COLS` — a copy of `CAT_COLS` from `merge_data.py`.
It's duplicated on purpose so this module doesn't import `merge_data` (which would pull in
scikit-learn, bloating the tiny drift image).

**(b) Pure helpers (unit-tested, no Evidently):**
- `categorical_features(df)` — which categorical columns are present (minus the target).
- `latest_f1()` — reads the F1 already computed on the new batch from `artifacts/metrics/*_metrics.json`
  (we **reuse** it instead of re-predicting, keeping the drift image tiny).
- `summarize_report(report_dict)` — pulls the headline numbers out of Evidently's JSON, defensively.
- `build_contract(...)` — assembles the small, stable metrics JSON (see §9.7).

**(c) The Evidently call (imported lazily):**
```python
def _build_report(reference, current):
    from evidently import ColumnMapping
    from evidently.metric_preset import DataDriftPreset, TargetDriftPreset
    from evidently.report import Report
    mapping = ColumnMapping(target="grav", task="classification",
                            categorical_features=categorical_features(reference))
    report = Report(metrics=[DataDriftPreset(), TargetDriftPreset()])
    report.run(reference_data=reference, current_data=current, column_mapping=mapping)
    return report
```
The `ColumnMapping` is what tells Evidently *which column is the target* and *which are categories* —
so it uses the right statistical test per column and separates feature drift from target drift.

**(d) `run()` — orchestration + the gate:**
1. load `reference_raw.csv` + `current_raw.csv` (fail clearly if missing),
2. build the report, save **HTML** + **JSON** to `artifacts/reports/drift/`,
3. read F1, write the **contract** JSON,
4. **the gate:** if `F1 < threshold` (or no F1 found) → `return 1` → the process exits non-zero →
   Airflow marks `detect_drift` red → the pipeline stops → nothing is promoted. Otherwise `return 0`.

### Where it sits in the DAG

```
… → train_and_log_mlflow → detect_drift → compare_against_champion → promote_to_production → reload_fastapi
                              ^ new: runs after training (so F1 exists) and BEFORE the promotion decision
```

`detect_drift` runs in the `asp-drift` image with the **whole repo mounted at `/app`** (so it can
read `data/` + `artifacts/` and import `services.monitoring.drift`), and reads `ASP_F1_THRESHOLD`.

---

## 9.4 Reproduce it yourself (Windows / Docker Desktop)

### Step 0 — build the drift image (once)

From the **repo root**, in PowerShell:

```powershell
docker build -f infra/airflow/Dockerfile.drift -t asp-drift:latest infra/airflow
docker images | Select-String asp-drift          # confirm it exists
```

### Step 1 — make sure the raw frames exist

The drift step needs `reference_raw.csv` + `current_raw.csv`. If you built your processed data
*before* this phase, rebuild once so they're created:

```powershell
# rebuild processed data (creates the two raw frames too)
docker compose --profile build-only build         # (only if images changed)
# then re-run the pipeline's make_dataset step, or from a local env:
uv run python -c "from common.data.make_dataset import process_data; process_data(overwrite=True)"
dir data\processed         # should now list reference_raw.csv and current_raw.csv
```

### Step 2 — run the drift step directly (fast feedback)

You can run the whole step in the drift image without Airflow, mounting the repo at `/app`:

```powershell
docker run --rm -v "${PWD}:/app" -w /app asp-drift:latest python -m services.monitoring.drift
```

Expected: it logs "GATE PASSED: F1=… >= threshold=0.65" and writes three files under
`artifacts\reports\drift\`. Open the HTML in a browser:

```powershell
start artifacts\reports\drift\drift_report_2024.html
type artifacts\reports\drift\latest_metrics.json
```

### Step 3 — run it inside the full retraining DAG

Step 2 ran `detect_drift` on its own. This step runs it **as part of the whole `asp_retraining`
pipeline**, so you see it in the Airflow UI exactly as it runs in production — after training,
gating promotion. Follow the sub-steps in order.

**3.1 — Confirm all four images exist** (build them once; the drift image is built in Step 0):

```powershell
docker images | Select-String "asp-backend|asp-training|asp-airflow-runner|asp-drift"
```

You should see all four. If you changed any training code since the last build, rebuild the
training image (needs UID/GID on Windows — see the Phase-8 guide §8.4):

```powershell
docker compose --profile build-only build
```

**3.2 — Start (or recreate) Airflow.** Always run this from **inside `infra/airflow/`** so Docker
Compose reads *that* `.env` (with your DagsHub token + the drift settings), not the repo-root one:

```powershell
cd C:\Users\nithinkarkal\Documents\GitHub\accident-severity-predictor\infra\airflow
docker compose --env-file .env -f docker-compose.airflow.yml up -d --force-recreate
docker exec asp-airflow airflow dags list-import-errors      # should print nothing
```

**3.3 — Open the UI and trigger the pipeline.**

1. Open http://localhost:8080. User is `admin`; get the password with
   `docker exec asp-airflow cat /opt/airflow/standalone_admin_password.txt`.
2. Enable the **`asp_retraining`** DAG (toggle on the left).
3. Click **▶ Trigger DAG**, then open the **Graph** tab to watch.

**3.4 — Watch it run.** The full chain runs: `download → build → validate → version → train →`
**`detect_drift`** `→ compare → promote → reload`. Training takes a few minutes; then the new
**`detect_drift`** box runs (a few seconds):

- **dark green** = gate passed (F1 ≥ threshold) → `compare` / `promote` continue,
- **red** = gate failed (F1 below threshold) → the pipeline stops, nothing is promoted.

Click `detect_drift` → **Logs** to see the `Drift on N columns … GATE PASSED/FAILED` lines. The
HTML + JSON reports appear on your host in `artifacts\reports\drift\`.

**3.5 — Prove the gate actually blocks promotion (the demo moment).** Force a failure by setting an
impossibly high threshold, so no model can pass:

1. Edit `infra/airflow/.env` and change the line to `ASP_F1_THRESHOLD=0.99`.
2. Recreate the container so it picks up the new value (env vars are injected at start, not read
   live), then re-trigger the DAG:

   ```powershell
   docker compose --env-file .env -f docker-compose.airflow.yml up -d --force-recreate
   ```

Re-trigger `asp_retraining` and watch: **`detect_drift` turns RED**, and
**`compare_against_champion` / `promote_to_production` are skipped** (they never run — the gate
stopped the pipeline). That is the whole point: a model below the quality bar is never promoted.

**3.6 — Put the threshold back.** Edit `infra/airflow/.env` back to `ASP_F1_THRESHOLD=0.65` and
recreate once more:

```powershell
docker compose --env-file .env -f docker-compose.airflow.yml up -d --force-recreate
```

> **Why `--force-recreate` each time you edit `.env`:** Docker injects environment variables when the
> container **starts**. A running container will not see edits to `.env` until you recreate it.

---

## 9.5 How to verify

- `docker run … asp-drift:latest python -m services.monitoring.drift` exits **0** and prints
  "GATE PASSED"; `artifacts/reports/drift/` has `drift_report_<year>.html`, `.json`, and
  `latest_metrics.json`.
- The unit tests pass in the normal suite (Evidently mocked):
  ```powershell
  uv run pytest services/monitoring/tests/test_drift.py -q
  ```
- In the DAG, `detect_drift` is green on a healthy run; with `ASP_F1_THRESHOLD=0.99` it goes red and
  the pipeline stops before `compare_against_champion`.

---

## 9.6 Troubleshooting (Windows/VS Code)

| Symptom | Cause / Fix |
|---------|-------------|
| `Missing reference_raw.csv / current_raw.csv` | You built processed data before this phase. Rebuild: `process_data(overwrite=True)` (Step 1). |
| `detect_drift` fails: `No module named services` | The repo must be mounted at `/app` and `working_dir=/app` (the DAG does this). For a manual `docker run`, include `-v "${PWD}:/app" -w /app`. |
| `docker build` of the drift image is slow | Evidently pulls scipy/plotly/numpy wheels — first build takes a few minutes, then it's cached. |
| `detect_drift` **hangs** for many minutes at "Building Evidently drift report" | Evidently is choking on **high-cardinality** columns (commune code `com`, coordinates `lat`/`long` have thousands of categories). `drift.py` guards this by dropping any column with > `MAX_CARDINALITY` (50) distinct values and sampling to `SAMPLE_ROWS` (40k) — so it now finishes in seconds. If it still hangs, lower those constants. |
| HTML report looks blank in VS Code's preview | VS Code doesn't run the report's JavaScript. Open the `.html` in a real browser (`start …html`). |
| Evidently `ImportError` on `ColumnMapping`/`Preset` | Wrong Evidently version. The image pins `evidently>=0.4.30,<0.5` (the API this code uses). Rebuild the image. |
| Gate fails unexpectedly | Check `artifacts/reports/drift/latest_metrics.json` → compare `f1_score` vs `f1_threshold`. Lower `ASP_F1_THRESHOLD` if your model legitimately scores lower. |

---

## 9.7 The metrics contract (for Prometheus / Grafana / frontend, later)

The step writes one small, **stable** file that future consumers read —
`artifacts/reports/drift/latest_metrics.json`:

```json
{ "year": 2024, "dataset_drift": false, "drift_share": 0.0, "n_drifted_features": 0,
  "n_features": 22, "target_drift_detected": false, "target_drift_score": 0.11,
  "f1_score": 0.71, "f1_threshold": 0.65, "passed": true,
  "generated_at": "2026-08-06T15:00:00Z" }
```

Because this schema is fixed, wiring consumers later needs **no change** to the drift code:
- **Prometheus** — a short-lived task can't be scraped, so *push* these numbers to a **Pushgateway**
  as gauges (drift_share, target_drift_score, f1_score), labelled by year.
- **Grafana** — dashboard panels over those gauges (drift share by year, F1 vs threshold line).
- **Frontend (Streamlit)** — a "Data Quality" tab rendering the HTML report + headline numbers.

*(Consumer wiring is a later phase — the contract is what makes it plug-and-play.)*

---

## 9.8 Checkpoint

You understand Phase 9 when you can explain:
- The three things drift detection checks (data drift, target drift, F1 decay) and why we gate on F1.
- Why we run on the **raw** reference/current frames (the normalization gotcha), and where they come from.
- Why Evidently is isolated in the `asp-drift` image, and how the unit tests avoid needing it.
- Where `detect_drift` sits in the DAG and what happens when the gate fails.
- What the **metrics contract** is and why it's written now (so Prometheus/Grafana/frontend plug in later).

---

*Additive extension beyond Phase 8. Reuses the 2021-23 vs 2024 split, the `validate_data` gate
pattern, and the `artifacts/reports/` + DVC-push plumbing already in the project.*
