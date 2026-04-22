from __future__ import annotations

import ast
import csv
import ctypes
import json
import os
import re
import time
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
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
DEFAULT_KAGGLE_PROCESSED_FILENAME = "kaggle-recipes.imported.json"
DEFAULT_RECIPE_NLG_PROCESSED_FILENAME = "recipenlg.imported.json"
DEFAULT_RECIPE_NLG_MAX_OUTPUT_RECIPES = 500
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
    "breakfast": ("breakfast", "brunch", "pancake", "pancakes", "waffle", "waffles", "oatmeal", "omelet", "omelette", "scramble", "parfait", "smoothie", "muffin", "muffins"),
    "dessert": ("dessert", "desserts", "cookie", "cake", "pie", "brownie", "cobbler", "ice cream", "frosting"),
    "drink": ("drink", "drinks", "beverage", "cocktail", "smoothie bowl", "tea"),
    "lunch": ("lunch", "sandwich", "wrap", "salad"),
    "dinner": ("dinner", "main dish", "main dishes", "bowl", "pasta", "skillet", "soup", "stew", "chili", "curry", "stir fry"),
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
    max_output_recipes: int | None = None
    max_recorded_rejections: int = 500
    row_limit: int | None = None
    progress_every_rows: int = 100_000
    checkpoint_every_rows: int = 100_000


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


def _is_recipenlg_schema(row: dict) -> bool:
    return "title" in row and "ingredients" in row and "directions" in row and "NER" in row and "link" in row


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
        processed_path=(
            processed_path
            if processed_path is not None
            else _default_processed_dir_for(paths[0]) / DEFAULT_KAGGLE_PROCESSED_FILENAME
        ),
        config=config,
    )


def import_recipenlg_dataset(
    raw_path: str | Path,
    *,
    processed_path: str | Path | None = None,
    config: ImportConfig | None = None,
) -> ImportResult:
    raw_file = Path(raw_path)
    active_config = config or ImportConfig()
    output_file = (
        Path(processed_path)
        if processed_path is not None
        else _default_processed_dir_for(raw_file) / DEFAULT_RECIPE_NLG_PROCESSED_FILENAME
    )
    stats_file = output_file.with_suffix(".stats.json")
    checkpoint_file = output_file.with_suffix(".checkpoint.json")
    lock_path, run_id = _acquire_import_lock(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_cap = (
        active_config.max_output_recipes
        if active_config.max_output_recipes is not None
        else DEFAULT_RECIPE_NLG_MAX_OUTPUT_RECIPES
    )
    accepted_total = 0
    raw_count = 0
    reason_counts: dict[str, int] = {}
    recorded_rejections: list[ImportRejection] = []
    imported_recipes: list[NormalizedRecipe] = []
    started_at = _utcnow()
    print(
        "RecipeNLG import started:",
        json.dumps(
            {
                "run_id": run_id,
                "source": str(raw_file),
                "output_path": str(output_file),
                "stats_path": str(stats_file),
                "checkpoint_path": str(checkpoint_file),
                "row_limit": active_config.row_limit,
            }
        ),
        flush=True,
    )

    try:
        with raw_file.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader):
                if active_config.row_limit is not None and raw_count >= active_config.row_limit:
                    break
                raw_count += 1
                source_recipe_id, title = _extract_row_identity(dict(row), index)
                try:
                    normalized = _normalize_row(dict(row), raw_file, source_recipe_id, active_config)
                except RowRejectedError as exc:
                    for reason in exc.reasons:
                        reason_counts[reason] = reason_counts.get(reason, 0) + 1
                    if len(recorded_rejections) < active_config.max_recorded_rejections:
                        recorded_rejections.append(
                            ImportRejection(
                                source_recipe_id=source_recipe_id,
                                title=title,
                                reasons=tuple(exc.reasons),
                            )
                        )
                    _maybe_report_recipenlg_progress(raw_count, accepted_total, active_config)
                    _maybe_write_recipenlg_checkpoint(
                        checkpoint_file=checkpoint_file,
                        config=active_config,
                        raw_count=raw_count,
                        accepted_count=accepted_total,
                        written_count=len(imported_recipes),
                        imported_recipes=tuple(imported_recipes),
                        reason_counts=reason_counts,
                        source_names=(raw_file.name,),
                        run_id=run_id,
                        started_at=started_at,
                        output_file=output_file,
                    )
                    continue

                accepted_total += 1
                if len(imported_recipes) < output_cap:
                    imported_recipes.append(normalized)
                _maybe_report_recipenlg_progress(raw_count, accepted_total, active_config)
                _maybe_write_recipenlg_checkpoint(
                    checkpoint_file=checkpoint_file,
                    config=active_config,
                    raw_count=raw_count,
                    accepted_count=accepted_total,
                    written_count=len(imported_recipes),
                    imported_recipes=tuple(imported_recipes),
                    reason_counts=reason_counts,
                    source_names=(raw_file.name,),
                    run_id=run_id,
                    started_at=started_at,
                    output_file=output_file,
                )

        _write_recipenlg_stage_checkpoint(
            checkpoint_file=checkpoint_file,
            raw_count=raw_count,
            accepted_count=accepted_total,
            written_count=len(imported_recipes),
            imported_recipes=tuple(imported_recipes),
            reason_counts=reason_counts,
            source_names=(raw_file.name,),
            run_id=run_id,
            started_at=started_at,
            output_file=output_file,
            row_limit=active_config.row_limit,
            stage="building_diversity_metadata",
        )
        print(
            "RecipeNLG finalizing:",
            json.dumps({"stage": "building_diversity_metadata", "recipes": len(imported_recipes)}),
            flush=True,
        )
        enriched_recipes = tuple(
            replace(recipe, diversity=build_diversity_metadata(recipe))
            for recipe in imported_recipes
        )
        _write_recipenlg_stage_checkpoint(
            checkpoint_file=checkpoint_file,
            raw_count=raw_count,
            accepted_count=accepted_total,
            written_count=len(imported_recipes),
            imported_recipes=enriched_recipes,
            reason_counts=reason_counts,
            source_names=(raw_file.name,),
            run_id=run_id,
            started_at=started_at,
            output_file=output_file,
            row_limit=active_config.row_limit,
            stage="annotating_similarity",
        )
        print(
            "RecipeNLG finalizing:",
            json.dumps({"stage": "annotating_similarity", "recipes": len(enriched_recipes)}),
            flush=True,
        )
        clustered_recipes = annotate_recipe_similarity(
            enriched_recipes,
            progress_every_recipes=500,
            progress_callback=lambda event: print("RecipeNLG similarity progress:", json.dumps(event), flush=True),
        )
        payload = {"recipes": [_recipe_to_dict(recipe) for recipe in clustered_recipes]}
        stats = _build_streaming_import_stats(
            raw_count=raw_count,
            accepted_count=accepted_total,
            written_count=len(clustered_recipes),
            imported_recipes=clustered_recipes,
            reason_counts=reason_counts,
            source_names=(raw_file.name,),
        )
        stats.update(
            {
                "status": "completed",
                "run_id": run_id,
                "started_at": started_at,
                "completed_at": _utcnow(),
                "row_limit": active_config.row_limit,
                "checkpoint_path": str(checkpoint_file),
            }
        )
        checkpoint_payload = dict(stats)
        checkpoint_payload["status"] = "completed"
        checkpoint_payload["stage"] = "completed"
        checkpoint_payload["output_path"] = str(output_file)
        _write_recipenlg_stage_checkpoint(
            checkpoint_file=checkpoint_file,
            raw_count=raw_count,
            accepted_count=accepted_total,
            written_count=len(clustered_recipes),
            imported_recipes=tuple(clustered_recipes),
            reason_counts=reason_counts,
            source_names=(raw_file.name,),
            run_id=run_id,
            started_at=started_at,
            output_file=output_file,
            row_limit=active_config.row_limit,
            stage="validating_collection",
        )
        print(
            "RecipeNLG finalizing:",
            json.dumps({"stage": "validating_collection", "recipes": len(clustered_recipes)}),
            flush=True,
        )
        validation_issues = validate_recipe_collection(tuple(clustered_recipes))
        _write_recipenlg_stage_checkpoint(
            checkpoint_file=checkpoint_file,
            raw_count=raw_count,
            accepted_count=accepted_total,
            written_count=len(clustered_recipes),
            imported_recipes=tuple(clustered_recipes),
            reason_counts=reason_counts,
            source_names=(raw_file.name,),
            run_id=run_id,
            started_at=started_at,
            output_file=output_file,
            row_limit=active_config.row_limit,
            stage="writing_output_files",
        )
        print(
            "RecipeNLG finalizing:",
            json.dumps(
                {
                    "stage": "writing_output_files",
                    "recipes": len(clustered_recipes),
                    "output_path": str(output_file),
                }
            ),
            flush=True,
        )
        _write_json_atomic(output_file, payload)
        _write_json_atomic(stats_file, stats)
        _write_json_atomic(checkpoint_file, checkpoint_payload)
        return ImportResult(
            imported_recipes=tuple(clustered_recipes),
            rejected_rows=tuple(recorded_rejections),
            output_path=str(output_file),
            stats_path=str(stats_file),
            stats=stats,
            validation_issues=validation_issues,
        )
    except Exception as exc:
        failure_stats = _build_streaming_import_stats(
            raw_count=raw_count,
            accepted_count=accepted_total,
            written_count=len(imported_recipes),
            imported_recipes=tuple(imported_recipes),
            reason_counts=reason_counts,
            source_names=(raw_file.name,),
        )
        failure_stats.update(
            {
                "status": "failed",
                "stage": "failed",
                "run_id": run_id,
                "started_at": started_at,
                "failed_at": _utcnow(),
                "row_limit": active_config.row_limit,
                "output_path": str(output_file),
                "error": str(exc),
            }
        )
        _write_json_atomic(checkpoint_file, failure_stats)
        raise
    finally:
        _release_import_lock(lock_path)


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
    if _is_recipenlg_schema(row):
        source_recipe_id = str(row.get("") or row.get("link") or f"row-{index + 1}").strip()
        title = str(row.get("title", "")).strip()
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
    if _is_recipenlg_schema(row):
        return _normalize_recipenlg_row(row, raw_file, source_recipe_id, config)

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


def _normalize_recipenlg_row(
    row: dict,
    raw_file: Path,
    source_recipe_id: str,
    config: ImportConfig,
) -> NormalizedRecipe:
    title = str(row.get("title", "")).strip()
    ingredient_rows = _parse_recipenlg_ingredients(str(row.get("ingredients", "")), str(row.get("NER", "")))
    step_rows = _parse_python_list_of_strings(str(row.get("directions", "")))
    meal_types = _derive_recipenlg_meal_types(title, step_rows)
    servings = _derive_servings_from_steps(step_rows)
    return _finalize_normalized_recipe(
        title=title,
        ingredient_rows=ingredient_rows,
        step_rows=step_rows,
        cuisine=_derive_cuisine_from_text(title),
        meal_types=meal_types,
        diet_tags=frozenset(),
        calories=CalorieEstimate(calories_per_serving=None),
        servings=servings,
        prep_time=0,
        cook_time=0,
        total_time=0,
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
        catalog_hint = str(ingredient_row.get("catalog_hint", "")).strip()
        resolved = _resolve_catalog_ingredient(catalog_hint or display_name)
        canonical_name = resolved[0] if resolved is not None else canonical_ingredient_name(display_name)
        metadata = resolved[1] if resolved is not None else lookup_ingredient_metadata(catalog_hint or display_name)
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


def _parse_recipenlg_ingredients(ingredients_value: str, ner_value: str) -> tuple[dict, ...]:
    ingredient_rows = _parse_python_list(ingredients_value)
    ner_rows = tuple(
        str(item).strip()
        for item in _parse_python_list(ner_value)
        if isinstance(item, str) and str(item).strip()
    )
    parsed_rows: list[dict] = []
    for index, row in enumerate(ingredient_rows):
        if not isinstance(row, str):
            continue
        parsed = _parse_free_text_ingredient(row)
        if parsed is None:
            parsed = {"name": row.strip(), "quantity": 1.0, "unit": "item"}
        catalog_hint = _resolve_recipenlg_catalog_hint(row, ner_rows, index)
        if catalog_hint:
            parsed["catalog_hint"] = catalog_hint
        parsed_rows.append(parsed)
    return tuple(parsed_rows)


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
    cleaned = re.sub(r"\(\s*\d+[^\)]*\)", " ", cleaned)
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
    unit, unit_token_count = _extract_unit_from_tokens(remainder)
    if unit == "item":
        name_tokens = remainder
        if unit_token_count:
            name_tokens = remainder[unit_token_count:]
    else:
        name_tokens = remainder[unit_token_count:]
    name = " ".join(name_tokens).strip(" -")
    if not name:
        return None
    return {"name": name, "quantity": quantity, "unit": unit}


def _extract_unit_from_tokens(tokens: list[str]) -> tuple[str, int]:
    if not tokens:
        return "item", 0
    normalized_tokens = [normalize_name(token) for token in tokens]
    container_tokens = {
        "bag",
        "bags",
        "bottle",
        "bottles",
        "box",
        "boxes",
        "carton",
        "cartons",
        "envelope",
        "envelopes",
        "jar",
        "jars",
        "package",
        "packages",
        "pkg",
        "pkgs",
    }
    size_tokens = {"small", "medium", "large"}
    if len(normalized_tokens) >= 2 and normalized_tokens[0] in size_tokens and normalized_tokens[1] in container_tokens:
        return "item", 2
    if normalized_tokens[0] in container_tokens:
        return "item", 1
    unit_token_count = 1
    unit = _normalize_kaggle_unit_text(tokens[0])
    for lookahead in (3, 2):
        if len(tokens) >= lookahead:
            candidate_unit = _normalize_kaggle_unit_text(" ".join(tokens[:lookahead]))
            if candidate_unit != "item" or normalize_name(tokens[lookahead - 1]) in container_tokens:
                return candidate_unit, lookahead
    return unit, unit_token_count


def _normalize_kaggle_unit_text(unit_text: str) -> str:
    normalized = normalize_name(unit_text)
    if not normalized:
        return "item"
    if "fluid ounce" in normalized or re.search(r"\b\d+\s*ounce\b", normalized):
        return "oz"
    if normalized in {"c", "cupful"}:
        return "cup"
    if normalized in {"pkg", "pkgs", "package", "packages"}:
        return "package"
    if "can" in normalized:
        return "can"
    if "package" in normalized:
        return "package"
    if "pinch" in normalized:
        return "pinch"
    if normalized in {"jar", "jars", "carton", "cartons", "box", "boxes", "bottle", "bottles", "bag", "bags", "envelope", "envelopes"}:
        return "item"
    if normalized in {"wedge", "wedges", "inch", "inches"}:
        return "item"
    if normalized in {"small", "medium", "large", "head"}:
        return "item"
    canonical = normalize_unit(normalized)
    if canonical in {"block", "can", "clove", "cup", "item", "lb", "oz", "package", "pinch", "slice", "stalk", "tbsp", "tsp"}:
        return canonical
    return "item"


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
    normalized_path = normalize_name(cuisine_path)
    if any(
        label in normalized_path
        for label in (
            "applesauce recipes",
            "crisps and crumbles recipes",
            "dips and spreads recipes",
            "sauces and condiments",
            "sauces",
        )
    ):
        return ()
    if any(
        label in normalized_path
        for label in (
            "breakfast and brunch",
            "breakfast bread recipes",
            "muffin recipes",
            "pancake recipes",
            "quick bread recipes",
            "smoothie recipes",
        )
    ):
        return ("breakfast",)
    if _contains_meal_keyword(combined, MEAL_KEYWORD_GROUPS["dessert"]):
        return ()
    if _contains_meal_keyword(combined, MEAL_KEYWORD_GROUPS["breakfast"]):
        return ("breakfast",)
    if _contains_meal_keyword(combined, MEAL_KEYWORD_GROUPS["drink"]):
        return ()
    if _contains_meal_keyword(combined, MEAL_KEYWORD_GROUPS["lunch"]):
        return ("lunch", "dinner")
    if _contains_meal_keyword(combined, MEAL_KEYWORD_GROUPS["dinner"]):
        return ("dinner",)
    return ()


def _derive_recipenlg_meal_types(title: str, steps: tuple[str, ...]) -> tuple[str, ...]:
    combined = " ".join(filter(None, [normalize_name(title), " ".join(normalize_name(step) for step in steps[:2])]))
    if _contains_meal_keyword(combined, MEAL_KEYWORD_GROUPS["dessert"]):
        return ()
    if _contains_meal_keyword(combined, MEAL_KEYWORD_GROUPS["drink"]):
        return ()
    if _contains_meal_keyword(combined, MEAL_KEYWORD_GROUPS["breakfast"]):
        return ("breakfast",)
    if _contains_meal_keyword(combined, MEAL_KEYWORD_GROUPS["lunch"]):
        return ("lunch", "dinner")
    return ("dinner",)


def _contains_meal_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    tokens = tuple(normalize_name(text).split())
    for keyword in keywords:
        keyword_tokens = tuple(normalize_name(keyword).split())
        if _contains_token_sequence(tokens, keyword_tokens):
            return True
    return False


def _derive_cuisine_from_text(title: str) -> str:
    normalized_title = normalize_name(title)
    cuisine_keywords = (
        ("italian", "italian"),
        ("mexican", "mexican"),
        ("greek", "greek"),
        ("indian", "indian"),
        ("thai", "thai"),
        ("chinese", "chinese"),
        ("japanese", "japanese"),
        ("mediterranean", "mediterranean"),
        ("french", "french"),
        ("american", "american"),
    )
    for keyword, cuisine in cuisine_keywords:
        if keyword in normalized_title:
            return cuisine
    return "unknown"


def _derive_servings_from_steps(steps: tuple[str, ...]) -> int:
    combined = " ".join(steps)
    patterns = (
        r"\b(?:yield|yields|yielding)\s+(\d+)\b",
        r"\bserves?\s+(\d+)\b",
        r"\bmakes?\s+(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, combined, flags=re.IGNORECASE)
        if match:
            return max(1, int(match.group(1)))
    return 4


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


def _resolve_recipenlg_catalog_hint(
    ingredient_text: str,
    ner_rows: tuple[str, ...],
    index: int,
) -> str:
    if index < len(ner_rows):
        return ner_rows[index]
    normalized_ingredient = normalize_name(ingredient_text)
    best_hint = ""
    best_length = 0
    for ner_value in ner_rows:
        normalized_ner = normalize_name(ner_value)
        if not normalized_ner:
            continue
        if normalized_ner in normalized_ingredient or _contains_token_sequence(
            tuple(normalized_ingredient.split()),
            tuple(normalized_ner.split()),
        ):
            if len(normalized_ner.split()) > best_length:
                best_hint = ner_value
                best_length = len(normalized_ner.split())
    return best_hint


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
            "beaten",
            "bite",
            "bite-size",
            "bite-sized",
            "boneless",
            "broken",
            "chopped",
            "cooked",
            "cored",
            "cubed",
            "chunks",
            "cut",
            "diced",
            "divided",
            "drained",
            "extra",
            "fresh",
            "finely",
            "frozen",
            "ground",
            "halves",
            "into",
            "large",
            "matchsticks",
            "melted",
            "minced",
            "more",
            "or",
            "packed",
            "peeled",
            "pieces",
            "pitted",
            "pounded",
            "quartered",
            "reduced",
            "seeded",
            "sodium",
            "skinless",
            "sliced",
            "softened",
            "such",
            "sweet",
            "tart",
            "thinly",
            "to",
            "virgin",
            "with",
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


def _build_streaming_import_stats(
    *,
    raw_count: int,
    accepted_count: int,
    written_count: int,
    imported_recipes: tuple[NormalizedRecipe, ...],
    reason_counts: dict[str, int],
    source_names: tuple[str, ...] = (),
) -> dict:
    meal_type_counts: dict[str, int] = {}
    cuisine_counts: dict[str, int] = {}
    for recipe in imported_recipes:
        for meal_type in recipe.meal_types:
            meal_type_counts[meal_type] = meal_type_counts.get(meal_type, 0) + 1
        cuisine_counts[recipe.cuisine] = cuisine_counts.get(recipe.cuisine, 0) + 1
    ordered_reasons = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "sources": list(source_names),
        "raw_count": raw_count,
        "accepted_count": accepted_count,
        "written_count": written_count,
        "rejected_count": raw_count - accepted_count,
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


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _import_lock_path(output_file: Path) -> Path:
    return output_file.with_suffix(".lock.json")


def _is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _is_pid_running_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _is_pid_running_windows(pid: int) -> bool:
    process_query_limited_information = 0x1000
    still_active = 259
    error_invalid_parameter = 87
    error_access_denied = 5
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.GetExitCodeProcess.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))
    kernel32.GetExitCodeProcess.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int

    handle = kernel32.OpenProcess(process_query_limited_information, 0, pid)
    if not handle:
        error_code = ctypes.get_last_error()
        if error_code == error_invalid_parameter:
            return False
        if error_code == error_access_denied:
            return True
        return True

    try:
        exit_code = ctypes.c_uint32()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return True
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _acquire_import_lock(output_file: Path) -> tuple[Path, str]:
    lock_path = _import_lock_path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:12]
    lock_payload = {
        "run_id": run_id,
        "pid": os.getpid(),
        "started_at": _utcnow(),
        "output_path": str(output_file),
    }
    while True:
        try:
            with lock_path.open("x", encoding="utf-8") as handle:
                json.dump(lock_payload, handle, indent=2)
            return lock_path, run_id
        except FileExistsError:
            existing = _read_existing_lock(lock_path)
            existing_pid = existing.get("pid")
            if isinstance(existing_pid, int) and _is_pid_running(existing_pid):
                raise RuntimeError(
                    f"Another RecipeNLG import appears active for {output_file}. "
                    f"Lock file: {lock_path}"
                )
            stale_path = lock_path.with_name(f"{lock_path.stem}.stale-{int(time.time())}{lock_path.suffix}")
            lock_path.replace(stale_path)


def _read_existing_lock(lock_path: Path) -> dict:
    try:
        return json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _release_import_lock(lock_path: Path) -> None:
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return


def _write_json_atomic(path: Path, payload: object) -> None:
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _maybe_report_recipenlg_progress(raw_count: int, accepted_count: int, config: ImportConfig) -> None:
    if config.progress_every_rows <= 0:
        return
    if raw_count % config.progress_every_rows != 0:
        return
    print(
        "RecipeNLG progress:",
        json.dumps(
            {
                "rows_scanned": raw_count,
                "accepted_count": accepted_count,
                "rejected_count": raw_count - accepted_count,
            }
        ),
        flush=True,
    )


def _maybe_write_recipenlg_checkpoint(
    *,
    checkpoint_file: Path,
    config: ImportConfig,
    raw_count: int,
    accepted_count: int,
    written_count: int,
    imported_recipes: tuple[NormalizedRecipe, ...],
    reason_counts: dict[str, int],
    source_names: tuple[str, ...],
    run_id: str,
    started_at: str,
    output_file: Path,
) -> None:
    if config.checkpoint_every_rows <= 0:
        return
    if raw_count % config.checkpoint_every_rows != 0:
        return
    checkpoint_stats = _build_streaming_import_stats(
        raw_count=raw_count,
        accepted_count=accepted_count,
        written_count=written_count,
        imported_recipes=imported_recipes,
        reason_counts=reason_counts,
        source_names=source_names,
    )
    checkpoint_stats.update(
        {
            "status": "running",
            "stage": "streaming_rows",
            "run_id": run_id,
            "started_at": started_at,
            "updated_at": _utcnow(),
            "row_limit": config.row_limit,
            "output_path": str(output_file),
        }
    )
    _write_json_atomic(checkpoint_file, checkpoint_stats)


def _write_recipenlg_stage_checkpoint(
    *,
    checkpoint_file: Path,
    raw_count: int,
    accepted_count: int,
    written_count: int,
    imported_recipes: tuple[NormalizedRecipe, ...],
    reason_counts: dict[str, int],
    source_names: tuple[str, ...],
    run_id: str,
    started_at: str,
    output_file: Path,
    row_limit: int | None,
    stage: str,
) -> None:
    checkpoint_stats = _build_streaming_import_stats(
        raw_count=raw_count,
        accepted_count=accepted_count,
        written_count=written_count,
        imported_recipes=imported_recipes,
        reason_counts=reason_counts,
        source_names=source_names,
    )
    checkpoint_stats.update(
        {
            "status": "running",
            "stage": stage,
            "run_id": run_id,
            "started_at": started_at,
            "updated_at": _utcnow(),
            "row_limit": row_limit,
            "output_path": str(output_file),
        }
    )
    _write_json_atomic(checkpoint_file, checkpoint_stats)
