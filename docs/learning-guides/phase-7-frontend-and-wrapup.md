# Phase 7 — Frontend & Wrap-up

> **Goal of this final phase:** look at the `services/frontend/` Streamlit scaffold (what exists,
> what's intended, and how it *would* call the backend), then step all the way back and see the
> whole system as one machine — how data → DVC → processing → training → API → containers → CI fit
> together, the design principles that recur throughout, and a consolidated punch-list of the
> improvements we flagged along the way.

You've now read every substantive line of this repository. This phase ties the bow.

---

## 7.1 The frontend — an honest look at a scaffold

Let's be straight about the current state, because a good engineer reports what *is*, not what's
implied:

```
services/frontend/
└── .gitkeep          # <- that's the entire contents
```

The frontend is a **placeholder**. There is no Streamlit code yet — only:

- an empty `services/frontend/` folder (kept in Git by a `.gitkeep`, the Phase 0 pattern), and
- the dependencies reserved for it in `pyproject.toml`'s `frontend` group:

```toml
frontend = [
    "plotly>=6.9.0",       # interactive charts
    "streamlit>=1.59.1",   # the UI framework
]
```

No `.py` file anywhere imports Streamlit yet. So this phase can't *walk* frontend code — instead
it explains what the scaffold is *for* and how it will plug into everything you've already learned.
(The `infra/docker/` and `infra/tracking/` folders are the same story: reserved `.gitkeep`
placeholders for future infrastructure and experiment-tracking work.)

### What the frontend is meant to be

**Streamlit** turns a plain Python script into a web app — no HTML/JS required. You write
`st.number_input(...)`, `st.button(...)`, `st.write(...)` and Streamlit renders a live UI. It's the
standard quick way to put a friendly face on an ML model. Here it's intended to be the **human
front door** to the backend API from Phase 4: a form where someone enters accident details and gets
a severity prediction back, without touching `curl` or Swagger.

### How it will connect (the design is already implied)

Everything the frontend needs already exists — this is why the API was built the way it was:

- The **`PredictionRequest` schema** (Phase 4) is exactly the set of form fields the UI must
  collect: `place`, `catu`, `sexe`, `victim_age`, `catv`, `lat`, `long`, `hour`, … each with its
  valid range (`ge`/`le`) that maps straight to input widgets' min/max.
- The **`/api/v1/predict` endpoint** is the one call it makes. The `requests`/`httpx` dependency is
  already in the backend group; the frontend would POST the form values and read back the
  `PredictionResponse` (`severity`, `severity_code`, `probability`, `model_used`).
- **Plotly** is reserved for visualizing results — e.g. a gauge of the predicted probability, or a
  map pin from the `lat`/`long` inputs.

A minimal version of what a `services/frontend/app.py` will likely look like (illustrative — not in
the repo yet):

```python
import requests
import streamlit as st

st.title("Accident Severity Predictor")

# collect a few features (bounds come straight from PredictionRequest)
victim_age = st.number_input("Victim age", min_value=1, max_value=120, value=30)
catv       = st.selectbox("Vehicle category (0–6)", options=list(range(7)))
atm        = st.selectbox("Weather", options=[0, 1], format_func=lambda x: ["Normal", "Adverse"][x])
# ...the rest of the ~28 fields...

if st.button("Predict"):
    payload = {"victim_age": victim_age, "catv": catv, "atm": atm, ...}
    resp = requests.post("http://backend:8000/api/v1/predict", json=payload)  # 'backend' = compose service name
    result = resp.json()
    st.metric("Severity", result["severity"])
    st.write(f"Confidence: {result['probability']:.0%}  ·  model: {result['model_used']}")
```

Two integration details worth noting for when you (or the team) build it:

- It would call the backend by its **compose service name** (`http://backend:8000`) if it runs as a
  container on the same `asp-network` (Phase 5) — Docker's internal DNS resolves service names.
  From your laptop it'd be `http://localhost:8000`.
- It would become a **third compose service** (`frontend`) with its own `Dockerfile.frontend` and
  the `frontend` dependency group — slotting cleanly into the two-image pattern from Phase 5.

So the frontend is "designed-in but not built." That's a perfectly normal state for a project of
this scope, and finishing it is the most natural next hands-on exercise (see §7.4).

---

## 7.2 The whole system, end to end

Step back and look at the machine you've now read in full. Here is the entire data-and-control flow
across all seven phases:

```
        ┌──────────────────────────────────────────────────────────────────────────────┐
        │                         ACCIDENT SEVERITY PREDICTOR                            │
        └──────────────────────────────────────────────────────────────────────────────┘

  data.gouv.fr API                     DagsHub (Git + DVC S3 remote)
        │                                    ▲            │
        │ download_data.py (P1/P2)           │ dvc push   │ dvc pull
        ▼                                    │            ▼
  data/raw/  ──make_dataset (P2)──▶  data/processed/ ──train (P3)──▶  artifacts/{models,metrics,reports}/
     │  clean→merge→split→impute/scale        │  X/y train+test          │  model.joblib + features.json
     │  (4 BAAC tables → 1 dataset)           │                          │  + metrics.json + plots
     └────────────── all three chained by dvc.yaml (P1): download → make_dataset → train ┘
                                                                          │
                                                          load_latest_model() reads artifacts/
                                                                          ▼
   USER ──HTTP──▶  FastAPI backend (P4)  ──/predict──▶  RandomForest.predict  ──▶  severity + probability
        │            /health  /train                     (feature-aligned via features.json)
        │              │
        │              └─/train──▶ docker run asp-training (P4+P5, docker-out-of-docker) ──writes new model──┐
        │                                                                                                     │
        │                                                                              hot-reload ◀───────────┘
        ▼
   (future) Streamlit frontend (P7)  ──POST /predict──▶  backend

        ══════════════════════════════════════════════════════════════════════════════
        Packaging:  two Docker images + docker-compose  (P5)
        Quality:    pre-commit locally (P0)  +  GitHub Actions on push/PR (P6)
        Foundation: uv + pyproject groups, Ruff/mypy/pytest, common/ vs services/ (P0)
```

Trace one prediction through it: raw French CSVs are downloaded and versioned (P1), cleaned and
merged into one leakage-free train/test dataset (P2), used to train a versioned Random Forest whose
feature order is saved alongside it (P3); the FastAPI backend loads that model at startup, validates
an incoming request, aligns its columns to the saved feature list, and returns a severity with a
probability (P4); the whole thing runs as containers wired by compose (P5); and every code change is
gated by automated quality and test pipelines (P6). The frontend (P7) is the last, not-yet-built
mile.

---

## 7.3 The design principles that recur

If you internalize nothing else, internalize these — they showed up in *every* phase and they are
what make this a real MLOps project rather than a notebook:

1. **Reproducibility everywhere.** `random_state=42`, `uv.lock`, `dvc.lock`, `--frozen` installs,
   pinned pre-commit and Action versions, DVC-versioned data and models. The same inputs always
   produce the same outputs — the bedrock of trustworthy ML.
2. **Separation of concerns.** `common/` (library) vs `services/` (deployables); routes vs schemas
   vs services in the API; training separate from evaluation; two Docker images instead of one.
   Each piece does one thing and can be changed in isolation.
3. **Single source of truth for config.** `paths.py` centralizes every path and every knob
   (`DATA_PROCESSING_CONFIG`, `MODEL_CONFIG`). Behavior changes in one place and flows everywhere.
4. **Fail fast, fail loud, fail helpfully.** Explicit `raise FileNotFoundError("Missing usagers
   dataset for 2022")`, HTTP `503`/`422` with the actual missing/extra features, CI ordering that
   stops at the cheapest failing check, container crash-logs before health checks.
5. **Defense in depth on quality.** The *same* checks (Ruff, mypy, pytest, 80% coverage) run
   locally (pre-commit) *and* on the server (Actions). Two independent nets.
6. **Idempotency.** Downloaders skip existing files, `make_dataset` skips existing outputs, DVC
   re-runs only changed stages, `load_latest_model` no-ops if already loaded. Safe to re-run
   anything.
7. **Leakage awareness.** Fit imputers/scaler on train only; hold out 2024 as a temporal test set.
   The pipeline is built to give *honest* performance numbers.
8. **Versioned artifacts, never overwritten.** Timestamped model names keep a full history and make
   rollback trivial.

---

## 7.4 Consolidated punch-list — what you'd improve next

Reading critically is part of learning. Here's every gap we flagged, plus the frontend, in rough
priority order. None of these make the project "bad" — they're the natural next iterations, and
each is a great hands-on exercise for your own build.

1. **Train/serve scaling skew — ✅ RESOLVED (was highest priority, from Phase 4).** Training used to
   scale features with `StandardScaler` while the API fed *raw* values to `model.predict` — a skew.
   The team fixed it by **removing feature scaling entirely** (the model is a scale-invariant Random
   Forest, so scaling bought nothing), so train and serve now share the same raw, imputed feature
   space. If a future model *needs* scaling, do it the robust way: bundle impute → scale → model into
   one `sklearn.Pipeline`, save that single object, and load it in `prediction_service` — then the
   transforms are identical by construction.
2. **Build the Streamlit frontend (from this phase).** Turn the scaffold into a real UI over
   `/predict`, add a `Dockerfile.frontend`, and register it as a third compose service on
   `asp-network`.
3. **Trim the backend image (from Phase 5).** It installs the `training` dependency group it
   doesn't need to *serve*. Installing only `--group backend` yields a smaller, faster, more secure
   image.
4. **Wire up experiment tracking (the reserved `infra/tracking/`).** The repo name-drops MLflow in
   branches; adding it would log each training run's params/metrics/model for comparison — the
   natural companion to the timestamped-model versioning.
5. **Add data/label provenance to `/predict` responses and consider batch prediction.** Currently
   one row at a time; a `/predict/batch` endpoint (accepting a CSV or list) is a common next need.
6. **Monitoring (the classic "next phase" of MLOps).** With 2024 held out, this project is set up
   perfectly for drift monitoring — compare live inputs/predictions against the training
   distribution and alert on drift. (This is exactly the direction your parallel build is heading.)

---

## 7.5 A learner's roadmap — how to *do* it yourself

You said you want to simulate and reproduce this. Here's the end-to-end sequence, pulling together
the "Reproduce it yourself" sections from all seven guides into one runbook:

```bash
# ── Foundation (Phase 0) ─────────────────────────────────────────────
uv python pin 3.12
uv sync --all-groups
uv run pre-commit install
uv run ruff check . && uv run mypy common services && uv run pytest   # all green?

# ── Data (Phases 1–2) ────────────────────────────────────────────────
# Option A: real versioned data (needs DagsHub token)
uv run dvc remote modify origin --local access_key_id     <TOKEN>
uv run dvc remote modify origin --local secret_access_key <TOKEN>
uv run dvc pull
# Option B: no token — fetch open data directly, then build
uv run python -c "from common.data.download_data import download_raw_data; \
                  [download_raw_data(year=y) for y in (2021,2022,2023,2024)]"
uv run python -m common.data.make_dataset            # -> data/processed/{X,y}_{train,test}.csv

# ── Train + evaluate (Phase 3) ───────────────────────────────────────
uv run python -m services.training.train             # -> artifacts/{models,metrics,reports}/
cat artifacts/metrics/*_metrics.json                 # read your scores

# ── Serve (Phase 4) ──────────────────────────────────────────────────
uv run uvicorn services.backend.src.main:app --reload --port 8000
#   then open http://localhost:8000/docs  and try /health, /predict

# ── Containerize (Phase 5) ───────────────────────────────────────────
echo "HOST_PROJECT_ROOT=$(pwd)" > .env
docker compose --profile build-only build            # build training image
docker compose up -d --build backend                 # run API in a container
curl http://localhost:8000/api/v1/health

# ── Or reproduce the entire pipeline in one shot (Phases 1–3 via DVC) ─
uv run dvc repro                                      # download -> make_dataset -> train, only what changed
```

Do it once end-to-end and the seven phases stop being separate documents and become a single mental
model. The best way to cement each guide is to make a small deliberate change and watch its
consequences ripple: bump `n_estimators` in `MODEL_CONFIG` and `dvc repro`; add a Ruff violation and
watch pre-commit *and* CI catch it; delete a processed file and watch the idempotency guard rebuild
it.

---

## 7.6 Series checkpoint — you're done

Across seven phases you've learned, from this one real codebase:

- **P0** — how a production Python/ML repo is structured and quality-gated (`uv`, groups, Ruff,
  mypy, pytest, pre-commit, the `common`/`services` split).
- **P1** — why and how data + models are versioned with **DVC** and a DagsHub remote, and how a
  `dvc.yaml` pipeline reproduces work intelligently.
- **P2** — real-world data cleaning, feature engineering, leakage-free splitting/scaling — turning
  four messy BAAC tables into one honest dataset.
- **P3** — a config-driven training service that produces versioned, self-describing model
  artifacts and honest evaluation.
- **P4** — a layered FastAPI service that validates, predicts, and can trigger its own retraining —
  and a genuine train/serve-skew bug you can now spot anywhere.
- **P5** — packaging the system as Docker images and orchestrating it with compose, including the
  docker-out-of-docker training pattern.
- **P6** — automated CI/CD that re-enforces every quality gate on the server, with reusable
  workflows, matrix builds, and layered container tests.
- **P7** — where the human-facing frontend fits, and how every layer composes into one system.

That's the full arc of an MLOps project: **data you can trust → a model you can reproduce → a
service you can run → infrastructure you can deploy → automation you can rely on.**

You have the complete map now. The most valuable next step is to run the §7.5 runbook on your own
machine, then tackle the §7.4 punch-list — starting with the scaling fix — on your parallel build.
Good luck, and enjoy it.

---

*End of the learning-guide series. All seven phase documents live in `learning-guides/`. Revisit the
[README](README.md) for the index.*
