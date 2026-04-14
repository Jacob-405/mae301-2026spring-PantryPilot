# MVP Data Layout

This directory is the stable home for local recipe datasets used by PantryPilot's MVP and later milestones.

## Subdirectories

- `raw/`: source snapshots exactly as collected from approved local files or exports
- `processed/`: normalized records derived from `raw/` and ready for deterministic planning

The planner is not wired to these directories yet in Milestone 1. They exist now so larger datasets can be added without reshaping the repo later.
