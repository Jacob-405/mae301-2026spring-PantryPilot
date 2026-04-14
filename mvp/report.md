# PantryPilot MVP Report

## Executive Summary

PantryPilot is a deterministic weekly meal-planning MVP built in Streamlit. The current system accepts budget, servings, dietary constraints, pantry staples, calorie targets, and variety preferences, then generates a 7-day meal plan with a shopping list and package-based cost estimate. The MVP now supports a local-first recipe data pipeline that can import manually provided raw recipe files, normalize them into a planner-ready format, cluster duplicates, and load processed datasets into the app when available.

## User & Use Case

Primary user:

- a student or household planner who wants a safe, budget-aware weekly meal plan

Core use case:

- enter preferences and constraints
- generate a deterministic weekly plan
- review shopping list and estimated cost
- reuse favorites or regenerate individual meals

Key user requirements currently supported:

- allergy-aware filtering
- pantry subtraction
- budget compliance
- calorie-aware planning
- variety controls and leftovers mode

## System Design

High-level components:

- Streamlit app: [app.py](C:/Users/Legom/mae301-2026spring-PantryPilot/mvp/app.py)
- planner and runtime models: `pantry_pilot/models.py`, `pantry_pilot/planner.py`
- grocery providers and fallback logic: `pantry_pilot/providers.py`
- built-in sample dataset: `pantry_pilot/sample_data.py`
- local data pipeline:
  - schema and validation: `pantry_pilot/data_pipeline/schema.py`, `pantry_pilot/data_pipeline/validation.py`
  - offline import: `pantry_pilot/data_pipeline/importer.py`
  - duplicate clustering: `pantry_pilot/data_pipeline/similarity.py`
  - ingredient normalization backbone: `pantry_pilot/ingredient_catalog.py`

Current runtime behavior:

- the app prefers a valid processed dataset in `mvp/data/processed/recipes.imported.json`
- otherwise it falls back to the built-in curated sample dataset

## Data

### Source(s)

Current sources in the repo:

- built-in handcrafted fallback recipes in `pantry_pilot/sample_data.py`
- manually placed local raw files under `mvp/data/raw/`

The MVP is local-first and does not require runtime recipe APIs.

### Size

Current shipped fallback dataset:

- a small curated recipe set embedded in code for reliable fallback behavior

Imported dataset size:

- determined by the raw local files supplied by the user
- summarized by `mvp/data/processed/recipes.imported.stats.json` after running the importer

Suggested fields to record for demos:

- raw row count
- accepted row count
- rejected row count
- top reject reasons

### Cleaning

Current cleaning and normalization steps:

- normalize ingredient aliases to canonical names
- normalize units conservatively
- reject rows with missing ingredients or instructions
- reject rows with too many unmapped ingredients
- reject rows with unusable units for mapped ingredients
- reject rows with unknown or incomplete allergen completeness
- derive diversity metadata
- cluster exact and near-duplicate recipes

### Processing stages

1. Raw local file placed in `mvp/data/raw/`
2. Offline import into normalized `NormalizedRecipe` records
3. Validation and row rejection
4. Diversity metadata enrichment
5. Exact/near-duplicate clustering
6. Processed export to `mvp/data/processed/recipes.imported.json`
7. Stats export to `mvp/data/processed/recipes.imported.stats.json`
8. App loads processed dataset if valid, else falls back to built-in sample data

### Splits

The current MVP does not use train/validation/test splits because the planner is rule-based and deterministic rather than ML-trained.

## Models / Planner Logic Actually Used

PantryPilot currently uses deterministic planning logic, not a trained predictive model.

Implemented planning logic includes:

- hard safety filters for allergens, excluded ingredients, diets, cuisine, and prep time
- package-based budget estimation
- pantry-aware shopping list aggregation
- calorie-target penalties
- variety penalties and leftovers incentives
- meal structure handling
- meal replacement using the same deterministic scoring framework

## Evaluation

Current evaluation approach:

- unit tests for allergy filtering
- shopping-list aggregation tests
- budget compliance tests
- pricing fallback tests
- schema and import validation tests
- duplicate and near-duplicate clustering tests
- determinism tests for planning and replacement behavior

Recommended demo evidence:

- show the processed stats file after import
- run the app with and without a processed dataset present
- demonstrate that unsafe processed recipes remain filtered out

## Limitations & Risks

- the processed dataset loader is conservative and rejects malformed records by falling back entirely to the sample dataset
- ingredient and unit coverage is limited to the current catalog
- duplicate detection is explainable but intentionally simple
- imported datasets still depend on high-quality local raw files
- the planner is rule-based and may not reflect personal taste beyond the provided constraints
- real store pricing depends on optional credentials and provider availability

## Next Steps

- broaden ingredient catalog coverage for larger local datasets
- support multiple processed dataset files or batches
- add richer import reporting in the UI
- use similarity cluster metadata to strengthen planner-level variety decisions
- add curated benchmark scenarios for instructor demos
- expand documentation with a concrete dataset summary once the final local dataset is chosen
