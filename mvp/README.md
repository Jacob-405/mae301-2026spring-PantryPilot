
# PantryPilot MVP Workspace

This folder contains the MVP app entrypoint, local data directories, and reproducibility documentation for PantryPilot.

## Workspace layout

- `app.py`: Streamlit app entrypoint
- `data/raw/`: manually placed local raw recipe files
- `data/processed/`: processed planner-ready recipe exports and import stats
- `report.md`: MVP report scaffold for the course deliverable

## Environment setup

PantryPilot assumes Python 3.12 and Windows PowerShell.

1. Create and activate a virtual environment.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Place raw data

Copy local raw recipe files into [raw](C:/Users/Legom/mae301-2026spring-PantryPilot/mvp/data/raw).

Supported input formats:

- JSON with either a top-level recipe list or `{ "recipes": [...] }`
- CSV with JSON-encoded `ingredients` and `instructions` columns

Example input file:

- [example_recipes.json](C:/Users/Legom/mae301-2026spring-PantryPilot/mvp/data/raw/example_recipes.json)

## Run the import pipeline

Import one local raw file into the processed dataset format:

```powershell
.\.venv\Scripts\python.exe -m pantry_pilot.data_pipeline.cli mvp/data/raw/example_recipes.json
```

Optional output path:

```powershell
.\.venv\Scripts\python.exe -m pantry_pilot.data_pipeline.cli mvp/data/raw/example_recipes.json --processed-path mvp/data/processed/recipes.imported.json
```

Generic importer outputs:

- `mvp/data/processed/recipes.imported.json`
- `mvp/data/processed/recipes.imported.stats.json`

Current main offline dataset:

- `mvp/data/processed/recipenlg-full-20260416T0625Z.json`
- `mvp/data/processed/recipenlg-full-20260416T0625Z.stats.json`
- `mvp/data/processed/recipenlg-full-20260416T0625Z.checkpoint.json`

RecipeNLG full import command used for the current main dataset:

```powershell
.\.venv\Scripts\python.exe -m pantry_pilot.data_pipeline.cli mvp/data/raw/recipenlg/RecipeNLG_dataset.csv --recipenlg --processed-path mvp/data/processed/recipenlg-full-20260416T0625Z.json --max-output-recipes 3000000 --progress-every 100000 --checkpoint-every 100000
```

The stats file summarizes:

- raw row count
- accepted row count
- rejected row count
- common rejection reasons

## Launch the app

```powershell
.\.venv\Scripts\python.exe -m streamlit run mvp/app.py
```

The app will:

- prefer `mvp/data/processed/recipenlg-full-20260416T0625Z.json` when a valid processed dataset is present
- fall back to the built-in curated sample dataset otherwise

## Run tests

Run all tests:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run only importer and dataset tests:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_phase10_import_pipeline tests.test_phase11_deduplication tests.test_phase2_providers -v
```

## Notes for the MVP demo

- The planner remains deterministic for the same settings.
- Unknown or incomplete allergen metadata is treated as unsafe.
- Grocery pricing still falls back to the local mock provider when store pricing is unavailable.
- The processed dataset integration is conservative: invalid processed files cleanly fall back to the built-in sample dataset.
- For long RecipeNLG runs in this environment, use a direct attached `.\.venv\Scripts\python.exe ...` invocation rather than `Start-Process`.
