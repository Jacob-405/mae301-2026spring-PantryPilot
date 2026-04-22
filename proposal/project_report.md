# PantryPilot Proposal Report

## Problem

The project started from a simple planning problem: students and budget-conscious households often want to cook, but still struggle to turn pantry ingredients, time limits, food preferences, and safety constraints into realistic meals. That usually leads to wasted groceries, repetitive meals, or fallback takeout.

The proposal framed PantryPilot as a tool for users who need help with:

- weekly grocery budgets
- pantry reuse
- allergies and exclusions
- calorie guidance
- limited prep time

## Proposed Solution

The proposed solution was PantryPilot: an AI-assisted recipe and meal-planning system that could:

1. use ingredients already on hand to reduce waste
2. build a weekly plan that fits budget and nutrition constraints
3. adapt meal suggestions to preferences, exclusions, and practical cooking limits

The original idea expected a generation component to help with recipe-style outputs while surrounding planner logic enforced the harder user constraints.

## Technical Approach

The proposal expected a system built from:

- recipe data with ingredients and steps
- nutrition and cost data for lightweight estimation
- a generation component for recipe-style outputs
- filtering and ranking logic for safety and budget/calorie fit
- validation so outputs remained practical rather than purely creative

## MVP Description

The intended MVP scope was a local demo where a user enters pantry items, budget, exclusions, preferences, and calorie guidance, then receives:

- a set of usable meal options
- a weekly meal plan
- a shopping list with estimated cost

## Data

The proposal anticipated open recipe datasets, public nutrition data, and a small editable grocery-pricing layer. That direction evolved into the current PantryPilot runtime documented in:

- [mvp/report.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/mvp/report.md)
- [docs/runtime_data_contract.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/runtime_data_contract.md)
- [docs/nutrition_data_plan.md](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/nutrition_data_plan.md)

## Evaluation Plan

At proposal time, the expected evaluation focus was:

- whether outputs respected user constraints
- whether the system could produce practical, readable meal suggestions
- whether cost and calorie estimates were useful enough for planning
- whether the final demo was easy to run locally from the repo

## Risks And Limitations

The early proposal identified several risks:

- inconsistent recipe formatting and data quality
- safety and correctness around allergens and exclusions
- imperfect cost and nutrition estimates
- the risk that a generative component might produce unrealistic meals without enough guardrails

## Next Steps From The Proposal

The next steps implied by the proposal were:

- gather and normalize usable recipe data
- define safety and constraint enforcement rules
- build a local MVP demo
- turn the early AI-heavy concept into a practical planning workflow

That work ultimately converged into the deterministic PantryPilot meal planner now documented in the current repo.
