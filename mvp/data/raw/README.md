# Raw Recipe Data

Put original recipe source files here.

Current primary offline source:

- RecipeNLG CSV: `mvp/data/raw/recipenlg/RecipeNLG_dataset.csv`

Other source folders may remain for comparison or historical debugging, but the MVP's current main offline recipe corpus is RecipeNLG.

Recommended organization for large local datasets:

- one subdirectory per source
- preserve original filenames when practical
- keep source-specific notes or licenses next to the source files

Examples:

- `mvp/data/raw/usda-demo/recipes.json`
- `mvp/data/raw/internal-curation/batch-001.csv`

## Supported import formats

PantryPilot's offline importer currently supports:

- JSON files containing either a top-level list of recipe objects or a `{ "recipes": [...] }` object
- CSV files where nested `ingredients` and `instructions` columns contain JSON arrays

Expected fields per recipe row:

- `source_recipe_id`
- `title`
- `servings`
- `prep_time_minutes`
- `cook_time_minutes`
- `total_time_minutes`
- `ingredients`
- `instructions`
- `calories_per_serving` (optional)
- `cuisine` (optional)
- `meal_types` (optional, comma-separated)
- `diet_tags` (optional, comma-separated)
- `allergen_completeness`
- `allergens`

See `mvp/data/raw/example_recipes.json` for a tiny JSON example.
