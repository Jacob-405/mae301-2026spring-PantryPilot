from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict, dataclass

from pantry_pilot.models import PlannedMeal, PlannerRequest
from pantry_pilot.planner import PlanningProgress, WeeklyMealPlanner


@dataclass(frozen=True)
class SlotSelectionDiagnosis:
    request_name: str
    slot_label: str
    candidate_gathering_seconds: float
    main_candidate_count: int
    side_candidate_count: int
    main_selected_title: str | None
    side_selected_title: str | None
    main_timing: dict[str, object] | None
    side_timing: dict[str, object] | None
    main_diagnostics_seconds: float
    side_diagnostics_seconds: float
    progress_event_count: int
    progress_samples: tuple[dict[str, object], ...]


def balanced_budget_request() -> PlannerRequest:
    return PlannerRequest(
        weekly_budget=90.0,
        servings=2,
        cuisine_preferences=("mediterranean", "mexican", "american"),
        allergies=(),
        excluded_ingredients=(),
        diet_restrictions=(),
        pantry_staples=("olive oil", "cinnamon"),
        max_prep_time_minutes=35,
        meals_per_day=2,
        meal_structure=("lunch", "dinner"),
        pricing_mode="mock",
        daily_calorie_target_min=1800,
        daily_calorie_target_max=2300,
        variety_preference="balanced",
        leftovers_mode="off",
    )


def diagnose_monday_lunch(request: PlannerRequest | None = None) -> SlotSelectionDiagnosis:
    active_request = request or balanced_budget_request()
    planner = WeeklyMealPlanner(selection_profiling_enabled=True)
    progress_updates: list[PlanningProgress] = []
    planner.set_progress_callback(progress_updates.append)

    candidates = planner.filter_recipes(active_request)
    pantry_inventory = planner._normalized_pantry_inventory(active_request)
    planner._validate_constraint_support(candidates, active_request, pantry_inventory)
    variety_profile = planner._variety_profile(active_request)
    request_cycle_offset = planner._next_request_cycle_offset(active_request)
    planner._warm_recipe_feature_caches(candidates, active_request)

    slot_started_at = time.perf_counter()
    slot_groups = planner._slot_recipe_groups(candidates, active_request, 1)
    candidate_gathering_seconds = time.perf_counter() - slot_started_at
    planner._set_active_slot_progress(label="Planning Monday lunch", completed=1, total=(7 * active_request.meals_per_day) + 3)
    planner._report_progress(
        "selection",
        "Planning Monday lunch",
        1,
        (7 * active_request.meals_per_day) + 3,
        f"{len(slot_groups.mains)} main candidates, {len(slot_groups.sides)} side candidates.",
    )

    main_outcome = planner._best_choice(
        all_candidates=candidates,
        candidates=slot_groups.mains,
        request=active_request,
        pantry_inventory=pantry_inventory,
        variety_profile=variety_profile,
        purchased_quantities={},
        meals=[],
        day_number=1,
        slot_number=1,
        current_total=0.0,
        request_cycle_offset=request_cycle_offset,
        candidate_role="main",
        anchor_recipe=None,
        enforce_repeat_cap=True,
    )

    main_selected_title = None
    main_diagnostics_seconds = 0.0
    side_selected_title = None
    side_outcome = None
    side_diagnostics_seconds = 0.0

    purchased_quantities = {}
    meals = []
    if main_outcome is not None:
        diagnostic_started_at = time.perf_counter()
        planner._build_selection_diagnostic(
            main_outcome,
            1,
            1,
            active_request,
            used_repeat_fallback=False,
            anchor_recipe=None,
        )
        main_diagnostics_seconds = time.perf_counter() - diagnostic_started_at
        main_selected_title = main_outcome.selected.recipe.title
        planner._apply_recipe(purchased_quantities, main_outcome.selected.recipe, active_request, pantry_inventory)
        meals.append(
            PlannedMeal(
                day=1,
                slot=1,
                recipe=main_outcome.selected.recipe,
                scaled_servings=active_request.servings,
                incremental_cost=main_outcome.selected.incremental_cost,
                consumed_cost=planner._estimate_recipe_consumed_cost(
                    main_outcome.selected.recipe,
                    active_request,
                    pantry_inventory,
                ),
                meal_role="main",
            )
        )

        current_total = planner._estimate_total_cost(purchased_quantities).total_cost
        projected_day_calories = planner._projected_day_calories(
            candidates,
            meals,
            None,
            active_request,
            1,
            1,
        )
        current_penalty = planner._calorie_target_penalty(
            projected_day_calories,
            active_request.daily_calorie_target_min,
            active_request.daily_calorie_target_max,
        )
        side_outcome = planner._best_choice(
            all_candidates=candidates,
            candidates=slot_groups.sides,
            request=active_request,
            pantry_inventory=pantry_inventory,
            variety_profile=variety_profile,
            purchased_quantities=purchased_quantities,
            meals=meals,
            day_number=1,
            slot_number=1,
            current_total=current_total,
            request_cycle_offset=0,
            candidate_role="side",
            anchor_recipe=main_outcome.selected.recipe,
            enforce_repeat_cap=False,
        )
        if side_outcome is not None:
            side_day_calories = planner._projected_day_calories(
                candidates,
                meals,
                side_outcome.selected.recipe,
                active_request,
                1,
                1,
            )
            side_penalty = planner._calorie_target_penalty(
                side_day_calories,
                active_request.daily_calorie_target_min,
                active_request.daily_calorie_target_max,
            )
            if side_day_calories <= active_request.daily_calorie_target_max + 200 and side_penalty <= current_penalty:
                diagnostic_started_at = time.perf_counter()
                planner._build_selection_diagnostic(
                    side_outcome,
                    1,
                    1,
                    active_request,
                    used_repeat_fallback=False,
                    anchor_recipe=main_outcome.selected.recipe,
                )
                side_diagnostics_seconds = time.perf_counter() - diagnostic_started_at
                side_selected_title = side_outcome.selected.recipe.title
            else:
                side_outcome = None
    planner._clear_active_slot_progress()

    progress_samples = tuple(
        {
            "stage": update.stage,
            "label": update.label,
            "detail": update.detail,
            "percent": round(update.percent, 4),
        }
        for update in progress_updates[:12]
    )
    return SlotSelectionDiagnosis(
        request_name="balanced_budget_week",
        slot_label="monday_lunch",
        candidate_gathering_seconds=round(candidate_gathering_seconds, 4),
        main_candidate_count=len(slot_groups.mains),
        side_candidate_count=len(slot_groups.sides),
        main_selected_title=main_selected_title,
        side_selected_title=side_selected_title,
        main_timing=None if main_outcome is None else asdict(main_outcome.timing),
        side_timing=None if side_outcome is None else asdict(side_outcome.timing),
        main_diagnostics_seconds=round(main_diagnostics_seconds, 4),
        side_diagnostics_seconds=round(side_diagnostics_seconds, 4),
        progress_event_count=len(progress_updates),
        progress_samples=progress_samples,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose Monday lunch selection timing.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    args = parser.parse_args()
    diagnosis = diagnose_monday_lunch()
    if args.json:
        print(json.dumps(asdict(diagnosis), indent=2))
        return
    print(f"Request: {diagnosis.request_name}")
    print(f"Slot: {diagnosis.slot_label}")
    print(f"Candidate gathering: {diagnosis.candidate_gathering_seconds:.4f}s")
    print(f"Main candidates: {diagnosis.main_candidate_count}")
    print(f"Side candidates: {diagnosis.side_candidate_count}")
    print(f"Selected main: {diagnosis.main_selected_title}")
    print(f"Selected side: {diagnosis.side_selected_title}")
    print(f"Main timing: {diagnosis.main_timing}")
    print(f"Side timing: {diagnosis.side_timing}")
    print(f"Main diagnostics: {diagnosis.main_diagnostics_seconds:.4f}s")
    print(f"Side diagnostics: {diagnosis.side_diagnostics_seconds:.4f}s")
    print(f"Progress events: {diagnosis.progress_event_count}")
    for sample in diagnosis.progress_samples:
        print(sample)


if __name__ == "__main__":
    main()
