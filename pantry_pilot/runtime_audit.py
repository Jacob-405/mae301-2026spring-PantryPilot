from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

from pantry_pilot.models import PlannerRequest, Recipe
from pantry_pilot.pantry_carryover import DEFAULT_PANTRY_CARRYOVER_PATH
from pantry_pilot.planner import WeeklyMealPlanner
from pantry_pilot.providers import (
    DEFAULT_PROCESSED_RECIPES_PATH,
    MockGroceryProvider,
    build_pricing_context,
    resolve_recipe_runtime,
)
from pantry_pilot.nutrition import (
    USDA_MEAL_GUIDANCE_PATH,
    guidance_mapping_keys,
    USDA_RUNTIME_MANIFEST_PATH,
    USDA_RUNTIME_MAPPINGS_PATH,
    USDA_RUNTIME_RECORDS_PATH,
    runtime_nutrition_mapping_keys,
    runtime_nutrition_record_keys,
)


@dataclass(frozen=True)
class RuntimeDataContract:
    active_recipe_corpus_path: str
    active_recipe_source: str
    recipe_fallback_active: bool
    recipe_fallback_reason: str
    processed_recipe_count: int
    nutrition_manifest_path: str
    nutrition_manifest_exists: bool
    nutrition_records_path: str
    nutrition_records_exists: bool
    nutrition_mappings_path: str
    nutrition_mappings_exists: bool
    guidance_path: str
    guidance_exists: bool
    pantry_carryover_path: str
    pantry_carryover_exists: bool
    default_pricing_source: str
    mock_price_catalog_count: int
    real_store_mode_available: bool
    real_store_fallback_target: str
    runtime_local_only_for_nutrition: bool
    runtime_local_only_for_guidance: bool
    carryover_behavior: str
    pricing_behavior: str


@dataclass(frozen=True)
class RuntimeCoverageAudit:
    total_recipes: int
    meal_type_counts: dict[str, int]
    inferred_role_counts: dict[str, int]
    nutrition_recipe_count: int
    calorie_recipe_count: int
    priced_recipe_count: int
    nutrition_unknown_count: int
    calorie_unknown_count: int
    price_unknown_count: int
    allergen_unknown_count: int
    weak_main_count: int
    usda_mapped_ingredient_count: int
    usda_record_count: int
    guidance_mapping_count: int
    recipe_fallback_active: bool
    active_recipe_source: str
    weak_spots: tuple[str, ...]


def build_runtime_data_contract() -> RuntimeDataContract:
    _, recipe_status = resolve_recipe_runtime(DEFAULT_PROCESSED_RECIPES_PATH)
    default_pricing_context = build_pricing_context(
        pricing_mode="mock",
        zip_code="",
        store_location_id="",
    )
    real_store_available = bool(default_pricing_context.pricing_source == "kroger")
    mock_catalog = MockGroceryProvider()

    return RuntimeDataContract(
        active_recipe_corpus_path=str(Path(recipe_status.processed_dataset_path).resolve()),
        active_recipe_source=recipe_status.active_source,
        recipe_fallback_active=recipe_status.fallback_active,
        recipe_fallback_reason=recipe_status.fallback_reason,
        processed_recipe_count=recipe_status.processed_recipe_count,
        nutrition_manifest_path=str(USDA_RUNTIME_MANIFEST_PATH.resolve()),
        nutrition_manifest_exists=USDA_RUNTIME_MANIFEST_PATH.exists(),
        nutrition_records_path=str(USDA_RUNTIME_RECORDS_PATH.resolve()),
        nutrition_records_exists=USDA_RUNTIME_RECORDS_PATH.exists(),
        nutrition_mappings_path=str(USDA_RUNTIME_MAPPINGS_PATH.resolve()),
        nutrition_mappings_exists=USDA_RUNTIME_MAPPINGS_PATH.exists(),
        guidance_path=str(USDA_MEAL_GUIDANCE_PATH.resolve()),
        guidance_exists=USDA_MEAL_GUIDANCE_PATH.exists(),
        pantry_carryover_path=str(DEFAULT_PANTRY_CARRYOVER_PATH.resolve()),
        pantry_carryover_exists=DEFAULT_PANTRY_CARRYOVER_PATH.exists(),
        default_pricing_source=default_pricing_context.pricing_source,
        mock_price_catalog_count=len(mock_catalog._catalog),
        real_store_mode_available=real_store_available,
        real_store_fallback_target="mock",
        runtime_local_only_for_nutrition=True,
        runtime_local_only_for_guidance=True,
        carryover_behavior="Planner loads carryover from the pantry store and applies leftover package quantities across plans.",
        pricing_behavior="Default runtime uses the local mock provider; real-store pricing is optional and falls back to mock pricing on provider unavailability.",
    )


def build_runtime_coverage_audit() -> RuntimeCoverageAudit:
    recipes, recipe_status = resolve_recipe_runtime(DEFAULT_PROCESSED_RECIPES_PATH)
    planner = WeeklyMealPlanner(recipe_provider=None, grocery_provider=MockGroceryProvider())
    pricing_request = PlannerRequest(
        weekly_budget=9999.0,
        servings=2,
        cuisine_preferences=(),
        allergies=(),
        excluded_ingredients=(),
        diet_restrictions=(),
        pantry_staples=(),
        max_prep_time_minutes=999,
        meals_per_day=1,
        meal_structure=("dinner",),
        pricing_mode="mock",
        daily_calorie_target_min=0,
        daily_calorie_target_max=99999,
    )
    pantry_inventory = frozenset()

    meal_type_counts: Counter[str] = Counter()
    inferred_role_counts: Counter[str] = Counter()
    weak_main_count = 0
    nutrition_recipe_count = 0
    calorie_recipe_count = 0
    priced_recipe_count = 0
    allergen_unknown_count = 0

    for recipe in recipes:
        for meal_type in recipe.meal_types:
            meal_type_counts[meal_type] += 1
        inferred_role_counts[planner._recipe_role(recipe, "dinner")] += 1
        if recipe.estimated_nutrition_per_serving is not None:
            nutrition_recipe_count += 1
        if recipe.estimated_calories_per_serving is not None:
            calorie_recipe_count += 1
        if recipe.allergens is None:
            allergen_unknown_count += 1
        if planner._recipe_cost_is_known(recipe, pricing_request, pantry_inventory):
            priced_recipe_count += 1
        if any(
            meal_type in {"lunch", "dinner"}
            for meal_type in recipe.meal_types
        ):
            tagged_slots = [meal_type for meal_type in recipe.meal_types if meal_type in {"lunch", "dinner"}]
            if tagged_slots and not any(planner._is_reasonable_meal_for_slot(recipe, slot) for slot in tagged_slots):
                weak_main_count += 1

    total_recipes = len(recipes)
    weak_spots = tuple(
        spot
        for spot in (
            "recipe_fallback_active" if recipe_status.fallback_active else "",
            "nutrition_unknowns_present" if nutrition_recipe_count < total_recipes else "",
            "pricing_unknowns_present" if priced_recipe_count < total_recipes else "",
            "allergen_unknowns_present" if allergen_unknown_count else "",
            "weak_mains_present" if weak_main_count else "",
        )
        if spot
    )

    return RuntimeCoverageAudit(
        total_recipes=total_recipes,
        meal_type_counts=dict(sorted(meal_type_counts.items())),
        inferred_role_counts=dict(sorted(inferred_role_counts.items())),
        nutrition_recipe_count=nutrition_recipe_count,
        calorie_recipe_count=calorie_recipe_count,
        priced_recipe_count=priced_recipe_count,
        nutrition_unknown_count=total_recipes - nutrition_recipe_count,
        calorie_unknown_count=total_recipes - calorie_recipe_count,
        price_unknown_count=total_recipes - priced_recipe_count,
        allergen_unknown_count=allergen_unknown_count,
        weak_main_count=weak_main_count,
        usda_mapped_ingredient_count=len(runtime_nutrition_mapping_keys()),
        usda_record_count=len(runtime_nutrition_record_keys()),
        guidance_mapping_count=len(guidance_mapping_keys()),
        recipe_fallback_active=recipe_status.fallback_active,
        active_recipe_source=recipe_status.active_source,
        weak_spots=weak_spots,
    )


def render_runtime_audit_text(
    contract: RuntimeDataContract,
    coverage: RuntimeCoverageAudit,
) -> str:
    lines = [
        "PantryPilot Runtime Contract",
        f"Active recipe source: {contract.active_recipe_source}",
        f"Active recipe corpus path: {contract.active_recipe_corpus_path}",
        f"Recipe fallback active: {contract.recipe_fallback_active}",
        f"Processed recipe count: {contract.processed_recipe_count}",
        f"Nutrition mappings path: {contract.nutrition_mappings_path}",
        f"Nutrition records path: {contract.nutrition_records_path}",
        f"Guidance path: {contract.guidance_path}",
        f"Pantry carryover path: {contract.pantry_carryover_path}",
        f"Default pricing source: {contract.default_pricing_source}",
        "",
        "Runtime Coverage Audit",
        f"Total recipes: {coverage.total_recipes}",
        f"Meal type counts: {coverage.meal_type_counts}",
        f"Inferred dinner roles: {coverage.inferred_role_counts}",
        f"Nutrition coverage: {coverage.nutrition_recipe_count}/{coverage.total_recipes}",
        f"Calorie coverage: {coverage.calorie_recipe_count}/{coverage.total_recipes}",
        f"Pricing coverage: {coverage.priced_recipe_count}/{coverage.total_recipes}",
        f"Nutrition unknown count: {coverage.nutrition_unknown_count}",
        f"Price unknown count: {coverage.price_unknown_count}",
        f"Allergen unknown count: {coverage.allergen_unknown_count}",
        f"Weak main count: {coverage.weak_main_count}",
        f"USDA mapped ingredients: {coverage.usda_mapped_ingredient_count}",
        f"Guidance mappings: {coverage.guidance_mapping_count}",
        f"Weak spots: {list(coverage.weak_spots)}",
    ]
    if contract.recipe_fallback_reason:
        lines.append(f"Recipe fallback reason: {contract.recipe_fallback_reason}")
    return "\n".join(lines)


def _build_payload() -> dict[str, object]:
    contract = build_runtime_data_contract()
    coverage = build_runtime_coverage_audit()
    return {
        "contract": asdict(contract),
        "coverage": asdict(coverage),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="PantryPilot runtime contract and data-health audit")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a text summary.")
    args = parser.parse_args()

    payload = _build_payload()
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    contract = RuntimeDataContract(**payload["contract"])
    coverage = RuntimeCoverageAudit(**payload["coverage"])
    print(render_runtime_audit_text(contract, coverage))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
