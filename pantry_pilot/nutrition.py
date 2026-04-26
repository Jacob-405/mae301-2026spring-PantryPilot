from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from pantry_pilot.ingredient_catalog import canonical_ingredient_name
from pantry_pilot.usda_build import (
    USDA_RUNTIME_MANIFEST_PATH as USDA_FULL_MANIFEST_PATH,
    USDA_RUNTIME_MAPPINGS_PATH as USDA_FULL_MAPPINGS_PATH,
    USDA_RUNTIME_RECORDS_PATH as USDA_FULL_RECORDS_PATH,
)


@dataclass(frozen=True)
class IngredientNutritionRecord:
    key: str
    reference_unit: str
    calories: float
    protein_grams: float
    carbs_grams: float
    fat_grams: float
    source: str = "local-offline"
    source_dataset: str = ""
    source_food_id: int | None = None
    source_description: str = ""
    source_release: str = ""
    pilot: bool = False


@dataclass(frozen=True)
class IngredientGuidanceRecord:
    canonical_ingredient: str
    food_group_tags: frozenset[str]
    component_tags: frozenset[str]
    source: str = "myplate-guidance"
    notes: str = ""


DATA_DIR = Path(__file__).resolve().parent / "data"
USDA_RUNTIME_MANIFEST_PATH = USDA_FULL_MANIFEST_PATH
USDA_RUNTIME_RECORDS_PATH = USDA_FULL_RECORDS_PATH
USDA_RUNTIME_MAPPINGS_PATH = USDA_FULL_MAPPINGS_PATH
USDA_PILOT_MANIFEST_PATH = DATA_DIR / "usda_nutrition_pilot_manifest.json"
USDA_PILOT_RECORDS_PATH = DATA_DIR / "usda_nutrition_pilot_records.json"
USDA_PILOT_MAPPINGS_PATH = DATA_DIR / "usda_nutrition_pilot_mappings.json"
USDA_MEAL_GUIDANCE_PATH = DATA_DIR / "usda_meal_guidance_tags.json"


_HEURISTIC_NUTRITION_RECORDS: tuple[IngredientNutritionRecord, ...] = (
    IngredientNutritionRecord("apple", "item", 95.0, 0.5, 25.1, 0.3),
    IngredientNutritionRecord("avocado", "item", 240.0, 3.0, 12.8, 22.0),
    IngredientNutritionRecord("banana", "item", 105.0, 1.3, 27.0, 0.4),
    IngredientNutritionRecord("balsamic vinegar", "tbsp", 14.0, 0.1, 2.7, 0.0),
    IngredientNutritionRecord("bell pepper", "item", 31.0, 1.0, 7.0, 0.3),
    IngredientNutritionRecord("black beans", "can", 227.0, 15.2, 40.8, 0.9),
    IngredientNutritionRecord("black pepper", "tsp", 5.0, 0.2, 1.3, 0.1),
    IngredientNutritionRecord("blueberries", "cup", 85.0, 1.1, 21.4, 0.5),
    IngredientNutritionRecord("bread", "slice", 80.0, 3.0, 14.0, 1.0),
    IngredientNutritionRecord("bread crumbs", "cup", 427.0, 14.0, 78.0, 5.0),
    IngredientNutritionRecord("broccoli", "cup", 31.0, 2.5, 6.0, 0.3),
    IngredientNutritionRecord("butter", "tbsp", 102.0, 0.1, 0.0, 11.5),
    IngredientNutritionRecord("buttermilk", "cup", 152.0, 8.1, 11.7, 8.1),
    IngredientNutritionRecord("canned tomatoes", "can", 90.0, 4.0, 20.0, 0.6),
    IngredientNutritionRecord("carrot", "item", 25.0, 0.6, 6.0, 0.1),
    IngredientNutritionRecord("celery", "stalk", 6.0, 0.3, 1.2, 0.1),
    IngredientNutritionRecord("cheddar cheese", "cup", 455.0, 28.0, 3.8, 37.0),
    IngredientNutritionRecord("chicken", "lb", 748.0, 108.0, 0.0, 32.0),
    IngredientNutritionRecord("chicken breast", "lb", 748.0, 108.0, 0.0, 16.0),
    IngredientNutritionRecord("chicken broth", "cup", 15.0, 1.4, 1.0, 0.5),
    IngredientNutritionRecord("chickpeas", "can", 210.0, 10.9, 35.8, 3.6),
    IngredientNutritionRecord("chili powder", "tbsp", 24.0, 1.1, 4.3, 1.4),
    IngredientNutritionRecord("cilantro", "tbsp", 1.0, 0.1, 0.1, 0.0),
    IngredientNutritionRecord("cinnamon", "tsp", 6.0, 0.1, 2.1, 0.0),
    IngredientNutritionRecord("corn", "cup", 143.0, 5.0, 31.0, 2.2),
    IngredientNutritionRecord("cornstarch", "tbsp", 30.0, 0.0, 7.0, 0.0),
    IngredientNutritionRecord("cucumber", "item", 16.0, 0.7, 3.8, 0.1),
    IngredientNutritionRecord("cumin", "tbsp", 22.0, 1.1, 2.6, 1.3),
    IngredientNutritionRecord("curry powder", "tbsp", 20.0, 0.8, 3.6, 0.9),
    IngredientNutritionRecord("eggs", "item", 72.0, 6.3, 0.4, 4.8),
    IngredientNutritionRecord("feta", "cup", 396.0, 21.0, 6.0, 32.0),
    IngredientNutritionRecord("figs", "item", 37.0, 0.4, 9.6, 0.2),
    IngredientNutritionRecord("flour", "cup", 455.0, 13.0, 95.0, 1.2),
    IngredientNutritionRecord("flour tortillas", "item", 140.0, 4.0, 24.0, 3.5),
    IngredientNutritionRecord("frozen berries", "cup", 70.0, 1.0, 17.0, 0.5),
    IngredientNutritionRecord("garlic", "clove", 4.0, 0.2, 1.0, 0.0),
    IngredientNutritionRecord("garlic powder", "tbsp", 10.0, 0.5, 2.3, 0.0),
    IngredientNutritionRecord("ginger", "tbsp", 5.0, 0.1, 1.1, 0.0),
    IngredientNutritionRecord("granola", "cup", 597.0, 13.0, 83.0, 24.0),
    IngredientNutritionRecord("ground beef", "lb", 1152.0, 77.0, 0.0, 92.0),
    IngredientNutritionRecord("ground turkey", "lb", 770.0, 85.0, 0.0, 44.0),
    IngredientNutritionRecord("honey", "tbsp", 64.0, 0.1, 17.3, 0.0),
    IngredientNutritionRecord("hot sauce", "tbsp", 0.0, 0.0, 0.0, 0.0),
    IngredientNutritionRecord("lemon", "item", 17.0, 0.6, 5.4, 0.2),
    IngredientNutritionRecord("lemon juice", "tbsp", 4.0, 0.1, 1.3, 0.0),
    IngredientNutritionRecord("lentils", "cup", 230.0, 17.9, 39.9, 0.8),
    IngredientNutritionRecord("lime", "item", 20.0, 0.5, 7.1, 0.1),
    IngredientNutritionRecord("lime juice", "tbsp", 4.0, 0.1, 1.3, 0.0),
    IngredientNutritionRecord("mayonnaise", "tbsp", 94.0, 0.1, 0.1, 10.3),
    IngredientNutritionRecord("milk", "cup", 149.0, 7.7, 11.7, 7.9),
    IngredientNutritionRecord("mozzarella cheese", "cup", 336.0, 24.0, 6.0, 24.0),
    IngredientNutritionRecord("mushroom", "cup", 15.0, 2.2, 2.3, 0.2),
    IngredientNutritionRecord("olive oil", "tbsp", 119.0, 0.0, 0.0, 13.5),
    IngredientNutritionRecord("onion", "item", 44.0, 1.2, 10.3, 0.1),
    IngredientNutritionRecord("orange juice", "cup", 112.0, 1.7, 25.8, 0.5),
    IngredientNutritionRecord("oregano", "tsp", 3.0, 0.1, 0.7, 0.1),
    IngredientNutritionRecord("paprika", "tbsp", 20.0, 1.0, 3.7, 0.9),
    IngredientNutritionRecord("parmesan", "tbsp", 22.0, 2.0, 0.2, 1.4),
    IngredientNutritionRecord("parsley", "tbsp", 1.0, 0.1, 0.2, 0.0),
    IngredientNutritionRecord("pasta", "oz", 100.0, 3.5, 21.0, 0.6),
    IngredientNutritionRecord("peanut butter", "tbsp", 94.0, 3.5, 3.2, 8.0),
    IngredientNutritionRecord("pineapple", "cup", 82.0, 0.9, 21.7, 0.2),
    IngredientNutritionRecord("potato", "item", 163.0, 4.3, 37.0, 0.2),
    IngredientNutritionRecord("raisins", "cup", 434.0, 5.0, 115.0, 0.5),
    IngredientNutritionRecord("red pepper flakes", "tbsp", 17.0, 0.6, 3.0, 0.9),
    IngredientNutritionRecord("rice", "cup", 206.0, 4.3, 45.0, 0.4),
    IngredientNutritionRecord("rice vinegar", "tbsp", 3.0, 0.0, 0.7, 0.0),
    IngredientNutritionRecord("rolled oats", "cup", 307.0, 10.7, 54.8, 5.3),
    IngredientNutritionRecord("salt", "tsp", 0.0, 0.0, 0.0, 0.0),
    IngredientNutritionRecord("salsa", "cup", 36.0, 1.5, 7.0, 0.2),
    IngredientNutritionRecord("sesame oil", "tbsp", 120.0, 0.0, 0.0, 14.0),
    IngredientNutritionRecord("soy sauce", "tbsp", 9.0, 1.3, 0.8, 0.1),
    IngredientNutritionRecord("spinach", "cup", 7.0, 0.9, 1.1, 0.1),
    IngredientNutritionRecord("strawberries", "cup", 49.0, 1.0, 11.7, 0.5),
    IngredientNutritionRecord("sugar", "cup", 774.0, 0.0, 200.0, 0.0),
    IngredientNutritionRecord("tofu", "block", 360.0, 40.0, 8.0, 20.0),
    IngredientNutritionRecord("tomato", "item", 22.0, 1.1, 4.8, 0.2),
    IngredientNutritionRecord("tomato sauce", "cup", 80.0, 3.3, 17.0, 0.4),
    IngredientNutritionRecord("turmeric", "tbsp", 21.0, 0.6, 4.1, 0.7),
    IngredientNutritionRecord("vanilla extract", "tsp", 12.0, 0.0, 0.5, 0.0),
    IngredientNutritionRecord("vegetable broth", "cup", 15.0, 0.5, 1.7, 0.4),
    IngredientNutritionRecord("vegetable oil", "tbsp", 120.0, 0.0, 0.0, 14.0),
    IngredientNutritionRecord("walnuts", "tbsp", 185.0, 4.3, 3.9, 18.5),
    IngredientNutritionRecord("water", "cup", 0.0, 0.0, 0.0, 0.0),
    IngredientNutritionRecord("worcestershire sauce", "tbsp", 13.0, 0.0, 3.0, 0.0),
    IngredientNutritionRecord("yogurt", "cup", 150.0, 13.0, 17.0, 4.0),
    IngredientNutritionRecord("zucchini", "item", 33.0, 2.4, 6.1, 0.6),
)

HEURISTIC_INGREDIENT_NUTRITION_RECORDS = {
    record.key: record for record in _HEURISTIC_NUTRITION_RECORDS
}

HEURISTIC_INGREDIENT_TO_NUTRITION_KEY = {
    "apple": "apple",
    "avocado": "avocado",
    "banana": "banana",
    "balsamic vinegar": "balsamic vinegar",
    "bell pepper": "bell pepper",
    "black beans": "black beans",
    "black pepper": "black pepper",
    "blueberries": "blueberries",
    "bread": "bread",
    "bread crumbs": "bread crumbs",
    "broccoli": "broccoli",
    "butter": "butter",
    "buttermilk": "buttermilk",
    "canned tomatoes": "canned tomatoes",
    "carrot": "carrot",
    "celery": "celery",
    "cheddar cheese": "cheddar cheese",
    "chicken": "chicken",
    "chicken breast": "chicken breast",
    "chicken broth": "chicken broth",
    "chickpeas": "chickpeas",
    "chili powder": "chili powder",
    "cilantro": "cilantro",
    "cinnamon": "cinnamon",
    "corn": "corn",
    "cornstarch": "cornstarch",
    "cucumber": "cucumber",
    "cumin": "cumin",
    "curry powder": "curry powder",
    "eggs": "eggs",
    "feta": "feta",
    "figs": "figs",
    "flour": "flour",
    "flour tortillas": "flour tortillas",
    "frozen berries": "frozen berries",
    "garlic": "garlic",
    "garlic powder": "garlic powder",
    "ginger": "ginger",
    "granola": "granola",
    "ground beef": "ground beef",
    "ground turkey": "ground turkey",
    "honey": "honey",
    "hot sauce": "hot sauce",
    "lemon": "lemon",
    "lemon juice": "lemon juice",
    "lentils": "lentils",
    "lime": "lime",
    "lime juice": "lime juice",
    "mayonnaise": "mayonnaise",
    "milk": "milk",
    "mozzarella cheese": "mozzarella cheese",
    "mushroom": "mushroom",
    "olive oil": "olive oil",
    "onion": "onion",
    "orange juice": "orange juice",
    "oregano": "oregano",
    "paprika": "paprika",
    "parmesan": "parmesan",
    "parsley": "parsley",
    "pasta": "pasta",
    "peanut butter": "peanut butter",
    "pineapple": "pineapple",
    "potato": "potato",
    "raisins": "raisins",
    "red pepper flakes": "red pepper flakes",
    "rice": "rice",
    "rice vinegar": "rice vinegar",
    "rolled oats": "rolled oats",
    "salt": "salt",
    "salsa": "salsa",
    "sesame oil": "sesame oil",
    "soy sauce": "soy sauce",
    "spinach": "spinach",
    "strawberries": "strawberries",
    "sugar": "sugar",
    "tofu": "tofu",
    "tomato": "tomato",
    "tomato sauce": "tomato sauce",
    "turmeric": "turmeric",
    "vanilla extract": "vanilla extract",
    "vegetable broth": "vegetable broth",
    "vegetable oil": "vegetable oil",
    "walnuts": "walnuts",
    "water": "water",
    "worcestershire sauce": "worcestershire sauce",
    "yogurt": "yogurt",
    "zucchini": "zucchini",
}


def nutrition_record_keys() -> tuple[str, ...]:
    return tuple(sorted(_all_nutrition_records()))


def runtime_nutrition_record_keys() -> tuple[str, ...]:
    return tuple(sorted(_load_usda_runtime_records()))


def runtime_nutrition_mapping_keys() -> tuple[str, ...]:
    return tuple(sorted(_load_usda_runtime_mappings()))


def pilot_nutrition_record_keys() -> tuple[str, ...]:
    return tuple(sorted(_load_usda_pilot_records()))


def pilot_nutrition_mapping_keys() -> tuple[str, ...]:
    return tuple(sorted(_load_usda_pilot_mappings()))


def guidance_mapping_keys() -> tuple[str, ...]:
    return tuple(sorted(_load_meal_guidance()))


def ingredient_nutrition_key(
    value: str,
    *,
    include_usda_full: bool = True,
    include_usda_pilot: bool = True,
    include_heuristic: bool = True,
) -> str | None:
    canonical_name = canonical_ingredient_name(value)
    if include_usda_full:
        runtime_key = _load_usda_runtime_mappings().get(canonical_name)
        if runtime_key is not None:
            return runtime_key
    if include_usda_pilot:
        pilot_key = _load_usda_pilot_mappings().get(canonical_name)
        if pilot_key is not None:
            return pilot_key
    if include_heuristic:
        return HEURISTIC_INGREDIENT_TO_NUTRITION_KEY.get(canonical_name)
    return None


def lookup_ingredient_nutrition(
    value: str,
    *,
    include_usda_full: bool = True,
    include_usda_pilot: bool = True,
    include_heuristic: bool = True,
) -> IngredientNutritionRecord | None:
    nutrition_key = ingredient_nutrition_key(
        value,
        include_usda_full=include_usda_full,
        include_usda_pilot=include_usda_pilot,
        include_heuristic=include_heuristic,
    )
    if nutrition_key is None:
        return None
    return _all_nutrition_records().get(nutrition_key)


def lookup_ingredient_nutrition_candidates(
    value: str,
    *,
    include_usda_full: bool = True,
    include_usda_pilot: bool = True,
    include_heuristic: bool = True,
) -> tuple[IngredientNutritionRecord, ...]:
    canonical_name = canonical_ingredient_name(value)
    records: list[IngredientNutritionRecord] = []
    if include_usda_full:
        runtime_key = _load_usda_runtime_mappings().get(canonical_name)
        if runtime_key is not None:
            runtime_record = _load_usda_runtime_records().get(runtime_key)
            if runtime_record is not None:
                records.append(runtime_record)
    if include_usda_pilot:
        pilot_key = _load_usda_pilot_mappings().get(canonical_name)
        if pilot_key is not None:
            pilot_record = _load_usda_pilot_records().get(pilot_key)
            if pilot_record is not None:
                records.append(pilot_record)
    if include_heuristic:
        heuristic_key = HEURISTIC_INGREDIENT_TO_NUTRITION_KEY.get(canonical_name)
        if heuristic_key is not None:
            heuristic_record = HEURISTIC_INGREDIENT_NUTRITION_RECORDS.get(heuristic_key)
            if heuristic_record is not None:
                records.append(heuristic_record)
    return tuple(records)


def lookup_ingredient_guidance(value: str) -> IngredientGuidanceRecord | None:
    canonical_name = canonical_ingredient_name(value)
    return _load_meal_guidance().get(canonical_name)


@lru_cache(maxsize=1)
def _all_nutrition_records() -> dict[str, IngredientNutritionRecord]:
    records = dict(HEURISTIC_INGREDIENT_NUTRITION_RECORDS)
    records.update(_load_usda_runtime_records())
    records.update(_load_usda_pilot_records())
    return records


@lru_cache(maxsize=1)
def _load_usda_runtime_manifest() -> dict[str, object]:
    return _load_json_dict(USDA_RUNTIME_MANIFEST_PATH)


@lru_cache(maxsize=1)
def _load_usda_runtime_records() -> dict[str, IngredientNutritionRecord]:
    payload = _load_json_dict(USDA_RUNTIME_RECORDS_PATH)
    records: dict[str, IngredientNutritionRecord] = {}
    for row in payload.get("records", ()):
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or row.get("canonical_ingredient") or "").strip()
        reference_unit = str(row.get("reference_unit") or "").strip()
        if not key or not reference_unit:
            continue
        try:
            records[key] = IngredientNutritionRecord(
                key=key,
                reference_unit=reference_unit,
                calories=float(row["calories"]),
                protein_grams=float(row["protein_grams"]),
                carbs_grams=float(row["carbs_grams"]),
                fat_grams=float(row["fat_grams"]),
                source=str(row.get("source") or "usda-fdc"),
                source_dataset=str(row.get("source_dataset") or ""),
                source_food_id=(
                    int(row["source_food_id"])
                    if row.get("source_food_id") not in (None, "")
                    else None
                ),
                source_description=str(row.get("source_description") or ""),
                source_release=str(row.get("source_release") or ""),
                pilot=False,
            )
        except (TypeError, ValueError, KeyError):
            continue
    return records


@lru_cache(maxsize=1)
def _load_usda_runtime_mappings() -> dict[str, str]:
    payload = _load_json_dict(USDA_RUNTIME_MAPPINGS_PATH)
    mappings: dict[str, str] = {}
    for row in payload.get("mappings", ()):
        if not isinstance(row, dict):
            continue
        canonical_name = canonical_ingredient_name(str(row.get("canonical_ingredient") or ""))
        if not canonical_name:
            continue
        mappings[canonical_name] = canonical_name
    return mappings


@lru_cache(maxsize=1)
def _load_usda_pilot_manifest() -> dict[str, object]:
    return _load_json_dict(USDA_PILOT_MANIFEST_PATH)


@lru_cache(maxsize=1)
def _load_usda_pilot_records() -> dict[str, IngredientNutritionRecord]:
    payload = _load_json_dict(USDA_PILOT_RECORDS_PATH)
    records: dict[str, IngredientNutritionRecord] = {}
    for row in payload.get("records", ()):
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip()
        reference_unit = str(row.get("reference_unit") or "").strip()
        if not key or not reference_unit:
            continue
        try:
            records[key] = IngredientNutritionRecord(
                key=key,
                reference_unit=reference_unit,
                calories=float(row["calories"]),
                protein_grams=float(row["protein_grams"]),
                carbs_grams=float(row["carbs_grams"]),
                fat_grams=float(row["fat_grams"]),
                source=str(row.get("source") or "usda-fdc-pilot"),
                source_dataset=str(row.get("source_dataset") or ""),
                source_food_id=(
                    int(row["source_food_id"])
                    if row.get("source_food_id") not in (None, "")
                    else None
                ),
                source_description=str(row.get("source_description") or ""),
                source_release=str(row.get("source_release") or ""),
                pilot=bool(row.get("pilot", True)),
            )
        except (TypeError, ValueError, KeyError):
            continue
    return records


@lru_cache(maxsize=1)
def _load_usda_pilot_mappings() -> dict[str, str]:
    payload = _load_json_dict(USDA_PILOT_MAPPINGS_PATH)
    mappings: dict[str, str] = {}
    for row in payload.get("mappings", ()):
        if not isinstance(row, dict):
            continue
        canonical_name = canonical_ingredient_name(str(row.get("canonical_ingredient") or ""))
        nutrition_key = str(row.get("nutrition_key") or "").strip()
        if canonical_name and nutrition_key:
            mappings[canonical_name] = nutrition_key
    return mappings


@lru_cache(maxsize=1)
def _load_meal_guidance() -> dict[str, IngredientGuidanceRecord]:
    payload = _load_json_dict(USDA_MEAL_GUIDANCE_PATH)
    guidance: dict[str, IngredientGuidanceRecord] = {}
    for row in payload.get("mappings", ()):
        if not isinstance(row, dict):
            continue
        canonical_name = canonical_ingredient_name(str(row.get("canonical_ingredient") or ""))
        food_group_tags = frozenset(
            str(tag).strip()
            for tag in row.get("food_group_tags", ())
            if str(tag).strip()
        )
        component_tags = frozenset(
            str(tag).strip()
            for tag in row.get("component_tags", ())
            if str(tag).strip()
        )
        if canonical_name and (food_group_tags or component_tags):
            guidance[canonical_name] = IngredientGuidanceRecord(
                canonical_ingredient=canonical_name,
                food_group_tags=food_group_tags,
                component_tags=component_tags,
                source=str(row.get("source") or "myplate-guidance"),
                notes=str(row.get("notes") or ""),
            )
    return guidance


def _load_json_dict(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload
