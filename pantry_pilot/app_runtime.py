from __future__ import annotations

from dataclasses import dataclass

from pantry_pilot.models import MealPlan, PlannerRequest
from pantry_pilot.pantry_carryover import PantryCarryoverStore, PantryInventoryItem
from pantry_pilot.personal_targets import summarize_targets
from pantry_pilot.plan_display import build_plan_text_export, build_shopping_list_csv, summarize_calories
from pantry_pilot.planner import AggregatedIngredient, WeeklyMealPlanner
from pantry_pilot.providers import PricingContext, build_pricing_context


@dataclass(frozen=True)
class AppPlanSnapshot:
    request: PlannerRequest
    planner: WeeklyMealPlanner
    pricing_context: PricingContext
    plan: MealPlan
    pantry_inventory: tuple[PantryInventoryItem, ...]
    calorie_target_text: str
    export_text: str
    shopping_list_csv: str


def format_calorie_target(minimum: int, maximum: int) -> str:
    return f"{minimum:,} to {maximum:,} calories per day"


def format_personal_target_caption(request: PlannerRequest) -> str | None:
    summary = summarize_targets(request.personal_targets)
    if summary is None:
        return None
    return (
        f"Estimated planning guidance: {summary.calorie_target_text}; "
        f"{summary.macro_target_text}; {summary.food_group_target_text}."
    )


def build_planner_and_context(
    request: PlannerRequest,
    pantry_store: PantryCarryoverStore | None = None,
    progress_callback=None,
) -> tuple[WeeklyMealPlanner, PricingContext, tuple[PantryInventoryItem, ...]]:
    carryover_store = pantry_store or PantryCarryoverStore()
    pantry_inventory = carryover_store.load_inventory()
    pricing_context = build_pricing_context(
        pricing_mode=request.pricing_mode,
        zip_code=request.zip_code,
        store_location_id=request.store_location_id,
    )
    planner = WeeklyMealPlanner(
        grocery_provider=pricing_context.provider,
        carryover_inventory={
            item.name: AggregatedIngredient(quantity=item.quantity, unit=item.unit)
            for item in pantry_inventory
        },
        pricing_source=pricing_context.pricing_source,
        selected_store=pricing_context.selected_store,
    )
    if progress_callback is not None:
        planner.set_progress_callback(progress_callback)
    return planner, pricing_context, pantry_inventory


def build_plan_snapshot(
    request: PlannerRequest,
    pantry_store: PantryCarryoverStore | None = None,
    progress_callback=None,
) -> AppPlanSnapshot:
    planner, pricing_context, pantry_inventory = build_planner_and_context(
        request,
        pantry_store=pantry_store,
        progress_callback=progress_callback,
    )
    plan = planner.create_plan(request)
    selection_diagnostics = planner.latest_selection_diagnostics()
    calorie_target_text = format_calorie_target(
        request.daily_calorie_target_min,
        request.daily_calorie_target_max,
    )
    # Force the same export/runtime helpers the app uses to stay render-safe.
    summarize_calories(plan.meals)
    export_text = build_plan_text_export(
        request,
        plan,
        calorie_target_text,
        selection_diagnostics=selection_diagnostics,
    )
    shopping_list_csv = build_shopping_list_csv(plan)
    return AppPlanSnapshot(
        request=request,
        planner=planner,
        pricing_context=pricing_context,
        plan=plan,
        pantry_inventory=pantry_inventory,
        calorie_target_text=calorie_target_text,
        export_text=export_text,
        shopping_list_csv=shopping_list_csv,
    )
