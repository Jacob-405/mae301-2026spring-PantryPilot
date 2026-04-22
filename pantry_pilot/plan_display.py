from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from typing import Callable, Iterable

from pantry_pilot.models import MealPlan, NutritionEstimate, PlannedMeal, PlannerRequest
from pantry_pilot.personal_targets import summarize_targets
from pantry_pilot.planner import DailyNutrientDeficits, DailyNutrientState, MealCompositionProfile, MealSelectionDiagnostic
from pantry_pilot.planner import day_name, slot_label

UNKNOWN_LABEL = "Unknown"


@dataclass(frozen=True)
class CalorieSummary:
    known_total: int
    unknown_meal_count: int
    meal_count: int

    @property
    def is_partial(self) -> bool:
        return self.unknown_meal_count > 0


@dataclass(frozen=True)
class WeeklyNutritionSummary:
    calories_known_total: int
    protein_known_total: float
    carbs_known_total: float
    fat_known_total: float
    unknown_meal_count: int
    meal_count: int

    @property
    def is_partial(self) -> bool:
        return self.unknown_meal_count > 0


@dataclass(frozen=True)
class DayPlanSummary:
    day: int
    label: str
    calorie_display: str
    status_label: str
    status_help: str
    meal_count: int
    consumed_cost_known_total: float
    consumed_cost_is_partial: bool
    added_shopping_total: float


@dataclass(frozen=True)
class ShoppingListDisplayRow:
    ingredient: str
    amount_needed: str
    carryover_used: str
    amount_being_bought: str
    leftover_after_plan: str
    package_count: int
    estimated_cost: str
    price_source: str


@dataclass(frozen=True)
class ShoppingListSection:
    title: str
    rows: tuple[ShoppingListDisplayRow, ...]


def meal_total_calories(meal: PlannedMeal) -> int | None:
    calories_per_serving = meal.recipe.estimated_calories_per_serving
    if calories_per_serving is None:
        return None
    return calories_per_serving * meal.scaled_servings


def summarize_calories(meals: Iterable[PlannedMeal]) -> CalorieSummary:
    known_total = 0
    unknown_meal_count = 0
    meal_count = 0
    for meal in meals:
        meal_count += 1
        total = meal_total_calories(meal)
        if total is None:
            unknown_meal_count += 1
            continue
        known_total += total
    return CalorieSummary(
        known_total=known_total,
        unknown_meal_count=unknown_meal_count,
        meal_count=meal_count,
    )


def meal_total_nutrition(meal: PlannedMeal) -> NutritionEstimate | None:
    nutrition = meal.recipe.estimated_nutrition_per_serving
    if nutrition is None:
        return None
    scale = meal.scaled_servings
    return NutritionEstimate(
        calories=nutrition.calories * scale,
        protein_grams=round(nutrition.protein_grams * scale, 1),
        carbs_grams=round(nutrition.carbs_grams * scale, 1),
        fat_grams=round(nutrition.fat_grams * scale, 1),
    )


def summarize_weekly_nutrition(meals: Iterable[PlannedMeal]) -> WeeklyNutritionSummary:
    calories_total = 0
    protein_total = 0.0
    carbs_total = 0.0
    fat_total = 0.0
    unknown_meal_count = 0
    meal_count = 0
    for meal in meals:
        meal_count += 1
        nutrition = meal_total_nutrition(meal)
        if nutrition is None:
            unknown_meal_count += 1
            continue
        calories_total += nutrition.calories
        protein_total += nutrition.protein_grams
        carbs_total += nutrition.carbs_grams
        fat_total += nutrition.fat_grams
    return WeeklyNutritionSummary(
        calories_known_total=calories_total,
        protein_known_total=round(protein_total, 1),
        carbs_known_total=round(carbs_total, 1),
        fat_known_total=round(fat_total, 1),
        unknown_meal_count=unknown_meal_count,
        meal_count=meal_count,
    )


def format_optional_minutes(minutes: int | None) -> str:
    if minutes is None:
        return UNKNOWN_LABEL
    return f"{minutes} min"


def format_optional_currency(amount: float | None) -> str:
    if amount is None:
        return UNKNOWN_LABEL
    return f"${amount:.2f}"


def format_optional_calories_per_serving(calories: int | None) -> str:
    if calories is None:
        return UNKNOWN_LABEL
    return f"{calories:,}"


def format_optional_nutrition(nutrition: NutritionEstimate | None) -> str:
    if nutrition is None:
        return UNKNOWN_LABEL
    return (
        f"{nutrition.calories:,} cal | "
        f"P {nutrition.protein_grams:.1f}g | "
        f"C {nutrition.carbs_grams:.1f}g | "
        f"F {nutrition.fat_grams:.1f}g"
    )


def format_weekly_nutrition_summary(summary: WeeklyNutritionSummary) -> str:
    if summary.unknown_meal_count == summary.meal_count:
        return "Unknown"
    known_label = "known" if summary.is_partial else "estimated"
    return (
        f"{summary.calories_known_total:,} cal {known_label} | "
        f"P {summary.protein_known_total:.1f}g | "
        f"C {summary.carbs_known_total:.1f}g | "
        f"F {summary.fat_known_total:.1f}g"
    )


def format_estimate_confidence_label(
    meal: PlannedMeal,
    diagnostic: MealSelectionDiagnostic | None = None,
) -> str:
    if meal.recipe.estimated_nutrition_per_serving is None or meal.consumed_cost is None:
        return "Partial estimate"
    if diagnostic is None:
        return "Estimated"
    if "stage:role-gating:fallback" in diagnostic.reasons or "main-anchor:weak" in diagnostic.reasons:
        return "Lower-confidence estimate"
    return "Estimated"


def confidence_note(
    meal: PlannedMeal,
    diagnostic: MealSelectionDiagnostic | None = None,
) -> str | None:
    if meal.recipe.estimated_nutrition_per_serving is None:
        return "Nutrition is only partially known for this meal."
    if meal.consumed_cost is None:
        return "Consumed cost is partial because some ingredient pricing is still unknown."
    if diagnostic is not None and ("stage:role-gating:fallback" in diagnostic.reasons or "main-anchor:weak" in diagnostic.reasons):
        return "This meal fit the week, but its main-anchor confidence is weaker than the best-case ideal."
    return None


def format_compact_currency_total(amount: float, *, partial: bool = False) -> str:
    if partial:
        return f"${amount:.2f} known"
    return f"${amount:.2f}"


def format_calorie_total_metric(summary: CalorieSummary) -> str:
    if not summary.is_partial:
        return f"{summary.known_total:,}"
    if summary.known_total == 0:
        return UNKNOWN_LABEL
    return f"{summary.known_total:,} known"


def format_average_calorie_metric(summary: CalorieSummary, *, days: int = 7) -> str:
    if not summary.is_partial:
        return f"{round(summary.known_total / days):,}"
    if summary.known_total == 0:
        return UNKNOWN_LABEL
    return f"{round(summary.known_total / days):,} known"


def format_calorie_coverage_note(summary: CalorieSummary) -> str | None:
    if not summary.is_partial:
        return None
    meal_label = "meal" if summary.unknown_meal_count == 1 else "meals"
    return (
        f"Partial calorie total. {summary.unknown_meal_count} {meal_label} "
        "have unknown calorie estimates."
    )


def format_daily_calorie_display(summary: CalorieSummary) -> str:
    if summary.is_partial:
        if summary.known_total == 0:
            return UNKNOWN_LABEL
        return f"{summary.known_total:,} known (partial)"
    return f"{summary.known_total:,}"


def calorie_status_label(summary: CalorieSummary, minimum: int, maximum: int) -> tuple[str, str]:
    if summary.is_partial:
        return (
            "Unknown",
            "Daily calories cannot be compared to the selected target because one or more meals have unknown calorie estimates.",
        )
    if summary.known_total < minimum:
        return "Below target", "Daily calories are under the selected target range."
    if summary.known_total > maximum:
        return "Above target", "Daily calories are above the selected target range."
    return "Within target", "Daily calories are within the selected target range."


def build_day_plan_summaries(
    request: PlannerRequest,
    plan: MealPlan,
) -> tuple[DayPlanSummary, ...]:
    summaries: list[DayPlanSummary] = []
    for day in range(1, 8):
        day_meals = [meal for meal in plan.meals if meal.day == day]
        daily_calorie_summary = summarize_calories(day_meals)
        status_label, status_help = calorie_status_label(
            daily_calorie_summary,
            request.daily_calorie_target_min,
            request.daily_calorie_target_max,
        )
        known_consumed_total = round(
            sum(meal.consumed_cost or 0.0 for meal in day_meals),
            2,
        )
        consumed_partial = any(meal.consumed_cost is None for meal in day_meals)
        added_shopping_total = round(sum(meal.incremental_cost for meal in day_meals), 2)
        summaries.append(
            DayPlanSummary(
                day=day,
                label=day_name(day),
                calorie_display=format_daily_calorie_display(daily_calorie_summary),
                status_label=status_label,
                status_help=status_help,
                meal_count=len(day_meals),
                consumed_cost_known_total=known_consumed_total,
                consumed_cost_is_partial=consumed_partial,
                added_shopping_total=added_shopping_total,
            )
        )
    return tuple(summaries)


def shopping_category_for_item(item_name: str) -> str:
    normalized = item_name.casefold()
    produce_keywords = (
        "apple",
        "avocado",
        "banana",
        "basil",
        "berry",
        "broccoli",
        "cabbage",
        "carrot",
        "cauliflower",
        "celery",
        "cilantro",
        "cucumber",
        "dill",
        "garlic",
        "greens",
        "jalapeno",
        "kale",
        "lemon",
        "lettuce",
        "lime",
        "mushroom",
        "onion",
        "parsley",
        "pepper",
        "potato",
        "romaine",
        "salad",
        "spinach",
        "squash",
        "tomato",
        "zucchini",
    )
    protein_keywords = (
        "beef",
        "beans",
        "chicken",
        "chickpea",
        "egg",
        "fish",
        "lentil",
        "pork",
        "salmon",
        "sausage",
        "shrimp",
        "steak",
        "tofu",
        "tuna",
        "turkey",
    )
    dairy_keywords = (
        "butter",
        "cheese",
        "cream",
        "creamer",
        "milk",
        "mozzarella",
        "parmesan",
        "sour cream",
        "yogurt",
    )
    grain_keywords = (
        "bread",
        "bun",
        "cereal",
        "flour",
        "noodle",
        "oat",
        "pasta",
        "quinoa",
        "rice",
        "tortilla",
    )
    pantry_keywords = (
        "broth",
        "canned",
        "cinnamon",
        "cumin",
        "honey",
        "mustard",
        "oil",
        "paprika",
        "peanut butter",
        "pepper",
        "salt",
        "salsa",
        "sauce",
        "soy",
        "spice",
        "sugar",
        "vinegar",
    )
    if any(keyword in normalized for keyword in produce_keywords):
        return "Produce"
    if any(keyword in normalized for keyword in protein_keywords):
        return "Protein"
    if any(keyword in normalized for keyword in dairy_keywords):
        return "Dairy And Refrigerated"
    if any(keyword in normalized for keyword in grain_keywords):
        return "Grains And Starches"
    if any(keyword in normalized for keyword in pantry_keywords):
        return "Pantry"
    return "Other"


def build_grouped_shopping_sections(plan: MealPlan) -> tuple[ShoppingListSection, ...]:
    ordered_titles = (
        "Produce",
        "Protein",
        "Dairy And Refrigerated",
        "Grains And Starches",
        "Pantry",
        "Other",
    )
    grouped: dict[str, list[ShoppingListDisplayRow]] = {title: [] for title in ordered_titles}
    for item in sorted(plan.shopping_list, key=lambda entry: entry.name.casefold()):
        grouped[shopping_category_for_item(item.name)].append(
            ShoppingListDisplayRow(
                ingredient=item.name,
                amount_needed=f"{item.quantity} {item.unit}",
                carryover_used=(
                    "N/A"
                    if item.carryover_used_quantity == 0
                    else f"{item.carryover_used_quantity} {item.package_unit or item.unit}"
                ),
                amount_being_bought=(
                    "N/A"
                    if item.purchased_quantity == 0
                    else f"{item.purchased_quantity} {item.package_unit}"
                ),
                leftover_after_plan=(
                    "N/A"
                    if item.leftover_quantity_remaining == 0
                    else f"{item.leftover_quantity_remaining} {item.package_unit or item.unit}"
                ),
                package_count=item.estimated_packages,
                estimated_cost=format_optional_currency(item.estimated_cost),
                price_source=item.pricing_source,
            )
        )
    return tuple(
        ShoppingListSection(title=title, rows=tuple(rows))
        for title, rows in grouped.items()
        if rows
    )


def meal_selection_lookup(
    selection_diagnostics: Iterable[MealSelectionDiagnostic],
) -> dict[tuple[int, int, str], MealSelectionDiagnostic]:
    return {
        (diagnostic.day, diagnostic.slot_number, diagnostic.meal_role): diagnostic
        for diagnostic in selection_diagnostics
    }


def compact_selection_rationale(diagnostic: MealSelectionDiagnostic | None) -> str:
    if diagnostic is None:
        return "Chosen from the current safe, priced, under-budget pool."
    reason_map = {
        "main-anchor:strong": "strong anchor",
        "main-anchor:acceptable": "acceptable anchor",
        "target:protein-support": "supports protein target",
        "target:protein-range": "lands near protein target",
        "target:protein-gap": "fills a protein gap",
        "target:protein-priority": "prioritizes remaining protein needs",
        "target:produce-support": "supports produce target",
        "target:produce-gap": "fills a produce gap",
        "target:grains-support": "supports grain target",
        "target:dairy-support": "supports dairy target",
        "target:goal-high-protein": "fits high-protein goal",
        "target:calorie-guidance": "fits estimated guidance",
        "weekly:protein-variety": "adds protein variety",
        "weekly:produce-variety": "adds produce variety",
        "weekly:side-diversity": "improves side diversity",
        "weekly:side-produce-variety": "adds a different produce side",
        "weekly:vegetable-side-balance": "keeps the week vegetable-forward",
        "complements-main": "complements the main",
        "complements-main-produce-gap": "fills what the main lacks in produce",
        "complements-main-protein-gap": "fills what the main lacks in protein",
        "complements-main-starch-gap": "fills what the main lacks in starch",
        "pantry-support": "uses pantry staples",
        "preferred-cuisine": "matches cuisine preference",
        "calorie-alignment": "fits calorie target",
    }
    chosen_bits: list[str] = []
    for reason in diagnostic.reasons:
        if reason in reason_map:
            chosen_bits.append(reason_map[reason])
        if len(chosen_bits) == 3:
            break
    if not chosen_bits:
        chosen_bits.append("fit the week best")
    return "Why chosen: " + ", ".join(chosen_bits) + "."


def format_daily_nutrient_state(state: DailyNutrientState | None) -> str:
    if state is None:
        return "Unavailable"
    return (
        f"{state.calories:.0f} cal | "
        f"P {state.protein_grams:.1f}g | "
        f"C {state.carbs_grams:.1f}g | "
        f"F {state.fat_grams:.1f}g | "
        f"produce {state.produce_support:.1f} | "
        f"grains/starches {state.grains_starches_support:.1f} | "
        f"dairy {state.dairy_support:.1f}"
    )


def format_daily_nutrient_deficits(deficits: DailyNutrientDeficits | None) -> str:
    if deficits is None:
        return "Unavailable"
    bits = []
    if deficits.calories_below_min > 0:
        bits.append(f"{deficits.calories_below_min:.0f} cal below minimum")
    if deficits.calories_above_max > 0:
        bits.append(f"{deficits.calories_above_max:.0f} cal above maximum")
    bits.extend(
        (
            f"protein {deficits.protein_grams:.1f}g",
            f"carbs {deficits.carbs_grams:.1f}g",
            f"fat {deficits.fat_grams:.1f}g",
            f"produce {deficits.produce_support:.1f}",
            f"grains/starches {deficits.grains_starches_support:.1f}",
            f"dairy {deficits.dairy_support:.1f}",
        )
    )
    return ", ".join(bits)


def format_meal_composition_profile(profile: MealCompositionProfile | None) -> str:
    if profile is None:
        return "Unavailable"
    return (
        f"dominant {profile.dominant_component}, "
        f"{profile.heaviness}, "
        f"protein {profile.protein_support:.1f}, "
        f"vegetable {profile.vegetable_support:.1f}, "
        f"starch {profile.starch_support:.1f}, "
        f"dairy {profile.dairy_support:.1f}"
    )


def summarize_plan_balance(selection_diagnostics: Iterable[MealSelectionDiagnostic]) -> str:
    diagnostics = tuple(selection_diagnostics)
    if not diagnostics:
        return "Balance summary unavailable."
    strong_mains = sum(1 for diagnostic in diagnostics if "main-anchor:strong" in diagnostic.reasons)
    complementary_sides = sum(1 for diagnostic in diagnostics if "complements-main" in diagnostic.reasons)
    target_hits = sum(
        1
        for diagnostic in diagnostics
        if any(reason.startswith("target:") for reason in diagnostic.reasons)
    )
    variety_hits = sum(
        1
        for diagnostic in diagnostics
        if any(reason.startswith("weekly:") for reason in diagnostic.reasons)
    )
    return (
        f"{strong_mains} strong-anchor meals, "
        f"{complementary_sides} complementary sides, "
        f"{variety_hits} week-balance adjustments, "
        f"{target_hits} target-guided choices."
    )


def format_personal_target_summary(request: PlannerRequest) -> tuple[str, str] | None:
    summary = summarize_targets(request.personal_targets)
    if summary is None:
        return None
    return (
        f"{summary.calorie_target_text} | {summary.macro_target_text}",
        f"{summary.food_group_target_text}. {summary.guidance_note}",
    )


def summarize_carryover_usage(plan: MealPlan) -> str:
    used_items = [item for item in plan.shopping_list if item.carryover_used_quantity > 0]
    if not used_items:
        return "No pantry carryover was used this week."
    total_used = round(sum(item.carryover_used_quantity for item in used_items), 2)
    return f"Pantry carryover used on {len(used_items)} ingredient(s), {total_used} total package-unit equivalents."


def build_plan_text_export(
    request: PlannerRequest,
    plan: MealPlan,
    calorie_target_text: str,
    repeat_label_getter: Callable[[PlannedMeal], tuple[str, str] | None] | None = None,
    selection_diagnostics: Iterable[MealSelectionDiagnostic] = (),
) -> str:
    weekly_summary = summarize_calories(plan.meals)
    weekly_nutrition = summarize_weekly_nutrition(plan.meals)
    diagnostic_lookup = meal_selection_lookup(selection_diagnostics)
    weekly_lines = [
        "PantryPilot Weekly Plan",
        "",
        f"Budget: ${request.weekly_budget:.2f}",
        f"Estimated spend: ${plan.estimated_total_cost:.2f}",
        f"Remaining budget: ${request.weekly_budget - plan.estimated_total_cost:.2f}",
        f"Weekly calories: {format_calorie_total_metric(weekly_summary)}",
        f"Average calories per day: {format_average_calorie_metric(weekly_summary)}",
        f"Weekly nutrition: {format_weekly_nutrition_summary(weekly_nutrition)}",
        f"Calorie target: {calorie_target_text}",
        f"Meal structure: {' + '.join(value.title() for value in request.meal_structure or ('meal',))}",
        f"Variety preference: {request.variety_preference.title()}",
        f"Leftovers mode: {request.leftovers_mode.title()}",
        f"Carryover summary: {summarize_carryover_usage(plan)}",
        f"Plan balance summary: {summarize_plan_balance(selection_diagnostics)}",
    ]
    target_summary = format_personal_target_summary(request)
    if target_summary is not None:
        weekly_lines.append(f"Personal target guidance: {target_summary[0]}")
        weekly_lines.append(f"Guidance note: {target_summary[1]}")
    calorie_note = format_calorie_coverage_note(weekly_summary)
    if calorie_note:
        weekly_lines.append(f"Calories note: {calorie_note}")
    if weekly_nutrition.is_partial:
        weekly_lines.append(
            f"Nutrition note: {weekly_nutrition.unknown_meal_count} meal(s) still have partial or unknown nutrition."
        )
    weekly_lines.extend(["", "Weekly Plan", ""])

    lines = weekly_lines
    for day in range(1, 8):
        day_meals = [meal for meal in plan.meals if meal.day == day]
        daily_summary = summarize_calories(day_meals)
        day_status, _ = calorie_status_label(
            daily_summary,
            request.daily_calorie_target_min,
            request.daily_calorie_target_max,
        )
        lines.append(f"{day_name(day)}")
        lines.append(f"  Daily calories: {format_daily_calorie_display(daily_summary)} ({day_status})")
        for meal in day_meals:
            meal_calories = meal_total_calories(meal)
            meal_nutrition = meal_total_nutrition(meal)
            diagnostic = diagnostic_lookup.get((meal.day, meal.slot, meal.meal_role))
            repeat_suffix = ""
            if repeat_label_getter is not None:
                repeat_badge = repeat_label_getter(meal)
                if repeat_badge is not None:
                    repeat_suffix = f" [{repeat_badge[0]}: {repeat_badge[1]}]"
            lines.append(
                "  "
                + f"{slot_label(request.meals_per_day, meal.slot, request.meal_structure)}: "
                + f"{meal.recipe.title} ({meal.meal_role}) | {format_optional_minutes(meal.recipe.prep_time_minutes)} | "
                + f"consumed {format_optional_currency(meal.consumed_cost)} | "
                + f"added shopping {format_optional_currency(meal.incremental_cost)} | "
                + (
                    f"{meal_calories:,} calories"
                    if meal_calories is not None
                    else f"{UNKNOWN_LABEL} calories"
                )
                + repeat_suffix
            )
            lines.append(f"    Nutrition: {format_optional_nutrition(meal_nutrition)}")
            lines.append(f"    Confidence: {format_estimate_confidence_label(meal, diagnostic)}")
            lines.append(f"    {compact_selection_rationale(diagnostic)}")
            if diagnostic is not None:
                lines.append(f"    Daily state before: {format_daily_nutrient_state(diagnostic.daily_state_before)}")
                lines.append(f"    Daily state after: {format_daily_nutrient_state(diagnostic.daily_state_after)}")
                lines.append(
                    f"    Remaining deficits before: {format_daily_nutrient_deficits(diagnostic.daily_deficits_before)}"
                )
                lines.append(
                    f"    Remaining deficits after: {format_daily_nutrient_deficits(diagnostic.daily_deficits_after)}"
                )
                if diagnostic.meal_role == "side":
                    lines.append(
                        f"    Main composition: {format_meal_composition_profile(diagnostic.anchor_composition_profile)}"
                    )
                    lines.append(
                        f"    Side composition: {format_meal_composition_profile(diagnostic.selected_composition_profile)}"
                    )
                    if diagnostic.runner_up_loss_reasons:
                        lines.append(
                            "    Runner-up lost because: " + ", ".join(diagnostic.runner_up_loss_reasons)
                        )
            note = confidence_note(meal, diagnostic)
            if note:
                lines.append(f"    Note: {note}")
        lines.append("")

    lines.extend(["Shopping List", ""])
    for item in plan.shopping_list:
        lines.append(
            f"- {item.name}: need {item.quantity} {item.unit}, "
            f"use carryover {item.carryover_used_quantity} {item.package_unit or item.unit}, "
            f"buy {item.purchased_quantity} {item.package_unit or item.unit}, "
            f"leftover {item.leftover_quantity_remaining} {item.package_unit or item.unit}, "
            f"packages {item.estimated_packages}, "
            f"estimated cost {format_optional_currency(item.estimated_cost)}"
        )

    if plan.notes:
        lines.extend(["", "Planner Notes"])
        for note in plan.notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


def build_shopping_list_csv(plan: MealPlan) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Ingredient",
            "Amount Needed",
            "Carryover Used",
            "Amount Being Bought",
            "Leftover After Plan",
            "Package Count",
            "Estimated Cost",
            "Price Source",
        ]
    )
    for item in plan.shopping_list:
        writer.writerow(
            [
                item.name,
                f"{item.quantity} {item.unit}",
                (
                    "N/A"
                    if item.carryover_used_quantity == 0
                    else f"{item.carryover_used_quantity} {item.package_unit or item.unit}"
                ),
                "N/A" if item.purchased_quantity == 0 else f"{item.purchased_quantity} {item.package_unit}",
                (
                    "N/A"
                    if item.leftover_quantity_remaining == 0
                    else f"{item.leftover_quantity_remaining} {item.package_unit or item.unit}"
                ),
                item.estimated_packages,
                UNKNOWN_LABEL if item.estimated_cost is None else f"{item.estimated_cost:.2f}",
                item.pricing_source,
            ]
        )
    return output.getvalue()
