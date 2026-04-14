# Processed Recipe Data

Put normalized recipe files here after validation.

Recommended organization:

- store deterministic exports only
- keep file formats simple for the MVP, such as JSON or JSONL
- partition by source or batch once the dataset grows

Examples:

- `mvp/data/processed/recipes.normalized.json`
- `mvp/data/processed/demo-source/recipes-0001.jsonl`
