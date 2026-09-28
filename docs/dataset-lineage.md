# Dataset & Code Lineage in MLflow

**Goal:** make every MLflow run answer the question *"which exact dataset and which exact code produced this model?"* — with one glance, not guesswork.

## The problem it solves

With many experiments on DagsHub, the runs look almost identical. Previously, the only way to link a run to its training data was to correlate **timestamps** between the MLflow run and the DVC/git commit history — exactly the weak spot a reviewer can probe ("prove which data trained this model"). Nothing inside the run recorded the data version.

## What we added

A small, self-contained module, [`common/utils/lineage.py`](../common/utils/lineage.py), that collects **lineage tags** and attaches them to each run. It is called once inside `log_run()` in [`common/utils/mlflow.py`](../common/utils/mlflow.py), right after metrics are logged.

Tags written to every run:

| Tag | Meaning | Source |
|---|---|---|
| `git_commit`, `git_commit_short` | the exact **code** version | `git rev-parse HEAD` |
| `git_branch` | branch at train time | `git rev-parse --abbrev-ref HEAD` |
| `git_dirty` | were there uncommitted changes? | `git status --porcelain` |
| `dvc_processed_data_md5` | the **dataset** fingerprint (training data) | `dvc.lock` → `make_dataset` → `data/processed/` |
| `dvc_raw_data_md5` | raw data fingerprint | `dvc.lock` → `download_data` → `data/raw/` |
| `dvc_lock_md5` | one fingerprint of the whole pipeline lock | md5 of `dvc.lock` |
| `data_years`, `exclusive_test_year` | data window + held-out year | project config |
| `lineage_logged_at` | when lineage was captured | UTC timestamp |

Because DVC stores an **immutable md5** for each pipeline output, `dvc_processed_data_md5` *is* the identity of the training data. Pair it with `git_commit` and any run is fully reproducible.

## Why it can never break training

Every lookup is wrapped and degrades to `"unknown"`:

- **No `.git`** (e.g. inside the training container)? It reads the `GIT_COMMIT` / `GIT_BRANCH` env vars if provided, else `"unknown"`.
- **No `dvc.lock`**? It reads the `DVC_DATA_HASH` env var if provided, else `"unknown"`.
- **No PyYAML**? It falls back to a tiny regex parser for `dvc.lock`.

The call site in `log_run()` is itself wrapped in `try/except`, so a lineage failure only logs a warning — it never fails the run.

## How to verify

```powershell
# unit tests for the module
uv run pytest common/tests/test_lineage.py -q

# see the tags a run would get, right now, from the repo root
uv run python -c "from common.utils.lineage import collect_lineage; import json; print(json.dumps(collect_lineage(), indent=2))"
```

After the next training run, open the run on DagsHub → **Tags**: you'll see `git_commit`, `dvc_processed_data_md5`, etc. To reproduce that run's data later:

```powershell
git checkout <git_commit>
dvc checkout           # restores data/ to the md5 recorded in that commit's dvc.lock
```

## Next step (optional)

For the containerized Airflow run, pass the two env vars into the `train_and_log_mlflow` task so the container records the same lineage the scheduler sees:
`GIT_COMMIT` (from `git rev-parse HEAD`) and `DVC_DATA_HASH` (from the `make_dataset` out in `dvc.lock`).
