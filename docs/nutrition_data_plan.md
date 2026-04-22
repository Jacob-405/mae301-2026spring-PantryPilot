# Real Nutrition Data Selection and Integration Design

## Goal

Replace PantryPilot's current heuristic ingredient nutrition layer with a real USDA-backed local nutrition source, and define a safe balanced-meal guidance layer that improves planning without turning federal dietary guidance into rigid medical rules.

This phase is design-only. It does not start broad ingestion or planner rewrites.

## Current Gap

- The repo currently uses a local heuristic nutrition table in `pantry_pilot/nutrition.py`.
- That table is explicit and debuggable, but it is still hand-curated and incomplete.
- Balanced meal scoring exists in `pantry_pilot/planner.py`, but it is still mostly title/ingredient heuristic logic rather than a food-group-aware guidance layer.
- The next upgrade is not another recipe corpus. It is a stronger ingredient nutrition source plus a more defensible meal-balance guidance input.

## Sources Evaluated

### USDA FoodData Central

Evaluated as the candidate real nutrition source.

What matters for PantryPilot:

- Official USDA source
- Public-domain / CC0 data
- Downloadable JSON and CSV snapshots
- Multiple food data types
- Good fit for local cache or local snapshot use
- Avoids planner-time API dependency

Relevant official characteristics:

- Foundation Foods: analytically derived USDA data for commodity and minimally processed foods
- SR Legacy: historical USDA nutrient data, final release in 2018
- FNDDS: USDA survey-food nutrient and portion-weight data for foods reported in NHANES
- Download snapshots exist in JSON/CSV
- API exists, but requires a key and is rate-limited

### Dietary Guidelines for Americans / MyPlate

Evaluated as the candidate balanced-meal guidance source.

What matters for PantryPilot:

- Official USDA/HHS dietary guidance
- Stable enough to encode as local scoring inputs
- Broad food-group framing rather than medical prescriptive meal rules
- Good fit for a soft guidance layer

Relevant official characteristics:

- Dietary Guidelines define healthy dietary patterns and food-group-oriented guidance
- MyPlate provides practical food-group framing:
  - vegetables
  - fruits
  - grains
  - protein foods
  - dairy
- MyPlate also clarifies category boundaries that matter for PantryPilot:
  - beans, peas, and lentils count in Protein Foods and are also part of Vegetables
  - cream cheese, sour cream, cream, and butter are not part of the Dairy Group

## Recommendation

### Best-Fit Nutrition Source

Use a **local FoodData Central snapshot** with this priority order:

1. `Foundation Foods` as the primary source for commodity and minimally processed ingredients
2. `SR Legacy` as a fallback for broader baseline coverage
3. `FNDDS` as a targeted fallback for common generic prepared pantry ingredients that PantryPilot actually uses

Do **not** make live USDA API lookups part of core meal-planning runtime.

Do **not** start with Branded Foods as the MVP base.

Reasoning:

- Foundation Foods is the best semantic fit for PantryPilot canonical ingredients like `broccoli`, `lentils`, `olive oil`, and `zucchini`.
- SR Legacy fills many common gaps while remaining local and stable.
- FNDDS is useful for generic mixed pantry items such as `cream of mushroom soup` or `flour tortillas`, where commodity records are not always the best match.
- Branded Foods is much larger, noisier, and more operationally expensive. It is a poor first step for a debuggable MVP nutrition layer.

### Best-Fit Healthy-Meal Guidance Source

Use **MyPlate + Dietary Guidelines for Americans** as a **soft scoring guidance layer**, not hard planner rules.

Reasoning:

- MyPlate gives PantryPilot a stable food-group vocabulary that maps well onto meal composition.
- Dietary Guidelines support nutrient-dense, food-group-oriented meal construction.
- Hard rules would be the wrong fit for PantryPilot MVP because:
  - user calorie targets and diet restrictions already vary
  - federal guidance is population guidance, not per-user clinical prescription
  - rigid enforcement would increase failure cases and reduce planner flexibility

Safest MVP choice:

- `soft scoring guidance` only

Not recommended for MVP:

- `hard rules`
- `hard rules + soft scoring` at planner runtime

## Why These Sources Fit PantryPilot Better Than Alternatives

### FoodData Central vs. staying heuristic-only

FoodData Central is better because:

- it is real source data rather than hand-entered nutrition approximations
- it is official, documented, and locally cacheable
- it supports explicit source attribution and release pinning
- it allows PantryPilot to keep honest unknowns when mapping fails

The heuristic table should remain only as a temporary fallback during rollout, not the target system.

### FoodData Central local snapshot vs. live API runtime

Local snapshots are better because:

- planner runtime stays offline and deterministic
- no API keys are needed for normal meal planning
- no API rate-limit failures can break planning
- data can be version-pinned and diffed
- mapping jobs can be chunked and resumed

The USDA API is still useful, but only for:

- one-time exploration
- bootstrap experiments
- optional cache fill during an offline mapping workflow

### MyPlate / DGA vs. homemade balance rules only

MyPlate / DGA are better because:

- they provide an official structure for food-group-aware balance
- they are easier to explain than ad hoc internal scoring
- they align with PantryPilot's main + optional side design

The current heuristic balance layer is still useful, but it should evolve into a scored interpretation of food-group guidance rather than remain mostly title-based forever.

## Proof Of Fit: Representative PantryPilot Ingredient Sample

Pilot method:

- Used a representative 20-ingredient sample spanning commodity foods, minimally processed staples, sauces, dairy-like pantry items, and mixed prepared pantry ingredients.
- Queried official USDA FoodData Central downloadable snapshots:
  - Foundation Foods
  - SR Legacy
  - FNDDS
- Stored the raw pilot output in [docs/usda_mapping_sample.json](/C:/Users/Legom/mae301-2026spring-PantryPilot/docs/usda_mapping_sample.json).

### Reviewed Sample Coverage

Reviewed manually from the pilot output:

- `15/20` clean matches
- `4/20` partial / needs curated disambiguation
- `1/20` no clean match in the pilot

This is a **75% clean-match rate** on a deliberately mixed sample before building a real alias table or curated review workflow.

### Example Mappings

| PantryPilot ingredient | USDA candidate | Data type fit | Reviewed verdict | Notes |
|---|---|---|---|---|
| `apple` | `Apples, fuji, with skin, raw` | Foundation | clean | clear commodity match |
| `black beans` | `Beans, black, canned, sodium added, drained and rinsed` | FNDDS/SR | clean | acceptable generic pantry match |
| `broccoli` | `Broccoli, raw` | Foundation | clean | ideal commodity match |
| `carrot` | `Carrots, baby, raw` | Foundation | clean | close commodity match |
| `chicken breast` | `Chicken, breast, meat and skin, raw` | Foundation | clean | good base ingredient match |
| `cilantro` | `Coriander (cilantro) leaves, raw` | SR Legacy | clean | alias resolution required |
| `cream cheese` | `Cream cheese, full fat, block` | Foundation | clean | strong processed-ingredient match |
| `granola` | `Cereals ready-to-eat, granola, homemade` | SR Legacy | clean | acceptable generic match |
| `lentils` | `Lentils, dry` | Foundation/SR | clean | strong commodity match |
| `olive oil` | `Olive oil` | Foundation/SR | clean | ideal match |
| `rice` | `Rice, black, unenriched, raw` | SR Legacy | clean | generic commodity family exists; curated subtype choice needed |
| `sour cream` | `Sour cream, light` | SR Legacy | clean | acceptable generic match |
| `soy sauce` | `Soy sauce made from soy (tamari)` | SR Legacy | clean | acceptable pantry sauce match |
| `zucchini` | `Squash, summer, green, zucchini, includes skin, raw` | SR Legacy | clean | strong commodity match |
| `cream of mushroom soup` | `Soup, cream of mushroom, canned, condensed` | SR Legacy/FNDDS | clean | good generic prepared pantry match |
| `cheddar cheese` | `Cheese spread, American or Cheddar cheese base, reduced fat` | SR Legacy | partial | wrong subtype; needs curated disambiguation to regular cheddar |
| `flour tortillas` | `Taco, flour tortilla, beef, cheese` | FNDDS | partial | assembled dish, not tortilla ingredient |
| `stuffing mix` | `Brownberry Sage and Onion Stuffing Mix, dry` | FNDDS/brand-like | partial | usable only if PantryPilot accepts generic packaged mix mapping |
| `tofu` | `Tofu, fried` | SR Legacy | partial | needs unflavored/plain tofu selection |
| `garam masala` | `SMART SOUP, Indian Bean Masala` | weak | fail | spice blend needs curated fallback or manual record |

### Where Mappings Fail And Why

Main failure modes:

1. **Subtype ambiguity**
   - Example: `cheddar cheese`
   - USDA has many cheddar-like products; a naive text match can land on cheese spreads or flavored packaged foods.

2. **Prepared-food false positives**
   - Example: `flour tortillas`
   - A loose search can land on tacos or assembled dishes instead of the pantry ingredient.

3. **Brand-heavy or packaged generic categories**
   - Example: `stuffing mix`
   - Data exists, but it may be easiest to reach through branded or prepared records rather than a clean generic commodity.

4. **Spice blend gaps**
   - Example: `garam masala`
   - USDA coverage is much weaker for some mixed spice blends than for single-ingredient foods.

### Expected Coverage For Calories, Protein, Carbs, Fat

Expected rollout-level estimate for PantryPilot canonical ingredients:

- Commodity and minimally processed ingredients:
  - high expected coverage for calories, protein, carbs, and fat
- Generic pantry processed staples:
  - moderate-to-high expected coverage using SR Legacy and FNDDS fallback
- Mixed spice blends / specialty sauces / highly specific pantry mixes:
  - lower expected clean-match coverage

Practical MVP expectation:

- calories / protein / carbs / fat should become available for the large majority of PantryPilot's commonly used canonical ingredients
- a smaller tail of ingredients should remain explicitly unmapped until curated review is added

Important constraint:

- if no trusted mapping exists, nutrition must remain unknown
- do not backslide into fake zeros

## Integration Design

### Target Architecture

Add a real USDA-backed support layer alongside the existing planner:

1. `nutrition_source_snapshot`
   - pinned local USDA data snapshot metadata
   - release dates and source data types

2. `nutrition_source_food`
   - compact local extracted USDA rows needed by PantryPilot
   - not the whole raw USDA archive at planner runtime

3. `ingredient_to_usda_map`
   - explicit PantryPilot canonical ingredient -> USDA mapping
   - stores confidence, source data type, chosen food id, and review status

4. `derived_ingredient_nutrition`
   - normalized PantryPilot nutrition record derived from USDA data
   - one row per PantryPilot canonical ingredient

5. `meal_balance_guidance`
   - food-group-oriented scoring inputs used by the planner

### Recommended Data Schema

#### Ingredient Nutrition Record

```json
{
  "canonical_ingredient": "olive oil",
  "source_system": "usda-fdc",
  "source_dataset": "foundation",
  "source_release": "2025-12-18",
  "source_food_id": 0,
  "source_description": "Olive oil",
  "reference_amount": 1.0,
  "reference_unit": "tbsp",
  "calories": 119.0,
  "protein_grams": 0.0,
  "carbs_grams": 0.0,
  "fat_grams": 13.5,
  "nutrient_quality": "direct-usda",
  "unit_basis_notes": "",
  "derived_from_snapshot": true
}
```

#### Mapped PantryPilot Ingredient

```json
{
  "canonical_ingredient": "cilantro",
  "mapping_status": "mapped",
  "mapping_method": "curated-alias",
  "search_terms": ["coriander", "cilantro", "leaves"],
  "selected_source_dataset": "sr_legacy",
  "selected_source_food_id": 0,
  "selected_source_description": "Coriander (cilantro) leaves, raw",
  "confidence": "high",
  "review_status": "reviewed",
  "notes": "cilantro requires coriander alias"
}
```

#### Meal-Balance Guidance / Scoring Inputs

```json
{
  "canonical_ingredient": "black beans",
  "food_group_tags": ["protein_foods", "vegetables_legumes", "carb_support"],
  "myplate_credit_basis": "soft",
  "meal_balance_weight": {
    "protein_support": 1.0,
    "vegetable_support": 0.4,
    "carb_support": 0.6
  },
  "guidance_notes": "beans/peas/lentils count in protein foods and are also part of vegetables"
}
```

### Planner-Time Usage

Planner runtime should read only:

- a compact local nutrition table
- a compact explicit PantryPilot ingredient mapping table
- a compact local meal-guidance table

Planner runtime should **not**:

- download USDA data
- call the USDA API
- search raw USDA snapshots

## Runtime-Safety Design

### Non-Negotiable Safety Rules

- no giant one-shot ingestion job
- no planner-time network dependency
- no long fragile 7+ hour process
- every step file-backed and restartable

### Safe Processing Pipeline

1. **Pin a USDA snapshot**
   - store exact source URLs and release dates
   - treat the snapshot as immutable input for one mapping run

2. **Extract only needed fields**
   - build a compact local USDA subset table from Foundation / SR Legacy / FNDDS
   - keep only:
     - food id
     - description
     - source dataset
     - release
     - macro nutrients
     - limited measure metadata needed for PantryPilot units

3. **Chunk PantryPilot ingredient mapping**
   - process canonical ingredients in small batches such as `10-25`
   - write a checkpoint file after each batch

4. **Store reviewable candidate lists**
   - for each ingredient, save top candidate rows and mapping reasons
   - do not auto-accept ambiguous mappings silently

5. **Produce compact derived records**
   - once a mapping is accepted, emit a compact PantryPilot nutrition record
   - keep the planner pointed at that derived compact table

### Required Checkpoint Files

- `data/nutrition/usda_snapshot_manifest.json`
- `data/nutrition/usda_compact_foods.jsonl`
- `data/nutrition/mapping_candidates.jsonl`
- `data/nutrition/mapping_decisions.jsonl`
- `data/nutrition/derived_pantrypilot_nutrition.json`

### Tiny Pilot Run Before Broad Mapping

Required pilot before any larger job:

- sample only `20-30` canonical PantryPilot ingredients
- generate candidate lists
- manually review ambiguous matches
- confirm macro extraction format
- confirm unit/reference strategy

Only after that passes should PantryPilot attempt a broader mapping job.

### Success / Failure Criteria

Pilot success:

- at least `70%` of the pilot sample maps cleanly
- ambiguous cases are explicitly surfaced
- no fake zero nutrition values are introduced
- derived records include calories, protein, carbs, and fat where mapped
- rerunning the pilot is idempotent and resumes from checkpoint

Pilot failure:

- candidate matching is dominated by branded/restaurant false positives
- macro extraction differs too much across USDA data types for a simple MVP parser
- unit/reference normalization cannot be made explicit and debuggable

## Recommended Next Implementation Phase

`Phase D - USDA Nutrition Pilot Integration`

Scope:

- add a small USDA snapshot manifest
- add a compact extracted-food schema
- add a tiny batch mapping prototype for `20-30` PantryPilot ingredients
- add checkpoint files and resume support
- add tests proving:
  - checkpoint resume works
  - ambiguous mappings stay unresolved
  - mapped ingredients expose calories/protein/carbs/fat
  - planner runtime uses only local derived nutrition data

Not in that phase:

- no full-catalog ingestion
- no UI redesign
- no runtime USDA API calls
