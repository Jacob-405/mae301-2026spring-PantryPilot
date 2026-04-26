# MVP Data Layout

This directory is the stable home for local recipe datasets used by PantryPilot's MVP.

## Subdirectories

- `raw/`: source snapshots exactly as collected from approved local files or exports
- `processed/`: normalized records derived from `raw/` and ready for deterministic planning

Current MVP runtime behavior:

- the app defaults to `mvp/data/processed/recipenlg-full-20260416T0625Z.json`
- the app falls back to the built-in sample dataset only if the processed dataset fails to load
- raw RecipeNLG source data lives under `mvp/data/raw/recipenlg/`
