from __future__ import annotations

import ast
import csv
import json
import re
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from pantry_pilot.data_pipeline.schema import (
    AllergenAssessment,
    AllergenCompleteness,
    CalorieEstimate,
    IngredientRecord,
    NormalizedRecipe,
    SourceMetadata,
)
from pantry_pilot.data_pipeline.similarity import annotate_recipe_similarity, build_diversity_metadata
from pantry_pilot.data_pipeline.validation import ValidationIssue, validate_recipe_collection
from pantry_pilot.ingredient_catalog import (
    canonical_ingredient_name,
    ingredient_catalog_entries,
    lookup_ingredient_metadata,
)
from pantry_pilot.normalization import normalize_name, normalize_unit, parse_csv_list


DEFAULT_PROCESSED_FILENAME = "recipes.imported.json"
UNICODE_FRACTIONS = {
    "¼": "1/4",
    "½": "1/2",
    "¾": "3/4",
    "⅐": "1/7",
    "⅑": "1/9",
    "⅒": "1/10",
    "⅓": "1/3",
    "⅔": "2/3",
    "⅕": "1/5",
    "⅖": "2/5",
    "⅗": "3/5",
    "⅘": "4/5",
    "⅙": "1/6",
    "⅚": "5/6",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
}
MEAL_KEYWORD_GROUPS = {
    "breakfast": ("breakfast", "brunch", "pancake", "waffle", "oatmeal", "omelet", "omelette", "scramble", "parfait", "smoothie"),
    "dessert": ("dessert", "desserts", "cookie", "cake", "pie", "brownie", "cobbler", "ice cream", "frosting"),
    "drink": ("drink", "drinks", "beverage", "cocktail", "smoothie bowl"),
    "lunch": ("lunch", "sandwich", "wrap", "salad"),
    "dinner": ("dinner", "main dish", "main dishes", "pasta", "skillet", "soup", "stew", "chili", "curry", "stir fry"),
}
GENERIC_CUISINE_SEGMENTS = frozenset(
    {
        "appetizers and snacks",
        "bread",
        "breakfast and brunch",
        "dessert",
        "desserts",
        "dinner",
        "everyday cooking",
        "lunch",
        "main dishes",
        "salad",
        "side dish",
        "side dishes",
        "soups stews and chili",
        "u s recipes",
        "world cuisine",
    }
)
IGNORED_IMPORT_INGREDIENTS = frozenset(
    {
        "black pepper",
        "salt",
        "water",
    }
)
IGNORED_IMPORT_PHRASES = (
    "salt and ground black pepper to taste",
    "salt to taste",
    "pepper to taste",
)
NON_SUBSTANTIAL_IMPORT_INGREDIENTS = frozenset(
    {
        "black pepper",
        "butter",
        "chili powder",
        "cinnamon",
        "cumin",
        "curry powder",
        "flour",
        "garlic powder",
        "ginger",
        "honey",
        "olive oil",
        "oregano",
        "paprika",
        "salt",
        "soy sauce",
        "vegetable oil",
        "water",
    }
)


@dataclass(frozen=True)
class ImportConfig:
    max_unmapped_ingredient_fraction: float = 0.25
    reject_unknown_allergens: bool = True


@dataclass(frozen=True)
class ImportRejection:
    source_recipe_id: str
    title: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class ImportResult:
    imported_recipes: tuple[NormalizedRecipe, ...]
    rejected_rows: tuple[ImportRejection, ...]
    output_path: str
    stats_path: str
    stats: dict
    validation_issues: tuple[ValidationIssue, ...] = ()


def import_recipes_from_files(
    raw_paths: tuple[str | Path, ...] | list[str | Path],
    *,
    processed_path: str | Path | None = None,
    config: ImportConfig | None = None,
) -> ImportResult:
    active_config = config or ImportConfig()
    all_recipes: list[NormalizedRecipe] = []
    all_rejections: list[ImportRejection] = []
    total_raw_count = 0
    source_names: list[str] = []
    base_processed_dir: Path | None = None

    for raw_path in raw_paths:
        raw_file = Path(raw_path)
        source_names.append(raw_file.name)
        total_raw_count += _count_raw_rows(raw_file)
        recipes, rejections = _normalize_rows(_load_raw_rows(raw_file), raw_file, active_config)
        all_recipes.extend(recipes)
        all_rejections.extend(rejections)
        if base_processed_dir is None:
            base_processed_dir = _default_processed_dir_for(raw_file)

    enriched_recipes = tuple(
        replace(recipe, diversity=build_diversity_metadata(recipe))
        for recipe in all_recipes
    )
    clustered_recipes = annotate_recipe_similarity(enriched_recipes)

    if processed_path is not None:
        output_file = Path(processed_path)
    else:
        output_file = (base_processed_dir or Path("mvp/data/processed")) / DEFAULT_PROCESSED_FILENAME
    output_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"recipes": [_recipe_to_dict(recipe) for recipe in clustered_recipes]}
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    stats_file = output_file.with_suffix(".stats.json")
    stats = _build_import_stats(total_raw_count, clustered_recipes, all_rejections, tuple(source_names))
    stats_file.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    validation_issues = validate_recipe_collection(tuple(clustered_recipes))
    return ImportResult(
        imported_recipes=tuple(clustered_recipes),
        rejected_rows=tuple(all_rejections),
        output_path=str(output_file),
        stats_path=str(stats_file),
        stats=stats,
        validation_issues=validation_issues,
    )


def import_recipes_from_file(
    raw_path: str | Path,
    *,
    processed_path: str | Path | None = None,
    config: ImportConfig | None = None,
) -> ImportResult:
    return import_recipes_from_files(
        (raw_path,),
        processed_path=processed_path,
        config=config,
    )


def _count_raw_rows(raw_file: Path) -> int:
    return len(_load_raw_rows(raw_file))


def _default_processed_dir_for(raw_file: Path) -> Path:
    parts = list(raw_file.parts)
    if "raw" in parts:
        raw_index = parts.index("raw")
        return Path(*parts[:raw_index], "processed")
    return Path("mvp/data/processed")


def _is_kaggle_train_schema(row: dict) -> bool:
    return "recipe_name" in row and "ingredients" in row and "directions" in row


def _is_kaggle_test_schema(row: dict) -> bool:
    return "Name" in row and "Ingredients" in row and "Directions" in row


def import_kaggle_recipe_directory(
    raw_dir: str | Path,
    *,
    processed_path: str | Path | None = None,
    config: ImportConfig | None = None,
) -> ImportResult:
    directory = Path(raw_dir)
    paths = tuple(
        path
        for path in (
            directory / "recipes.csv",
            directory / "test_recipes.csv",
        )
        if path.exists()
    )
    if not paths:
        raise ValueError(f"No Kaggle recipe files found in {directory}")
    return import_recipes_from_files(
        paths,
        processed_path=processed_path,
        config=config,
    )


def _load_raw_rows(raw_file: Path) -> tuple[dict, ...]:
    suffix = raw_file.suffix.lower()
    if suffix == ".json":
        return _load_json_rows(raw_file)
    if suffix == ".csv":
        return _load_csv_rows(raw_file)
    raise ValueError(f"Unsupported raw file format: {raw_file.suffix}")


def _load_json_rows(raw_file: Path) -> tuple[dict, ...]:
    payload = json.loads(raw_file.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return tuple(_ensure_row_dict(row) for row in payload)
    if isinstance(payload, dict) and isinstance(payload.get("recipes"), list):
        return tuple(_ensure_row_dict(row) for row in payload["recipes"])
    raise ValueError("JSON raw import files must contain a list or a top-level 'recipes' list.")


def _load_csv_rows(raw_file: Path) -> tuple[dict, ...]:
    with raw_file.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return tuple(dict(row) for row in reader)


def _ensure_row_dict(row: object) -> dict:
    if not isinstance(row, dict):
        raise ValueError(f"Each raw recipe row must be an object, got: {type(row)!r}")
    return row


def _normalize_rows(
    rows: tuple[dict, ...],
    raw_file: Path,
    config: ImportConfig,
) -> tuple[list[NormalizedRecipe], list[ImportRejection]]:
    recipes: list[NormalizedRecipe] = []
    rejections: list[ImportRejection] = []

    for index, row in enumerate(rows):
        source_recipe_id, title = _extract_row_identity(row, index)
        try:
            normalized = _normalize_row(row, raw_file, source_recipe_id, config)
        except RowRejectedError as exc:
            rejections.append(
                ImportRejection(
                    source_recipe_id=source_recipe_id,
                    title=title,
                    reasons=tuple(exc.reasons),
                )
            )
            continue
        recipes.append(normalized)

    return recipes, rejections


class RowRejectedError(ValueError):
    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__("; ".join(reasons))


def _extract_row_identity(row: dict, index: int) -> tuple[str, str]:
    if _is_kaggle_train_schema(row):
        source_recipe_id = str(row.get("") or row.get("url") or f"row-{index + 1}").strip()
        title = str(row.get("recipe_name", "")).strip()
        return source_recipe_id or f"row-{index + 1}", title
    if _is_kaggle_test_schema(row):
        source_recipe_id = str(row.get("Row") or row.get("url") or f"row-{index + 1}").strip()
        title = str(row.get("Name", "")).strip()
        return source_recipe_id or f"row-{index + 1}", title
    source_recipe_id = str(row.get("source_recipe_id") or row.get("recipe_id") or f"row-{index + 1}").strip()
    title = str(row.get("title", "")).strip()
    return source_recipe_id, title


def _normalize_row(
    row: dict,
    raw_file: Path,
    source_recipe_id: str,
    config: ImportConfig,
) -> NormalizedRecipe:
    if _is_kaggle_train_schema(row):
        return _normalize_kaggle_train_row(row, raw_file, source_recipe_id, config)
    if _is_kaggle_test_schema(row):
        return _normalize_kaggle_test_row(row, raw_file, source_recipe_id, config)

    reasons: list[str] = []
    title = str(row.get("title", "")).strip()
    if not title:
        reasons.append("Missing title.")

    ingredient_rows = _coerce_ingredients(row.get("ingredients"))
    if not ingredient_rows:
        reasons.append("Missing ingredients.")

    step_rows = _coerce_steps(row.get("instructions") or row.get("steps"))
    if not step_rows:
        reasons.append("Missing instructions.")

    allergens = _coerce_allergen_assessment(row.get("allergens"), row.get("allergen_completeness"))
    if config.reject_unknown_allergens and allergens.completeness is not AllergenCompleteness.COMPLETE:
        reasons.append("Allergen completeness is missing or unsafe.")

    ingredients: list[IngredientRecord] = []
    mapped_count = 0
    unusable_units = 0
    for ingredient_index, ingredient_row in enumerate(ingredient_rows):
        display_name = str(ingredient_row.get("name", "")).strip()
        quantity = _coerce_float(ingredient_row.get("quantity"), default=0.0)
        unit = normalize_unit(str(ingredient_row.get("unit", "")))
        canonical_name = canonical_ingredient_name(display_name)
        metadata = lookup_ingredient_metadata(display_name)
        if metadata is not None:
            mapped_count += 1
            if metadata.supported_units and unit not in metadata.supported_units:
                unusable_units += 1
        if not display_name or quantity <= 0 or not unit:
            reasons.append(f"Ingredient row {ingredient_index + 1} is incomplete.")
            continue
        ingredients.append(
            IngredientRecord(
                ingredient_id=f"{normalize_name(canonical_name).replace(' ', '-')}-{ingredient_index + 1}",
                display_name=display_name,
                canonical_name=canonical_name,
                quantity=quantity,
                unit=unit,
            )
        )

    if ingredient_rows:
        unmapped_fraction = 1.0 - (mapped_count / len(ingredient_rows))
        if unmapped_fraction > config.max_unmapped_ingredient_fraction:
            reasons.append("Too many ingredients could not be mapped to the PantryPilot catalog.")
    if unusable_units:
        reasons.append("One or more ingredient units are unusable for the mapped ingredient catalog entry.")

    if reasons:
        raise RowRejectedError(reasons)

    servings = max(1, int(round(_coerce_float(row.get("servings"), default=1.0))))
    prep_time = int(round(_coerce_float(row.get("prep_time_minutes"), default=0.0)))
    cook_time = int(round(_coerce_float(row.get("cook_time_minutes"), default=0.0)))
    total_time = int(round(_coerce_float(row.get("total_time_minutes"), default=float(prep_time + cook_time))))
    cuisine = normalize_name(str(row.get("cuisine", "") or "unknown"))
    meal_types = parse_csv_list(str(row.get("meal_types", "") or "meal")) or ("meal",)
    diet_tags = frozenset(parse_csv_list(str(row.get("diet_tags", ""))))
    calories_value = row.get("calories_per_serving")
    calories = CalorieEstimate(
        calories_per_serving=None if calories_value in (None, "") else int(round(_coerce_float(calories_value, default=0.0))),
        source="raw-import" if calories_value not in (None, "") else "",
    )
    search_text = " ".join(
        filter(
            None,
            [
                normalize_name(title),
                cuisine,
                " ".join(ingredient.canonical_name for ingredient in ingredients),
                " ".join(meal_types),
            ],
        )
    )
    source = SourceMetadata(
        source_id=normalize_name(raw_file.stem).replace(" ", "-") or "local-import",
        source_name=raw_file.name,
        source_type=raw_file.suffix.lower().lstrip(".") or "local-file",
        file_path=str(raw_file),
    )
    recipe_id = _recipe_id_from_title(title, source_recipe_id)
    return NormalizedRecipe(
        recipe_id=recipe_id,
        title=title,
        source=source,
        source_recipe_id=source_recipe_id,
        cuisine=cuisine,
        meal_types=meal_types,
        diet_tags=diet_tags,
        allergens=allergens,
        ingredients=tuple(ingredients),
        steps=tuple(step_rows),
        servings=servings,
        prep_time_minutes=prep_time,
        cook_time_minutes=cook_time,
        total_time_minutes=total_time,
        calories=calories,
        normalized_search_text=search_text,
    )


def _normalize_kaggle_train_row(
    row: dict,
    raw_file: Path,
    source_recipe_id: str,
    config: ImportConfig,
) -> NormalizedRecipe:
    title = str(row.get("recipe_name", "")).strip()
    ingredient_rows = _parse_kaggle_train_ingredients(str(row.get("ingredients", "")))
    step_rows = tuple(step for step in str(row.get("directions", "")).splitlines() if step.strip())
    cuisine = _derive_cuisine_from_path(str(row.get("cuisine_path", "")))
    meal_types = _derive_meal_types(title, str(row.get("cuisine_path", "")))
    servings = max(1, int(round(_coerce_float(row.get("servings"), default=1.0))))
    prep_time = _parse_time_text(str(row.get("prep_time", "")))
    cook_time = _parse_time_text(str(row.get("cook_time", "")))
    total_time = _parse_time_text(str(row.get("total_time", ""))) or (prep_time + cook_time)
    calories = CalorieEstimate(
        calories_per_serving=_parse_calories_per_serving(str(row.get("nutrition", "")), servings),
        source="kaggle-nutrition" if str(row.get("nutrition", "")).strip() else "",
    )
    return _finalize_normalized_recipe(
        title=title,
        ingredient_rows=ingredient_rows,
        step_rows=step_rows,
        cuisine=cuisine,
        meal_types=meal_types,
        diet_tags=frozenset(),
        calories=calories,
        servings=servings,
        prep_time=prep_time,
        cook_time=cook_time,
        total_time=total_time,
        raw_file=raw_file,
        source_recipe_id=source_recipe_id,
        config=config,
    )


def _normalize_kaggle_test_row(
    row: dict,
    raw_file: Path,
    source_recipe_id: str,
    config: ImportConfig,
) -> NormalizedRecipe:
    title = str(row.get("Name", "")).strip()
    ingredient_rows = _parse_kaggle_test_ingredients(str(row.get("Ingredients", "")))
    step_rows = _parse_python_list_of_strings(str(row.get("Directions", "")))
    meal_types = _derive_meal_types(title, "")
    servings = max(1, int(round(_coerce_float(row.get("Servings"), default=1.0))))
    prep_time = _parse_time_text(str(row.get("Prep Time", "")))
    cook_time = _parse_time_text(str(row.get("Cook Time", "")))
    total_time = _parse_time_text(str(row.get("Total Time", ""))) or (prep_time + cook_time)
    return _finalize_normalized_recipe(
        title=title,
        ingredient_rows=ingredient_rows,
        step_rows=step_rows,
        cuisine="unknown",
        meal_types=meal_types,
        diet_tags=frozenset(),
        calories=CalorieEstimate(calories_per_serving=None),
        servings=servings,
        prep_time=prep_time,
        cook_time=cook_time,
        total_time=total_time,
        raw_file=raw_file,
        source_recipe_id=source_recipe_id,
        config=config,
    )


def _finalize_normalized_recipe(
    *,
    title: str,
    ingredient_rows: tuple[dict, ...],
    step_rows: tuple[str, ...],
    cuisine: str,
    meal_types: tuple[str, ...],
    diet_tags: frozenset[str],
    calories: CalorieEstimate,
    servings: int,
    prep_time: int,
    cook_time: int,
    total_time: int,
    raw_file: Path,
    source_recipe_id: str,
    config: ImportConfig,
) -> NormalizedRecipe:
    reasons: list[str] = []
    if not title:
        reasons.append("Missing title.")
    filtered_ingredient_rows = tuple(
        ingredient_row
        for ingredient_row in ingredient_rows
        if not _should_ignore_import_ingredient(str(ingredient_row.get("name", "")).strip())
    )
    if not filtered_ingredient_rows:
        reasons.append("Missing ingredients.")
    if not step_rows:
        reasons.append("Missing instructions.")
    if not meal_types:
        reasons.append("Meal type could not be mapped to planner meal categories.")

    ingredients: list[IngredientRecord] = []
    mapped_count = 0
    unusable_units = 0
    canonical_names: list[str] = []
    substantial_ingredient_count = 0
    for ingredient_index, ingredient_row in enumerate(filtered_ingredient_rows):
        display_name = str(ingredient_row.get("name", "")).strip()
        quantity = _coerce_float(ingredient_row.get("quantity"), default=0.0)
        resolved = _resolve_catalog_ingredient(display_name)
        canonical_name = resolved[0] if resolved is not None else canonical_ingredient_name(display_name)
        metadata = resolved[1] if resolved is not None else lookup_ingredient_metadata(display_name)
        unit = _normalize_import_unit(str(ingredient_row.get("unit", "")), metadata)
        if metadata is not None:
            mapped_count += 1
            if metadata.supported_units and unit not in metadata.supported_units:
                unusable_units += 1
        if not display_name or quantity <= 0 or not unit:
            reasons.append(f"Ingredient row {ingredient_index + 1} is incomplete.")
            continue
        ingredients.append(
            IngredientRecord(
                ingredient_id=f"{normalize_name(canonical_name).replace(' ', '-')}-{ingredient_index + 1}",
                display_name=display_name,
                canonical_name=canonical_name,
                quantity=quantity,
                unit=unit,
            )
        )
        canonical_names.append(canonical_name)
        if canonical_name not in NON_SUBSTANTIAL_IMPORT_INGREDIENTS:
            substantial_ingredient_count += 1

    if filtered_ingredient_rows:
        unmapped_fraction = 1.0 - (mapped_count / len(filtered_ingredient_rows))
        if unmapped_fraction > config.max_unmapped_ingredient_fraction:
            reasons.append("Too many ingredients could not be mapped to the PantryPilot catalog.")
    if len(ingredients) < 3 or substantial_ingredient_count < 2:
        reasons.append("Imported recipe does not retain enough substantial mapped ingredients.")
    if unusable_units:
        reasons.append("One or more ingredient units are unusable for the mapped ingredient catalog entry.")

    allergens = _derive_catalog_allergen_assessment(tuple(canonical_names))
    if config.reject_unknown_allergens and allergens.completeness is not AllergenCompleteness.COMPLETE:
        reasons.append("Allergen completeness is missing or unsafe.")
    if not diet_tags:
        diet_tags = _derive_catalog_diet_tags(tuple(canonical_names))

    if reasons:
        raise RowRejectedError(reasons)

    search_text = " ".join(
        filter(
            None,
            [
                normalize_name(title),
                cuisine,
                " ".join(canonical_names),
                " ".join(meal_types),
            ],
        )
    )
    source = SourceMetadata(
        source_id=normalize_name(raw_file.stem).replace(" ", "-") or "local-import",
        source_name=raw_file.name,
        source_type=raw_file.suffix.lower().lstrip(".") or "local-file",
        file_path=str(raw_file),
    )
    recipe_id = _recipe_id_from_title(title, source_recipe_id)
    return NormalizedRecipe(
        recipe_id=recipe_id,
        title=title,
        source=source,
        source_recipe_id=source_recipe_id,
        cuisine=cuisine,
        meal_types=meal_types,
        diet_tags=diet_tags,
        allergens=allergens,
        ingredients=tuple(ingredients),
        steps=tuple(step_rows),
        servings=servings,
        prep_time_minutes=prep_time,
        cook_time_minutes=cook_time,
        total_time_minutes=total_time,
        calories=calories,
        normalized_search_text=search_text,
    )


def _recipe_id_from_title(title: str, source_recipe_id: str) -> str:
    title_slug = normalize_name(title).replace(" ", "-")
    source_slug = normalize_name(source_recipe_id).replace(" ", "-")
    return f"{title_slug}-{source_slug}".strip("-")


def _parse_time_text(value: str) -> int:
    text = normalize_name(value)
    if not text:
        return 0
    hours = 0.0
    minutes = 0.0
    hour_match = re.search(r"(\d+(?:\.\d+)?)\s*hr", text)
    minute_match = re.search(r"(\d+(?:\.\d+)?)\s*min", text)
    if hour_match:
        hours = float(hour_match.group(1))
    if minute_match:
        minutes = float(minute_match.group(1))
    if not hour_match and not minute_match:
        return int(round(_coerce_float(text, default=0.0)))
    return int(round((hours * 60) + minutes))


def _parse_calories_per_serving(nutrition_text: str, servings: int) -> int | None:
    normalized = nutrition_text or ""
    calorie_match = re.search(r"calories\s+(\d+)", normalized, flags=re.IGNORECASE)
    if calorie_match:
        return max(0, int(calorie_match.group(1)))
    return None


def _coerce_ingredients(value: object) -> tuple[dict, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return tuple(_ensure_row_dict(item) for item in parsed)
        return ()
    if isinstance(value, list):
        return tuple(_ensure_row_dict(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_ensure_row_dict(item) for item in value)
    return ()


def _parse_kaggle_train_ingredients(value: str) -> tuple[dict, ...]:
    if not value.strip():
        return ()
    fragments = [fragment.strip() for fragment in value.split(",") if fragment.strip()]
    merged: list[str] = []
    for fragment in fragments:
        if _looks_like_new_ingredient_fragment(fragment) or not merged:
            merged.append(fragment)
        else:
            merged[-1] = f"{merged[-1]}, {fragment}"
    ingredient_rows = []
    for fragment in merged:
        parsed = _parse_free_text_ingredient(fragment)
        if parsed is not None:
            ingredient_rows.append(parsed)
    return tuple(ingredient_rows)


def _parse_kaggle_test_ingredients(value: str) -> tuple[dict, ...]:
    rows = _parse_python_list(value)
    ingredient_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        display_name = str(row.get("name", "")).strip()
        quantity = _parse_quantity_text(str(row.get("quantity", "")))
        unit = _normalize_kaggle_unit_text(str(row.get("unit", "")))
        if quantity <= 0 or not display_name:
            continue
        ingredient_rows.append({"name": display_name, "quantity": quantity, "unit": unit})
    return tuple(ingredient_rows)


def _parse_python_list_of_strings(value: str) -> tuple[str, ...]:
    rows = _parse_python_list(value)
    return tuple(str(item).strip() for item in rows if str(item).strip())


def _parse_python_list(value: str) -> list:
    if not value.strip():
        return []
    try:
        parsed = ast.literal_eval(value)
    except (SyntaxError, ValueError):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
    return parsed if isinstance(parsed, list) else []


def _looks_like_new_ingredient_fragment(fragment: str) -> bool:
    normalized = _normalize_fraction_text(fragment)
    return bool(re.match(r"^\s*(optional:)?\s*(\d+|\d+\s+\d+/\d+|\d+/\d+)", normalized, flags=re.IGNORECASE))


def _parse_free_text_ingredient(fragment: str) -> dict | None:
    cleaned = fragment.strip()
    if not cleaned:
        return None
    cleaned = cleaned.replace("Optional:", "").replace("optional:", "").strip()
    cleaned = cleaned.replace("to taste", "").replace("as needed", "").strip(" ,")
    normalized = _normalize_fraction_text(cleaned)
    tokens = normalized.split()
    if not tokens:
        return None

    quantity_token_count = 0
    if tokens and _is_quantity_token(tokens[0]):
        quantity_token_count = 1
        if len(tokens) > 1 and _is_quantity_token(tokens[1]) and "/" in tokens[1]:
            quantity_token_count = 2
    quantity = _parse_quantity_text(" ".join(tokens[:quantity_token_count])) if quantity_token_count else 1.0
    remainder = tokens[quantity_token_count:]
    if not remainder:
        return None
    unit_token_count = 1
    unit = _normalize_kaggle_unit_text(remainder[0])
    for lookahead in (2, 3):
        if len(remainder) >= lookahead:
            candidate_unit = _normalize_kaggle_unit_text(" ".join(remainder[:lookahead]))
            if candidate_unit in {"can", "package"}:
                unit = candidate_unit
                unit_token_count = lookahead
                break
    if unit == "item":
        name_tokens = remainder
    else:
        name_tokens = remainder[unit_token_count:]
    name = " ".join(name_tokens).strip(" -")
    if not name:
        return None
    return {"name": name, "quantity": quantity, "unit": unit}


def _normalize_kaggle_unit_text(unit_text: str) -> str:
    normalized = normalize_name(unit_text)
    if not normalized:
        return "item"
    if "can" in normalized:
        return "can"
    if "package" in normalized:
        return "package"
    if "pinch" in normalized:
        return "pinch"
    if normalized in {"small", "medium", "large", "head"}:
        return "item"
    return normalize_unit(normalized)


def _normalize_import_unit(raw_unit: str, metadata: object | None) -> str:
    unit = normalize_unit(str(raw_unit))
    supported_units = tuple(getattr(metadata, "supported_units", ()))
    if unit:
        if unit == "package" and "block" in supported_units:
            return "block"
        return unit
    if "item" in supported_units:
        return "item"
    return unit


def _should_ignore_import_ingredient(display_name: str) -> bool:
    normalized_name = normalize_name(display_name)
    if normalized_name in IGNORED_IMPORT_INGREDIENTS:
        return True
    if any(phrase in normalized_name for phrase in IGNORED_IMPORT_PHRASES):
        return True
    resolved = _resolve_catalog_ingredient(display_name)
    if resolved is not None and resolved[0] in IGNORED_IMPORT_INGREDIENTS:
        return True
    return False


def _coerce_steps(value: object) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return tuple(str(item).strip() for item in parsed if str(item).strip())
        return ()
    if isinstance(value, list):
        return tuple(str(item).strip() for item in value if str(item).strip())
    if isinstance(value, tuple):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _derive_cuisine_from_path(value: str) -> str:
    parts = [normalize_name(part) for part in value.split("/") if normalize_name(part)]
    for part in parts:
        if part not in GENERIC_CUISINE_SEGMENTS:
            return part
    return "unknown"


def _derive_meal_types(title: str, cuisine_path: str) -> tuple[str, ...]:
    combined = " ".join(filter(None, [normalize_name(title), normalize_name(cuisine_path)]))
    if any(keyword in combined for keyword in MEAL_KEYWORD_GROUPS["dessert"]):
        return ()
    if any(keyword in combined for keyword in MEAL_KEYWORD_GROUPS["drink"]):
        return ()
    if any(keyword in combined for keyword in MEAL_KEYWORD_GROUPS["breakfast"]):
        return ("breakfast",)
    if any(keyword in combined for keyword in MEAL_KEYWORD_GROUPS["lunch"]):
        return ("lunch", "dinner")
    if any(keyword in combined for keyword in MEAL_KEYWORD_GROUPS["dinner"]):
        return ("dinner",)
    return ("dinner",)


def _coerce_allergen_assessment(allergens_value: object, completeness_value: object) -> AllergenAssessment:
    completeness_text = normalize_name(str(completeness_value or "unknown"))
    completeness = {
        "complete": AllergenCompleteness.COMPLETE,
        "partial": AllergenCompleteness.PARTIAL,
        "unknown": AllergenCompleteness.UNKNOWN,
    }.get(completeness_text, AllergenCompleteness.UNKNOWN)

    allergens: frozenset[str] | None
    if allergens_value in (None, ""):
        allergens = frozenset() if completeness is AllergenCompleteness.COMPLETE else None
    elif isinstance(allergens_value, str):
        parsed = None
        try:
            parsed = json.loads(allergens_value)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            allergens = frozenset(normalize_name(str(item)) for item in parsed if normalize_name(str(item)))
        else:
            allergens = frozenset(parse_csv_list(allergens_value))
    elif isinstance(allergens_value, (list, tuple, set, frozenset)):
        allergens = frozenset(normalize_name(str(item)) for item in allergens_value if normalize_name(str(item)))
    else:
        allergens = None

    return AllergenAssessment(
        allergens=allergens,
        completeness=completeness,
        unsafe_if_unknown=True,
    )


def _derive_catalog_allergen_assessment(ingredient_names: tuple[str, ...]) -> AllergenAssessment:
    allergens: set[str] = set()
    for ingredient_name in ingredient_names:
        metadata = lookup_ingredient_metadata(ingredient_name)
        if metadata is None or metadata.allergens is None:
            return AllergenAssessment(
                allergens=None,
                completeness=AllergenCompleteness.UNKNOWN,
                unsafe_if_unknown=True,
            )
        allergens.update(metadata.allergens)
    return AllergenAssessment(
        allergens=frozenset(sorted(allergens)),
        completeness=AllergenCompleteness.COMPLETE,
        unsafe_if_unknown=True,
    )


def _derive_catalog_diet_tags(ingredient_names: tuple[str, ...]) -> frozenset[str]:
    profiles = []
    for ingredient_name in ingredient_names:
        metadata = lookup_ingredient_metadata(ingredient_name)
        if metadata is None or metadata.allergens is None:
            return frozenset()
        profiles.append(metadata)
    tags: set[str] = set()
    if profiles and all(not profile.diet_flags.meat for profile in profiles):
        tags.add("vegetarian")
    if profiles and all(not profile.diet_flags.meat and not profile.diet_flags.animal_product for profile in profiles):
        tags.add("vegan")
    if profiles and all("gluten" not in profile.allergens for profile in profiles):
        tags.add("gluten-free")
    if profiles and all("dairy" not in profile.allergens for profile in profiles):
        tags.add("dairy-free")
    return frozenset(sorted(tags))


def _coerce_float(value: object, *, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_quantity_text(value: str) -> float:
    text = _normalize_fraction_text(value).strip()
    if not text:
        return 0.0
    if re.match(r"^\d+\s+\d+/\d+$", text):
        whole, fraction = text.split()
        numerator, denominator = fraction.split("/")
        return float(whole) + (float(numerator) / float(denominator))
    if re.match(r"^\d+/\d+$", text):
        numerator, denominator = text.split("/")
        return float(numerator) / float(denominator)
    try:
        return float(text)
    except ValueError:
        return 0.0


def _normalize_fraction_text(value: str) -> str:
    normalized = value
    for source, target in UNICODE_FRACTIONS.items():
        normalized = normalized.replace(source, f" {target} ")
    return " ".join(normalized.split())


def _is_quantity_token(token: str) -> bool:
    return bool(re.match(r"^\d+$|^\d+/\d+$", token))


def _resolve_catalog_ingredient(display_name: str) -> tuple[str, object] | None:
    for variant in _ingredient_lookup_variants(display_name):
        metadata = lookup_ingredient_metadata(variant)
        if metadata is not None:
            return metadata.canonical_name, metadata

    best_match: tuple[str, object, int] | None = None
    for variant in _ingredient_lookup_variants(display_name):
        variant_tokens = tuple(variant.split())
        for entry in ingredient_catalog_entries():
            candidate_names = (entry.canonical_name, *entry.aliases)
            for candidate_name in candidate_names:
                normalized_candidate = normalize_name(candidate_name)
                candidate_tokens = tuple(normalized_candidate.split())
                if len(candidate_tokens) < 2:
                    continue
                if _contains_token_sequence(variant_tokens, candidate_tokens):
                    score = len(candidate_tokens)
                    if best_match is None or score > best_match[2]:
                        best_match = (entry.canonical_name, entry, score)
    if best_match is None:
        return None
    return best_match[0], best_match[1]


def _ingredient_lookup_variants(display_name: str) -> tuple[str, ...]:
    normalized = normalize_name(display_name)
    if not normalized:
        return ()
    variants = [normalized]
    no_commas = normalized.replace(",", " ")
    variants.append(" ".join(no_commas.split()))
    stripped_tokens = [
        token
        for token in no_commas.split()
        if token
        not in {
            "and",
            "boneless",
            "broken",
            "chunks",
            "cut",
            "diced",
            "divided",
            "drained",
            "fresh",
            "ground",
            "halves",
            "into",
            "large",
            "matchsticks",
            "minced",
            "skinless",
            "sliced",
            "thinly",
            "to",
        }
    ]
    if stripped_tokens:
        variants.append(" ".join(stripped_tokens))
    unique_variants: list[str] = []
    for variant in variants:
        cleaned = " ".join(variant.split())
        if cleaned and cleaned not in unique_variants:
            unique_variants.append(cleaned)
    return tuple(unique_variants)


def _contains_token_sequence(haystack: tuple[str, ...], needle: tuple[str, ...]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    for index in range(len(haystack) - len(needle) + 1):
        if haystack[index : index + len(needle)] == needle:
            return True
    return False


def _recipe_to_dict(recipe: NormalizedRecipe) -> dict:
    payload = asdict(recipe)
    payload["diet_tags"] = sorted(recipe.diet_tags)
    payload["allergens"]["allergens"] = None if recipe.allergens.allergens is None else sorted(recipe.allergens.allergens)
    return payload


def _build_import_stats(
    raw_count: int,
    imported_recipes: tuple[NormalizedRecipe, ...],
    rejections: list[ImportRejection],
    source_names: tuple[str, ...] = (),
) -> dict:
    reason_counts: dict[str, int] = {}
    for rejection in rejections:
        for reason in rejection.reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    ordered_reasons = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    meal_type_counts: dict[str, int] = {}
    cuisine_counts: dict[str, int] = {}
    for recipe in imported_recipes:
        for meal_type in recipe.meal_types:
            meal_type_counts[meal_type] = meal_type_counts.get(meal_type, 0) + 1
        cuisine_counts[recipe.cuisine] = cuisine_counts.get(recipe.cuisine, 0) + 1
    return {
        "sources": list(source_names),
        "raw_count": raw_count,
        "accepted_count": len(imported_recipes),
        "rejected_count": len(rejections),
        "common_reject_reasons": ordered_reasons,
        "meal_type_distribution": [
            {"meal_type": meal_type, "count": count}
            for meal_type, count in sorted(meal_type_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "cuisine_distribution": [
            {"cuisine": cuisine, "count": count}
            for cuisine, count in sorted(cuisine_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
    }
