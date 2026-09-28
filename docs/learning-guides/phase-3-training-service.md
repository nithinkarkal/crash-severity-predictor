# Phase 3 — Training Service

> **Goal of this phase:** read the `services/training/` service end to end — how it loads the
> processed data from Phase 2, trains a Random Forest driven entirely by `MODEL_CONFIG`, saves a
> **timestamped, versioned** model plus its companion artifacts, then evaluates it on the held-out
> test set and writes metrics and a confusion matrix. This is the `train` stage from Phase 1's
> DVC pipeline, opened up.

This is our first *service* (Phase 0's distinction: `common/` is a library, `services/` are
deployable units). It imports from `common/` but stands on its own and can be run as a script or
inside a Docker container (Phase 5).

---

## 3.1 What & Why — the shape of a training service

A training service has one job: **turn processed data into a trained, saved, evaluated model —
reproducibly.** This one does it in three files:

```
services/training/
├── train.py                     ← ENTRY POINT (DVC `train` stage + Docker run this)
├── src/
│   ├── train_model.py           ← fit the model, save model + features + params + importance plot
│   └── evaluate_model.py        ← load latest model, score on test set, save metrics + confusion matrix
└── tests/
    ├── test_train_model.py      ← 7 tests
    └── test_evaluate_model.py   ← 8 tests
```

The design keeps **training** and **evaluation** as two separate functions (`run_training`,
`run_evaluation`) that `train.py` calls in sequence. Separating them matters: you can retrain
without re-evaluating, or evaluate an existing model without retraining — and each is unit-tested
in isolation.

Everything the service needs to *decide* (which algorithm settings, how many features to plot)
comes from `MODEL_CONFIG` in `common/utils/paths.py` (Phase 0). The service itself hard-codes
nothing about the model's hyperparameters — change them in one config dict and the whole service
follows.

---

## 3.2 The entry point — `train.py`

```python
from common.utils.paths import METRIC_DIR, MODEL_CONFIG, MODEL_DIR, PROCESSED_DATA_DIR, REPORT_DIR
from services.training.src.evaluate_model import run_evaluation
from services.training.src.train_model import run_training

def main() -> None:
    run_training(
        processed_data_dir=PROCESSED_DATA_DIR,
        model_out_dir=MODEL_DIR,
        reports_dir=REPORT_DIR,
        model_name=MODEL_CONFIG["model_name"],            # "model"
        model_parameters=MODEL_CONFIG["model_parameters"],# {random_state:42, n_estimators:200, n_jobs:-1}
        top_n_features=MODEL_CONFIG["top_n_features"],     # 20
    )
    # eval is used here for docker entrypoint
    run_evaluation(
        model_name=MODEL_CONFIG["model_name"],
        processed_data_dir=PROCESSED_DATA_DIR,
        model_dir=MODEL_DIR,
        metrics_dir=METRIC_DIR,
        reports_dir=REPORT_DIR,
    )

if __name__ == "__main__":
    main()
```

This tiny file is the *composition root* — it does no logic itself, it just wires config to the
two workers and runs them in order: **train, then evaluate.** It's exactly what the DVC stage
calls (`uv run python -m services.training.train`) and what the training Docker image runs on
start (Phase 5). Because both steps run together, a single `train` invocation produces **all
three** DVC outputs at once — `artifacts/models/`, `artifacts/metrics/`, `artifacts/reports/` —
which is why the pipeline groups them under one stage.

Note the path constants (`MODEL_DIR`, etc.) all come from `paths.py`, so the service writes to the
same `artifacts/` folders that DVC versions. No path is invented locally.

---

## 3.3 `train_model.py` — fit and save

### Loading the data

```python
X_train = load_processed_csv(processed_data_dir / "X_train.csv")
y_train = load_processed_csv(processed_data_dir / "y_train.csv").squeeze()
```

It reads the already-cleaned, already-imputed CSVs that Phase 2 produced. `.squeeze()` turns the
single-column `y_train` DataFrame into a 1-D Series, which is the shape scikit-learn expects for a
target. **Important consequence:** the model trains on data that was *imputed in Phase 2* (feature
scaling was removed, so the values are the model's own integer category codes and counts — not
standardized). (Keep that in mind; it's part of the serving question we've been tracking.)

### The model

```python
model = RandomForestClassifier(**model_parameters)   # n_estimators=200, n_jobs=-1, random_state=42
model.fit(X_train, y_train)
```

A **Random Forest** — an ensemble of decision trees. A sound default for this kind of tabular,
mixed-type problem: it handles non-linear relationships and feature interactions with almost no
tuning, is robust to outliers, and gives you feature importances "for free." The three configured
parameters are worth knowing:

- **`n_estimators=200`** — 200 trees. More trees = more stable predictions, up to a point, at the
  cost of memory and time. (This is largely why the saved forest is big — recall the ~6 GB
  `artifacts/models/` from Phase 1.)
- **`n_jobs=-1`** — use *all* CPU cores to build trees in parallel. Big speed-up on training.
- **`random_state=42`** — fixed seed → the same forest every run (reproducibility, again).

The `**model_parameters` splat means the *config dict* is passed straight into the constructor —
add a parameter to `MODEL_CONFIG` and it flows through with no code change.

### Timestamped versioning — never overwrite a model

```python
def _generate_model_name(base_name):
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")     # e.g. 20260722125017
    return f"{base_name}_{timestamp}"                        # "model" -> "model_20260722125017"
```

Every training run produces a **new, uniquely named** model file — `model_20260722125017.joblib`
— rather than clobbering the previous one. This is a deliberate, professional pattern: you keep a
*history* of models, can compare them, and can roll back if a new one is worse. It's why
`artifacts/models/` held **21 files** in Phase 1's `dvc.lock` (several model versions, each with
its companion files) and why the DVC `train` stage used `persist: true` (don't wipe prior models).

There's a small helper for round-tripping names:

```python
def _resolve_base_model_name(model_name, model_dir):
    """if given an already-timestamped name that exists on disk, strip back to the base name."""
    if "_" in model_name:
        if (model_dir / f"{model_name}.joblib").exists():
            return model_name.rsplit("_", 1)[0]     # "model_2026...": -> "model"
    return model_name
```

This stops names from snowballing into `model_2026..._2026...` if a full timestamped name is ever
passed back in. A defensive edge-case guard — the kind of thing you add after getting bitten once.

### Saving the artifacts

```python
def save_model_artifacts(model, features, model_parameters, model_out_dir, reports_dir, model_name, top_n_features=20):
    model_path      = model_out_dir / f"{model_name}.joblib"
    features_path   = model_out_dir / f"{model_name}_features.json"
    params_path     = model_out_dir / f"{model_name}_parameters.json"
    importance_path = reports_dir   / f"{model_name}_feature_importance.png"

    joblib.dump(model, model_path)                              # 1) the trained forest
    json.dump(features, open(features_path, "w"), indent=4)     # 2) exact feature column list/order
    json.dump(model_parameters, open(params_path, "w"), indent=4)  # 3) the hyperparameters used

    feature_importance = (pd.Series(model.feature_importances_, index=features)
                          .sort_values(ascending=False).head(top_n_features).sort_values(ascending=True))
    # ...barh plot...
    plt.savefig(importance_path, dpi=300)                       # 4) top-20 feature importance chart
    return {"model": ..., "features": ..., "parameters": ..., "feature_importance": ...}
```

Four artifacts per model, and each exists for a reason:

1. **`.joblib`** — the serialized model. `joblib` is scikit-learn's recommended serializer (more
   efficient than `pickle` for the big numpy arrays inside a forest).
2. **`_features.json`** — the **exact list of feature columns, in order.** This is the quiet hero
   of the whole project. A Random Forest cares about *column order and identity*; at prediction
   time you must feed features in precisely the same order they were trained on. Saving this list
   alongside the model is how the serving side (Phase 4) can align an incoming request to the
   model's expected inputs. This is a big part of the answer to the Phase 2 question.
3. **`_parameters.json`** — the hyperparameters, saved for provenance ("how was this model
   trained?"). Reproducibility and auditability.
4. **`_feature_importance.png`** — a horizontal bar chart of the top-N most important features.
   Human-readable model insight — which factors most drive severity — saved to `artifacts/reports/`.

Saving the model *and* its metadata *and* a visual report together is the mark of a training step
built for a team and for production, not just for a notebook.

---

## 3.4 `evaluate_model.py` — score the model honestly

### Find the model to evaluate

```python
matplotlib.use("Agg")   # headless backend: render to file, no screen needed (Docker/CI safe)

def _latest_model_path(model_dir, model_name):
    files = list(model_dir.glob(f"{model_name}_*.joblib"))
    if not files:
        raise FileNotFoundError(f"No trained model found for '{model_name}_*.joblib'")
    return max(files, key=lambda p: p.stat().st_mtime)     # newest by modification time
```

Because training writes timestamped files, evaluation picks the **most recent** one by file
modification time. So `train.py`'s "train then evaluate" always scores the model that was just
produced.

`matplotlib.use("Agg")` at import time is a small but crucial detail: **"Agg"** is a non-interactive
backend that draws straight to an image file. Without it, matplotlib may try to open a GUI window,
which crashes in a container or CI runner that has no display. Setting it here makes plotting safe
everywhere.

### Predict and measure

```python
X_test = load_processed_csv(processed_data_dir / "X_test.csv")
y_test = load_processed_csv(processed_data_dir / "y_test.csv").squeeze()
y_pred = model.predict(X_test)

metrics = {
    "Model":     actual_model_name,
    "Accuracy":  accuracy_score(y_test, y_pred),
    "Precision": precision_score(y_test, y_pred),
    "Recall":    recall_score(y_test, y_pred),
    "F1 Score":  f1_score(y_test, y_pred),
}
```

The model predicts on the **2024 held-out test set** (Phase 2's temporal split) — data it never
saw in training, so these numbers are an *honest* estimate of real-world performance. The four
metrics are the standard binary-classification set:

- **Accuracy** — fraction of all predictions that were correct. Easy to read, but misleading on
  imbalanced data.
- **Precision** — of the accidents the model *flagged as serious*, how many actually were. (Low
  precision = many false alarms.)
- **Recall** — of the accidents that *were serious*, how many the model caught. (Low recall =
  missing real serious accidents — usually the costlier error here.)
- **F1** — the harmonic mean of precision and recall, a single balanced score. For a safety
  problem like accident severity, precision/recall/F1 matter more than raw accuracy, because you
  care specifically about catching the serious (minority) cases.

### Save metrics + confusion matrix

```python
json.dump(metrics, open(metrics_path, "w"), indent=4)      # artifacts/metrics/<model>_metrics.json

ConfusionMatrixDisplay.from_predictions(y_test, y_pred, cmap="Blues", normalize="true", ax=ax, colorbar=False)
plt.savefig(confusion_matrix_path, dpi=300)                # artifacts/reports/<model>_confusion_matrix.png
```

Metrics go to `artifacts/metrics/` as JSON (machine-readable, diffable, DVC-tracked — recall "6
files" there in `dvc.lock`). The **confusion matrix** — normalized by true class (`normalize="true"`,
so each row shows the *rate* at which a true class is predicted as each label) — goes to
`artifacts/reports/` as a PNG. Together they tell you not just *how good* the model is but
*where* it errs (e.g. does it confuse serious accidents for non-serious?).

---

## 3.4a MLflow — experiment tracking & the model registry

> **Added after the first draft** (PRs "MLflow tracking" and "MLflow model registry"). Training no
> longer just writes files to disk — it also logs to **MLflow** (hosted on DagsHub) and registers
> the model in the **MLflow Model Registry**. This is what makes retraining governable in Phase 8.

Two ideas, kept separate on purpose:

**1. Experiment tracking (every run is recorded).** `common/utils/mlflow.py::setup_mlflow` points
MLflow at the DagsHub tracking server (headless auth via `DAGSHUB_USER_TOKEN`), and `log_run` logs
the run's **params, metrics, and artifacts**. So every training run is a permanent, comparable
record on DagsHub — you can see F1 across runs, not just the latest file on disk.

**2. The model registry (named, versioned, promotable).** On top of tracking, the registry gives the
model a **name**, incrementing **versions**, and movable **aliases**:

- `register_model(...)` — after logging the run, registers the trained model as a **new candidate
  version** (v1, v2, v3, …) under the registered model name.
- `promote_if_better(registered_version, metric_name, ...)` — the **champion/challenger** logic. It
  reads the metric of the version currently carrying the **`production`** alias, compares the new
  candidate against it, and *only if the candidate is better*:
  - moves the old production version to the **`fallback`** alias (so you can roll back), and
  - moves the **`production`** alias onto the new version.
  If there's no current production version yet, the candidate becomes production directly.
- `load_registered_model(alias="production")` — how the serving side (Phase 4) loads *the* live
  model by alias, without hard-coding a version number.

```python
# services/training/train.py (essence)
with mlflow.start_run():
    ...                                     # train + log params/metrics/artifacts
    registered_version = register_model(...)   # register a NEW candidate version

    # By default training STOPS here — it registers a candidate but does NOT promote.
    if os.environ.get("ASP_PROMOTE_AFTER_TRAIN", "0") == "1":
        promote_if_better(registered_version=registered_version, ...)
```

**Why training doesn't auto-promote.** Notice the guard: by default `train.py` only *trains, logs,
and registers a candidate* — it does **not** flip the `production` alias. Promotion is governed by
the **retraining DAG** (Phase 8, "Option B"), which runs `compare` then `promote` as explicit,
auditable steps via `services.training.promote`. Setting `ASP_PROMOTE_AFTER_TRAIN=1` lets training
self-promote instead (handy for a one-off local run). This separation is the whole point of Option B:
*deciding* to promote is a governed pipeline step, not a side effect of training.

---

## 3.5 Where this leaves the "serving" question

We've now seen most of the answer to the thread we started in Phase 2. At training time:

- the model is trained on **imputed** features (produced in Phase 2 — no scaling anymore), and
- the **exact feature list/order** is saved next to the model in `_features.json`.

So the serving side (Phase 4) will be able to align an incoming request's columns to the model's
expected features. Because **feature scaling was removed**, the serving side no longer has to
reproduce a `StandardScaler` (mean/std) on live input — a fresh accident just needs its columns
aligned to `_features.json`. Keep one flag raised for Phase 4: *"how does `prediction_service.py`
align a raw request's columns before calling `model.predict`?"*

---

## 3.6 The tests (15 tests)

| Test file | Tests | What it protects |
|-----------|------:|------------------|
| `test_train_model.py` | 7 | name generation, returns a fitted model, saves all 4 artifacts, **auto-versioning creates 2+ files**, missing-data raises, saved model reloads |
| `test_evaluate_model.py` | 8 | picks latest model, missing-model/missing-data raise, returns metrics dict, writes metrics JSON + confusion PNG, **metrics are floats in [0,1]** |

Patterns worth noting (they reuse Phase 2's toolkit):

- **Everything runs on `tmp_path` with tiny synthetic data.** `training_data` writes a 5-row
  `X_train.csv`/`y_train.csv`; the tests then train a 10-tree forest in milliseconds. No real
  data, no DVC, no network — fast and hermetic.
- **The versioning test actually sleeps.** `test_run_training_auto_versions` calls `run_training`
  twice with `time.sleep(1)` between them, because the version name is a *second-resolution*
  timestamp — the pause guarantees two distinct filenames, then asserts `>= 2` model files exist.
  A neat illustration of testing time-dependent behavior deliberately.
- **Round-trip test.** `test_save_artifacts_loadable_model` doesn't just check the file exists — it
  `joblib.load`s it back and asserts it's a `RandomForestClassifier`. Proving an artifact is
  *usable*, not merely *present*, is the difference between a real test and a box-tick.
- **Contract tests on metrics.** `test_eval_metrics_are_floats_0_to_1` asserts every metric is a
  float in `[0, 1]` — catching whole classes of bugs (a metric returning `None`, a numpy type that
  won't JSON-serialize, or a value outside the valid range).

---

## 3.7 Reproduce it yourself

### Run the real training stage (needs `data/processed/` from Phase 2)

```bash
uv run python -m services.training.train
```

**Expected output:** logs *"Loading processed training dataset… Training RandomForest model…
Saving model as 'model_<timestamp>'… Training completed."* then evaluation logs ending in a line
like `Evaluation completed | Accuracy=0.xxxx | Precision=0.xxxx | Recall=0.xxxx | F1=0.xxxx`.
Afterwards:

```bash
ls artifacts/models/     # model_<ts>.joblib, model_<ts>_features.json, model_<ts>_parameters.json
ls artifacts/metrics/    # model_<ts>_metrics.json
ls artifacts/reports/    # model_<ts>_feature_importance.png, model_<ts>_confusion_matrix.png
cat artifacts/metrics/*_metrics.json          # read the scores
```

> Heads-up: with `n_estimators=200` on the full dataset this can take a while and produce a large
> model file. To experiment faster, run it via Python with smaller settings (below).

### Fast experiment — no full dataset, tiny model

```python
from services.training.src.train_model import run_training
from services.training.src.evaluate_model import run_evaluation

# point at a folder that has X_train/y_train (and X_test/y_test for eval)
run_training("data/processed", "artifacts/models", "artifacts/reports",
             model_name="model", model_parameters={"n_estimators": 20, "random_state": 42, "n_jobs": -1})
print(run_evaluation("model", "data/processed", "artifacts/models", "artifacts/metrics", "artifacts/reports"))
```

### Always available — run the tests (no data needed)

```bash
uv run pytest services/training/tests -v
```

**Expected output:** 15 tests `PASSED`, in a couple of seconds. Great for watching versioning,
artifact-saving, and metric computation behave on synthetic data.

---

## 3.8 Phase 3 checkpoint

You understand Phase 3 when you can explain:

- Why `train.py` is a thin composition root that runs `run_training` then `run_evaluation`, and why
  that produces all three DVC `train` outputs at once.
- How `MODEL_CONFIG` drives the model — and what `n_estimators=200`, `n_jobs=-1`, `random_state=42`
  each do.
- The **timestamped versioning** scheme, why models are never overwritten, and how it explains the
  many files in `artifacts/models/` plus DVC's `persist: true`.
- The four saved artifacts and why each exists — especially why **`_features.json`** (feature
  order) is critical for correct serving.
- Why evaluation runs on the **2024 held-out** set, and what accuracy / precision / recall / F1 each
  tell you (and why precision/recall matter most for a safety problem).
- What `matplotlib.use("Agg")` is for, and why `normalize="true"` on the confusion matrix is useful.
- The serving hand-off: `_features.json` carries the exact feature order to Phase 4 (and with
  scaling removed, there's no scaler to reproduce — just column alignment). The registry's
  `production` alias is how serving picks *which* model to load.

---

### Next up — Phase 4: Backend API

We enter `services/backend/` — the FastAPI application. We'll read how it's structured (routes,
schemas, services), how it loads the latest model on startup (`lifespan`), how `/predict` turns a
request into a prediction, how `/train` triggers training, and — the payoff — exactly how
`prediction_service.py` handles the feature-alignment question we've been tracking since Phase 2.
We'll also meet the **JWT auth** that now guards `/predict` and `/train`. Say **"Phase 4"** when
you're ready.
