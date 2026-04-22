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

- the app prefers the validated full RecipeNLG dataset in `mvp/data/processed/recipenlg-full-20260416T0625Z.json`
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

- current main offline dataset: `mvp/data/processed/recipenlg-full-20260416T0625Z.json`
- summarized by `mvp/data/processed/recipenlg-full-20260416T0625Z.stats.json`
- verified counts:
  - raw row count: `2231142`
  - accepted row count: `23021`
  - written row count: `23021`
  - rejected row count: `2208121`

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
6. Processed export to a deterministic processed JSON dataset
7. Stats export to a matching processed stats JSON file
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

Current reproducible evidence in the repo:

- full RecipeNLG import artifacts:
  - `mvp/data/processed/recipenlg-full-20260416T0625Z.json`
  - `mvp/data/processed/recipenlg-full-20260416T0625Z.stats.json`
  - `mvp/data/processed/recipenlg-full-20260416T0625Z.checkpoint.json`
- planner fix log with phase-by-phase findings and verification:
  - `docs/recipe_planner_fix_plan.md`
- fast regression suite:
  - `tests/test_phase6_regressions.py`

Suggested instructor verification commands:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_phase6_regressions
```

```powershell
.\.venv\Scripts\python.exe -c "from pantry_pilot.app_runtime import build_plan_snapshot; from pantry_pilot.models import PlannerRequest; snapshot = build_plan_snapshot(PlannerRequest(weekly_budget=140.0, servings=2, cuisine_preferences=(), allergies=(), excluded_ingredients=(), diet_restrictions=(), pantry_staples=(), max_prep_time_minutes=35, meals_per_day=1, meal_structure=('dinner',), pricing_mode='mock', daily_calorie_target_min=800, daily_calorie_target_max=1200, variety_preference='balanced', leftovers_mode='off')); print('meals', len(snapshot.plan.meals)); print('cost', snapshot.plan.estimated_total_cost); print('unknown_costs', sum(item.estimated_cost is None for item in snapshot.plan.shopping_list))"
```

Current verified outcomes from those checks:

- the planner uses the full processed RecipeNLG dataset by default
- unknown metadata is preserved as unknown rather than collapsing to zero
- calorie target and weekly budget materially affect selection in targeted regression tests
- known bad sauce/dip/relish titles are excluded from meal slots in regression coverage
- a calorie-constrained weekly dinner plan can now complete on the real RecipeNLG dataset with priced shopping-list items

Recommended demo evidence:

- show the processed stats file after import
- run the app with and without a processed dataset present
- demonstrate that unsafe processed recipes remain filtered out
- show that the app now defaults to the validated full RecipeNLG dataset

## Limitations & Risks

- the processed dataset loader is conservative and rejects malformed records by falling back entirely to the sample dataset
- ingredient and unit coverage is limited to the current catalog
- duplicate detection is explainable but intentionally simple
- imported datasets still depend on high-quality local raw files
- the planner is rule-based and may not reflect personal taste beyond the provided constraints
- real store pricing depends on optional credentials and provider availability

## Final Acceptance

Frozen demo/runtime files:

- `mvp/data/processed/recipenlg-full-20260416T0625Z.json`
- `pantry_pilot/data/usda_nutrition_pilot_manifest.json`
- `pantry_pilot/data/usda_nutrition_pilot_mappings.json`
- `pantry_pilot/data/usda_nutrition_pilot_records.json`
- `pantry_pilot/data/usda_meal_guidance_tags.json`

Reproducible acceptance commands:

```powershell
.\.venv\Scripts\python.exe -m pantry_pilot.acceptance --scenario balanced_week --json
.\.venv\Scripts\python.exe -m pantry_pilot.acceptance --scenario tight_budget --json
.\.venv\Scripts\python.exe -m pantry_pilot.acceptance --scenario carryover_reuse --json
.\.venv\Scripts\python.exe -m pantry_pilot.acceptance --scenario allergy_constrained --json
```

Verified final scenario outcomes:

- `balanced_week`
  - `PASS`
  - `meal_count=12`
  - `estimated_total_cost=56.1`
- `tight_budget`
  - `PASS`
  - `meal_count=12`
  - `estimated_total_cost=17.0`
  - `remaining_budget=28.0`
- `carryover_reuse`
  - `PASS`
  - `carryover_inventory_count_after_week1=6`
  - `second_week_carryover_used_items=6`
  - `second_week_reduced_purchase_items=4`
- `allergy_constrained`
  - `PASS`
  - `meal_count=12`
  - `forbidden_allergen_hits=[]`

Final frozen runtime snapshot:

- `active_recipe_source=processed-dataset`
- `recipe_fallback_active=false`
- `total_recipes=23021`
- `nutrition_recipe_count=22196`
- `priced_recipe_count=21444`
- `nutrition_unknown_count=825`
- `price_unknown_count=1577`
- `weak_main_count=7293`
- `usda_mapped_ingredient_count=24`
- `guidance_mapping_count=35`

Current known limitations remain:

- some recipe nutrition and pricing values are still partial
- balanced-meal guidance is scoring-based, not medical advice
- RecipeNLG role inference is still imperfect on some titles
- demo acceptance is frozen on the local mock-pricing path rather than a live store provider

## Next Steps

- broaden ingredient catalog coverage for larger local datasets
- support multiple processed dataset files or batches
- add richer import reporting in the UI
- use similarity cluster metadata to strengthen planner-level variety decisions
- add curated benchmark scenarios for instructor demos
- optionally replace the timestamped RecipeNLG dataset path with a stable alias once the team wants a non-versioned default filename

## MAE301 Deliverable Check

Present in the repo:

- `/mvp/` app code and workspace
- `/mvp/README.md` demo and setup instructions
- `/mvp/report.md` project report
- data source and preprocessing documentation in `mvp/README.md`, `mvp/data/README.md`, and `pantry_pilot/data_pipeline/`
- evaluation evidence in `tests/test_phase6_regressions.py` and `docs/recipe_planner_fix_plan.md`
- limitations, risks, and next steps in this report

Remaining gap list after this audit:

- no major MVP deliverable is missing
- the main remaining cleanup is presentation-oriented rather than structural:
  - optionally prune or ignore old generated processed artifacts before final submission packaging
  - optionally replace the timestamped main dataset filename with a stable alias if the course submission format prefers one
