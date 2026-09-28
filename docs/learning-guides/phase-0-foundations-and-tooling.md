# Phase 0 — Foundations & Tooling

> **Goal of this phase:** understand the skeleton the whole project hangs on — how the
> repository is laid out, how dependencies are managed with `uv`, how quality is enforced
> automatically (Ruff, mypy, pre-commit, tests), how common tasks are run through the
> Makefile, and how the team collaborates through Git. None of this is "the ML" yet — it is
> the disciplined scaffolding that makes the ML reproducible and safe to change.

Think of Phase 0 as *setting up the workshop before touching the wood*. A 30-year habit:
the teams that ship reliable ML are the ones who invest here first.

---

## 0.1 What & Why — the big picture

A production ML repo has to answer five questions cleanly, and this project answers each
with a specific tool:

| Question | Tool used here |
|----------|----------------|
| What Python and packages do we need, exactly? | **`uv`** + `pyproject.toml` + `uv.lock` |
| How is the code organized? | A **`common/` + `services/`** package layout |
| How do we keep code quality consistent? | **Ruff** (lint+format) + **mypy** (types) |
| How do we stop bad code being committed? | **pre-commit** hooks |
| How do we run routine commands the same way every time? | **Makefile** |
| How do we collaborate without breaking `main`? | A **Git branch workflow** |

The theme is **"make the right thing the easy thing."** If quality checks run automatically,
nobody has to remember them.

---

## 0.2 The repository layout

Run this at the repo root to see the shape (ignoring the big generated folders):

```bash
# Windows PowerShell or Git Bash
find . -not -path '*/.git/*' -type d -maxdepth 2   # Git Bash / macOS / Linux
```

The important top-level structure:

```
accident-severity-predictor/
├── common/                 # Shared, reusable Python package
│   ├── data/               #   data pipeline scripts (download, clean, merge, make_dataset)
│   ├── tests/              #   unit tests for the data scripts
│   └── utils/              #   cross-cutting helpers (paths, logging)
├── services/               # Independent runnable services (microservice style)
│   ├── backend/            #   FastAPI app that serves predictions & triggers training
│   ├── training/           #   the training + evaluation service
│   └── frontend/           #   Streamlit UI (scaffolded, built later)
├── data/                   # Data lives here — CONTENTS are git-ignored, tracked by DVC
│   ├── raw/  processed/  external/
├── artifacts/              # Model, metrics, reports — CONTENTS git-ignored, tracked by DVC
│   ├── models/  metrics/  reports/
├── infra/                  # Infra placeholders (docker, tracking)
├── notebooks/exploration/  # EDA notebook(s)
├── docs/                   # Project documentation (e.g., dvc_setup.md)
├── .github/workflows/      # CI/CD pipelines (GitHub Actions)
├── dvc.yaml   dvc.lock     # The DVC pipeline definition + lock
├── docker-compose.yaml     # Multi-service run definition
├── Makefile                # Shortcut commands
├── pyproject.toml          # Project metadata, dependencies, tool config
├── uv.lock                 # Exact resolved dependency versions
├── .pre-commit-config.yaml # Automated pre-commit quality gates
└── README.md
```

**Why this split matters.** The single most important architectural decision visible here is
`common/` vs `services/`:

- **`common/`** is a *library*: pure, importable Python that several services can reuse
  (the data-cleaning functions, the path constants, the logger). It has no `main()` that
  "runs the app"; it is imported.
- **`services/`** are *deployable units*: each one is something you can start (an API, a
  training job, a UI). They *import from* `common/` but not from each other.

This is the classic "shared kernel + independent services" shape. It keeps the data logic in
exactly one place, so the training service and the API can't drift apart on how a feature is
computed.

A second decision visible in the layout: **directories are committed but their heavy contents
are not.** `data/` and `artifacts/` exist in Git (via `.gitkeep` placeholder files) so the
folder structure is guaranteed, but the actual CSVs and model files are ignored by Git and
handed to **DVC** instead (Phase 1). This keeps the Git repo small and text-only.

---

## 0.3 Dependency management with `uv` and `pyproject.toml`

**What `uv` is:** a very fast, modern Python package and environment manager (a single tool
replacing `pip` + `venv` + `pip-tools`). The project standardizes on it.

**Install uv** (one-time, per machine):

```bash
# Windows (PowerShell) — either of these
winget install Astral-sh.uv
# or
scoop install uv

# macOS
brew install uv

# Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Reading `pyproject.toml`

This one file does three jobs. Let's read it in pieces.

**(a) Project identity + Python version**

```toml
[project]
name = "accident-severity-predictor"
version = "0.1.0"
description = "ML pipeline for predicting accident severity using French road accident data (BAAC)"
readme = "README.md"
requires-python = ">=3.12"
dependencies = []
```

Note `dependencies = []` is **empty**. That is intentional — this project puts *nothing* in
the always-installed core and instead uses **dependency groups** (below), so each environment
(backend vs training vs dev) only pulls what it needs.

**(b) Dependency groups — the key idea**

```toml
[dependency-groups]
backend  = ["fastapi", "uvicorn", "pydantic", "pydantic-settings", "requests", "httpx2"]
dev      = ["dvc[s3]", "ipykernel", "jupyterlab", "mypy", "pre-commit", "pytest", "pytest-cov", "python-dotenv", "ruff"]
frontend = ["plotly", "streamlit"]
training = ["lightgbm", "xgboost", "scikit-learn", "pandas", "numpy", "matplotlib", "seaborn", "plotly", "joblib"]
```
*(versions trimmed for readability — see the file for exact pins)*

**Why groups?** The **training** image needs heavy ML libraries (LightGBM, XGBoost, pandas).
The **backend** API does *not* — it only needs FastAPI and friends. By separating them, the
backend Docker image stays small and fast, and CI can install just what a given job needs.
The **dev** group holds everything you want on a developer laptop (test runner, linters,
notebooks, DVC).

**(c) Tool configuration** — the same file also configures Ruff, mypy, pytest, and coverage
(covered in 0.5 and 0.6). Keeping tool config in `pyproject.toml` means one source of truth.

### `uv.lock` — the reproducibility guarantee

`pyproject.toml` says *what* you want (e.g. "fastapi >= 0.139"). `uv.lock` records the *exact*
version of every package and sub-dependency that was actually resolved, with hashes. Committing
the lock file means every teammate and every CI run installs **byte-for-byte the same
environment**. You never edit `uv.lock` by hand; `uv` maintains it.

### Reproduce it yourself

```bash
# 1. Pin the interpreter this project expects (creates a .python-version file)
uv python pin 3.12

# 2. Create the virtual env and install ALL groups (dev + backend + training + frontend)
uv sync --all-groups
```

**Expected output:** uv creates a `.venv/` folder and prints a list of resolved/installed
packages ending in something like `Installed NN packages in ...s`. After this you can run any
project command with `uv run <cmd>` (no manual "activate" needed — `uv run` uses `.venv`
automatically).

**Checkpoint:**

```bash
uv run python --version        # -> Python 3.12.x
uv run ruff --version          # -> ruff 0.x
uv run pytest --version        # -> pytest 9.x
```

---

## 0.4 The Makefile — one-word commands

**What it is:** `make` reads a `Makefile` and runs the named recipe. It turns long, easy-to-
mistype commands into short verbs. Here is the whole file, annotated:

```makefile
.PHONY: init-project dvc-pull train-model dvc-push run-pipeline run-backend stop-backend

init-project:            # run once after cloning: install every dependency group
	uv sync --all-groups

dvc-pull:                # download the current data + model versions from the DVC remote
	uv run dvc pull

run-backend:             # build & start the FastAPI backend container in the background
	docker compose up -d --build backend

stop-backend:            # stop and remove the compose services
	docker compose down

dvc-push:                # upload new data/model versions to the DVC remote
	uv run dvc push

run-pipeline:            # reproduce the whole DVC pipeline, then push results
	uv run dvc repro
	uv run dvc push
```

**Why it matters:** the Makefile is *executable documentation*. A newcomer doesn't need to
know the exact `docker compose` incantation — they run `make run-backend`. It also guarantees
everyone runs the *same* command, which prevents "works on my machine" drift.

- `.PHONY` tells `make` these names are commands, not files to build. Without it, if a file
  named `dvc-push` ever existed, `make dvc-push` would think there was "nothing to do."

### Reproduce it yourself

```bash
make init-project     # equivalent to: uv sync --all-groups
```

*(On Windows, `make` isn't installed by default. Options: install it via `choco install make`
or Git Bash, or just run the underlying command shown under each recipe.)*

---

## 0.5 Code quality: Ruff + mypy

Two automated gatekeepers, both configured inside `pyproject.toml`.

### Ruff — linter *and* formatter (very fast)

```toml
[tool.ruff]
line-length = 150
target-version = "py312"
exclude = [".venv", "artifacts", "data", "htmlcov", ".pytest_cache", "notebooks"]

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B"]
```

Those codes turn on rule families: **E/W** (PEP 8 style), **F** (Pyflakes — unused imports,
undefined names), **I** (import sorting, like isort), **N** (naming conventions), **UP**
(modernize old syntax), **B** (bugbear — likely bugs).

A neat, real-world detail — **per-file rule relaxations**:

```toml
[tool.ruff.lint.per-file-ignores]
"common/data/*.py"          = ["N803", "N806"]   # allow X_train, X_test (ML naming)
"services/training/src/*.py"= ["N803", "N806"]
"notebooks/**/*.ipynb"      = ["N803", "N806", "W291"]
```

`N803`/`N806` normally forbid uppercase argument/variable names, but ML code universally uses
`X_train`, `X_test`, `y_train`. Rather than fight the convention, the project *documents* the
exception exactly where it applies. That's mature tooling: rules serve the code, not vice versa.

### mypy — static type checking

```toml
[tool.mypy]
python_version = "3.12"
disallow_untyped_defs = true      # every function must have type hints
disallow_incomplete_defs = true
warn_unused_ignores = true
strict_equality = true
# ...many strict flags on...
```

This is a **strict** configuration: every function needs type annotations, and many subtle
mistakes become errors. Third-party libraries without type stubs (sklearn, pandas, joblib,
matplotlib) are exempted so their missing types don't create noise:

```toml
[[tool.mypy.overrides]]
module = ["sklearn.*", "joblib", "matplotlib.*", "pandas.*"]
ignore_missing_imports = true
```

Tests get relaxed rules (you don't want strict typing to slow down writing tests):

```toml
[[tool.mypy.overrides]]
module = ["common.tests.*", "services.training.tests.*", "services.backend.tests.*"]
disallow_untyped_defs = false
```

### Reproduce it yourself

```bash
uv run ruff check .        # lint; add --fix to auto-fix
uv run ruff format .       # auto-format
uv run mypy common services
```

**Expected output (healthy repo):** `All checks passed!` from Ruff, and mypy either reports
`Success: no issues found` or a small list you can read.

---

## 0.6 Tests + coverage (pytest)

Also configured in `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["common/tests", "services/training/tests", "services/backend/tests"]
pythonpath = ["."]
addopts = [
    "-v", "--tb=short",
    "--cov=common", "--cov=services",
    "--cov-report=term-missing",
    "--cov-report=html:htmlcov",
    "--cov-fail-under=80",     # BUILD FAILS if coverage < 80%
    "-ra",
]
```

Key ideas:

- **`testpaths`** — pytest looks in each service's own `tests/` folder. Tests live *next to*
  the code they test, not in one giant global folder.
- **`pythonpath = ["."]`** — lets tests `import common...` / `import services...` from the repo
  root without installing the project.
- **`--cov-fail-under=80`** — a hard quality gate: if less than 80% of the code is exercised by
  tests, the command exits non-zero (and CI goes red). This is how you *enforce* a testing
  culture instead of merely hoping for one.
- Coverage reports are emitted three ways: terminal (`term-missing` shows which lines are
  untested), an HTML site in `htmlcov/`, and `coverage.xml` (machine-readable, for CI).

### Reproduce it yourself

```bash
uv run pytest
```

**Expected output:** a list of tests with `PASSED`, then a coverage table per file, then a
total percentage. If the total is ≥ 80%, exit code 0. Open `htmlcov/index.html` in a browser
to explore line-by-line coverage.

---

## 0.7 pre-commit — quality gates that run automatically

**The problem it solves:** linters and tests only help if people actually run them. `pre-commit`
wires them to fire **on every `git commit`**, so broken or unformatted code can't enter history.

Reading `.pre-commit-config.yaml`:

```yaml
default_language_version:
  python: python3.12

repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit    # Ruff hooks (pinned version)
    hooks:
      - id: ruff-check     # lint, auto-fixing what it can (args: [--fix])
      - id: ruff-format    # format

  - repo: https://github.com/pre-commit/pre-commit-hooks  # generic hygiene hooks
    hooks:
      - id: check-yaml            # valid YAML
      - id: check-json            # valid JSON
      - id: check-toml            # valid TOML
      - id: trailing-whitespace   # strip trailing spaces
      - id: end-of-file-fixer     # ensure files end in a newline
      - id: check-merge-conflict  # block committing <<<<<<< markers
      - id: check-added-large-files
      - id: mixed-line-ending

  - repo: local                   # run OUR tools using the project's own env
    hooks:
      - id: mypy
        entry: uv run mypy common services
        language: system
        pass_filenames: false
      - id: pytest
        entry: uv run pytest
        language: system
        pass_filenames: false
```

Two things worth noticing:

1. **Pinned versions** (`rev: v0.16.0`, `rev: v6.0.0`). The exact hook versions are frozen so
   every developer gets identical checks — the same reproducibility principle as `uv.lock`.
2. **The `local` repo** runs mypy and pytest through `uv run`, i.e. inside *this project's*
   environment (`language: system`, `pass_filenames: false` = "run the whole suite, not just
   changed files"). So a commit that breaks a type or a test is rejected before it's created.

### Reproduce it yourself

```bash
uv run pre-commit install         # installs the git hook (one-time per clone)
uv run pre-commit run --all-files # run every hook against the whole repo right now
```

**Expected output:** each hook prints `Passed`, `Failed`, or `Skipped`. On first run some
formatting/whitespace hooks may modify files and report `Failed` — re-staging and re-running
should then pass. After `install`, the same checks run automatically each time you `git commit`.

---

## 0.8 The shared utilities in `common/utils/`

Two small but foundational files every later phase relies on.

### `paths.py` — one source of truth for locations and config

```python
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]   # walk up 3 levels: utils -> common -> root

DATA_DIR      = PROJECT_ROOT / "data"
RAW_DATA_DIR  = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
MODEL_DIR     = ARTIFACTS_DIR / "models"
# ...etc for metrics, reports, services, common...
```

**Why this exists — and why it's important.** Notice `PROJECT_ROOT` is derived from
`__file__` (the location of *this* source file), **not** from the current working directory.
This means paths are correct no matter *where* you launch a script from — VS Code's run button,
a terminal in a subfolder, or a Docker container. Relative paths like `../data` are the #1 cause
of "FileNotFoundError that only happens sometimes"; anchoring to `__file__` eliminates that whole
class of bug.

The same file also centralizes **project configuration** as plain dictionaries:

```python
API_CONFIG = {                      # where to fetch the dataset from
    "dataset_url": "https://www.data.gouv.fr/api/1/datasets/",
    "dataset_slug": "bases-de-donnees-annuelles-des-accidents-corporels-...",
}
DATA_PROCESSING_CONFIG = {
    "years": [2021, 2022, 2023, 2024],
    "exclusive_test_year": 2024,    # 2024 held out as unseen data
    "test_size": 0.3,
    "random_state": 42,
    "normalize": True,
}
MODEL_CONFIG = {
    "model_name": "model",
    "model_parameters": {"random_state": 42, "n_estimators": 200, "n_jobs": -1},
    "top_n_features": 20,
}
```

Keeping these as constants (instead of magic numbers scattered through the code) means you can
change "train on which years?" or "how many trees?" in exactly one place, and every stage picks
it up. `random_state = 42` everywhere is the reproducibility habit again — same seed, same split,
same result.

### `asp_logging.py` — consistent logging

```python
def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:          # guard: don't attach duplicate handlers on re-import
        return logger
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
```

Every module calls `get_logger(__name__)` and gets the same timestamped format. Two details a
beginner should note: using **`logging` instead of `print`** gives you levels (INFO/WARNING/
ERROR) and is the professional norm; and the **`if logger.handlers: return`** guard prevents the
classic bug where re-importing a module stacks up duplicate handlers and every line prints twice.

---

## 0.9 The Git collaboration workflow

From the README, the team rule is explicit: **never commit directly to `main`.**

The intended flow:

```bash
git checkout develop          # the integration branch
git pull                      # get latest
git checkout -b feature/my-change   # your own branch off develop
# ...work, commit...
git push -u origin feature/my-change
# then open a Pull Request into develop
```

The remote branches confirm this is how the team actually worked:

```
main                                   # protected, release-quality
develop                                # integration branch
feature/dvc-init-data-versioning       # one branch per unit of work
feature/ml-explore-dataset
feature/mlflow-add-experiment-tracking
bugfix/dvc-github-repos-access-permissions
...
```

Every merge into `develop`/`main` goes through a **Pull Request**, and the repo ships a PR
template (`.github/pull_request_template.md`) that pre-fills a checklist:

```
## Summary
Describe your changes.
## Checklist
- [ ] Code builds successfully
- [ ] Tests pass
- [ ] Documentation updated (if needed)
```

**Why this matters:** the branch-per-feature + PR model means `main` is always deployable, every
change is reviewed, and CI (Phase 6) runs on the PR *before* code merges. Combined with
pre-commit (local gate) and GitHub Actions (server gate), you get *two* independent safety nets.

---

## 0.10 Phase 0 checkpoint

You understand Phase 0 when you can explain, in your own words:

- Why the code is split into `common/` (a reusable library) and `services/` (deployable units).
- Why `data/` and `artifacts/` folders are committed but their contents are not.
- What `uv sync --all-groups` does, and why dependencies are split into groups.
- The difference between `pyproject.toml` (what you want) and `uv.lock` (exactly what you got).
- How Ruff, mypy, pytest, and pre-commit each contribute to keeping quality high automatically.
- Why `PROJECT_ROOT = Path(__file__).resolve().parents[2]` is more robust than `../data`.
- The branch-per-feature → Pull Request Git workflow.

**A minimal end-to-end dry run** (safe; installs env and runs the checks — no data needed):

```bash
uv python pin 3.12
uv sync --all-groups
uv run pre-commit install
uv run ruff check .
uv run mypy common services
uv run pytest        # note: some tests may skip if data/models aren't present yet — that's expected
```

If those run and pass (or cleanly skip data-dependent tests), your foundation is solid.

---

### Next up — Phase 1: Data Acquisition & DVC Pipeline

We'll cover *why* Git alone can't version datasets, how DVC solves it, how the three
`dvc.yaml` stages (`download_data → make_dataset → train`) chain together, and how the DagsHub
remote stores the actual data and models. Say the word and I'll write it.
