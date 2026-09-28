# Phase 2 — Data Processing Modules

> **Goal of this phase:** follow the raw BAAC CSVs all the way to a clean, model-ready
> train/test dataset. You'll read the whole `common/data/` package — the filesystem helpers,
> the CSV readers, the per-table cleaners, the merge/split/feature logic, and the
> `make_dataset` orchestrator that ties them together — plus the 56 unit tests that guard
> every step. This is the `make_dataset` stage from Phase 1's pipeline, opened up.

This is the longest phase because it is where **domain knowledge lives**. Anyone can call
`model.fit()`; the real work — and the real bugs — are in turning messy government CSVs into
honest features. Read it slowly.

---

## 2.1 What & Why — from 4 raw tables to 1 dataset

The French BAAC dataset publishes accident data as **four separate tables per year**, each a
semicolon-separated CSV:

| French name | Code used in repo | Contents | One row per… |
|-------------|-------------------|----------|--------------|
| `usagers` | `usa` | people involved (victims), incl. the **target** `grav` (severity) | person |
| `vehicules` | `veh` | vehicles involved | vehicle |
| `caracteristiques` | `car` | accident circumstances (time, weather, location) | accident |
| `lieux` | `lie` | the road/place | accident |

They are linked by a shared key, **`Num_Acc`** (accident number), plus `id_vehicule`/`num_veh`
to connect a person to their vehicle. The job of `common/data/` is to:

1. **Clean** each table (fix quirks, recode values, engineer a few features).
2. **Merge** the four into one wide table with **one row per accident**.
3. **Split** into train/test (holding out 2024 as unseen).
4. **Impute** features — *fitting only on the training data* (this is the single most
   important correctness rule in the whole phase).
5. **Save** `X_train / X_test / y_train / y_test` as CSVs into `data/processed/`.

The module map:

```
make_dataset.py          ← the ORCHESTRATOR (runs the whole flow; this is the DVC stage entry)
├── check_structure.py   ← filesystem helpers (exists? create dir?)
├── dataset_io.py        ← read CSVs (raw=';'  processed=',')
├── clean_data.py        ← per-table cleaning + feature engineering
└── merge_data.py        ← collect paths, merge, split, impute, save
```

Everything is **plain functions** (no classes, no global state) — easy to test, easy to reason
about, and matching the beginner-friendly, heavily-commented style of the repo.

---

## 2.2 `check_structure.py` — filesystem helpers

Small, boring, and used everywhere. Four functions:

```python
def dir_exists(dir_path)  -> bool: return Path(dir_path).is_dir()
def file_exists(file_path)-> bool: return Path(file_path).is_file()

def create_dir(dir_path) -> bool:
    """create dir if missing; return True if it was actually created, False if it existed."""
    dir_path = Path(dir_path)
    if dir_path.exists():
        return False
    dir_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created directory: {dir_path}")
    return True

def ensure_directories(dirs) -> int:
    """create any missing dirs, return how many were created."""
    created = 0
    for d in dirs:
        if create_dir(d):
            created += 1
    return created
```

**Why bother wrapping `Path`?** Two reasons. First, intent: `file_exists(p)` reads better than
`Path(p).is_file()` scattered around. Second, the **return-value contract** — `create_dir`
returns `True`/`False` so callers (and tests) can tell whether it *did* something. That's why
`download_data` (Phase 1) could ask `file_exists(...)` to stay idempotent. These are the kind of
tiny, well-tested primitives that keep the rest of the code clean.

---

## 2.3 `dataset_io.py` — reading CSVs

```python
def load_raw_csv(path) -> pd.DataFrame:
    return pd.read_csv(path, sep=";", low_memory=False)   # raw BAAC files are ';'-separated

def load_processed_csv(path) -> pd.DataFrame:
    return pd.read_csv(path)                               # our processed files are ','-separated
```

A deceptively important detail: **raw BAAC CSVs use `;` as the separator** (common in
European/French data, because commas are decimal separators there). Forget the `sep=";"` and
pandas reads the whole line as one giant column — a classic first-day bug. The processed files
this project *writes* use the normal comma, so they read with plain `pd.read_csv`.

`low_memory=False` tells pandas to read the whole column before guessing its type, avoiding
mixed-type warnings on these large, irregular files.

---

## 2.4 `clean_data.py` — per-table cleaning (the domain logic)

This is where raw quirks get fixed and a few features get engineered. Two shared helpers first,
then one function per table.

### Shared helpers

```python
def correct_id_anomaly(df):
    """fix the 2022 quirk where the accident key was renamed 'Accident_Id'."""
    if df.get("Accident_Id", None) is not None:
        df["Num_Acc"] = df.Accident_Id
        df = df.drop(columns=["Accident_Id"])
    return df

def clean_object_columns(df):
    """strip non-breaking spaces (\\xa0) and surrounding whitespace from text columns."""
    obj_cols = df.select_dtypes(include=["object", "str"]).columns
    df[obj_cols] = df[obj_cols].apply(lambda s: s.str.replace("\xa0", "", regex=False).str.strip())
    return df
```

Two real-world data problems:

- **The 2022 schema change.** In 2022 the government renamed the key column from `Num_Acc` to
  `Accident_Id`. Without `correct_id_anomaly`, the 2022 tables wouldn't join to the others. This
  is a perfect example of why you *never* trust a multi-year dataset to be consistent.
- **Non-breaking spaces (`\xa0`).** Exported spreadsheets often contain these invisible
  characters. `"75 "` vs `"75"` vs `"75\xa0"` look identical but compare as different — and would
  silently break groupings and joins. Stripping them up front prevents hours of confusion.

### `process_users` — the table with the target

```python
def process_users(df):
    df = correct_id_anomaly(df)
    df = clean_object_columns(df)

    # TARGET remap: raw grav is 1=Unharmed, 2=Killed, 3=Injured(hospitalized), 4=Lightly injured
    #   -> binary:   0 = Unharmed or Lightly injured   |   1 = Hospitalized or Killed
    df["grav"] = df["grav"].replace([1, 2, 3, 4], [0, 1, 1, 0])

    # engineered feature: victim age = accident year - birth year
    df["year_acc"]   = df["Num_Acc"].astype(str).str[:4].astype(int)  # first 4 digits of key = year
    df["victim_age"] = df["year_acc"] - df["an_nais"]
    df.loc[(df["victim_age"] > 120) | (df["victim_age"] < 0), "victim_age"] = np.nan  # kill impossible ages
    df = df.drop(columns=["an_nais"])

    # engineered feature: how many victims in this accident
    nb_victim = df.groupby("Num_Acc").size().rename("nb_victim")
    df = df.merge(nb_victim, on="Num_Acc", how="inner")
    return df
```

Three things a data scientist should internalize here:

1. **The problem was reframed as binary classification.** The raw 4-level severity is collapsed
   to *serious (1) vs not-serious (0)*. That's a modeling decision with consequences: it makes
   the target more balanced and the business question ("is this a serious accident?") sharper,
   but throws away the killed-vs-hospitalized distinction. (Worth noting: your own parallel build
   kept 4 ordinal classes — same dataset, different framing. Neither is "wrong"; they answer
   different questions.)
2. **`year_acc` is decoded from the key itself** — the first four characters of `Num_Acc` are the
   year. Clever, and it means age can be computed without a separate date column.
3. **Guardrails on engineered features** — ages `>120` or `<0` become `NaN` rather than being
   trusted. Real data has data-entry errors; a mature pipeline neutralizes them instead of
   feeding "age = 221" to a model.

### `process_vehicles` — collapsing a 40-category variable

```python
def process_vehicles(df):
    df = correct_id_anomaly(df); df = clean_object_columns(df)
    catv_value     = [0,1,2,3,4,5,6,7,8,...,99]     # ~40 raw vehicle-category codes
    catv_value_new = [0,1,1,2,1,1,6,2,5,...,0]      # mapped down to ~7 meaningful groups
    df["catv"] = df["catv"].replace(catv_value, catv_value_new)
    nb_vehicles = df.groupby("Num_Acc").size().rename("nb_vehicles")
    df = df.merge(nb_vehicles, on="Num_Acc", how="inner")
    return df
```

The raw `catv` (vehicle category) has ~40 codes — many rare or historical. Modeling on 40 sparse
categories is noisy; the project **hand-maps them into ~7 semantically meaningful groups**
(cars, two-wheelers, heavy vehicles, etc.). This is *domain-driven feature engineering* — you
need to know what the codes mean to group them sensibly. It also derives `nb_vehicles` per
accident (a proxy for collision complexity).

### `process_characteristics` — time, geography, weather

```python
def process_characteristics(df):
    df = correct_id_anomaly(df); df = clean_object_columns(df)

    # Corsica: departments "2A"/"2B" aren't numeric -> recode to 201/202 so the column can be Int
    df["dep"] = df["dep"].str.replace("2A", "201").str.replace("2B", "202")
    df["com"] = df["com"].str.replace("2A", "201").str.replace("2B", "202")

    df["hour"] = df["hrmn"].astype(str).str[:-3]        # "08:30" -> "08"  (keep the hour only)
    df = df.drop(columns=["hrmn", "an"])

    cols = ["dep", "com", "hour"]
    df[cols] = df[cols].apply(pd.to_numeric, errors="coerce").astype("Int64")  # nullable int

    df["lat"]  = df["lat"].str.replace(",", ".").astype(float)   # French decimals "48,85" -> 48.85
    df["long"] = df["long"].str.replace(",", ".").astype(float)

    weather_map = {1:0, 2:1,3:1,4:1,5:1,6:1,7:1, 8:0,9:0}   # normal(0) vs adverse(1) weather
    df["atm"] = df["atm"].replace(weather_map)
    return df
```

A cluster of very French data-cleaning realities, each worth remembering:

- **Corsica's `2A`/`2B`** department codes are the only non-numeric ones; recoding to `201`/`202`
  lets the column stay a clean integer.
- **French decimal commas** — `"48,8566"` must become `"48.8566"` before `float()`.
- **`hour` from `hrmn`** — dropping minutes keeps a low-cardinality, model-friendly hour feature.
- **Weather binarized** — 9 raw `atm` codes collapsed to normal/adverse. Same simplification
  philosophy as `catv` and the target.
- **`Int64`** (capital I) is pandas' *nullable* integer type, so a column can hold both integers
  and `NaN` — ordinary numpy `int` can't.

### `process_places`

```python
def process_places(df):
    df = correct_id_anomaly(df)
    df = clean_object_columns(df)
    return df
```

Minimal — the `lieux` table mostly needs the shared cleanups. Its columns get filtered later in
the merge step's `DROP_COLS`.

---

## 2.5 `merge_data.py` — join, split, and prepare features

This module has the most consequential logic. Read each function with care.

### Collecting file paths

```python
def collect_raw_data_paths(raw_data_dir):
    """index the raw CSVs as files[table][year] = Path, e.g. files['usa'][2021]."""
    files = defaultdict(dict)
    for file_path in raw_data_dir.glob("*.csv"):
        table = file_path.stem[:3].lower()   # 'usagers-2021' -> 'usa'
        year  = int(file_path.stem[-4:])     # '...-2021'      -> 2021
        files[table][year] = file_path
    return files
```

It reads filenames to build a two-level lookup: the first 3 letters identify the table
(`usa/veh/car/lie`) and the last 4 characters the year. So downstream code can ask for exactly
`files["car"][2023]`.

### Merging the four tables — one row per accident

```python
def merge_datasets(df_users, df_veh, df_places, df_caract):
    fusion1 = df_users.merge(df_veh, on=["Num_Acc", "num_veh", "id_vehicule"], how="inner")
    fusion1 = fusion1.sort_values(by="grav", ascending=False)      # most-severe victim first
    fusion1 = fusion1.drop_duplicates(subset=["Num_Acc"], keep="first")  # keep 1 row/accident
    fusion2 = fusion1.merge(df_places,  on="Num_Acc", how="left")
    df      = fusion2.merge(df_caract, on="Num_Acc", how="left")
    return df
```

This is the crux of the whole dataset design, and it encodes a real modeling decision:

- Users join to vehicles on person+vehicle keys (`inner` — keep only matched rows).
- Then it **sorts by `grav` descending and keeps the first row per `Num_Acc`.** Because an
  accident can involve several people with different severities, this collapses each accident to
  **its single most-severe outcome**. In other words: *"predict whether this accident produced a
  serious casualty."* That's a deliberate, defensible choice — and one you must know about to
  interpret the model.
- Places and characteristics join with `left` (keep every accident even if its place/characteristic
  row is missing).

The tests pin this behavior down exactly (`test_merge_deduplicates_by_severity`: accident 1 has
victims with grav 0 and 1 → the merged row keeps grav = 1).

### Sentinels → NaN, and dropping columns

```python
REPLACE_MINUS1_NA_COLS = ["trajet","secu1","catv","obsm","motor","circ","surf","situ","vma","atm","col"]
REPLACE_0_NA_COLS      = ["trajet","catv","motor"]
DROP_COLS              = ["senc","larrout","actp","manv","choc","nbv", "Num_Acc","id_vehicule",...]  # 30 cols

def process_merged_dataset(df):
    df[REPLACE_MINUS1_NA_COLS] = df[REPLACE_MINUS1_NA_COLS].replace(-1, np.nan)  # -1 = "not specified"
    df[REPLACE_0_NA_COLS]      = df[REPLACE_0_NA_COLS].replace(0, np.nan)        # 0  = "not applicable"
    df = df.drop(columns=DROP_COLS)
    return df
```

In BAAC coding, **`-1` means "not filled in" and (for some columns) `0` means "not applicable."**
Left as-is, a model would treat `-1` as a real number smaller than all valid codes — nonsense.
Converting them to `NaN` marks them as genuinely missing so the imputer (next step) can handle
them properly. `DROP_COLS` removes identifiers (`Num_Acc`, `id_vehicule` — keys, not features)
and columns judged unhelpful/too-sparse. This is where the wide merged table is trimmed to a
modeling feature set.

### Splitting — the leakage-free temporal holdout

```python
def split_data(df_collection, exclusive_test_year=None, test_size=0.3, random_state=42):
    if exclusive_test_year:                       # e.g. 2024
        train = pd.concat([df for year, df in df_collection.items() if year != exclusive_test_year],
                          ignore_index=True)
        X_train, y_train = train.drop(columns=["grav"]), train["grav"]
        test = df_collection[exclusive_test_year]
        X_test,  y_test  = test.drop(columns=["grav"]),  test["grav"]
    else:
        df = pd.concat(df_collection.values(), ignore_index=True)
        X, y = df.drop(columns=["grav"]), df["grav"]
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=random_state)
    return X_train, X_test, y_train, y_test
```

Two split *strategies*, selected by whether `exclusive_test_year` is set:

- **Temporal holdout (the configured default, 2024):** train on 2021–2023, test on **2024** —
  data the model has never seen and that comes from the *future* relative to training. This is the
  gold standard for evaluating whether a model will work on next year's accidents, and it mirrors
  reality (you always predict the future from the past). It also sidesteps leakage from having two
  people in the same accident land in both train and test.
- **Random split (fallback):** ordinary `train_test_split` with a fixed `random_state=42` for
  reproducibility, used only if no exclusive year is given.

### Feature preparation — impute only, **fit on train only**

```python
def process_features(X_train, X_test):
    cat_cols = [c for c in CAT_COLS if c in X_train.columns]
    num_cols = [c for c in X_train.columns if c not in cat_cols]

    median_imputer = SimpleImputer(strategy="median")          # numeric NaNs -> column median
    mode_imputer   = SimpleImputer(strategy="most_frequent")   # categorical NaNs -> column mode

    X_train[num_cols] = median_imputer.fit_transform(X_train[num_cols])  # FIT + transform on train
    X_test[num_cols]  = median_imputer.transform(X_test[num_cols])       # transform test w/ train stats

    X_train[cat_cols] = mode_imputer.fit_transform(X_train[cat_cols])
    X_test[cat_cols]  = mode_imputer.transform(X_test[cat_cols])

    return X_train, X_test
```

> **Update — feature scaling was removed.** An earlier version of this function also applied a
> `StandardScaler` (behind a `normalize=True` flag). That was **removed** (PR "Removed feature
> normalization"): the features are the model's own integer category codes and a few counts, and the
> tree-based model doesn't need them scaled — scaling only obscured them and complicated serving.
> So `process_features` now **only imputes missing values**; there is no scaler and no `normalize`
> flag (the `DATA_PROCESSING_CONFIG["normalize"]` key is gone too).

**This is still the most important correctness detail in the data pipeline — read it twice.**

Notice the asymmetry: every imputer is `.fit_transform(...)` on **train** but only
`.transform(...)` on **test**. The median and the mode are learned **from the training data only**,
then *applied* to the test data.

Why it matters: if you computed the median or mode over the *combined* data, information from the
test set would leak into training, and your test score would be optimistically biased — the model
would look better than it really is. Fitting on train and transforming test is exactly how you'd
have to operate in production (you can't peek at future data), so it gives an *honest* estimate of
real-world performance. Getting this wrong is one of the most common — and most invisible — mistakes
in applied ML. This code gets it right.

> **One thing to keep in your back pocket for Phase 4:** the fitted `imputer` objects are *not saved
> here* — `process_features` fits them, uses them, and lets them go, saving only the already-imputed
> CSVs. That's fine for producing a training dataset. (With scaling now removed, the serving side has
> one fewer transformer to reproduce for a brand-new incoming accident.)

### Saving

```python
def save_datasets(X_train, X_test, y_train, y_test, processed_data_dir):
    for df, filename in zip([X_train, X_test, y_train, y_test], ["X_train","X_test","y_train","y_test"]):
        df.to_csv(processed_data_dir / f"{filename}.csv", index=False)
```

Four CSVs written to `data/processed/` — matching the "4 files, ~145 MB" we saw in Phase 1's
`dvc.lock`. `index=False` avoids writing pandas' row numbers as a phantom column.

---

## 2.6 `make_dataset.py` — the orchestrator

This is the entry point the DVC `make_dataset` stage runs. It wires the pieces together.

### Idempotency guard

```python
PROCESSED_FILES = ["X_train.csv","X_test.csv","y_train.csv","y_test.csv"]

def processed_data_exists(processed_data_dir):
    return all(file_exists(processed_data_dir / f) for f in PROCESSED_FILES)
```

Same "don't redo finished work" philosophy as the downloader. If all four outputs already exist
and you didn't pass `overwrite=True`, the whole stage short-circuits.

### Per-year assembly

```python
def process_yearly_data(raw_path_collection, year):
    df_users  = process_users(load_raw_csv(raw_path_collection["usa"][year]))   # (raises FileNotFoundError if missing)
    df_veh    = process_vehicles(load_raw_csv(raw_path_collection["veh"][year]))
    df_caract = process_characteristics(load_raw_csv(raw_path_collection["car"][year]))
    df_places = process_places(load_raw_csv(raw_path_collection["lie"][year]))
    df = merge_datasets(df_users, df_veh, df_places, df_caract)
    df = process_merged_dataset(df)
    return df
```

For one year: load each of the four raw CSVs, clean each, merge, apply sentinel/drop processing.
Each table is checked and raises a clear `FileNotFoundError` (e.g. *"Missing usagers dataset for
2022"*) if absent — fail fast with a message you can act on.

### The full flow

```python
def process_data(years=[2021,2022,2023,2024], exclusive_test_year=2024, ..., overwrite=False):
    if processed_data_exists(processed_data_dir) and not overwrite:
        logger.info("Processed data already exists, skipping."); return

    raw_paths = collect_raw_data_paths(raw_data_dir)
    df_years = {year: process_yearly_data(raw_paths, year) for year in years}     # clean+merge each year

    X_train, X_test, y_train, y_test = split_data(df_years, exclusive_test_year=exclusive_test_year, ...)
    X_train, X_test = process_features(X_train, X_test)       # impute only (train-fit)
    save_datasets(X_train, X_test, y_train, y_test, processed_data_dir)

if __name__ == "__main__":
    process_data()          # <- what `python -m common.data.make_dataset` runs
```

Read top to bottom, it's the whole story: guard → collect paths → clean+merge every year →
split (2024 held out) → impute (fit on train) → save four CSVs. Every default comes from
`DATA_PROCESSING_CONFIG` in `paths.py`, so the pipeline's behavior is controlled from that one
config dictionary.

---

## 2.7 The tests in `common/tests/` (56 tests)

Every module above has a matching test file. This is what lets the team refactor fearlessly and
what keeps CI's 80% coverage gate satisfied. The counts:

| Test file | Tests | What it protects |
|-----------|------:|------------------|
| `test_check_structure.py` | 12 | dir/file existence, `create_dir` return contract, nested creation |
| `test_clean_data.py` | 14 | target remap, age + outlier handling, `catv` mapping, Corsica recode, weather, `\xa0` stripping |
| `test_merge_data.py` | 10 | path collection, merge dedup-by-severity, sentinel→NaN, both split modes, imputation |
| `test_dataset_io.py` | 5 | `;` vs `,` reading, `FileNotFoundError` on missing files |
| `test_download_data.py` | 4 | API filtering, skip-existing, API-failure, skip non-csv/baac (Phase 1 code) |
| `test_paths.py` | 11 | `PROJECT_ROOT` absolute, config sanity (years are ints, 0<test_size<1, etc.) |

Two testing techniques worth studying because you'll reuse them constantly:

**1. `tmp_path` — real files in a throwaway folder.** pytest's built-in `tmp_path` fixture hands
each test a fresh temporary directory. So `test_create_dir_nested` actually creates
`tmp_path/a/b/c` on disk and checks it exists — a real filesystem test that cleans itself up and
never touches your project. The cleaning tests build tiny in-memory DataFrames (fixtures like
`users_df`) with just the columns under test and assert the exact transformed values, e.g.:

```python
def test_process_users_gravity_mapping(users_df):
    result = process_users(users_df)
    assert list(result["grav"]) == [0, 1, 1]     # raw [1,2,3] -> binary [0,1,1]
```

**2. Mocking the network — `test_download_data.py`.** Unit tests must never actually hit the
internet (slow, flaky, and it'd hammer a public API). So the download tests **patch**
`requests.get` with a `MagicMock` that returns a canned API response, then assert the *filtering
logic* behaves — that 2021 CSVs download, wrong-year/`baac`/`.pdf` files are skipped, existing
files are skipped, and a 404 raises. This isolates *your* code from *their* server. Learning to
mock external dependencies is a core professional testing skill, and this file is a clean example.

---

## 2.8 Reproduce it yourself

### If you have the raw data (from `dvc pull`, or downloaded via Phase 1)

```bash
# run the whole make_dataset stage directly
uv run python -m common.data.make_dataset
ls -lh data/processed/          # expect X_train.csv, X_test.csv, y_train.csv, y_test.csv
```

**Expected output:** log lines *"Processing years: [2021, 2022, 2023, 2024]"*, one *"Processing
dataset <year>"* per year, then *"Splitting… Processing features… Saving… Dataset preprocessing
completed."* — and four CSVs appear. Re-running prints *"Processed data already exists,
skipping."* (the idempotency guard). To force a rebuild: run it from Python with
`process_data(overwrite=True)`.

### Always available — run the tests (no data needed)

```bash
uv run pytest common/tests -v
```

**Expected output:** ~56 tests, all `PASSED`, plus a coverage table. These use synthetic
fixtures and `tmp_path`, so they run anywhere in seconds — a great way to *watch the cleaning
logic behave* without downloading a single real CSV. To see one module in isolation:

```bash
uv run pytest common/tests/test_clean_data.py -v
```

### Explore interactively (recommended for learning)

Open a Python REPL and step through one table:

```python
from common.data.dataset_io import load_raw_csv
from common.data.clean_data import process_users
df = load_raw_csv("data/raw/usagers-2023.csv")   # needs the raw file present
clean = process_users(df)
print(clean[["grav", "victim_age", "nb_victim"]].head())
print(clean["grav"].value_counts())              # see the 0/1 target balance
```

---

## 2.9 Phase 2 checkpoint

You understand Phase 2 when you can explain:

- The four BAAC tables, the `Num_Acc` join key, and why raw CSVs need `sep=";"`.
- Why `correct_id_anomaly` and `\xa0` stripping exist (real multi-year data inconsistencies).
- How the target `grav` was reframed to binary, and how `victim_age` / `nb_victim` / `nb_vehicles`
  are engineered (and guarded against impossible values).
- Why `catv` and `atm` are collapsed into fewer categories (domain-driven simplification).
- What `merge_datasets` does with `sort_values(grav)` + `drop_duplicates` — one most-severe row
  per accident — and why that defines the prediction task.
- Why `-1`/`0` become `NaN` before imputation.
- **The leakage rule:** the imputers are `fit` on train and only `transform` test —
  and why fitting on combined data would give a dishonest score. (Feature scaling was removed, so
  the imputers are now the only fitted transformers.)
- Why 2024 is held out as a temporal test set.
- How `make_dataset.process_data` orchestrates the whole flow, and how `tmp_path` + `requests`
  mocking make the modules testable without disk or network.

**Open question we're carrying into later phases:** the fitted imputers aren't persisted
here — so we'll need to see how the serving path handles a live input. (Now that scaling is gone,
there's no scaler to reproduce — one fewer moving part on the serving side.)

---

### Next up — Phase 3: Training Service

We move from `common/` into `services/training/`. We'll read `train_model.py` and
`evaluate_model.py`, see how `MODEL_CONFIG` drives training, what artifacts (model, metrics,
reports) get produced into `artifacts/`, and how `services/training/train.py` — the entry point
for the DVC `train` stage — ties it together. Say **"Phase 3"** when you're ready.
