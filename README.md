# PantryPilot

PantryPilot is the main project in this repository. It is a deterministic weekly meal-planning app built with Streamlit and local-first data. The current system plans seven days of meals from real recipe data, applies hard safety checks for allergens and exclusions, estimates nutrition and grocery cost, tracks pantry carryover, and exposes planner reasoning for verification.

The repo still contains earlier milestone material, but the submission-ready center of gravity is now PantryPilot rather than the original nanoGPT exploration.

## What PantryPilot Does

- accepts weekly budget, servings, cuisine preferences, allergies, excluded ingredients, diet restrictions, pantry staples, prep-time limits, meal slots, and optional personal nutrition guidance
- builds a deterministic weekly plan with main/side roles, shopping list output, pantry carryover handling, and budget enforcement
- uses local recipe/runtime data by default and optionally Kroger or Fry's pricing when credentials are configured
- keeps unknown allergen data unsafe by default
- exposes planner diagnostics, daily nutrient state, and acceptance-style checks for balance and pairing quality

## Repo Map

- Proposal: [proposal/README.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/proposal/README.md)
- Phase 2 report: [phase2/report.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/phase2/report.md)
- MVP report: [mvp/report.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/mvp/report.md)
- App entrypoint: [mvp/app.py](/C:/Users/Legom/mae301-2026spring-PantryPilot/mvp/app.py)
- Main code: [pantry_pilot](/C:/Users/Legom/mae301-2026spring-PantryPilot/pantry_pilot)
- Tests: [tests](/C:/Users/Legom/mae301-2026spring-PantryPilot/tests)
- Runtime and data docs: [docs/README.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/README.md)

## Submission-Facing Structure

The folders a grader should care about first are:

- `proposal/`
- `phase2/`
- `mvp/`
- `docs/`
- `pantry_pilot/`
- `tests/`

Other top-level items such as local caches, generated artifacts, and machine-specific state are intentionally ignored or kept out of the submission flow.

## Run PantryPilot

Requirements:

- Python 3.12
- Windows PowerShell for the commands below

Setup:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Start the app:

```powershell
python -m streamlit run mvp/app.py
```

## Pricing Modes

PantryPilot works without API keys by using mock grocery pricing.

For Kroger or Fry's pricing, set:

- `KROGER_CLIENT_ID`
- `KROGER_CLIENT_SECRET`
- optional: `KROGER_API_SCOPE` with default `product.compact`

Example:

```powershell
$env:KROGER_CLIENT_ID="your-client-id"
$env:KROGER_CLIENT_SECRET="your-client-secret"
$env:KROGER_API_SCOPE="product.compact"
```

If credentials or store lookup fail, the app falls back to mock pricing rather than crashing.

## Verification

Fast submission-oriented checks:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_phase2_app_display
.\.venv\Scripts\python.exe -m unittest tests.test_phaseJ_acceptance
.\.venv\Scripts\python.exe -m unittest tests.test_phase6_regressions
```

Full suite:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Data and Runtime Notes

- The app is local-first and does not require runtime recipe scraping.
- Current runtime/data contracts live in:
  - [docs/runtime_data_contract.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/runtime_data_contract.md)
  - [docs/nutrition_data_plan.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/nutrition_data_plan.md)
  - [docs/recipe_planner_fix_plan.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/recipe_planner_fix_plan.md)
- Large raw imports, USDA snapshot inputs, temporary logs, and local carryover/favorites state are not part of the normal tracked submission surface.

## Historical Context

- `nanogpt/` is retained as earlier project context.
- `docs/lit-llama-main/` is legacy reference material and is not the main PantryPilot submission path.
