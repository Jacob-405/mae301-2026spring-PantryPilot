# PantryPilot Phase 2 Report

## Problem

The project needed to move from early concept work into a submission-ready PantryPilot system that could actually plan believable weekly meals under real user constraints. The main challenge was not just generating recipes, but building a planner that handled safety, budget, carryover, target guidance, and meal balance in a deterministic and inspectable way.

## Solution

Phase 2 matured PantryPilot into a deterministic weekly meal-planning application with:

- a Streamlit UI
- real runtime recipe data
- grocery cost estimation
- pantry carryover support
- nutrition-aware planning
- planner diagnostics and acceptance-style checks

## Technical Progress

The final Phase 2 state demonstrates:

- deterministic weekly meal planning from local recipe/runtime data
- weekly budget enforcement with package-based shopping estimates
- allergen and exclusion safety with unknown allergen data treated as unsafe
- personal-target and manual-target guidance for calories, macros, and food groups
- daily nutrient state tracking during planning
- main/side complement logic informed by daily deficits and week-level balance
- diagnostics explaining why meals were selected
- acceptance-style verification on real runtime scenarios

## MVP Description

The current MVP is a local-first weekly meal-planning app. A user can enter budget, servings, preferences, exclusions, allergies, meal structure, pantry staples, and nutrition guidance, then receive:

- a seven-day meal plan
- main/side meal assignments
- grocery list output
- cost estimates
- nutrition summaries
- planner reasoning and diagnostics

## Data

Key data/runtime inputs are documented in:

- [docs/runtime_data_contract.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/runtime_data_contract.md)
- [docs/nutrition_data_plan.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/nutrition_data_plan.md)
- [mvp/data/README.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/mvp/data/README.md)

The final runtime centers PantryPilot around local recipe data plus reviewed nutrition support rather than a live recipe scraping dependency.

## Evaluation

Phase 2 verification includes:

- unit coverage for planner logic, pricing, runtime wiring, and UI display helpers
- targeted regression coverage
- acceptance scenarios covering balanced weeks, high-protein weeks, tighter-calorie weeks, and pantry-carryover reuse
- diagnostics showing why meals were selected and how daily nutrient gaps changed

## Limitations

Current limitations still include:

- some recipe nutrition and pricing values remain partial
- recipe-title role inference is imperfect on some RecipeNLG entries
- balanced-meal guidance is planning support, not medical advice
- live provider behavior is still secondary to the local mock-pricing path for reproducible verification

## Next Steps

The next meaningful work after this phase is:

- harden main-meal realism on noisy RecipeNLG titles
- keep improving acceptance-style scenario coverage
- prepare the final submission branch/package with the repo structure already cleaned for grading

## Core Submission Artifacts

- App: [mvp/app.py](/C:/Users/Legom/mae301-2026spring-PantryPilot/mvp/app.py)
- MVP report: [mvp/report.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/mvp/report.md)
- Proposal report: [proposal/project_report.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/proposal/project_report.md)
- Runtime/data contract: [docs/runtime_data_contract.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/runtime_data_contract.md)
- Nutrition planning notes: [docs/nutrition_data_plan.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/nutrition_data_plan.md)
- Phase-by-phase fix log: [docs/recipe_planner_fix_plan.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/recipe_planner_fix_plan.md)
