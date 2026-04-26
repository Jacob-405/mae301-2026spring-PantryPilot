# PantryPilot Runtime Data Contract

## Goal

Define the exact local data and support files PantryPilot uses at planner runtime, the allowed fallback behavior, and the audit path used to confirm the website is reading the intended runtime state.

## Active Runtime Contract

### Recipe Corpus

- Active default recipe corpus path:
  - `mvp/data/processed/recipenlg-full-20260416T0625Z.json`
- Active runtime source in the normal path:
  - processed RecipeNLG dataset
- Allowed fallback:
  - `pantry_pilot/sample_data.py`
- Fallback rule:
  - sample fallback is only allowed when the processed dataset path is missing, unreadable, malformed, or yields no valid recipes
- Expected normal behavior:
  - fallback must be inactive in normal operation

### Nutrition Support

- Active local nutrition manifest:
  - `pantry_pilot/data/usda_nutrition_manifest.json`
- Active local nutrition mappings:
  - `pantry_pilot/data/usda_nutrition_mappings.json`
- Active local nutrition records:
  - `pantry_pilot/data/usda_nutrition_records.json`
- Active unresolved / ambiguous mapping report:
  - `pantry_pilot/data/usda_nutrition_unresolved.json`
- Runtime rule:
  - planner-time nutrition lookups stay local and file-backed
  - no USDA API calls at planner runtime
- Honest unknown rule:
  - unmapped or weakly mapped ingredients remain unknown
- Build rule:
  - raw USDA FoodData Central snapshots are handled offline through `python -m pantry_pilot.usda_build`
  - runtime never reads the raw USDA snapshots directly

### Guidance Support

- Active local guidance file:
  - `pantry_pilot/data/usda_meal_guidance_tags.json`
- Runtime rule:
  - guidance is local and deterministic
  - guidance is soft scoring support, not a hard medical rules engine

### Pantry Carryover

- Active carryover store path:
  - `data/pantry_carryover.json`
- Runtime rule:
  - planner loads pantry carryover from the carryover store
  - leftover package quantities can reduce future shopping
- Integrity rule:
  - carryover must not be confused with consumed meal cost

### Pricing / Cost Support

- Default runtime pricing source:
  - local mock grocery provider
- Optional real-store mode:
  - Kroger/Fry's provider
- Runtime rule:
  - real-store mode is optional
  - missing credentials or provider failure must fall back to mock pricing instead of breaking the planner
- Integrity rule:
  - consumed meal cost
  - added shopping cost
  - leftover pantry carryover
  stay distinct

## Runtime Audit Path

Use:

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m pantry_pilot.runtime_audit
```

JSON output:

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m pantry_pilot.runtime_audit --json
```

The audit reports:

- active runtime recipe source and path
- recipe fallback state
- total recipe count
- meal-type counts
- inferred dinner-role counts
- nutrition coverage
- calorie coverage
- pricing coverage
- honest unknown counts
- weak-main counts
- USDA/guidance mapping counts

The full offline build path is:

```powershell
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m pantry_pilot.usda_build download
C:\Users\Legom\AppData\Local\Programs\Python\Python312\python.exe -m pantry_pilot.usda_build build --reset
```

## Normal-Path Expectations

- processed RecipeNLG dataset is active
- recipe fallback is inactive
- full-build nutrition and guidance support files exist locally
- pantry carryover path is explicit
- pricing defaults to local mock behavior unless the user explicitly requests real-store pricing

## Failure Expectations

- missing required recipe/runtime artifacts fail clearly or surface truthful fallback state
- optional support gaps must preserve honest unknowns rather than inventing zeros
- no silent switch to live runtime nutrition/guidance dependencies is allowed
