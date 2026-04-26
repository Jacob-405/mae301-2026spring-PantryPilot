from __future__ import annotations

import argparse
import json
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from pantry_pilot.app_runtime import AppPlanSnapshot, build_plan_snapshot
from pantry_pilot.models import PlannerRequest, UserNutritionProfile
from pantry_pilot.pantry_carryover import PantryCarryoverStore
from pantry_pilot.personal_targets import generate_personal_targets
from pantry_pilot.runtime_audit import build_runtime_coverage_audit, build_runtime_data_contract


@dataclass(frozen=True)
class AcceptanceScenario:
    scenario_id: str
    name: str
    description: str


@dataclass(frozen=True)
class AcceptanceResult:
    scenario_id: str
    name: str
    passed: bool
    details: dict[str, object]


SCENARIOS = (
    AcceptanceScenario(
        scenario_id="balanced_week",
        name="Standard Balanced Week",
        description="Baseline balanced-week scenario on the real runtime stack with believable main-side pairings.",
    ),
    AcceptanceScenario(
        scenario_id="high_protein_week",
        name="High-Protein Profile Week",
        description="Profile-aware week where the planner should more clearly support protein-forward daily targets.",
    ),
    AcceptanceScenario(
        scenario_id="tighter_calorie_week",
        name="Tighter-Calorie Profile Week",
        description="Lower-calorie profile scenario that should still produce believable complementary pairings.",
    ),
    AcceptanceScenario(
        scenario_id="carryover_reuse",
        name="Pantry Carryover Reuse Week",
        description="Two-run scenario proving pantry carryover lowers later shopping needs while preserving balanced pairings.",
    ),
)


def _standard_request() -> PlannerRequest:
    return PlannerRequest(
        weekly_budget=140.0,
        servings=2,
        cuisine_preferences=("mediterranean", "mexican", "american"),
        allergies=(),
        excluded_ingredients=(),
        diet_restrictions=(),
        pantry_staples=("olive oil",),
        max_prep_time_minutes=35,
        meals_per_day=1,
        meal_structure=("dinner",),
        pricing_mode="mock",
        daily_calorie_target_min=800,
        daily_calorie_target_max=1200,
        variety_preference="balanced",
        leftovers_mode="off",
    )


def _high_protein_request() -> PlannerRequest:
    profile = UserNutritionProfile(
        age_years=34,
        sex="female",
        height_cm=168.0,
        weight_kg=72.0,
        activity_level="Low Active",
        planning_goal="High Protein Preference",
    )
    targets = generate_personal_targets(profile, meals_per_day=1)
    return PlannerRequest(
        weekly_budget=150.0,
        servings=2,
        cuisine_preferences=("american", "mediterranean"),
        allergies=(),
        excluded_ingredients=(),
        diet_restrictions=(),
        pantry_staples=("olive oil",),
        max_prep_time_minutes=35,
        meals_per_day=1,
        meal_structure=("dinner",),
        pricing_mode="mock",
        daily_calorie_target_min=targets.calorie_target_min,
        daily_calorie_target_max=targets.calorie_target_max,
        variety_preference="balanced",
        leftovers_mode="off",
        user_profile=profile,
        personal_targets=targets,
    )


def _tighter_calorie_request() -> PlannerRequest:
    profile = UserNutritionProfile(
        age_years=30,
        sex="female",
        height_cm=160.0,
        weight_kg=58.0,
        activity_level="Sedentary",
        planning_goal="Mild Deficit",
    )
    targets = generate_personal_targets(profile, meals_per_day=1)
    return PlannerRequest(
        weekly_budget=110.0,
        servings=2,
        cuisine_preferences=("mediterranean", "american"),
        allergies=(),
        excluded_ingredients=(),
        diet_restrictions=(),
        pantry_staples=(),
        max_prep_time_minutes=30,
        meals_per_day=1,
        meal_structure=("dinner",),
        pricing_mode="mock",
        daily_calorie_target_min=targets.calorie_target_min,
        daily_calorie_target_max=targets.calorie_target_max,
        variety_preference="balanced",
        leftovers_mode="off",
        user_profile=profile,
        personal_targets=targets,
    )


def _carryover_request() -> PlannerRequest:
    return PlannerRequest(
        weekly_budget=90.0,
        servings=2,
        cuisine_preferences=("american", "mediterranean"),
        allergies=(),
        excluded_ingredients=(),
        diet_restrictions=(),
        pantry_staples=("olive oil", "garlic"),
        max_prep_time_minutes=35,
        meals_per_day=1,
        meal_structure=("dinner",),
        pricing_mode="mock",
        daily_calorie_target_min=800,
        daily_calorie_target_max=1200,
        variety_preference="balanced",
        leftovers_mode="moderate",
    )


def _snapshot_summary(snapshot: AppPlanSnapshot) -> dict[str, object]:
    meals = snapshot.plan.meals
    return {
        "meal_count": len(meals),
        "main_count": sum(1 for meal in meals if meal.meal_role == "main"),
        "side_count": sum(1 for meal in meals if meal.meal_role == "side"),
        "estimated_total_cost": snapshot.plan.estimated_total_cost,
        "export_has_rationale": "Why chosen:" in snapshot.export_text,
        "export_has_confidence": "Confidence:" in snapshot.export_text,
        "export_has_weekly_nutrition": "Weekly nutrition:" in snapshot.export_text,
        "titles": [meal.recipe.title for meal in meals[:8]],
    }


def _pairing_quality_summary(snapshot: AppPlanSnapshot) -> dict[str, object]:
    diagnostics = snapshot.planner.latest_selection_diagnostics()
    main_diagnostics = [diagnostic for diagnostic in diagnostics if diagnostic.meal_role == "main"]
    side_diagnostics = [diagnostic for diagnostic in diagnostics if diagnostic.meal_role == "side"]
    role_appropriate_mains = sum(
        1
        for diagnostic in main_diagnostics
        if "main-anchor:strong" in diagnostic.reasons or "main-anchor:acceptable" in diagnostic.reasons
    )
    complementing_sides = sum(
        1
        for diagnostic in side_diagnostics
        if any(
            reason in diagnostic.reasons
            for reason in ("complements-main", "complements-main-produce-gap", "complements-main-protein-gap", "complements-main-starch-gap")
        )
    )
    starch_heavy_pairings = sum(
        1
        for diagnostic in side_diagnostics
        if diagnostic.anchor_composition_profile is not None
        and diagnostic.selected_composition_profile is not None
        and diagnostic.anchor_composition_profile.dominant_component == "starch"
        and diagnostic.selected_composition_profile.dominant_component == "starch"
    )
    produce_gap_supported = sum(
        1
        for diagnostic in side_diagnostics
        if diagnostic.daily_deficits_before is not None
        and diagnostic.daily_deficits_after is not None
        and diagnostic.daily_deficits_before.produce_support > diagnostic.daily_deficits_after.produce_support
    )
    protein_gap_supported = sum(
        1
        for diagnostic in side_diagnostics
        if diagnostic.daily_deficits_before is not None
        and diagnostic.daily_deficits_after is not None
        and diagnostic.daily_deficits_before.protein_grams > diagnostic.daily_deficits_after.protein_grams
    )
    vegetable_sides_when_needed = sum(
        1
        for diagnostic in side_diagnostics
        if diagnostic.daily_deficits_before is not None
        and diagnostic.daily_deficits_before.produce_support > 0.5
        and diagnostic.selected_composition_profile is not None
        and diagnostic.selected_composition_profile.vegetable_support >= 0.75
    )
    target_guided_choices = sum(
        1
        for diagnostic in diagnostics
        if any(reason.startswith("target:") for reason in diagnostic.reasons)
    )
    runner_up_explanations = sum(1 for diagnostic in side_diagnostics if diagnostic.runner_up_loss_reasons)
    side_count = len(side_diagnostics)
    return {
        "main_count": len(main_diagnostics),
        "side_count": side_count,
        "role_appropriate_mains": role_appropriate_mains,
        "complementing_sides": complementing_sides,
        "starch_heavy_pairings": starch_heavy_pairings,
        "produce_gap_supported": produce_gap_supported,
        "protein_gap_supported": protein_gap_supported,
        "vegetable_sides_when_needed": vegetable_sides_when_needed,
        "target_guided_choices": target_guided_choices,
        "runner_up_explanations": runner_up_explanations,
        "complement_ratio": round(complementing_sides / side_count, 3) if side_count else 0.0,
    }


def _merge_snapshot_details(snapshot: AppPlanSnapshot) -> dict[str, object]:
    details = _snapshot_summary(snapshot)
    details["pairing_quality"] = _pairing_quality_summary(snapshot)
    details["scenario_output"] = [
        {
            "day": meal.day,
            "slot": meal.slot,
            "title": meal.recipe.title,
            "role": meal.meal_role,
        }
        for meal in snapshot.plan.meals[:10]
    ]
    return details


def _run_balanced_week(store: PantryCarryoverStore) -> AcceptanceResult:
    started_at = time.perf_counter()
    snapshot = build_plan_snapshot(_standard_request(), pantry_store=store)
    details = _merge_snapshot_details(snapshot)
    details["daily_target"] = "800-1200"
    details["seconds"] = round(time.perf_counter() - started_at, 2)
    pairing_quality = details["pairing_quality"]
    passed = (
        details["meal_count"] >= 7
        and details["estimated_total_cost"] <= _standard_request().weekly_budget
        and bool(details["export_has_rationale"])
        and bool(details["export_has_confidence"])
        and bool(details["export_has_weekly_nutrition"])
        and pairing_quality["role_appropriate_mains"] == pairing_quality["main_count"]
        and pairing_quality["complementing_sides"] >= 1
        and pairing_quality["starch_heavy_pairings"] == 0
        and pairing_quality["produce_gap_supported"] >= 1
    )
    return AcceptanceResult("balanced_week", "Standard Balanced Week", passed, details)


def _run_high_protein_week(store: PantryCarryoverStore) -> AcceptanceResult:
    request = _high_protein_request()
    started_at = time.perf_counter()
    snapshot = build_plan_snapshot(request, pantry_store=store)
    details = _merge_snapshot_details(snapshot)
    details["protein_target_min_grams"] = request.personal_targets.protein_target_min_grams if request.personal_targets else None
    details["seconds"] = round(time.perf_counter() - started_at, 2)
    pairing_quality = details["pairing_quality"]
    passed = (
        details["meal_count"] >= 7
        and snapshot.plan.estimated_total_cost <= request.weekly_budget
        and pairing_quality["role_appropriate_mains"] == pairing_quality["main_count"]
        and pairing_quality["target_guided_choices"] >= 7
        and pairing_quality["protein_gap_supported"] >= 1
        and pairing_quality["starch_heavy_pairings"] == 0
    )
    return AcceptanceResult("high_protein_week", "High-Protein Profile Week", passed, details)


def _run_tighter_calorie_week(store: PantryCarryoverStore) -> AcceptanceResult:
    request = _tighter_calorie_request()
    started_at = time.perf_counter()
    snapshot = build_plan_snapshot(request, pantry_store=store)
    details = _merge_snapshot_details(snapshot)
    details["daily_target"] = f"{request.daily_calorie_target_min}-{request.daily_calorie_target_max}"
    details["remaining_budget"] = round(request.weekly_budget - snapshot.plan.estimated_total_cost, 2)
    details["seconds"] = round(time.perf_counter() - started_at, 2)
    pairing_quality = details["pairing_quality"]
    passed = (
        details["meal_count"] >= 7
        and snapshot.plan.estimated_total_cost <= request.weekly_budget
        and details["remaining_budget"] >= -0.01
        and pairing_quality["role_appropriate_mains"] == pairing_quality["main_count"]
        and pairing_quality["starch_heavy_pairings"] == 0
        and pairing_quality["produce_gap_supported"] >= 1
        and pairing_quality["target_guided_choices"] >= 7
    )
    return AcceptanceResult("tighter_calorie_week", "Tighter-Calorie Profile Week", passed, details)


def _run_carryover_reuse(store: PantryCarryoverStore) -> AcceptanceResult:
    request = _carryover_request()
    started_at = time.perf_counter()
    first_snapshot = build_plan_snapshot(request, pantry_store=store)
    updated_inventory = store.apply_plan(first_snapshot.plan)
    second_snapshot = build_plan_snapshot(request, pantry_store=store)
    baseline_second_snapshot = build_plan_snapshot(
        request,
        pantry_store=PantryCarryoverStore(
            store.storage_path.with_name(f"{store.storage_path.stem}_baseline.json")
        ),
    )
    first_total = first_snapshot.plan.estimated_total_cost
    second_total = second_snapshot.plan.estimated_total_cost
    baseline_second_total = baseline_second_snapshot.plan.estimated_total_cost
    carryover_used_items = sum(
        1 for item in second_snapshot.plan.shopping_list if item.carryover_used_quantity > 0
    )
    carryover_used_quantity = round(
        sum(item.carryover_used_quantity for item in second_snapshot.plan.shopping_list),
        2,
    )
    reduced_purchase_items = sum(
        1
        for item in second_snapshot.plan.shopping_list
        if item.carryover_used_quantity > 0 and item.purchased_quantity + 1e-9 < item.quantity
    )
    details = {
        "first_week_cost": first_total,
        "second_week_cost": second_total,
        "baseline_second_week_cost_without_carryover": baseline_second_total,
        "carryover_inventory_count_after_week1": len(updated_inventory),
        "second_week_carryover_used_items": carryover_used_items,
        "second_week_carryover_used_quantity": carryover_used_quantity,
        "second_week_reduced_purchase_items": reduced_purchase_items,
        "second_week_titles": [meal.recipe.title for meal in second_snapshot.plan.meals[:8]],
        "pairing_quality": _pairing_quality_summary(second_snapshot),
        "scenario_output": [
            {
                "day": meal.day,
                "slot": meal.slot,
                "title": meal.recipe.title,
                "role": meal.meal_role,
            }
            for meal in second_snapshot.plan.meals[:10]
        ],
        "seconds": round(time.perf_counter() - started_at, 2),
    }
    passed = (
        len(updated_inventory) > 0
        and carryover_used_items > 0
        and carryover_used_quantity > 0
        and reduced_purchase_items > 0
        and details["pairing_quality"]["role_appropriate_mains"] == details["pairing_quality"]["main_count"]
        and details["pairing_quality"]["starch_heavy_pairings"] == 0
    )
    return AcceptanceResult("carryover_reuse", "Pantry Carryover Reuse Week", passed, details)


SCENARIO_HANDLERS = {
    "balanced_week": _run_balanced_week,
    "high_protein_week": _run_high_protein_week,
    "tighter_calorie_week": _run_tighter_calorie_week,
    "carryover_reuse": _run_carryover_reuse,
}


def run_acceptance(scenario_ids: tuple[str, ...] | None = None) -> dict[str, object]:
    selected_ids = scenario_ids or tuple(scenario.scenario_id for scenario in SCENARIOS)
    selected_scenarios = tuple(
        scenario
        for scenario in SCENARIOS
        if scenario.scenario_id in selected_ids
    )
    if len(selected_scenarios) != len(selected_ids):
        missing = sorted(set(selected_ids) - {scenario.scenario_id for scenario in selected_scenarios})
        raise ValueError(f"Unknown acceptance scenario(s): {', '.join(missing)}")

    with tempfile.TemporaryDirectory() as tmpdir:
        results = []
        for scenario in selected_scenarios:
            handler = SCENARIO_HANDLERS[scenario.scenario_id]
            pantry_store = PantryCarryoverStore(Path(tmpdir) / f"{scenario.scenario_id}.json")
            results.append(handler(pantry_store))

    contract = build_runtime_data_contract()
    coverage = build_runtime_coverage_audit()
    all_passed = all(result.passed for result in results)
    return {
        "scenarios": [asdict(scenario) for scenario in selected_scenarios],
        "results": [asdict(result) for result in results],
        "all_passed": all_passed,
        "runtime_contract": asdict(contract),
        "runtime_coverage": asdict(coverage),
        "known_limitations": [
            "Some recipe nutrition and pricing values are still partial because USDA mappings and local price coverage are not complete for every ingredient.",
            "Balanced meal guidance is scoring-based, not medical advice or a personalized diet prescription.",
            "RecipeNLG remains the main corpus, so recipe quality still depends on source-data cleanliness and role inference.",
            "Real-store pricing is optional; demo/runtime acceptance is frozen on the local mock pricing path.",
        ],
    }


def render_acceptance_text(payload: dict[str, object]) -> str:
    lines = [
        "PantryPilot Final Acceptance",
        f"Overall result: {'PASS' if payload['all_passed'] else 'FAIL'}",
        "",
        "Acceptance Scenarios",
    ]
    for result in payload["results"]:
        status = "PASS" if result["passed"] else "FAIL"
        lines.append(f"- {result['name']}: {status}")
        lines.append(f"  Details: {result['details']}")
    lines.extend(
        [
            "",
            "Frozen Runtime",
            f"- Active recipe corpus: {payload['runtime_contract']['active_recipe_corpus_path']}",
            f"- Nutrition mappings: {payload['runtime_contract']['nutrition_mappings_path']}",
            f"- Nutrition records: {payload['runtime_contract']['nutrition_records_path']}",
            f"- Guidance file: {payload['runtime_contract']['guidance_path']}",
            f"- Pricing source: {payload['runtime_contract']['default_pricing_source']}",
            "",
            "Known Limitations",
        ]
    )
    for limitation in payload["known_limitations"]:
        lines.append(f"- {limitation}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run PantryPilot final acceptance scenarios.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument(
        "--scenario",
        action="append",
        choices=tuple(scenario.scenario_id for scenario in SCENARIOS),
        help="Run only the named scenario. Repeat to run multiple scenarios.",
    )
    args = parser.parse_args()

    payload = run_acceptance(tuple(args.scenario) if args.scenario else None)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload["all_passed"] else 1

    print(render_acceptance_text(payload))
    return 0 if payload["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
