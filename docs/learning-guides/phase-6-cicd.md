# Phase 6 — CI/CD (GitHub Actions)

> **Goal of this phase:** read the four GitHub Actions workflows in `.github/workflows/` and see
> how the project enforces quality **automatically on the server**, every push and pull request.
> You'll learn how the local pre-commit gates from Phase 0 get re-run in CI (defense in depth), how
> one orchestrator workflow chains three reusable ones in sequence, how the container images from
> Phase 5 are built and smoke-tested, and how the DagsHub/DVC secrets are injected safely.

CI/CD = **Continuous Integration / Continuous Delivery.** In plain terms: a robot that, on every
code change, checks out your branch, installs everything, and runs your quality checks — so bugs
are caught *before* they merge, not after. This project's CI is a small, clean example of the real
thing.

---

## 6.1 What & Why — two gates, not one

Recall Phase 0: **pre-commit** runs Ruff, mypy, and pytest on your machine before a commit is
created. So why run the same checks again in CI?

Because a *local* gate can be bypassed — a developer can skip hooks (`git commit --no-verify`),
have a misconfigured environment, or simply not install pre-commit. The **server-side** gate can't
be skipped: it runs on GitHub's runners, on a clean machine, for everyone, every time. The two
together are **defense in depth**:

```
   developer laptop                          GitHub servers
   ┌────────────────┐   git push / PR   ┌───────────────────────────┐
   │ pre-commit      │ ────────────────▶ │ GitHub Actions workflows  │
   │ (Phase 0 gate)  │                   │ (this phase's gate)       │
   │ can be skipped  │                   │ cannot be skipped         │
   └────────────────┘                    └───────────────────────────┘
```

The four workflow files divide the work:

| File | Role |
|------|------|
| `asp-ci.yaml` | **Orchestrator** — the entry point; triggers on push/PR and calls the other three in order |
| `asp-code-quality.yaml` | Reusable job — Ruff lint + Ruff format check + mypy |
| `asp-test-suite.yaml` | Reusable job — pytest with the coverage gate; uploads coverage reports |
| `asp-container-build.yaml` | Reusable job — build both Docker images, smoke-test, integration-test the backend |

---

## 6.2 `asp-ci.yaml` — the orchestrator

```yaml
name: 🚀 Accident Severity Predictor (ASP) CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  code-quality:
    uses: ./.github/workflows/asp-code-quality.yaml

  test-suite:
    needs: code-quality
    uses: ./.github/workflows/asp-test-suite.yaml

  container-build:
    needs: test-suite
    uses: ./.github/workflows/asp-container-build.yaml
    secrets:
      AWS_ACCESS_KEY_ID:     ${{ secrets.AWS_ACCESS_KEY_ID }}
      AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

Small file, three big ideas:

- **Triggers (`on:`)** — this pipeline runs on every **push to `main`/`develop`** and on every
  **pull request** targeting them. That's precisely the Git workflow from Phase 0: feature branch →
  PR into `develop` → CI runs on the PR *before* it can merge. So `main`/`develop` stay green.
- **Reusable workflows (`uses: ./...`)** — instead of one giant file, the real work lives in three
  separate, reusable workflows, and this orchestrator just *calls* them. This is the same
  "compose small pieces" philosophy as the code (routers, services). Each sub-workflow can also be
  run or reasoned about on its own.
- **Sequential gating (`needs:`)** — the jobs form a chain: `code-quality` → `test-suite` →
  `container-build`. `needs: code-quality` means test-suite only starts *if* code-quality passed;
  `needs: test-suite` gates the container build. This **fails fast and cheap**: if Ruff finds a
  lint error in seconds, CI stops there and never spends minutes building Docker images. Order the
  cheap checks first.

**Secrets flow down explicitly.** Only the last job needs cloud credentials (to `dvc pull`), so the
orchestrator passes `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` *only* into `container-build`. These
are GitHub repository **Secrets** — encrypted values set in the repo settings, never written in the
code. (Despite the `AWS_` names, recall from Phase 1 that DVC talks S3 to **DagsHub**; DagsHub
issues S3-style access keys, so the standard AWS env-var names are reused.)

---

## 6.3 `asp-code-quality.yaml` — the linting gate

```yaml
on:
  workflow_call:            # ← "I'm a reusable workflow, called by another workflow"

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4                 # 1) get the code
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }          # 2) the pinned interpreter
      - uses: astral-sh/setup-uv@v3
        with: { version: "latest", enable-cache: true }   # 3) install uv (with dependency caching)
      - run: uv sync --group dev --group backend --group training   # 4) install deps
      - run: uv run ruff check .                   # 5) lint
      - run: uv run ruff format --check .          # 6) formatting (check only, don't modify)
      - run: uv run mypy common/ services/         # 7) types
```

Read the steps as a recipe any CI job follows: **checkout → set up tools → install → run checks.**
Points worth noting:

- **`on: workflow_call`** marks this as a *reusable* workflow — it doesn't trigger on its own; it
  runs only when `asp-ci.yaml` calls it. That's what lets the orchestrator compose it.
- **`runs-on: ubuntu-latest`** — a fresh, clean Ubuntu VM each run. No leftover state; a true
  from-scratch check.
- **`setup-uv ... enable-cache: true`** — caches the resolved packages between runs keyed off
  `uv.lock`, so installs are fast when dependencies haven't changed. Same layer-caching instinct as
  the Dockerfiles (Phase 5), applied to CI.
- **The checks mirror pre-commit exactly** — `ruff check`, `ruff format --check` (note `--check`:
  in CI you *verify* formatting and fail if it's off, you don't silently rewrite files), and
  `mypy common/ services/`. If any step exits non-zero, the job fails red and the chain stops.

---

## 6.4 `asp-test-suite.yaml` — the testing gate

```yaml
on: { workflow_call: }
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - uses: astral-sh/setup-uv@v3
        with: { version: "latest", enable-cache: true }
      - run: uv sync --group dev --group backend --group training
      - run: uv run pytest                          # runs ALL tests + the 80% coverage gate

      - uses: actions/upload-artifact@v4            # save the HTML coverage report...
        if: always()
        with: { name: coverage-report, path: htmlcov/, if-no-files-found: ignore }
      - uses: actions/upload-artifact@v4            # ...and the XML one
        if: always()
        with: { name: coverage-xml, path: coverage.xml, if-no-files-found: ignore }
```

- **`uv run pytest`** runs the whole suite you've met across Phases 2–4 (common, training, backend —
  ~90 tests total). Because `pyproject.toml` set `--cov-fail-under=80` (Phase 0), **CI fails if
  coverage drops below 80%.** The quality bar is enforced by the machine, not by reviewers'
  goodwill.
- **`upload-artifact` with `if: always()`** — after the run (even if tests *failed*, thanks to
  `always()`), the `htmlcov/` and `coverage.xml` reports are uploaded and downloadable from the
  GitHub Actions run page. So when CI goes red you can open the coverage report and see exactly
  what's uncovered — the failure comes with evidence. `if-no-files-found: ignore` keeps it from
  erroring if a report wasn't produced.

> Remember from Phase 2–4 that many tests use `skipif` guards or synthetic data, so the suite runs
> green in CI *without* real data or a DagsHub token — an important design choice that keeps this
> gate fast and credential-free.

---

## 6.5 `asp-container-build.yaml` — build, smoke, integrate

The most involved workflow. It proves the Phase 5 images actually build and run. Two clever pieces:
a **build matrix** and a **layered testing strategy**.

### The matrix — build both images with one job definition

```yaml
on:
  workflow_call:
    secrets:
      AWS_ACCESS_KEY_ID:     { required: true }
      AWS_SECRET_ACCESS_KEY: { required: true }

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        service: [training, backend]
        include:
          - service: training
            dockerfile: services/training/Dockerfile.training
            image: asp-training:latest
            smoke_cmd: 'python -c "import services.training.train; print(\"OK\")"'
          - service: backend
            dockerfile: services/backend/Dockerfile.backend
            image: asp-backend:latest
            smoke_cmd: 'python -c "import services.backend.src.main; print(\"OK\")"'
```

A **matrix** runs the same job once per entry — here once for `training`, once for `backend`, **in
parallel**. The `include:` block attaches per-service values (which Dockerfile, image tag, smoke
command). One job definition, two builds, no duplication. Add a third service later and it's one
more matrix entry.

### The steps — pull data, build, then test in layers

```yaml
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5

      - name: 🚚 Pull ML Model from DagsHub (S3)
        env:
          AWS_ACCESS_KEY_ID:     ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: uv run dvc pull                       # bring in data/ + artifacts/ (incl. a model)

      - uses: docker/setup-buildx-action@v3        # modern Docker builder
      - name: 🐳 Build image
        run: docker build -f ${{ matrix.dockerfile }} -t ${{ matrix.image }} .
```

Note the **`dvc pull` step**: this is where the Phase 1 secrets come in. CI authenticates to
DagsHub with the injected keys and pulls the versioned data + model, so the built backend image can
actually load a real model for the integration test below. This closes the loop — DVC (Phase 1) and
the containers (Phase 5) meeting in CI.

Then three **increasing levels of confidence**:

**Level 1 — Smoke test (both images):**

```yaml
      - name: 🔥 Smoke test
        run: docker run --rm --entrypoint uv ${{ matrix.image }} run --no-sync ${{ matrix.smoke_cmd }}
```

The cheapest possible check: start the image and just *import the main module* (`import
services...; print("OK")`). It answers "does the image even load our code without an ImportError?"
in a second. Overriding `--entrypoint uv` runs the import instead of the container's normal job.

**Level 2 — Integration test (backend only):**

```yaml
      - name: 🏥 Integration test (backend)
        if: matrix.service == 'backend'
        run: |
          set -euo pipefail
          docker run -d --name asp-backend-test -p 8000:8000 \
            -v "$(pwd)/data:/app/data" -v "$(pwd)/artifacts:/app/artifacts" \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -e HOST_DATA_DIR="$(pwd)/data" -e HOST_ARTIFACTS_DIR="$(pwd)/artifacts" \
            ${{ matrix.image }}
          # ...wait, print status + logs...
          if [ "$(docker inspect -f '{{.State.Running}}' asp-backend-test)" != "true" ]; then
            echo "❌ Container crashed before health check!"; docker logs asp-backend-test; exit 1
          fi
          for i in {1..12}; do                     # retry health for up to ~36s
            if curl -sf http://localhost:8000/api/v1/health; then
              echo "✅ Health check passed!"; docker stop asp-backend-test && docker rm asp-backend-test; exit 0
            fi
            sleep 3
          done
          echo "❌ Health check failed after 12 attempts"; docker logs --tail 50 asp-backend-test; exit 1
```

This actually **runs the backend container exactly as Phase 5's compose would** — same volume
mounts, same socket mount, same `HOST_*` env vars — and then hits `/api/v1/health` until it
responds. It proves the built image doesn't just *import*, it *boots and serves*. Several marks of
a well-written CI script here:

- **`set -euo pipefail`** — bash strict mode: exit on any error, on undefined variables, and on a
  failure anywhere in a pipe. Without it, a failing command mid-script can be silently ignored.
- **A crash check before health** — it inspects `.State.Running` and dumps full logs if the
  container died on boot, so a startup crash gives you the logs immediately instead of a confusing
  "connection refused."
- **Retry with backoff** — 12 attempts × 3s. Servers take a moment to start; a single immediate
  curl would flake. Retrying is the correct pattern for "wait until ready."
- **Cleanup on both paths** — it stops/removes the test container whether the check passes or fails,
  leaving no debris on the runner.

**Level 3** would be end-to-end/deployment — this project stops at build + smoke + integration,
which is a sensible scope for a course/team project (the "CD/deploy" half is intentionally light).

---

## 6.6 How it all chains — the full CI run

```
  push to develop  (or PR into main/develop)
        │
        ▼
  ┌─ asp-ci.yaml (orchestrator) ─────────────────────────────────────────────┐
  │                                                                            │
  │  code-quality  ──needs──▶  test-suite  ──needs──▶  container-build         │
  │  ruff + mypy               pytest + 80% cov        matrix: [training,       │
  │  (seconds)                 (+ upload reports)      backend]                 │
  │                                                    dvc pull → build →       │
  │                                                    smoke → integration      │
  │  fail here → stop          fail here → stop        (secrets injected here)  │
  └────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
   all green → safe to merge ;  any red → PR blocked, with logs + coverage artifacts
```

Cheap checks first, expensive checks last, each gating the next. That ordering is the single most
important design decision in the whole pipeline.

---

## 6.7 Reproduce it yourself

CI runs on GitHub's servers, but you can reproduce **every check locally** — that's the point of
using the same `uv` commands everywhere.

```bash
# The code-quality job, locally:
uv run ruff check .
uv run ruff format --check .
uv run mypy common/ services/

# The test-suite job, locally:
uv run pytest                       # includes the 80% coverage gate

# The container-build smoke tests, locally (needs Docker):
docker build -f services/training/Dockerfile.training -t asp-training:latest .
docker run --rm --entrypoint uv asp-training:latest run --no-sync python -c "import services.training.train; print('OK')"

docker build -f services/backend/Dockerfile.backend -t asp-backend:latest .
docker run --rm --entrypoint uv asp-backend:latest run --no-sync python -c "import services.backend.src.main; print('OK')"
```

**Expected output:** the ruff/mypy/pytest commands behave exactly as they will in CI (green =
merge-safe). The smoke tests print `OK` if the images build and import cleanly.

### Watching it run for real

If you have push access to the repo: create a feature branch, make a trivial change, push, and open
a PR into `develop`. On the PR's **Checks** tab you'll see the three jobs run in sequence. Click any
job to read its step-by-step logs; if `test-suite` runs, download the **coverage-report** artifact
from the run summary. Introduce a deliberate lint error (e.g. an unused import) and watch
`code-quality` fail *and stop the chain* before test-suite ever starts — the "fail fast" design in
action.

> To run the full container-build job (with `dvc pull`) you need the DagsHub `AWS_ACCESS_KEY_ID` /
> `AWS_SECRET_ACCESS_KEY` set as repository **Secrets** (Settings → Secrets and variables →
> Actions). Without them, the code-quality and test-suite jobs still run fine — only the
> data-dependent container job needs credentials.

---

## 6.8 Phase 6 checkpoint

You understand Phase 6 when you can explain:

- Why CI re-runs the same checks as pre-commit (server-side gate that *can't* be skipped — defense
  in depth).
- What triggers the pipeline (`push`/`pull_request` to `main`/`develop`) and how that matches the
  Phase 0 branch→PR workflow.
- What a **reusable workflow** (`on: workflow_call`, `uses: ./...`) is and why the orchestrator
  pattern beats one giant file.
- How **`needs:`** creates a fail-fast sequential chain, and why cheap checks (lint) go before
  expensive ones (container build).
- How the code-quality and test-suite jobs mirror local commands, including `ruff format --check`
  (verify, don't rewrite) and the `--cov-fail-under=80` gate.
- Why coverage reports are uploaded with `if: always()`.
- The **build matrix** (both images from one job) and the **three testing levels** — smoke (import),
  integration (boot + `/health` with retries), and why level-3 deploy is intentionally out of scope.
- How **repository Secrets** flow only into the container-build job so `dvc pull` can authenticate
  to DagsHub — tying Phase 1's DVC to Phase 5's containers inside CI.
- The bash-hygiene touches: `set -euo pipefail`, crash-check-before-health, retry-with-backoff,
  cleanup-on-all-paths.

---

### Next up — Phase 7: Frontend & Wrap-up

The final phase. We'll look at the `services/frontend/` Streamlit scaffold (what's there, what's
intended, and how it would call the backend `/predict`), then step all the way back for a full
end-to-end recap: how data → DVC → processing → training → API → containers → CI fit together as one
system, the design principles that recur throughout, and a consolidated list of the improvements
we flagged along the way (chief among them the train/serve scaling fix from Phase 4). Say
**"Phase 7"** when you're ready to finish.
