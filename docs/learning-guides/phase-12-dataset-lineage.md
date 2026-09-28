# Phase 12 — Dataset & Code Lineage (reproducible MLflow runs)

> **Goal of this phase:** make every MLflow run answer, on its own, the question *"which exact
> dataset and which exact code produced this model?"* You'll read the small module
> `common/utils/lineage.py`, see how it reads the **DVC data hash** and the **git commit**, how it's
> wired into `log_run()` from Phase 3, and why it's written so it can *never* break a training run.

This is the first **post-defense enhancement** — a real gap that a reviewer can (and did) probe:
*"prove which data trained this model."* Before this, the only link between an MLflow run and its
data was the **timestamp** — you'd eyeball the run time and try to match it to a git/DVC commit. That
is fragile and unconvincing. This phase closes the loop.

---

## 12.1 What & Why — two versions, one run

A trained model is a function of exactly two things: the **code** that trained it and the **data** it
saw. To reproduce or audit a model you must pin *both*. We already version both — git for code, DVC
for data (Phase 1) — but nothing recorded *which* commit/hash a given MLflow run used.

The fix is small: at logging time, capture both identifiers and attach them to the run as **tags**.

```
   code version                data version
   (git commit SHA)            (DVC md5 of data/processed)
          └──────────┐   ┌──────────┘
                     ▼   ▼
              one MLflow run  ──▶  tags: git_commit=…, dvc_processed_data_md5=…
```

Because DVC stores an **immutable md5** for every pipeline output, the hash of `data/processed` *is*
the fingerprint of the training data. Pair it with the git commit and any run is fully reproducible.

---

## 12.2 Where the two identifiers come from

- **Code → git.** `git rev-parse HEAD` gives the commit SHA; `git status --porcelain` tells us if
  there were **uncommitted changes** at train time (a "dirty" tree — a warning sign for
  reproducibility).
- **Data → DVC.** Recall from Phase 1 that `dvc.lock` records an md5 for each stage's outputs:

  ```yaml
  make_dataset:
    outs:
    - path: data/processed/
      md5: 496d188249cc62daa5c56ece4733ec8a.dir   # ← the training-data fingerprint
  ```

  We read that md5 straight out of `dvc.lock` — no network, no `dvc` command needed.

---

## 12.3 The module — `common/utils/lineage.py`

The whole feature is one small, dependency-light module. Three private helpers and one public
function.

### Git half

```python
def _git_lineage(root: str) -> dict[str, str]:
    commit = os.environ.get("GIT_COMMIT") or _run_git(["rev-parse", "HEAD"], root)
    branch = os.environ.get("GIT_BRANCH") or _run_git(["rev-parse", "--abbrev-ref", "HEAD"], root)
    ...
    return {"git_commit": commit or UNKNOWN, "git_commit_short": commit[:8], ...}
```

- `_run_git` shells out with `subprocess`, but is wrapped in `try/except` returning `""` on any
  failure — **git missing, or not a repo, never crashes us.**
- **Env overrides first** (`GIT_COMMIT`, `GIT_BRANCH`). Why? Inside the training **container** there
  is often no `.git` directory (the DAG mounts only `data/` + `artifacts/`). So the caller can pass
  the commit as an env var; if it doesn't, we degrade to `"unknown"` rather than fail.

### Data half

```python
def _dvc_lineage(root: str) -> dict[str, str]:
    lock = Path(root) / "dvc.lock"
    if not lock.exists():
        env_hash = os.environ.get("DVC_DATA_HASH")   # container fallback
        ...
    text = lock.read_text(encoding="utf-8")
    tags["dvc_lock_md5"] = hashlib.md5(text.encode()).hexdigest()   # fingerprint of the whole lock
    try:
        import yaml
        stages = (yaml.safe_load(text) or {}).get("stages", {})
    except Exception:
        stages = {}
    if stages:
        tags["dvc_processed_data_md5"] = _find_out_md5(stages, "make_dataset", "data/processed")
    else:
        tags["dvc_processed_data_md5"] = _parse_lock_with_regex(text, "make_dataset", "data/processed")
```

Two robustness touches worth calling out:

- **`yaml` is optional.** PyYAML ships with dvc/mlflow, but rather than *depend* on it we `try` the
  clean YAML parse and **fall back to a tiny regex parser** (`_parse_lock_with_regex`) if it's
  missing. Self-contained by design.
- **`dvc_lock_md5`** is a single fingerprint of the entire lock file — a one-line "did *anything* in
  the pipeline change?" signal, complementary to the per-output hash.

### Public API

```python
def collect_lineage(project_root: Path | str = PROJECT_ROOT) -> dict[str, str]:
    tags = {}
    tags.update(_git_lineage(root))
    tags.update(_dvc_lineage(root))
    tags["data_years"] = ",".join(str(y) for y in DATA_PROCESSING_CONFIG.get("years", []))
    tags["exclusive_test_year"] = str(DATA_PROCESSING_CONFIG.get("exclusive_test_year", UNKNOWN))
    tags["lineage_logged_at"] = datetime.now(UTC).isoformat()
    return {k: (str(v) if v not in (None, "") else UNKNOWN) for k, v in tags.items()}
```

The final dict-comprehension guarantees **every value is a non-empty string** — MLflow tags must be
strings, so this is a safety net against a `None` slipping through.

---

## 12.4 Wiring it into `log_run()`

We don't call it from a new place — we hook the existing logging path from Phase 3
(`common/utils/mlflow.py`):

```python
mlflow.log_metrics(eval_out["metrics"])

# Dataset & code lineage — never fatal
try:
    lineage = collect_lineage()
    mlflow.set_tags(lineage)
    logger.info(f"Logged lineage: git={lineage.get('git_commit_short')} data(md5)={lineage.get('dvc_processed_data_md5')}")
except Exception as exc:
    logger.warning(f"Lineage tagging skipped ({exc}).")
```

The **`try/except` at the call site** is the last line of defence: even if lineage collection somehow
raised, it logs a warning and the training run continues. Observability must never break the thing it
observes.

---

## 12.5 The tags you get on every run

| Tag | Meaning |
|-----|---------|
| `git_commit`, `git_commit_short` | exact code version |
| `git_branch`, `git_dirty` | branch, and whether the tree had uncommitted changes |
| `dvc_processed_data_md5` | **training-data fingerprint** (from `dvc.lock`) |
| `dvc_raw_data_md5` | raw-data fingerprint |
| `dvc_lock_md5` | one fingerprint of the whole pipeline lock |
| `data_years`, `exclusive_test_year` | data window + the held-out year |
| `lineage_logged_at` | UTC timestamp of capture |

---

## 12.6 Reproduce it yourself

```powershell
# See the tags a run would get right now, straight from the repo:
uv run python -c "from common.utils.lineage import collect_lineage; import json; print(json.dumps(collect_lineage(), indent=2))"

# Unit tests for the module:
uv run pytest common/tests/test_lineage.py -q --no-cov
```

**Expected:** a JSON dict with a real `git_commit`, your `dvc_processed_data_md5`, etc. On a clean
tree `git_dirty` reads `false`; with uncommitted changes it reads `true`.

To reproduce a specific past model, read its tags in the DagsHub MLflow UI, then:

```powershell
git checkout <git_commit>     # restore the exact code
dvc checkout                  # restore data/ to the md5 recorded in that commit's dvc.lock
```

---

## 12.7 Phase 12 checkpoint

You understand Phase 12 when you can explain:

- Why a model needs **both** a code identifier and a data identifier to be reproducible.
- Where each comes from — `git rev-parse HEAD` and the `data/processed` md5 in `dvc.lock`.
- The three graceful fallbacks that stop lineage ever breaking a run: env-var overrides (no `.git`
  in the container), the YAML→regex fallback (no PyYAML), and the `try/except` at the call site.
- Why every tag value is coerced to a non-empty string.
- How you'd reproduce a run from its tags (`git checkout` + `dvc checkout`).

---

### Next up — Phase 13: Explainability & model transparency

We'll look at the `/explain` endpoint (per-prediction **SHAP** attributions), the **plain-language
summary** generated from those attributions, the `/model/info` endpoint, and the **model card**
(`MODEL_CARD.md`) — together, the "why did the model say that, and can I trust it?" layer.
