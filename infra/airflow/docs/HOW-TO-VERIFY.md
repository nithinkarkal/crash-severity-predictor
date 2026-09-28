# How to Verify — a run-it-yourself checklist

A single tick-list to **run each phase locally and confirm the result**. Every item is:
**command → what you should see**. Work top to bottom; each tier needs a bit more than the last.

- **Tier 0** — Python 3.12 + `uv` only. No data, no Docker, no accounts. (Phases 0, and the tests for 2/3/4/6.)
- **Tier 1** — + open internet. Real data, training, the API. No accounts needed.
- **Tier 2** — + **Docker Desktop**. Containers (Phase 5), image builds (Phase 6), Airflow (Phase 8).
- **Tier 3** — + a **DagsHub** token. `dvc pull/push` and the retraining DVC step.

You have GitHub Desktop, Docker Desktop, and DagsHub accounts, so all four tiers are open to you.

> Every phase guide also has its own **"Reproduce it yourself"** section with more detail — this
> file is the fast checklist that ties them together.

---

## 0. One-time setup (Tier 0)

```bash
# from the repo root
uv python pin 3.12
uv sync --all-groups         # installs the EXACT locked versions from uv.lock
uv run pre-commit install
```

✅ **Expected:** `uv sync` prints "Installed N packages" and creates `.venv/`.

> **Why use `uv sync` and not plain `pip`:** the project pins exact, mutually compatible versions
> in `uv.lock` (e.g. `pandas>=2.2,<3`, `mlflow>=2.22,<3`). `uv sync` installs those locked versions
> so the whole suite passes deterministically. If you install a random pandas/mlflow with plain
> `pip`, you can get version-mismatch failures in the data or MLflow tests. If you ever see such an
> error, your environment isn't the pinned one — re-run `uv sync`.

---

## Phase 0 — Foundations (Tier 0)

| Check | Command | ✅ Expected |
|-------|---------|------------|
| Python pinned | `uv run python --version` | `Python 3.12.x` |
| Lint | `uv run ruff check .` | `All checks passed!` |
| Format | `uv run ruff format --check .` | `... files already formatted` |
| Types | `uv run mypy common services` | `Success: no issues found` (or a short readable list) |
| Hooks installed | `uv run pre-commit run --all-files` | each hook `Passed` (may fix whitespace on first run) |

---

## Phase 2 & 3 & 4 & 6 — the test suites (Tier 0)

This is the fastest way to confirm the whole codebase is healthy — **no data or Docker needed**.

```bash
uv run pytest                      # all suites + the 80% coverage gate
# or target one area:
uv run pytest common/tests -v
uv run pytest services/training/tests -v
uv run pytest services/backend/tests -v
```

✅ **Expected:** all tests `PASSED` (≈100+ test instances across common/training/backend and the
Airflow feature), then a coverage table, then exit code 0 because coverage ≥ 80%.

> **Airflow feature tests** are collected by the same `uv run pytest`:
> `services/training/tests/test_promote.py` (steps 5 & 6 promotion logic) and
> `infra/airflow/tests/test_validate_data.py` (the `validate_data` gate) run always.
> `infra/airflow/tests/test_dags.py` (DAG-integrity) **skips** unless Airflow is installed — to run
> it: `uv sync --group airflow-tests` then `uv run pytest infra/airflow/tests/test_dags.py -q`
> (or run it inside the `asp-airflow` container). See phase-8 guide §8.7 → "Tests for this feature".

> Reference: in a quick sandbox run on the *wrong* pandas (2.3.3), 85/97 passed and the only 12
> failures were the pandas-3.0-syntax ones above. On your `uv sync` environment, expect **all green**.

---

## Phase 1 & 2 — data pipeline (Tier 1: needs internet)

```bash
# fetch the raw BAAC CSVs from data.gouv.fr (no account needed)
uv run python -m common.data.download_data
ls data/raw/                       # -> yearly CSVs (usagers-, vehicules-, caracteristiques-, lieux-)

# build the processed train/test dataset
uv run python -m common.data.make_dataset
ls data/processed/                 # -> X_train.csv X_test.csv y_train.csv y_test.csv
```

✅ **Expected:** log lines per year, then four CSVs in `data/processed/`. Re-running prints
*"Processed data already exists, skipping."* (the idempotency guard).

---

## Phase 3 — training (Tier 1)

```bash
uv run python -m services.training.train
cat artifacts/metrics/*_metrics.json
ls artifacts/models/               # model_<timestamp>.joblib + _features.json + _parameters.json
```

✅ **Expected:** logs ending `Evaluation completed | Accuracy=0.xx | Precision=0.xx | Recall=0.xx | F1=0.xx`,
a metrics JSON you can read, and a timestamped model + its feature list + a feature-importance PNG.

> First run trains 200 trees on the full dataset — it takes a while and the model file is large.

---

## Phase 4 — the API (Tier 1)

```bash
uv run uvicorn services.backend.src.main:app --reload --port 8000
```

Then in a browser open **http://localhost:8000/docs**, or from another terminal:

```bash
curl http://localhost:8000/api/v1/health
```

✅ **Expected:** `/health` → `{"status":"healthy","model_loaded":true,"model_name":"model_..."}`
(needs a model from Phase 3; otherwise `model_loaded:false`). Use the Swagger `/docs` page to POST
`/predict` with the sample payload and get back a `severity` + `probability`. Send `"sexe":5` to
watch validation reject it with a `422`.

---

## Phase 5, 6, 8 — Docker (Tier 2): the step-by-step you asked for

> Everything below is run from a terminal (PowerShell or Git Bash) with **Docker Desktop running**.
> Confirm Docker is up first: `docker ps` should return a header row without error.

### Step 1 — build the images (once)

From the **repo root**:

> **Windows first:** create a root `.env` with `UID=1000` and `GID=1000` before building, or the
> `asp-training` build fails with `groupadd: invalid group ID 'appuser'` (the training service uses a
> bare `${UID}` with no default). One line: `"UID=1000`nGID=1000" | Out-File -Encoding ascii .env`

```bash
docker compose --profile build-only build     # -> asp-training:latest
docker compose build backend                   # -> asp-backend:latest
docker build -f infra/airflow/Dockerfile.runner -t asp-airflow-runner:latest infra/airflow   # -> runner (for retraining DAG)
docker build -f infra/airflow/Dockerfile.drift  -t asp-drift:latest infra/airflow            # -> drift (detect_drift task, Phase 9)
docker images | findstr asp-                   # (Windows) list them; on mac/linux use `grep asp-`
```

✅ **Expected:** four images: `asp-backend`, `asp-training`, `asp-airflow-runner`, `asp-drift`.

> **Drift step (Phase 9).** The retraining DAG has a `detect_drift` task after `train`
> (Evidently data/target drift + an F1 gate that blocks promotion below `ASP_F1_THRESHOLD`).
> Unit tests run in the normal suite (Evidently mocked): `uv run pytest services/monitoring/tests -q`.
> Reproduce standalone: `docker run --rm -v "${PWD}:/app" -w /app asp-drift:latest python -m services.monitoring.drift`.
> See phase-9-drift-detection.md.

### Step 2 — run the backend API in a container (Phase 5)

Create a `.env` in the **repo root** with your absolute path:

```
HOST_PROJECT_ROOT=C:/Users/nithinkarkal/Documents/GitHub/accident-severity-predictor
```

Then:

```bash
docker compose up -d --build backend           # start it in the background
docker ps                                       # asp-backend should become "healthy" after ~10-40s
curl http://localhost:8000/api/v1/health
docker compose logs -f backend                  # watch logs (Ctrl-C to stop watching)
docker compose down                             # stop it when done
```

✅ **Expected:** `docker ps` shows `asp-backend ... (healthy)`; the health curl returns JSON. Same
API as Phase 4, now inside a container.

### Step 3 — the container smoke tests (Phase 6, optional)

```bash
docker run --rm --entrypoint uv asp-training:latest run --no-sync python -c "import services.training.train; print('OK')"
docker run --rm --entrypoint uv asp-backend:latest  run --no-sync python -c "import services.backend.src.main; print('OK')"
```

✅ **Expected:** each prints `OK` — the images import your code cleanly (this is what CI checks).

### Step 4 — Airflow: bring it up (Phase 8)

From the **`infra/airflow/` folder**:

```bash
cp .env.example .env
#   edit infra/airflow/.env: set HOST_PROJECT_ROOT (forward slashes on Windows):
#   HOST_PROJECT_ROOT=C:/Users/nithinkarkal/Documents/GitHub/accident-severity-predictor

docker compose -f docker-compose.airflow.yml up -d --build
docker exec asp-airflow airflow dags list-import-errors        # ✅ empty = DAGs parsed cleanly
docker exec asp-airflow airflow dags list | findstr asp        # -> asp_retraining (the only DAG)
```

Get the admin password (user is `admin`) and open the UI:

```bash
docker exec asp-airflow cat /opt/airflow/standalone_admin_password.txt
# newer builds instead: docker exec asp-airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

Open **http://localhost:8080** (user `admin`, that password). The project ships a **single DAG,
`asp_retraining`** — run it in Step 5.

✅ **Expected:** the UI loads and `asp_retraining` is listed with no import errors.

> **If a task goes red,** the cause is almost always one of five known local-run issues (UID/GID,
> DNS, `mkdir`, MLflow token, DVC creds). The phase-8 guide's **§8.9 "Real local-run playbook"** has
> the symptom→fix table. Fixes for DNS/`mkdir`/token are already in the committed code.

### Step 5 — Airflow: the full 8-task retraining DAG (Phase 8)

Same Airflow instance. Enable **`asp_retraining`** and trigger it.

> **If you changed training code, rebuild `asp-training` first.** Steps 4–6 run
> `services.training.train` / `services.training.promote` **inside** the image (baked in at build
> time, not mounted): `docker compose --profile build-only build`. Skip this and the compare/promote
> tasks fail with `No module named services.training.promote`.

✅ **Expected:** all steps run for real and go green — `check_and_ingest_data`, `build_dataset`,
`validate_data`, `train_and_log_mlflow` (train + log + **register** candidate),
`compare_against_champion` + `promote_to_production` (real MLflow registry compare + promote, "Option
B"), and `reload_fastapi` (POSTs `POST /api/v1/model/reload` — **lenient**: logs a warning and still
passes if the backend isn't running). Open `validate_data` → **Logs** for
`[VALIDATION] PASS: X_train=(...)`, and `compare_against_champion` → **Logs** for the
`candidate v… is BETTER/NOT better than current production …` verdict.

> To see `reload_fastapi` actually reload: run the backend (`docker compose up -d backend`, mapped to
> host :8000) and set `FASTAPI_RELOAD_URL=http://host.docker.internal:8000/api/v1/model/reload` in
> `infra/airflow/.env`. The task log then shows `reload -> 200`.

Three tasks need your DagsHub token (Tier 3 below): `train_and_log_mlflow`,
`compare_against_champion`, and `promote_to_production` (all hit MLflow), plus `version_dataset_dvc`
(DVC push). Confirm the DVC push via `version_dataset_dvc` → **Logs** for `N files pushed`, then
`dvc status -c` → *"Cache and remote 'origin' are in sync"*. Confirm the promotion on DagsHub →
repo → **Models**: the winning version gets the `production` alias, the old one `fallback`.

### Tear down

```bash
docker compose -f docker-compose.airflow.yml down      # from infra/airflow/
docker compose down                                      # from repo root (backend)
```

---

## Tier 3 — DagsHub / DVC (your DagsHub account)

Get a token: **dagshub.com → your repo → Remote → Data** (it shows an access key + secret).

**For `dvc pull`/`push` from the repo root:**

```bash
uv run dvc remote modify origin --local access_key_id     <YOUR_KEY>
uv run dvc remote modify origin --local secret_access_key <YOUR_SECRET>
uv run dvc pull        # download the versioned data + model
uv run dvc push        # upload new versions
```

✅ **Expected:** `dvc pull` fetches `data/` and `artifacts/`; `dvc status` → *"Data and pipelines
are up to date."*

**For the retraining DAG:** your single DagsHub default token goes into **three** lines of
**`infra/airflow/.env`** — it authenticates both MLflow (the train task) and the DVC/S3 push:

```
DAGSHUB_USER_TOKEN=<YOUR_TOKEN>      # MLflow auth for train_and_log_mlflow
AWS_ACCESS_KEY_ID=<YOUR_TOKEN>       # DagsHub S3 for version_dataset_dvc (dvc push)
AWS_SECRET_ACCESS_KEY=<YOUR_TOKEN>
```

Get the token at **dagshub.com → avatar → Settings → Tokens**. Then re-run `docker compose -f
docker-compose.airflow.yml up -d` (recreates the container so it picks up the new `.env`) and
re-trigger `asp_retraining`; the train task logs to MLflow and the DVC step pushes.

> **Security:** `infra/airflow/.env` is git-ignored — never commit it. If the token is ever exposed
> (chat, screenshot, logs), rotate it: DagsHub → Settings → Tokens → regenerate, update the three
> lines, and re-run `up -d`.

---

## Committing your Airflow work (GitHub Desktop)

The Airflow feature is on branch **`feature/airflow-orchestration`**, staged but not committed.

1. First, in a terminal, delete the sandbox leftovers (once):
   `del .git\index.lock` · `del airflow\__deltest.txt` · `rmdir /s /q airflow\dags\__pycache__`
2. Open **GitHub Desktop** → **Current Branch** → confirm `feature/airflow-orchestration`.
3. In **Changes**, tick the `infra/airflow/` files and `learning-guides/` files (Phase 8 + this doc).
4. Write a summary (e.g. *"feat(airflow): orchestrate DVC pipeline + 8-task retraining DAG"*), click
   **Commit to feature/airflow-orchestration**, then **Push origin**.
5. On GitHub, open a **Pull Request into `develop`** (use the PR description I drafted).

---

## Quick reference — what needs what

| Phase | Tier | One-line check |
|-------|------|----------------|
| 0 Foundations | 0 | `uv run ruff check .` → all passed |
| 2/3/4/6 tests | 0 | `uv run pytest` → all green, cov ≥ 80% |
| 1/2 data | 1 | `python -m common.data.make_dataset` → 4 CSVs |
| 3 training | 1 | `python -m services.training.train` → metrics JSON |
| 4 API | 1 | `curl /api/v1/health` → healthy JSON |
| 5 containers | 2 | `docker compose up -d backend` → healthy |
| 6 CI checks | 2 | smoke test prints `OK` |
| 8 Airflow | 2 | trigger `asp_retraining` → tasks go green |
| 8 retraining | 2–3 | trigger `asp_retraining` → green (DVC step needs Tier 3) |
| DVC | 3 | `dvc pull` → data + model fetched |
