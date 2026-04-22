from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
import urllib.request
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from pantry_pilot.ingredient_catalog import canonical_ingredient_name, canonical_unit_name, ingredient_catalog_entries


DATA_DIR = Path(__file__).resolve().parent / "data"
RAW_DIR = DATA_DIR / "nutrition_raw"
BUILD_DIR = DATA_DIR / "nutrition_build"

USDA_RUNTIME_MANIFEST_PATH = DATA_DIR / "usda_nutrition_manifest.json"
USDA_RUNTIME_RECORDS_PATH = DATA_DIR / "usda_nutrition_records.json"
USDA_RUNTIME_MAPPINGS_PATH = DATA_DIR / "usda_nutrition_mappings.json"
USDA_RUNTIME_UNRESOLVED_PATH = DATA_DIR / "usda_nutrition_unresolved.json"

BUILD_CHECKPOINT_PATH = BUILD_DIR / "usda_build_checkpoint.json"
COMPACT_FOODS_PATH = BUILD_DIR / "usda_compact_foods.jsonl"
MAPPING_CANDIDATES_PATH = BUILD_DIR / "usda_mapping_candidates.jsonl"
MAPPING_DECISIONS_PATH = BUILD_DIR / "usda_mapping_decisions.jsonl"

MAX_CANDIDATES_PER_INGREDIENT = 5
DEFAULT_BATCH_SIZE = 25
DEFAULT_PROCESSED_DATASET_RELATIVE_PATH = Path("mvp/data/processed/recipenlg-full-20260416T0625Z.json")

DATASET_PRIORITY = {
    "foundation": 3,
    "sr_legacy": 2,
    "fndds": 1,
}

DATASET_SPECS = (
    {
        "dataset": "foundation",
        "release": "2025-12-18",
        "url": "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_json_2025-12-18.zip",
    },
    {
        "dataset": "sr_legacy",
        "release": "2018-04",
        "url": "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip",
    },
    {
        "dataset": "fndds",
        "release": "2024-10-31",
        "url": "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_survey_food_json_2024-10-31.zip",
    },
)

MACRO_NUTRIENT_NUMBERS = {
    "1008": "calories",
    "1003": "protein_grams",
    "1005": "carbs_grams",
    "1004": "fat_grams",
}

GLOBAL_REJECT_TOKENS = frozenset(
    {
        "restaurant",
        "fast",
        "foods",
        "sandwich",
        "burger",
        "pizza",
        "taco",
        "burrito",
        "enchilada",
        "lasagna",
        "salad",
        "casserole",
        "cookie",
        "cake",
        "pudding",
        "beverage",
        "drink",
    }
)

QUERY_STOPWORDS = frozenset(
    {
        "fresh",
        "frozen",
        "dried",
        "dry",
        "raw",
        "cooked",
        "boneless",
        "skinless",
        "chopped",
        "diced",
        "minced",
        "large",
        "small",
        "medium",
        "halves",
        "pieces",
        "piece",
        "whole",
        "plain",
        "reduced",
        "low",
        "sodium",
        "fat",
        "free",
        "light",
        "homemade",
        "old",
        "fashioned",
        "quick",
        "cooking",
        "unsalted",
        "salted",
        "packed",
        "ground",
    }
)


@dataclass(frozen=True)
class CompactFoodRecord:
    dataset: str
    release: str
    food_id: int
    description: str
    normalized_description: str
    calories_per_100g: float | None
    protein_per_100g: float | None
    carbs_per_100g: float | None
    fat_per_100g: float | None
    portion_grams: dict[str, float]


CURATED_USDA_HINTS = {
    "apple": {"preferred_description": "Apples, fuji, with skin, raw", "preferred_dataset": "foundation", "reference_unit": "item", "grams_per_reference_unit": 182.0},
    "avocado": {"preferred_description": "Avocados, raw, all commercial varieties", "preferred_dataset": "foundation", "reference_unit": "item", "grams_per_reference_unit": 150.0},
    "bacon": {"preferred_description_contains": "bacon, meat only, cooked", "preferred_dataset": "foundation", "reference_unit": "slice"},
    "baking powder": {"preferred_description": "Leavening agents, baking powder, low-sodium", "preferred_dataset": "sr_legacy", "reference_unit": "tsp", "grams_per_reference_unit": 4.0},
    "baking soda": {"preferred_description": "Leavening agents, baking soda", "preferred_dataset": "sr_legacy", "reference_unit": "tsp", "grams_per_reference_unit": 4.8},
    "balsamic vinegar": {"preferred_description_contains": "vinegar, balsamic", "preferred_dataset": "fndds", "reference_unit": "tbsp"},
    "bell pepper": {"preferred_description_contains": "peppers, sweet, green, raw", "preferred_dataset": "foundation", "reference_unit": "item", "grams_per_reference_unit": 119.0},
    "black beans": {"preferred_description_contains": "beans, black, mature seeds", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "black pepper": {"preferred_description_contains": "spices, pepper, black", "preferred_dataset": "sr_legacy", "reference_unit": "tsp", "grams_per_reference_unit": 2.3},
    "blueberries": {"preferred_description_contains": "blueberries, raw", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "bread": {"preferred_description_contains": "bread, whole wheat", "preferred_dataset": "fndds", "reference_unit": "slice"},
    "bread crumbs": {"preferred_description_contains": "bread crumbs, dry", "preferred_dataset": "sr_legacy", "reference_unit": "cup"},
    "broccoli": {"preferred_description": "Broccoli, raw", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "butter": {"preferred_description_contains": "butter, salted", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "buttermilk": {"preferred_description_contains": "buttermilk", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "canned tomatoes": {"preferred_description_contains": "tomatoes, canned", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "carrot": {"preferred_description": "Carrots, raw", "preferred_dataset": "sr_legacy", "reference_unit": "item", "grams_per_reference_unit": 61.0},
    "celery": {"preferred_description_contains": "celery, raw", "preferred_dataset": "foundation", "reference_unit": "stalk", "grams_per_reference_unit": 40.0},
    "cheddar cheese": {"preferred_description_contains": "cheese, cheddar", "preferred_dataset": "foundation", "reference_unit": "oz"},
    "cheese": {"preferred_description_contains": "cheese, cheddar", "preferred_dataset": "foundation", "reference_unit": "oz"},
    "chicken": {"preferred_description_contains": "chicken, broilers or fryers, meat and skin, raw", "preferred_dataset": "sr_legacy", "reference_unit": "lb"},
    "chicken breast": {"preferred_description_contains": "chicken, broilers or fryers, breast, meat only, raw", "preferred_dataset": "sr_legacy", "reference_unit": "lb"},
    "chicken broth": {"preferred_description_contains": "broth, chicken", "preferred_dataset": "fndds", "reference_unit": "cup"},
    "chicken gravy": {"preferred_description_contains": "gravy, chicken", "preferred_dataset": "sr_legacy", "reference_unit": "cup"},
    "chickpeas": {"preferred_description_contains": "chickpeas", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "chili powder": {"preferred_description_contains": "spices, chili powder", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp"},
    "cilantro": {"preferred_description_contains": "coriander (cilantro) leaves, raw", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp"},
    "cinnamon": {"preferred_description_contains": "spices, cinnamon", "preferred_dataset": "sr_legacy", "reference_unit": "tsp", "grams_per_reference_unit": 2.6},
    "cocoa": {"preferred_description_contains": "cocoa, dry powder", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp"},
    "coconut": {"preferred_description_contains": "coconut, raw", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "corn": {"preferred_description_contains": "corn, sweet, yellow", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "cornstarch": {"preferred_description_contains": "cornstarch", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp"},
    "cream cheese": {"preferred_description_contains": "cream cheese", "preferred_dataset": "foundation", "reference_unit": "oz"},
    "cream of chicken soup": {"preferred_description_contains": "soup, cream of chicken", "preferred_dataset": "fndds", "reference_unit": "cup"},
    "cream of mushroom soup": {"preferred_description_contains": "soup, cream of mushroom", "preferred_dataset": "fndds", "reference_unit": "cup"},
    "cucumber": {"preferred_description_contains": "cucumber, with peel, raw", "preferred_dataset": "foundation", "reference_unit": "item", "grams_per_reference_unit": 301.0},
    "cumin": {"preferred_description_contains": "spices, cumin seed", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp"},
    "curry powder": {"preferred_description_contains": "spices, curry powder", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp"},
    "cayenne pepper": {"preferred_description_contains": "spices, pepper, red or cayenne", "preferred_dataset": "sr_legacy", "reference_unit": "tsp"},
    "cherries": {"preferred_description_contains": "cherries, sweet, raw", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "eggs": {"preferred_description": "Eggs, Grade A, Large, egg whole", "preferred_dataset": "foundation", "reference_unit": "item", "grams_per_reference_unit": 50.3},
    "evaporated milk": {"preferred_description_contains": "milk, canned, evaporated", "preferred_dataset": "sr_legacy", "reference_unit": "cup"},
    "feta": {"preferred_description_contains": "cheese, feta", "preferred_dataset": "foundation", "reference_unit": "oz"},
    "figs": {"preferred_description_contains": "figs, raw", "preferred_dataset": "foundation", "reference_unit": "item", "grams_per_reference_unit": 50.0},
    "flour": {"preferred_description": "Flour, wheat, all-purpose, enriched, unbleached", "preferred_dataset": "foundation", "reference_unit": "cup", "grams_per_reference_unit": 125.0},
    "flour tortillas": {"preferred_description_contains": "tortillas, ready-to-bake or -fry, flour", "preferred_dataset": "sr_legacy", "reference_unit": "item", "grams_per_reference_unit": 49.0},
    "frozen berries": {"preferred_description_contains": "berries, mixed", "preferred_dataset": "fndds", "reference_unit": "cup"},
    "garlic": {"preferred_description_contains": "garlic, raw", "preferred_dataset": "foundation", "reference_unit": "clove", "grams_per_reference_unit": 3.0},
    "garlic powder": {"preferred_description_contains": "spices, garlic powder", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp"},
    "ginger": {"preferred_description_contains": "ginger root, raw", "preferred_dataset": "foundation", "reference_unit": "tbsp", "grams_per_reference_unit": 6.0},
    "granola": {"preferred_description_contains": "granola", "preferred_dataset": "sr_legacy", "reference_unit": "cup"},
    "green onion": {"preferred_description_contains": "onions, spring or scallions", "preferred_dataset": "sr_legacy", "reference_unit": "item", "grams_per_reference_unit": 15.0},
    "ground beef": {"preferred_description_contains": "beef, ground", "preferred_dataset": "foundation", "reference_unit": "lb"},
    "ground turkey": {"preferred_description_contains": "turkey, ground", "preferred_dataset": "fndds", "reference_unit": "lb"},
    "heavy cream": {"preferred_description_contains": "cream, fluid, heavy whipping", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp"},
    "honey": {"preferred_description_contains": "honey", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "hot sauce": {"preferred_description_contains": "hot sauce", "preferred_dataset": "fndds", "reference_unit": "tbsp"},
    "lemon": {"preferred_description_contains": "lemons, raw, without peel", "preferred_dataset": "foundation", "reference_unit": "item", "grams_per_reference_unit": 58.0},
    "lemon juice": {"preferred_description_contains": "lemon juice, raw", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "lentils": {"preferred_description_contains": "lentils, mature seeds, cooked", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "lime": {"preferred_description_contains": "limes, raw", "preferred_dataset": "foundation", "reference_unit": "item", "grams_per_reference_unit": 67.0},
    "lime juice": {"preferred_description_contains": "lime juice, raw", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "mayonnaise": {"preferred_description": "Salad dressing, mayonnaise, regular", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp", "grams_per_reference_unit": 13.8},
    "milk": {"preferred_description_contains": "milk, whole", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "mozzarella cheese": {"preferred_description_contains": "cheese, mozzarella", "preferred_dataset": "foundation", "reference_unit": "oz"},
    "mushroom": {"preferred_description_contains": "mushrooms, raw", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "mustard": {"preferred_description_contains": "mustard, prepared", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "nutmeg": {"preferred_description_contains": "spices, nutmeg, ground", "preferred_dataset": "sr_legacy", "reference_unit": "tsp"},
    "olive oil": {"preferred_description": "Olive oil", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "onion": {"preferred_description": "Onions, raw", "preferred_dataset": "sr_legacy", "reference_unit": "item", "grams_per_reference_unit": 110.0},
    "orange juice": {"preferred_description_contains": "orange juice", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "oregano": {"preferred_description_contains": "spices, oregano, dried", "preferred_dataset": "sr_legacy", "reference_unit": "tsp"},
    "paprika": {"preferred_description_contains": "spices, paprika", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp"},
    "parmesan": {"preferred_description_contains": "cheese, parmesan", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "parsley": {"preferred_description_contains": "parsley, fresh", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "pasta": {"preferred_description_contains": "pasta, dry, unenriched", "preferred_dataset": "sr_legacy", "reference_unit": "oz"},
    "peanut butter": {"preferred_description_contains": "peanut butter", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "pecans": {"preferred_description_contains": "pecans", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "pineapple": {"preferred_description_contains": "pineapple, raw", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "potato": {"preferred_description": "Potatoes, flesh and skin, raw", "preferred_dataset": "sr_legacy", "reference_unit": "item", "grams_per_reference_unit": 173.0},
    "raisins": {"preferred_description_contains": "raisins, seedless", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "red pepper flakes": {"preferred_description_contains": "pepper, red or cayenne", "preferred_dataset": "sr_legacy", "reference_unit": "tsp"},
    "rice": {"preferred_description": "Rice, white, long-grain, regular, cooked, enriched, with salt", "preferred_dataset": "sr_legacy", "reference_unit": "cup", "grams_per_reference_unit": 158.0},
    "rice vinegar": {"preferred_description_contains": "vinegar, rice", "preferred_dataset": "fndds", "reference_unit": "tbsp"},
    "rolled oats": {"preferred_description_contains": "oats", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "salt": {"preferred_description_contains": "salt, table", "preferred_dataset": "sr_legacy", "reference_unit": "tsp"},
    "salsa": {"preferred_description_contains": "salsa", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "sesame oil": {"preferred_description_contains": "sesame oil", "preferred_dataset": "fndds", "reference_unit": "tbsp"},
    "sour cream": {"preferred_description": "Sour cream, light", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp", "grams_per_reference_unit": 12.0},
    "soy sauce": {"preferred_description_contains": "soy sauce", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "spinach": {"preferred_description_contains": "spinach, raw", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "strawberries": {"preferred_description_contains": "strawberries, raw", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "stuffing mix": {"preferred_description_contains": "stuffing mix, dry", "preferred_dataset": "fndds", "reference_unit": "cup"},
    "sugar": {"preferred_description_contains": "sugar, granulated", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "thyme": {"preferred_description_contains": "spices, thyme, dried", "preferred_dataset": "sr_legacy", "reference_unit": "tsp"},
    "tofu": {"preferred_description_contains": "tofu, raw", "preferred_dataset": "foundation", "reference_unit": "block", "grams_per_reference_unit": 397.0},
    "tomato": {"preferred_description": "Tomatoes, red, ripe, raw, year round average", "preferred_dataset": "sr_legacy", "reference_unit": "item", "grams_per_reference_unit": 91.0},
    "tomato sauce": {"preferred_description_contains": "sauce, tomato", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "turmeric": {"preferred_description_contains": "spices, turmeric, ground", "preferred_dataset": "sr_legacy", "reference_unit": "tbsp"},
    "vanilla extract": {"preferred_description_contains": "vanilla extract", "preferred_dataset": "sr_legacy", "reference_unit": "tsp"},
    "vegetable broth": {"preferred_description_contains": "broth, vegetable", "preferred_dataset": "fndds", "reference_unit": "cup"},
    "vegetable oil": {"preferred_description": "Vegetable oil, NFS", "preferred_dataset": "fndds", "reference_unit": "tbsp", "grams_per_reference_unit": 14.0},
    "walnuts": {"preferred_description_contains": "walnuts", "preferred_dataset": "foundation", "reference_unit": "tbsp"},
    "water": {"preferred_description_contains": "water", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "worcestershire sauce": {"preferred_description_contains": "worcestershire sauce", "preferred_dataset": "fndds", "reference_unit": "tbsp"},
    "yogurt": {"preferred_description_contains": "yogurt, plain", "preferred_dataset": "foundation", "reference_unit": "cup"},
    "zucchini": {"preferred_description_contains": "zucchini", "preferred_dataset": "foundation", "reference_unit": "item", "grams_per_reference_unit": 196.0},
}


def normalize_text(value: str) -> str:
    cleaned = (value or "").strip().lower().replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"[^a-z0-9\s,]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" ,")


def normalize_query_tokens(value: str) -> tuple[str, ...]:
    normalized = normalize_text(value)
    tokens: list[str] = []
    for token in normalized.replace(",", " ").split():
        if token in QUERY_STOPWORDS:
            continue
        if token.endswith("es") and len(token) > 4:
            token = token[:-2]
        elif token.endswith("s") and len(token) > 3:
            token = token[:-1]
        tokens.append(token)
    return tuple(tokens)


def dataset_specs() -> tuple[dict[str, str], ...]:
    return DATASET_SPECS


def default_processed_dataset_path() -> Path:
    return Path(__file__).resolve().parent.parent / DEFAULT_PROCESSED_DATASET_RELATIVE_PATH


def download_snapshots(*, force: bool = False) -> dict[str, str]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    downloaded: dict[str, str] = {}
    for spec in DATASET_SPECS:
        target = RAW_DIR / Path(spec["url"]).name
        if force or not target.exists():
            with urllib.request.urlopen(spec["url"]) as response, target.open("wb") as output:
                shutil.copyfileobj(response, output)
            downloaded[spec["dataset"]] = "downloaded"
        else:
            downloaded[spec["dataset"]] = "cached"
    return downloaded


def runtime_nutrition_mapping_count() -> int:
    payload = _load_json_dict(USDA_RUNTIME_MAPPINGS_PATH)
    return len(payload.get("mappings", ()))


def runtime_nutrition_record_count() -> int:
    payload = _load_json_dict(USDA_RUNTIME_RECORDS_PATH)
    return len(payload.get("records", ()))


def ingredient_frequency_counts(processed_dataset_path: Path | None = None) -> Counter[str]:
    from pantry_pilot.providers import load_processed_recipes

    effective_path = processed_dataset_path or default_processed_dataset_path()
    recipes = load_processed_recipes(effective_path)
    counts: Counter[str] = Counter()
    for recipe in recipes:
        for ingredient in recipe.ingredients:
            counts[canonical_ingredient_name(ingredient.name)] += 1
    for entry in ingredient_catalog_entries():
        counts.setdefault(entry.canonical_name, 0)
    return counts


def ranked_candidates_for_ingredient(
    ingredient_name: str,
    foods: tuple[CompactFoodRecord, ...],
) -> list[dict[str, object]]:
    canonical_name = canonical_ingredient_name(ingredient_name)
    query_tokens = normalize_query_tokens(canonical_name)
    if not query_tokens:
        return []
    preferred = CURATED_USDA_HINTS.get(canonical_name, {})
    candidates: list[dict[str, object]] = []
    for food in foods:
        score = score_candidate(canonical_name, query_tokens, food, preferred)
        if score <= 0:
            continue
        candidates.append(
            {
                "dataset": food.dataset,
                "food_id": food.food_id,
                "description": food.description,
                "normalized_description": food.normalized_description,
                "score": round(score, 3),
                "portion_grams": food.portion_grams,
            }
        )
    candidates.sort(
        key=lambda candidate: (
            -float(candidate["score"]),
            -DATASET_PRIORITY.get(str(candidate["dataset"]), 0),
            str(candidate["description"]),
            int(candidate["food_id"]),
        )
    )
    return candidates


def resolve_ingredient_mapping(
    ingredient_name: str,
    candidates: list[dict[str, object]],
) -> dict[str, object]:
    canonical_name = canonical_ingredient_name(ingredient_name)
    preferred = CURATED_USDA_HINTS.get(canonical_name, {})
    if not candidates:
        return {
            "canonical_ingredient": canonical_name,
            "mapping_status": "unresolved",
            "reason": "no confident USDA candidate",
            "top_candidates": (),
        }

    chosen = None
    method = ""
    confidence = "low"
    if preferred:
        chosen = _choose_preferred_candidate(candidates, preferred)
        if chosen is not None:
            method = "curated-review"
            confidence = "high"
    if chosen is None:
        top = candidates[0]
        runner_up = candidates[1] if len(candidates) > 1 else None
        margin = float(top["score"]) - float(runner_up["score"]) if runner_up is not None else float(top["score"])
        if float(top["score"]) >= 120.0 and margin >= 25.0:
            chosen = top
            method = "auto-exact"
            confidence = "high"
        elif float(top["score"]) >= 95.0 and margin >= 30.0:
            chosen = top
            method = "auto-normalized"
            confidence = "medium"
        elif float(top["score"]) >= 90.0 and runner_up is None:
            chosen = top
            method = "auto-single"
            confidence = "medium"
    if chosen is None:
        return {
            "canonical_ingredient": canonical_name,
            "mapping_status": "ambiguous",
            "reason": "multiple plausible USDA candidates",
            "top_candidates": tuple(candidates[:MAX_CANDIDATES_PER_INGREDIENT]),
        }

    return {
        "canonical_ingredient": canonical_name,
        "mapping_status": "mapped",
        "mapping_method": method,
        "confidence": confidence,
        "selected_source_dataset": chosen["dataset"],
        "selected_source_food_id": chosen["food_id"],
        "selected_source_description": chosen["description"],
        "review_status": "reviewed" if method == "curated-review" else "auto-accepted",
        "reference_unit_override": preferred.get("reference_unit", ""),
        "grams_per_reference_unit_override": preferred.get("grams_per_reference_unit"),
        "notes": preferred.get("notes", ""),
        "top_candidates": tuple(candidates[:MAX_CANDIDATES_PER_INGREDIENT]),
    }


def score_candidate(
    ingredient_name: str,
    query_tokens: tuple[str, ...],
    food: CompactFoodRecord,
    preferred: dict[str, object],
) -> float:
    description = food.normalized_description
    preferred_description = normalize_text(str(preferred.get("preferred_description") or ""))
    preferred_description_contains = normalize_text(str(preferred.get("preferred_description_contains") or ""))
    preferred_exact_match = bool(preferred_description and description == preferred_description)
    preferred_contains_match = bool(preferred_description_contains and preferred_description_contains in description)
    if not all(
        getattr(food, field) is not None
        for field in ("calories_per_100g", "protein_per_100g", "carbs_per_100g", "fat_per_100g")
    ):
        return 0.0
    if (
        not preferred_exact_match
        and not preferred_contains_match
        and any(token in description.split() for token in GLOBAL_REJECT_TOKENS if token not in query_tokens)
    ):
        return 0.0
    score = DATASET_PRIORITY.get(food.dataset, 0) * 10.0
    canonical_phrase = normalize_text(ingredient_name)
    if description == canonical_phrase:
        score += 120.0
    elif description.startswith(canonical_phrase):
        score += 95.0
    elif canonical_phrase in description:
        score += 70.0

    description_tokens = set(normalize_query_tokens(description))
    query_token_set = set(query_tokens)
    if query_token_set and query_token_set.issubset(description_tokens):
        score += 55.0
    score += len(query_token_set & description_tokens) * 6.0

    preferred_dataset = str(preferred.get("preferred_dataset") or "")
    if preferred_dataset and food.dataset == preferred_dataset:
        score += 40.0
    if preferred_exact_match:
        score += 100.0
    elif preferred_contains_match:
        score += 60.0

    if "raw" in description:
        score += 8.0
    if "cooked" in description:
        score += 4.0
    return score


def choose_reference_basis(
    *,
    canonical_name: str,
    portion_grams: dict[str, float],
    preferred_unit: str,
    preferred_grams: object,
) -> tuple[str, float] | None:
    if preferred_unit:
        normalized_unit = canonical_unit_name(preferred_unit)
        if preferred_grams not in (None, ""):
            return normalized_unit, float(preferred_grams)
        if normalized_unit in portion_grams:
            return normalized_unit, float(portion_grams[normalized_unit])

    for candidate in ("cup", "tbsp", "tsp", "item", "slice", "stalk", "clove", "oz", "lb"):
        if candidate in portion_grams:
            return candidate, float(portion_grams[candidate])

    if canonical_name in {
        "cheddar cheese",
        "cheese",
        "chicken",
        "chicken breast",
        "ground beef",
        "ground turkey",
        "pasta",
    }:
        return "oz", 28.3495
    return None


def build_runtime_records(
    mappings: list[dict[str, object]],
    foods: tuple[CompactFoodRecord, ...],
) -> list[dict[str, object]]:
    indexed_foods = {(food.dataset, food.food_id): food for food in foods}
    records: list[dict[str, object]] = []
    for mapping in mappings:
        food = indexed_foods.get((mapping["selected_source_dataset"], mapping["selected_source_food_id"]))
        if food is None:
            continue
        reference = choose_reference_basis(
            canonical_name=str(mapping["canonical_ingredient"]),
            portion_grams=food.portion_grams,
            preferred_unit=str(mapping.get("reference_unit_override") or ""),
            preferred_grams=mapping.get("grams_per_reference_unit_override"),
        )
        if reference is None:
            continue
        reference_unit, grams_per_reference_unit = reference
        scale = grams_per_reference_unit / 100.0
        records.append(
            {
                "key": str(mapping["canonical_ingredient"]),
                "canonical_ingredient": str(mapping["canonical_ingredient"]),
                "reference_unit": reference_unit,
                "grams_per_reference_unit": round(grams_per_reference_unit, 4),
                "calories": round(float(food.calories_per_100g) * scale, 4),
                "protein_grams": round(float(food.protein_per_100g) * scale, 4),
                "carbs_grams": round(float(food.carbs_per_100g) * scale, 4),
                "fat_grams": round(float(food.fat_per_100g) * scale, 4),
                "source": "usda-fdc",
                "source_dataset": food.dataset,
                "source_food_id": food.food_id,
                "source_description": food.description,
                "source_release": next(spec["release"] for spec in DATASET_SPECS if spec["dataset"] == food.dataset),
                "pilot": False,
            }
        )
    records.sort(key=lambda row: str(row["key"]))
    return records


def build_unresolved_report(unresolved: list[dict[str, object]], frequencies: Counter[str]) -> dict[str, object]:
    unresolved_rows = []
    for row in unresolved:
        unresolved_rows.append(
            {
                **row,
                "frequency": frequencies.get(str(row["canonical_ingredient"]), 0),
            }
        )
    unresolved_rows.sort(key=lambda row: (-int(row["frequency"]), str(row["canonical_ingredient"])))
    return {
        "source": "usda-fdc",
        "unresolved": unresolved_rows,
        "top_unmapped_by_frequency": unresolved_rows[:25],
    }


def load_runtime_unresolved() -> dict[str, object]:
    return _load_json_dict(USDA_RUNTIME_UNRESOLVED_PATH)


def build_full_usda_runtime(
    *,
    ingredient_names: tuple[str, ...] | None = None,
    processed_dataset_path: Path | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    reset: bool = False,
) -> dict[str, object]:
    started_at = time.perf_counter()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if reset:
        for path in (
            BUILD_CHECKPOINT_PATH,
            COMPACT_FOODS_PATH,
            MAPPING_CANDIDATES_PATH,
            MAPPING_DECISIONS_PATH,
            USDA_RUNTIME_MANIFEST_PATH,
            USDA_RUNTIME_RECORDS_PATH,
            USDA_RUNTIME_MAPPINGS_PATH,
            USDA_RUNTIME_UNRESOLVED_PATH,
        ):
            if path.exists():
                path.unlink()

    checkpoint = _load_json_dict(BUILD_CHECKPOINT_PATH)
    compact_checkpoint = dict(checkpoint.get("compact_datasets", {}))
    compact_files = _build_compact_foods(compact_checkpoint)

    foods = tuple(_load_compact_foods(compact_files))
    effective_dataset_path = processed_dataset_path or default_processed_dataset_path()
    frequencies = ingredient_frequency_counts(effective_dataset_path)
    ordered_ingredients = ingredient_names or tuple(
        ingredient
        for ingredient, _count in sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))
    )

    processed_names = set(checkpoint.get("processed_ingredients", ()))
    if reset:
        processed_names.clear()
    if not MAPPING_CANDIDATES_PATH.exists():
        MAPPING_CANDIDATES_PATH.write_text("", encoding="utf-8")
    if not MAPPING_DECISIONS_PATH.exists():
        MAPPING_DECISIONS_PATH.write_text("", encoding="utf-8")

    candidate_output = MAPPING_CANDIDATES_PATH.open("a", encoding="utf-8")
    decisions_output = MAPPING_DECISIONS_PATH.open("a", encoding="utf-8")
    try:
        for batch_start in range(0, len(ordered_ingredients), batch_size):
            batch = ordered_ingredients[batch_start : batch_start + batch_size]
            dirty = False
            for ingredient_name in batch:
                if ingredient_name in processed_names:
                    continue
                candidates = ranked_candidates_for_ingredient(ingredient_name, foods)
                candidate_output.write(
                    json.dumps(
                        {
                            "canonical_ingredient": ingredient_name,
                            "frequency": frequencies.get(ingredient_name, 0),
                            "candidates": candidates[:MAX_CANDIDATES_PER_INGREDIENT],
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
                decision = resolve_ingredient_mapping(ingredient_name, candidates)
                decisions_output.write(json.dumps(decision, sort_keys=True) + "\n")
                processed_names.add(ingredient_name)
                dirty = True
            if dirty:
                _write_checkpoint(
                    {
                        "compact_datasets": compact_checkpoint,
                        "processed_ingredients": sorted(processed_names),
                    }
                )
    finally:
        candidate_output.close()
        decisions_output.close()

    decisions = tuple(_load_jsonl(MAPPING_DECISIONS_PATH))
    mappings = [decision for decision in decisions if decision.get("mapping_status") == "mapped"]
    unresolved = [decision for decision in decisions if decision.get("mapping_status") != "mapped"]
    records = build_runtime_records(mappings, foods)
    unresolved_report = build_unresolved_report(unresolved, frequencies)
    manifest = {
        "source": "usda-fdc",
        "source_priority": ["foundation", "sr_legacy", "fndds"],
        "raw_snapshot_dir": str(RAW_DIR.resolve()),
        "build_dir": str(BUILD_DIR.resolve()),
        "processed_dataset_path": str(effective_dataset_path.resolve()),
        "datasets": [
            {
                **spec,
                "filename": Path(spec["url"]).name,
                "sha256": _sha256_file(RAW_DIR / Path(spec["url"]).name),
            }
            for spec in DATASET_SPECS
        ],
        "mapping_count": len(mappings),
        "record_count": len(records),
        "unresolved_count": len(unresolved_report["unresolved"]),
        "top_remaining_unmapped_count": len(unresolved_report["top_unmapped_by_frequency"]),
        "build_seconds": round(time.perf_counter() - started_at, 2),
        "build_mode": "full-local-usda",
    }

    USDA_RUNTIME_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    USDA_RUNTIME_MAPPINGS_PATH.write_text(
        json.dumps({"source": "usda-fdc", "mappings": mappings}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    USDA_RUNTIME_RECORDS_PATH.write_text(
        json.dumps({"source": "usda-fdc", "records": records}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    USDA_RUNTIME_UNRESOLVED_PATH.write_text(json.dumps(unresolved_report, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "manifest": manifest,
        "records": records,
        "mappings": mappings,
        "unresolved_report": unresolved_report,
    }


def _build_compact_foods(compact_checkpoint: dict[str, object]) -> tuple[Path, ...]:
    dataset_files: list[Path] = []
    for spec in DATASET_SPECS:
        target = BUILD_DIR / f"{spec['dataset']}_compact_foods.jsonl"
        dataset_files.append(target)
        if compact_checkpoint.get(spec["dataset"]) == "complete" and target.exists():
            continue
        compact_rows = _extract_dataset_compact_rows(spec)
        with target.open("w", encoding="utf-8") as output:
            for row in compact_rows:
                output.write(json.dumps(asdict(row), sort_keys=True) + "\n")
        compact_checkpoint[spec["dataset"]] = "complete"
        _write_checkpoint({"compact_datasets": compact_checkpoint})
    with COMPACT_FOODS_PATH.open("w", encoding="utf-8") as merged:
        for target in dataset_files:
            if target.exists():
                merged.write(target.read_text(encoding="utf-8"))
    return tuple(dataset_files)


def _extract_dataset_compact_rows(spec: dict[str, str]) -> list[CompactFoodRecord]:
    raw_path = RAW_DIR / Path(spec["url"]).name
    if not raw_path.exists():
        raise FileNotFoundError(f"Missing USDA snapshot: {raw_path}")
    with zipfile.ZipFile(raw_path) as archive:
        json_names = [name for name in archive.namelist() if name.lower().endswith(".json")]
        if not json_names:
            raise ValueError(f"No JSON file found in USDA snapshot: {raw_path.name}")
        with archive.open(json_names[0]) as raw_json:
            payload = json.load(raw_json)
    foods: list[CompactFoodRecord] = []
    for row in _iter_food_rows(payload):
        compact = _compact_food_row(spec["dataset"], spec["release"], row)
        if compact is not None:
            foods.append(compact)
    foods.sort(key=lambda row: (row.dataset, row.normalized_description, row.food_id))
    return foods


def _iter_food_rows(payload: object) -> tuple[dict[str, object], ...]:
    if isinstance(payload, list):
        return tuple(row for row in payload if _looks_like_food_row(row))
    if not isinstance(payload, dict):
        return ()
    rows: list[dict[str, object]] = []
    for value in payload.values():
        if isinstance(value, list):
            rows.extend(row for row in value if _looks_like_food_row(row))
    return tuple(rows)


def _looks_like_food_row(row: object) -> bool:
    return isinstance(row, dict) and bool(row.get("description")) and isinstance(row.get("foodNutrients"), list)


def _compact_food_row(dataset: str, release: str, row: dict[str, object]) -> CompactFoodRecord | None:
    try:
        food_id = int(row.get("fdcId") or row.get("foodId") or row.get("foodCode"))
    except (TypeError, ValueError):
        return None
    description = str(row.get("description") or "").strip()
    normalized_description = normalize_text(description)
    if not description or not normalized_description:
        return None
    nutrients = _extract_macro_nutrients(row.get("foodNutrients", ()))
    if not nutrients:
        return None
    portion_grams = _extract_portion_grams(row.get("foodPortions", ()))
    return CompactFoodRecord(
        dataset=dataset,
        release=release,
        food_id=food_id,
        description=description,
        normalized_description=normalized_description,
        calories_per_100g=nutrients.get("calories"),
        protein_per_100g=nutrients.get("protein_grams"),
        carbs_per_100g=nutrients.get("carbs_grams"),
        fat_per_100g=nutrients.get("fat_grams"),
        portion_grams=portion_grams,
    )


def _extract_macro_nutrients(entries: object) -> dict[str, float]:
    nutrients: dict[str, float] = {}
    if not isinstance(entries, list):
        return nutrients
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        nutrient_meta = entry.get("nutrient")
        nutrient_number = str(
            entry.get("nutrientNumber")
            or (nutrient_meta.get("number") if isinstance(nutrient_meta, dict) else "")
            or ""
        ).strip()
        nutrient_name = normalize_text(
            str(
                entry.get("nutrientName")
                or (nutrient_meta.get("name") if isinstance(nutrient_meta, dict) else "")
                or ""
            )
        )
        unit_name = normalize_text(
            str(
                entry.get("unitName")
                or (nutrient_meta.get("unitName") if isinstance(nutrient_meta, dict) else "")
                or ""
            )
        )
        amount = entry.get("amount", entry.get("value"))
        try:
            numeric_amount = float(amount)
        except (TypeError, ValueError):
            continue
        target_key = MACRO_NUTRIENT_NUMBERS.get(nutrient_number)
        if target_key is None:
            if nutrient_name.startswith("energy") and ("kcal" in nutrient_name or "kcal" in unit_name):
                target_key = "calories"
            elif nutrient_name == "protein":
                target_key = "protein_grams"
            elif nutrient_name.startswith("carbohydrate"):
                target_key = "carbs_grams"
            elif nutrient_name.startswith("total lipid") or nutrient_name.startswith("fat"):
                target_key = "fat_grams"
        if target_key is not None:
            nutrients[target_key] = numeric_amount
    if "calories" not in nutrients and all(key in nutrients for key in ("protein_grams", "carbs_grams", "fat_grams")):
        nutrients["calories"] = (
            (nutrients["protein_grams"] * 4.0)
            + (nutrients["carbs_grams"] * 4.0)
            + (nutrients["fat_grams"] * 9.0)
        )
    return nutrients


def _extract_portion_grams(entries: object) -> dict[str, float]:
    portion_grams: dict[str, float] = {}
    if not isinstance(entries, list):
        return portion_grams
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        try:
            gram_weight = float(entry.get("gramWeight"))
        except (TypeError, ValueError):
            continue
        if gram_weight <= 0:
            continue
        try:
            amount = float(entry.get("amount") or 1.0)
        except (TypeError, ValueError):
            amount = 1.0
        grams_per_unit = gram_weight / max(amount, 1e-9)

        measure_unit = entry.get("measureUnit")
        unit_candidates: list[str] = []
        if isinstance(measure_unit, dict):
            for raw_unit in (
                measure_unit.get("abbreviation"),
                measure_unit.get("name"),
                measure_unit.get("modifier"),
            ):
                if raw_unit:
                    unit_candidates.append(canonical_unit_name(str(raw_unit)))
        modifier = normalize_text(str(entry.get("modifier") or ""))
        for token in ("cup", "tbsp", "tsp", "item", "slice", "stalk", "clove", "oz", "lb"):
            if token in modifier:
                unit_candidates.append(token)
        if "tablespoon" in modifier:
            unit_candidates.append("tbsp")
        if "teaspoon" in modifier:
            unit_candidates.append("tsp")
        if "piece" in modifier or "whole" in modifier:
            unit_candidates.append("item")

        for unit in unit_candidates:
            if unit:
                current = portion_grams.get(unit)
                portion_grams[unit] = grams_per_unit if current is None else min(current, grams_per_unit)
    portion_grams.setdefault("oz", 28.3495)
    portion_grams.setdefault("lb", 453.592)
    return portion_grams


def _choose_preferred_candidate(
    candidates: list[dict[str, object]],
    preferred: dict[str, object],
) -> dict[str, object] | None:
    preferred_dataset = str(preferred.get("preferred_dataset") or "")
    preferred_description = normalize_text(str(preferred.get("preferred_description") or ""))
    preferred_description_contains = normalize_text(str(preferred.get("preferred_description_contains") or ""))
    filtered = candidates
    if preferred_dataset:
        filtered = [candidate for candidate in filtered if candidate["dataset"] == preferred_dataset]
    if preferred_description:
        exact_matches = [
            candidate
            for candidate in filtered
            if normalize_text(str(candidate["description"])) == preferred_description
        ]
        if len(exact_matches) == 1:
            return exact_matches[0]
    if preferred_description_contains:
        contains_matches = [
            candidate
            for candidate in filtered
            if preferred_description_contains in normalize_text(str(candidate["description"]))
        ]
        if len(contains_matches) == 1:
            return contains_matches[0]
        if contains_matches:
            contains_matches.sort(key=lambda candidate: (-float(candidate["score"]), str(candidate["description"])))
            return contains_matches[0]
    return None


def _load_compact_foods(dataset_files: tuple[Path, ...]) -> list[CompactFoodRecord]:
    foods: list[CompactFoodRecord] = []
    for path in dataset_files:
        if not path.exists():
            continue
        for row in _load_jsonl(path):
            foods.append(
                CompactFoodRecord(
                    dataset=str(row["dataset"]),
                    release=str(row["release"]),
                    food_id=int(row["food_id"]),
                    description=str(row["description"]),
                    normalized_description=str(row["normalized_description"]),
                    calories_per_100g=_optional_float(row.get("calories_per_100g")),
                    protein_per_100g=_optional_float(row.get("protein_per_100g")),
                    carbs_per_100g=_optional_float(row.get("carbs_per_100g")),
                    fat_per_100g=_optional_float(row.get("fat_per_100g")),
                    portion_grams={str(unit): float(value) for unit, value in dict(row.get("portion_grams", {})).items()},
                )
            )
    foods.sort(key=lambda food: (food.dataset, food.normalized_description, food.food_id))
    return foods


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _write_checkpoint(payload: dict[str, object]) -> None:
    merged = _load_json_dict(BUILD_CHECKPOINT_PATH)
    merged.update(payload)
    BUILD_CHECKPOINT_PATH.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")


def _load_json_dict(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_report_text(payload: dict[str, object]) -> str:
    manifest = payload["manifest"]
    unresolved_report = payload["unresolved_report"]
    lines = [
        "PantryPilot USDA Nutrition Build",
        f"Build seconds: {manifest['build_seconds']}",
        f"Mapped ingredients: {manifest['mapping_count']}",
        f"Runtime records: {manifest['record_count']}",
        f"Unresolved ingredients: {manifest['unresolved_count']}",
        "Top remaining unmapped:",
    ]
    for row in unresolved_report["top_unmapped_by_frequency"][:10]:
        lines.append(f"- {row['canonical_ingredient']}: {row['frequency']}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the full local USDA nutrition runtime artifacts for PantryPilot.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download_parser = subparsers.add_parser("download", help="Download pinned USDA FoodData Central snapshots.")
    download_parser.add_argument("--force", action="store_true", help="Re-download snapshots even if cached.")

    build_parser = subparsers.add_parser("build", help="Build runtime nutrition artifacts from local USDA snapshots.")
    build_parser.add_argument("--reset", action="store_true", help="Reset checkpoints and rebuild from scratch.")
    build_parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Ingredient batch size for checkpointed mapping.")
    build_parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")

    report_parser = subparsers.add_parser("report", help="Show the current build outputs.")
    report_parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")

    args = parser.parse_args()
    if args.command == "download":
        payload = download_snapshots(force=bool(args.force))
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.command == "build":
        payload = build_full_usda_runtime(batch_size=int(args.batch_size), reset=bool(args.reset))
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(build_report_text(payload))
        return 0

    payload = {
        "manifest": _load_json_dict(USDA_RUNTIME_MANIFEST_PATH),
        "unresolved_report": _load_json_dict(USDA_RUNTIME_UNRESOLVED_PATH),
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    print(build_report_text(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
