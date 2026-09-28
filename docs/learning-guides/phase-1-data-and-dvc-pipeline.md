# Phase 1 — Data Acquisition & DVC Pipeline

> **Goal of this phase:** understand how the project gets its data and — more importantly —
> how it *versions* that data and the whole pipeline that transforms it. You'll learn why Git
> alone is the wrong tool for datasets and models, what DVC adds, how the DagsHub remote stores
> the heavy files, how the three-stage pipeline in `dvc.yaml` chains together, and how to
> reproduce the entire flow with a single command.

In Phase 0 we set up the workshop. Phase 1 is where raw material enters the workshop — and
where we put a **serial number on every version of it** so results are always reproducible.

---

## 1.1 What & Why — the problem DVC solves

Machine learning has a versioning problem that ordinary software doesn't.

- Code is small and text-based. Git is perfect for it: it stores every version, shows diffs,
  merges branches.
- **Data and models are large and binary.** A dataset can be hundreds of MB or many GB. A
  trained model here is ~6 GB (see `dvc.lock`). Git was never designed for this — commit a few
  versions of a big binary file and your `.git` folder balloons, clones take forever, and diffs
  are meaningless.

But you *still need* to version data and models, because in ML **"the code" is not enough to
reproduce a result.** The same script on different data gives a different model. To reproduce an
experiment you must pin down *three* things together: the **code**, the **data**, and the
**parameters**.

**DVC (Data Version Control)** is the answer. The elegant core idea:

> Keep the *big files* in cheap remote storage (S3, DagsHub, Google Drive…), and keep only tiny
> *text pointers* to them in Git.

So Git tracks a small file that says "the dataset at this commit is the blob with MD5
`7a5dd7…`", and DVC knows how to fetch that exact blob from the remote. You get Git-like
versioning of huge files, without bloating Git. The pointer and the code live together in the
same commit, so `git checkout <old-commit>` + `dvc checkout` gives you the *exact* data that
went with that code.

---

## 1.2 How DVC is wired up in this repo

DVC was initialized with `dvc init`, which created the `.dvc/` folder. Two files matter:

### `.dvc/config` — where the big files live (the "remote")

```ini
[core]
    remote = origin
['remote "origin"']
    url = s3://dvc
    endpointurl = https://dagshub.com/Rackkoun/accident-severity-predictor.s3
```

Read this as: "there is a remote named **origin**; it speaks the **S3** protocol; the bucket is
`dvc`; and instead of Amazon, the S3 endpoint is **DagsHub**." DagsHub is a GitHub-for-ML host
that gives every repo a free S3-compatible bucket — that's where the actual CSVs and model
files are stored. `remote = origin` makes it the default, so `dvc push`/`dvc pull` use it
without you naming it each time.

> **Terminology note:** this DVC remote is *also* called `origin`, which is a coincidence of
> naming with the Git remote `origin`. They are two different things: Git's `origin` points to
> the DagsHub *git* repo; DVC's `origin` points to the DagsHub *S3 bucket*. Same host, different
> storage.

### `.dvc/.gitignore` — keeping secrets and cache out of Git

```
/config.local
/tmp
/cache
```

- **`config.local`** holds your *credentials* (access key + secret) and is git-ignored so
  secrets never get committed. The shared `config` holds only non-secret info (the URL).
- **`cache`** is DVC's local content-addressable store (the actual file blobs on your machine).
  It's ignored because it's large and reconstructable from the remote.

### Credentials — `docs/dvc_setup.md`

The project documents how a new developer connects to the remote:

```bash
git clone https://dagshub.com/Rackkoun/accident-severity-predictor.git
cd accident-severity-predictor

cp .env.example .env          # copy the environment template
uv sync --all-groups          # install deps (includes dvc[s3])

uv run dvc pull               # download the current data + model versions

# point DVC at your DagsHub token (stored LOCALLY, not committed)
dvc remote modify origin --local access_key_id  <token>
dvc remote modify origin --local secret_access_key <token>
```

The `--local` flag writes to `.dvc/config.local` (the git-ignored one), so your token stays on
your machine. This is the standard, safe pattern: **shared config in Git, secrets local only.**

> To actually pull the real data you need a DagsHub account with access to the Rackkoun repo and
> a token. You don't need this to *read and understand* the code — but you do if you want to run
> the real training on real data. If you don't have access, you can still study the scripts and
> even run the downloader against the public data.gouv.fr API (it's open).

---

## 1.3 The DVC pipeline — `dvc.yaml`

This is the centerpiece of the phase. `dvc.yaml` describes the data pipeline as a series of
**stages**, and DVC turns them into a dependency graph (a DAG) it can reproduce intelligently.

Here is the full file, which we'll dissect:

```yaml
stages:
  download_data:
    cmd: uv run python -m common.data.download_data
    deps:
      - common/data/download_data.py
      - common/utils/paths.py
    outs:
      - data/raw/:
          cache: true

  make_dataset:
    cmd: mkdir -p data/processed && uv run python -m common.data.make_dataset
    deps:
      - common/data/make_dataset.py
      - common/utils/paths.py
      - data/raw/
    outs:
      - data/processed/:
          cache: true

  train:
    cmd: uv run python -m services.training.train
    deps:
      - services/training/train.py
      - common/utils/paths.py
      - data/processed/
    outs:
      - artifacts/models/:    { cache: true, persist: true }
      - artifacts/metrics/:   { cache: true, persist: true }
      - artifacts/reports/:   { cache: true, persist: true }
```

Every stage has the same three-part anatomy:

- **`cmd`** — the shell command that *does* the work.
- **`deps`** — the *inputs*: files that, if they change, mean this stage must re-run.
- **`outs`** — the *outputs*: files this stage produces, which DVC will version and cache.

### The dependency graph (DAG)

Notice how the `outs` of one stage become the `deps` of the next:

```
   download_data                 make_dataset                    train
 ┌───────────────┐             ┌───────────────┐             ┌───────────────────────┐
 │ cmd: download │  data/raw/  │ cmd: make_    │  data/      │ cmd: train            │
 │               │────────────▶│      dataset  │  processed/ │                       │
 │ outs:         │  (out→dep)  │ outs:         │────────────▶│ outs: models/,        │
 │  data/raw/    │             │  data/        │  (out→dep)  │       metrics/,       │
 └───────────────┘             │  processed/   │             │       reports/        │
                               └───────────────┘             └───────────────────────┘
```

DVC reads these links and builds the arrows automatically. You can see it yourself:

```bash
uv run dvc dag        # prints an ASCII diagram of the pipeline
```

**Why this is powerful — smart re-runs.** Because DVC knows the graph *and* fingerprints
(MD5-hashes) every dep and out, `dvc repro` only re-runs what actually needs re-running:

- Change `make_dataset.py`? DVC re-runs `make_dataset` **and** `train` (downstream), but **skips**
  `download_data` (its inputs didn't change — no need to re-download 130 MB).
- Change nothing? `dvc repro` does nothing and tells you everything is up to date.

This is the same principle as `make`, but content-aware and extended to data. On a real project
this saves enormous amounts of time and compute.

### `cache: true` and `persist: true`

- **`cache: true`** (all outputs) — DVC stores the output in its cache and can push it to the
  remote. This is what makes the output *versioned and shareable*.
- **`persist: true`** (only the `train` outputs) — tells DVC *not to delete* the existing output
  before re-running the stage. Normally DVC clears an out before regenerating it; `persist`
  keeps prior models/metrics/reports around (useful when you want to accumulate or compare
  artifacts rather than wipe them each run).

### The `mkdir -p data/processed &&` in `make_dataset`

A small but instructive detail: the command ensures the output directory exists before the
Python script writes to it. `data/processed/`'s *contents* are git-ignored (Phase 0), so on a
fresh clone the folder might not exist yet. `mkdir -p` ("make parents, no error if it already
exists") is a defensive one-liner so the stage never fails on a clean machine.

---

## 1.4 `dvc.lock` — the fingerprint record

When you run the pipeline, DVC writes `dvc.lock` — the machine-generated "receipt" that records
the exact hash and size of every dep and out for each stage. A slice:

```yaml
  download_data:
    cmd: uv run python -m common.data.download_data
    deps:
    - path: common/data/download_data.py
      md5: 19eaf2c56b9646349559731e386ab827
      size: 2150
    outs:
    - path: data/raw/
      md5: 7a5dd7dd0e8cb18a912c5e37ae281547.dir
      size: 131546316          # ~131 MB
      nfiles: 16               # 16 CSV files
```

From the real lock file we can read actual facts about this project's data:

- **`data/raw/`** — 16 files, ~131 MB (the yearly BAAC CSVs).
- **`data/processed/`** — 4 files, ~145 MB (the cleaned/merged tables).
- **`artifacts/models/`** — 21 files, **~6 GB** (the trained model + supporting objects). This is
  the perfect illustration of *why Git can't do this* and DVC must.

`dvc.lock` is **committed to Git** (it's small text). It, together with the code, is what pins a
reproducible state: the lock says "this run used `data/raw/` with hash `7a5dd7…`", and DVC can
fetch exactly that from the remote. `git checkout <commit>` + `dvc checkout` = time travel to
the exact data+model of that commit.

---

## 1.5 Guided read — `common/data/download_data.py`

This is the script behind the `download_data` stage. It fetches the raw BAAC CSVs from the French
open-data portal **data.gouv.fr**. Let's read it in four parts.

**(a) Imports & config**

```python
import requests
from common.data.check_structure import file_exists
from common.utils.asp_logging import get_logger
from common.utils.paths import API_CONFIG, DATA_PROCESSING_CONFIG, RAW_DATA_DIR

logger = get_logger(__name__)
```

Everything it needs comes from the `common` package we met in Phase 0: the dataset URL/slug
(`API_CONFIG`), which years to fetch (`DATA_PROCESSING_CONFIG`), and where to save
(`RAW_DATA_DIR`). No hard-coded paths or URLs — all centralized.

**(b) The function signature — sensible defaults**

```python
def download_raw_data(
        year: int = 2021,
        dataset_api: str = API_CONFIG["dataset_url"],
        dataset_slug: str = API_CONFIG["dataset_slug"],
        output_dir: str | Path = RAW_DATA_DIR,
        overwrite: bool = False,
) -> list[Path]:
```

Fully type-hinted (mypy will insist — Phase 0). Defaults come from config, so calling
`download_raw_data(year=2022)` "just works." `overwrite=False` means it won't re-download files
it already has (see part d).

**(c) Ask the data.gouv.fr API for the dataset's file list**

```python
dataset_url = dataset_api + dataset_slug
output_dir = Path(output_dir)
output_dir.mkdir(parents=True, exist_ok=True)         # ensure target folder exists

logger.info(f"Fetching dataset metadata from {dataset_url}...")
response = requests.get(dataset_url)
if response.status_code != 200:
    raise Exception(f"Download dataset failed with status code ({response.status_code})")

dataset = response.json()
resources = dataset["resources"]                       # the list of downloadable files
```

data.gouv.fr exposes a REST API. Hitting the dataset URL returns JSON *metadata* — importantly a
`resources` list where each entry describes one downloadable file (its `title` and `url`). The
code fails loudly (`raise`) if the API doesn't return HTTP 200, so problems surface immediately
rather than silently producing an empty dataset.

**(d) Filter to the files we want, then stream them to disk**

```python
for resource in resources:
    title = resource.get("title", "")
    url   = resource.get("url", "")

    # keep only: a .csv, whose name contains the requested year, and is NOT a "baac" bundle
    if not title.endswith(".csv") or str(year) not in title or "baac" in title:
        continue

    output_path = output_dir / title
    if file_exists(output_path) and not overwrite:      # idempotent: skip what we already have
        logger.info(f"File already exists, skipping: {output_path}")
        output_paths.append(output_path)
        continue

    logger.info(f"Downloading {title}...")
    with requests.get(url, stream=True) as req:         # stream = don't load whole file in memory
        req.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in req.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
```

Three professional touches worth calling out:

1. **The filter** `not title.endswith(".csv") or str(year) not in title or "baac" in title`.
   The BAAC dataset publishes many files per year (the four tables — characteristics, places,
   vehicles, users — plus bundled/aggregated "baac" files). This keeps only the per-year CSVs
   and explicitly *excludes* the pre-bundled `baac` file, because this project wants the raw
   component tables so it can merge them itself (Phase 2).
2. **Idempotency** — `file_exists(...) and not overwrite` means re-running the script doesn't
   re-download files you already have. Safe to run repeatedly; only fetches what's missing.
3. **Streaming download** — `stream=True` + `iter_content(chunk_size=8192)` writes the file in
   8 KB chunks instead of loading the entire (large) CSV into RAM. Essential for big files.

**(e) The entry point**

```python
if __name__ == "__main__":
    for year in DATA_PROCESSING_CONFIG["years"]:        # [2021, 2022, 2023, 2024]
        download_raw_data(year=year)
    logger.info("Download completed!")
```

Running the module downloads every configured year. This block is exactly what the DVC stage
calls: `uv run python -m common.data.download_data`. (The `-m` flag runs it as a *module* so the
`common...` imports resolve from the repo root.)

> The 2024 data is downloaded but, per the project's design, **2024 is treated as held-out /
> future data** — a common practice so you have genuinely unseen data to test drift and
> generalization on later. You'll see that decision echoed in `DATA_PROCESSING_CONFIG`
> (`exclusive_test_year: 2024`).

---

## 1.6 Reproduce it yourself

There are two paths depending on whether you have DagsHub access.

### Path A — you have DagsHub credentials (full reproduction)

```bash
# one-time: connect your token (writes to .dvc/config.local, git-ignored)
uv run dvc remote modify origin --local access_key_id     <YOUR_TOKEN>
uv run dvc remote modify origin --local secret_access_key <YOUR_TOKEN>

uv run dvc status        # compare local state vs dvc.lock — shows what's changed
uv run dvc pull          # download data/ + artifacts/ from the DagsHub remote
uv run dvc dag           # visualize the pipeline graph
uv run dvc repro         # run only the stages whose inputs changed
uv run dvc push          # upload any new outputs back to the remote
```

**Expected output:**
- `dvc pull` → progress bars, then something like `A  data/raw/`, `A  artifacts/models/`, and
  `M files fetched`.
- `dvc repro` on an unchanged repo → `Stage 'download_data' didn't change, skipping` for each
  stage, ending "Data and pipelines are up to date."
- `dvc status` when clean → `Data and pipelines are up to date.`

### Path B — no DagsHub access (study the downloader against the open API)

You can still exercise the acquisition logic, because data.gouv.fr is public:

```bash
# fetch just one year into data/raw/ using the project's own function
uv run python -c "from common.data.download_data import download_raw_data; download_raw_data(year=2023)"

ls -lh data/raw/          # you should see per-year CSVs appear (characteristics, places, vehicles, users)
```

**Expected output:** log lines `Fetching dataset metadata...`, `Downloading <file>.csv...`, and a
handful of CSV files in `data/raw/`. You won't have the processed data or the 6 GB model (those
come from `dvc pull`), but you'll have proven the downloader works and seen the raw shape of the
data.

> Reminder from Phase 0: don't try to `git add` these CSVs — `data/raw/` contents are
> git-ignored on purpose and belong to DVC.

---

## 1.7 The mental model to keep

```
                 Git (small, text)                DVC remote = DagsHub S3 (big, binary)
      ┌───────────────────────────────┐        ┌────────────────────────────────────────┐
      │ code (*.py)                    │        │ data/raw/      (~131 MB, 16 files)       │
      │ dvc.yaml   (pipeline recipe)   │◀─pins─▶│ data/processed/(~145 MB, 4 files)        │
      │ dvc.lock   (fingerprints)      │        │ artifacts/models/ (~6 GB, 21 files)      │
      │ .dvc/config(remote address)    │        │ artifacts/metrics|reports/               │
      └───────────────────────────────┘        └────────────────────────────────────────┘
                 committed & reviewed                    fetched via dvc pull / push
```

- **Git** answers "what code and *which version* of the data/model?"
- **DVC + DagsHub** answers "give me the actual bytes for that version."
- **`dvc.yaml`** answers "how do I rebuild everything from scratch, running only what's needed?"

---

## 1.8 Phase 1 checkpoint

You understand Phase 1 when you can explain:

- Why Git is unsuitable for datasets and models, and how DVC's "pointer in Git, blob in remote"
  model fixes it.
- What the DagsHub S3 remote is and how `.dvc/config` vs `.dvc/config.local` split public
  address from private credentials.
- The three stages in `dvc.yaml`, how each stage's `outs` feed the next stage's `deps`, and why
  that lets `dvc repro` skip unchanged stages.
- What `dvc.lock` records and why it's committed while the data isn't.
- How `download_data.py` queries the data.gouv.fr API, filters to the right yearly CSVs (and why
  it excludes "baac" bundles), and streams them to disk idempotently.
- The commands: `dvc pull`, `dvc push`, `dvc repro`, `dvc dag`, `dvc status`.

---

### Next up — Phase 2: Data Processing Modules

We'll open the `common/data/` package and follow the raw CSVs through **cleaning, merging, and
dataset assembly** (`check_structure`, `clean_data`, `merge_data`, `dataset_io`,
`make_dataset`), and read the unit tests in `common/tests/` that guard each step. That's where
the four BAAC tables become one model-ready dataset. Say **"Phase 2"** when you're ready.
