# PantryPilot instructions

## Goal
Refactor this repo into a weekly meal-planning app.

## Product requirements
- Accept weekly budget, servings, cuisine preferences, allergies, excluded ingredients, diet restrictions, pantry staples, max prep time, and meals per day.
- Use real recipes and deterministic planning logic.
- Prefer official grocery APIs over website scraping.
- Start with a mock grocery provider so the app works without API keys.
- Unknown allergen data must be treated as unsafe.
- Never hard-code secrets. Read credentials from environment variables.
- Keep Streamlit unless there is a strong reason to replace it.

## Repo rules
- Major refactors are allowed.
- The current nanoGPT flow does not need to remain the core planner.
- Stop after each phase.
- After each phase, show the diff and explain how to test it.
- Add tests for allergy filtering, shopping-list aggregation, and budget compliance.
- Do not add new dependencies unless they are clearly needed.