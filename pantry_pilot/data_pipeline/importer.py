from __future__ import annotations

import csv
import json
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
from pantry_pilot.ingredient_catalog import canonical_ingredient_name, lookup_ingredient_metadata
from pantry_pilot.normalization import normalize_name, normalize_unit, parse_csv_list


DEFAULT_PROCESSED_FILENAME = "recipes.imported.json"


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


def import_recipes_from_file(
    raw_path: str | Path,
    *,
    processed_path: str | Path | None = None,
    config: ImportConfig | None = None,
) -> ImportResult:
    raw_file = Path(raw_path)
    active_config = config or ImportConfig()
    raw_rows = _load_raw_rows(raw_file)
    recipes, rejections = _normalize_rows(raw_rows, raw_file, active_config)

    enriched_recipes = tuple(
        replace(recipe, diversity=build_diversity_metadata(recipe))
        for recipe in recipes
    )
    clustered_recipes = annotate_recipe_similarity(enriched_recipes)

    output_file = Path(processed_path) if processed_path is not None else raw_file.parent.parent / "processed" / DEFAULT_PROCESSED_FILENAME
    output_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {"recipes": [_recipe_to_dict(recipe) for recipe in clustered_recipes]}
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    stats_file = output_file.with_suffix(".stats.json")
    stats = _build_import_stats(raw_rows, clustered_recipes, rejections)
    stats_file.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    validation_issues = validate_recipe_collection(tuple(clustered_recipes))
    return ImportResult(
        imported_recipes=tuple(clustered_recipes),
        rejected_rows=tuple(rejections),
        output_path=str(output_file),
        stats_path=str(stats_file),
        stats=stats,
        validation_issues=validation_issues,
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
        source_recipe_id = str(row.get("source_recipe_id") or row.get("recipe_id") or f"row-{index + 1}").strip()
        title = str(row.get("title", "")).strip()
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


def _normalize_row(
    row: dict,
    raw_file: Path,
    source_recipe_id: str,
    config: ImportConfig,
) -> NormalizedRecipe:
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


def _recipe_id_from_title(title: str, source_recipe_id: str) -> str:
    title_slug = normalize_name(title).replace(" ", "-")
    source_slug = normalize_name(source_recipe_id).replace(" ", "-")
    return f"{title_slug}-{source_slug}".strip("-")


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


def _coerce_float(value: object, *, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _recipe_to_dict(recipe: NormalizedRecipe) -> dict:
    payload = asdict(recipe)
    payload["diet_tags"] = sorted(recipe.diet_tags)
    payload["allergens"]["allergens"] = None if recipe.allergens.allergens is None else sorted(recipe.allergens.allergens)
    return payload


def _build_import_stats(
    raw_rows: tuple[dict, ...],
    imported_recipes: tuple[NormalizedRecipe, ...],
    rejections: list[ImportRejection],
) -> dict:
    reason_counts: dict[str, int] = {}
    for rejection in rejections:
        for reason in rejection.reasons:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    ordered_reasons = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "raw_count": len(raw_rows),
        "accepted_count": len(imported_recipes),
        "rejected_count": len(rejections),
        "common_reject_reasons": ordered_reasons,
    }
