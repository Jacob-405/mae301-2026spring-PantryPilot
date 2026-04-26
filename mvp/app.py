from dataclasses import replace
from datetime import datetime

import streamlit as st

from pantry_pilot.app_runtime import build_planner_and_context, format_calorie_target
from pantry_pilot.favorites import DEFAULT_FAVORITES_PATH, FavoritePlanStore
from pantry_pilot.personal_targets import generate_personal_targets, summarize_targets
from pantry_pilot.plan_failures import build_failure_feedback
from pantry_pilot.plan_failures import build_runtime_failure_feedback, is_transient_runtime_failure
from pantry_pilot.models import PlannerRequest, UserNutritionProfile
from pantry_pilot.normalization import normalize_name, parse_csv_list
from pantry_pilot.pantry_carryover import DEFAULT_PANTRY_CARRYOVER_PATH, PantryCarryoverStore
from pantry_pilot.plan_display import (
    build_day_plan_summaries,
    build_plan_text_export,
    build_grouped_shopping_sections,
    build_shopping_list_csv,
    calorie_status_label,
    compact_selection_rationale,
    confidence_note,
    format_average_calorie_metric,
    format_calorie_coverage_note,
    format_calorie_total_metric,
    format_compact_currency_total,
    format_daily_calorie_display,
    format_daily_nutrient_deficits,
    format_daily_nutrient_state,
    format_estimate_confidence_label,
    format_meal_composition_profile,
    format_optional_nutrition,
    format_optional_calories_per_serving,
    format_optional_currency,
    format_optional_minutes,
    meal_total_calories,
    meal_total_nutrition,
    meal_selection_lookup,
    summarize_carryover_usage,
    summarize_calories,
    summarize_plan_balance,
    summarize_weekly_nutrition,
    format_personal_target_summary,
    format_weekly_nutrition_summary,
)
from pantry_pilot.planner import PlannerError, WeeklyMealPlanner, day_name, slot_label
from pantry_pilot.providers import discover_kroger_locations, format_location_label


st.set_page_config(page_title="PantryPilot", layout="wide")
st.title("PantryPilot")
st.write("Build a deterministic 7-day meal plan from local recipes and grocery prices.")

MEAL_STRUCTURE_OPTIONS = {
    "Breakfast + Lunch + Dinner": ("breakfast", "lunch", "dinner"),
    "Lunch + Dinner": ("lunch", "dinner"),
    "Dinner Only": ("dinner",),
}
LEFTOVERS_MODE_OPTIONS = ("Off", "Moderate", "Frequent")
PROFILE_ACTIVITY_OPTIONS = ("Sedentary", "Low Active", "Active", "Very Active")
PROFILE_GOAL_OPTIONS = ("Maintain", "Mild Deficit", "Mild Surplus", "High Protein Preference")
FAVORITES_STORE = FavoritePlanStore()
PANTRY_CARRYOVER_STORE = PantryCarryoverStore()

FIELD_DEFAULTS = {
    "weekly_budget_input": 90.0,
    "servings_input": 2,
    "cuisine_preferences_input": "mediterranean, mexican, american",
    "allergies_input": "",
    "excluded_ingredients_input": "",
    "diet_restrictions_input": "",
    "pantry_staples_input": "olive oil, cinnamon",
    "max_prep_time_input": 35,
    "meal_structure_input": "Lunch + Dinner",
    "zip_code_input": "",
    "pricing_mode_input": "Mock pricing",
    "calorie_target_min_input": 1600,
    "calorie_target_max_input": 2200,
    "variety_preference_input": "Balanced",
    "leftovers_mode_input": "Off",
    "use_personal_targets_input": False,
    "profile_age_input": 35,
    "profile_sex_input": "Female",
    "profile_height_cm_input": 168.0,
    "profile_weight_kg_input": 72.0,
    "profile_activity_input": "Low Active",
    "profile_goal_input": "Maintain",
}

PRESET_SCENARIOS = {
    "Balanced Budget Week": {
        "weekly_budget_input": 90.0,
        "servings_input": 2,
        "cuisine_preferences_input": "mediterranean, mexican, american",
        "allergies_input": "",
        "excluded_ingredients_input": "",
        "diet_restrictions_input": "",
        "pantry_staples_input": "olive oil, cinnamon",
        "max_prep_time_input": 35,
        "meal_structure_input": "Lunch + Dinner",
        "pricing_mode_input": "Mock pricing",
        "calorie_target_min_input": 1800,
        "calorie_target_max_input": 2300,
        "variety_preference_input": "Balanced",
        "leftovers_mode_input": "Off",
    },
    "Vegetarian Budget Week": {
        "weekly_budget_input": 75.0,
        "servings_input": 2,
        "cuisine_preferences_input": "mediterranean, mexican, italian",
        "allergies_input": "",
        "excluded_ingredients_input": "chicken breast, ground turkey",
        "diet_restrictions_input": "vegetarian",
        "pantry_staples_input": "olive oil, garlic, onion",
        "max_prep_time_input": 30,
        "meal_structure_input": "Lunch + Dinner",
        "pricing_mode_input": "Mock pricing",
        "calorie_target_min_input": 1700,
        "calorie_target_max_input": 2200,
        "variety_preference_input": "High",
        "leftovers_mode_input": "Moderate",
    },
    "Pantry-First Week": {
        "weekly_budget_input": 60.0,
        "servings_input": 2,
        "cuisine_preferences_input": "mexican, mediterranean, american",
        "allergies_input": "",
        "excluded_ingredients_input": "",
        "diet_restrictions_input": "",
        "pantry_staples_input": "olive oil, rice, black beans, chickpeas, salsa, canned tomatoes, garlic",
        "max_prep_time_input": 35,
        "meal_structure_input": "Lunch + Dinner",
        "pricing_mode_input": "Mock pricing",
        "calorie_target_min_input": 1700,
        "calorie_target_max_input": 2300,
        "variety_preference_input": "Low",
        "leftovers_mode_input": "Frequent",
    },
    "Quick Prep Week": {
        "weekly_budget_input": 95.0,
        "servings_input": 2,
        "cuisine_preferences_input": "american, mediterranean",
        "allergies_input": "",
        "excluded_ingredients_input": "",
        "diet_restrictions_input": "",
        "pantry_staples_input": "olive oil, cinnamon, garlic",
        "max_prep_time_input": 20,
        "meal_structure_input": "Lunch + Dinner",
        "pricing_mode_input": "Mock pricing",
        "calorie_target_min_input": 1800,
        "calorie_target_max_input": 2400,
        "variety_preference_input": "High",
        "leftovers_mode_input": "Moderate",
    },
}


@st.cache_data(show_spinner=False)
def get_kroger_locations(zip_code: str):
    return discover_kroger_locations(zip_code)


def initialize_form_state() -> None:
    for key, value in FIELD_DEFAULTS.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("preset_selector", "Balanced Budget Week")
    st.session_state.setdefault("current_request", None)
    st.session_state.setdefault("current_plan", None)
    st.session_state.setdefault("plan_feedback", "")
    st.session_state.setdefault("plan_error", "")
    st.session_state.setdefault("favorite_name_input", "")
    st.session_state.setdefault("pantry_feedback", "")


def apply_preset(preset_name: str) -> None:
    preset = PRESET_SCENARIOS[preset_name]
    for key, value in preset.items():
        st.session_state[key] = value


def meal_structure_for_label(label: str) -> tuple[str, ...]:
    return MEAL_STRUCTURE_OPTIONS[label]


def meal_repeat_label(request: PlannerRequest, plan, meal) -> tuple[str, str] | None:
    prior_matches = [
        prior_meal
        for prior_meal in plan.meals
        if (prior_meal.day, prior_meal.slot) < (meal.day, meal.slot)
        and prior_meal.recipe.recipe_id == meal.recipe.recipe_id
    ]
    if not prior_matches:
        return None
    if normalize_name(request.leftovers_mode) != "off":
        return "Leftovers", "Cook once, eat again"
    return "Repeat meal", "This recipe appeared earlier in the week"


def current_profile_targets(meals_per_day: int):
    if not st.session_state.get("use_personal_targets_input"):
        return None, None
    profile = UserNutritionProfile(
        age_years=int(st.session_state["profile_age_input"]),
        sex=st.session_state["profile_sex_input"],
        height_cm=float(st.session_state["profile_height_cm_input"]),
        weight_kg=float(st.session_state["profile_weight_kg_input"]),
        activity_level=st.session_state["profile_activity_input"],
        planning_goal=st.session_state["profile_goal_input"],
    )
    targets = generate_personal_targets(profile, meals_per_day=meals_per_day)
    return profile, targets


def render_saved_plans() -> None:
    saved_plans, warning = FAVORITES_STORE.list_saved_plans()
    st.divider()
    st.subheader("Saved Plans")
    st.caption(f"Saved locally at `{DEFAULT_FAVORITES_PATH}`")
    if warning:
        st.warning(warning)
    if not saved_plans:
        st.caption("No saved plans yet.")
        return
    for record in saved_plans:
        entry = st.container(border=True)
        with entry:
            st.markdown(f"**{record.name}**")
            calorie_summary = summarize_calories(record.plan.meals)
            st.caption(
                f"Saved {record.saved_at} | "
                f"${record.plan.estimated_total_cost:.2f} | "
                f"{format_average_calorie_metric(calorie_summary)} avg calories/day"
            )
            coverage_note = format_calorie_coverage_note(calorie_summary)
            if coverage_note:
                st.caption(coverage_note)
            if st.button("Open Saved Plan", key=f"open-saved-{record.plan_id}", use_container_width=True):
                st.session_state["current_request"] = record.request
                st.session_state["current_plan"] = record.plan
                st.session_state["plan_feedback"] = f"Loaded saved plan: {record.name}."
                st.session_state["plan_error"] = ""
                st.rerun()


def validate_csv_field(raw_value: str, label: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    stripped = raw_value.strip()
    if not stripped:
        return errors, warnings
    if ";" in stripped and "," not in stripped:
        errors.append(f"{label} must use commas, not semicolons.")
    if stripped.startswith(",") or stripped.endswith(",") or ",," in stripped:
        warnings.append(f"{label} has blank entries. PantryPilot will ignore empty items.")
    if stripped and not parse_csv_list(raw_value):
        errors.append(f"{label} did not contain any valid comma-separated items.")
    return errors, warnings


def validate_request_inputs(
    weekly_budget: float,
    max_prep_time: int,
    meals_per_day: int,
    calorie_target_min: int,
    calorie_target_max: int,
    csv_inputs: dict[str, str],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if weekly_budget <= 0:
        errors.append("Weekly budget must be greater than $0.")
    elif weekly_budget < 25:
        warnings.append("The weekly budget is very low. A full 7-day plan may not fit.")

    if max_prep_time < 10 or max_prep_time > 180:
        errors.append("Max prep time must stay between 10 and 180 minutes.")
    elif max_prep_time <= 15:
        warnings.append("Very short prep limits can leave too few recipes to plan a full week.")

    if calorie_target_min >= calorie_target_max:
        errors.append("Daily calorie target minimum must be lower than the maximum.")
    if calorie_target_max < meals_per_day * 250:
        errors.append(
            f"The calorie target is too low for {meals_per_day} meals per day. Increase the daily maximum or reduce meals per day."
        )
    if calorie_target_min > meals_per_day * 1400:
        warnings.append("The calorie target is unusually high for the selected meals per day.")
    if calorie_target_max - calorie_target_min < meals_per_day * 150:
        warnings.append("The calorie target range is narrow. Planning may fail unless you loosen other constraints.")

    for label, raw_value in csv_inputs.items():
        field_errors, field_warnings = validate_csv_field(raw_value, label)
        errors.extend(field_errors)
        warnings.extend(field_warnings)

    return errors, warnings


def diagnose_no_match_constraints(planner: WeeklyMealPlanner, request: PlannerRequest) -> list[str]:
    causes: list[str] = []
    if request.allergies or request.diet_restrictions or request.excluded_ingredients:
        relaxed_safety_request = replace(
            request,
            allergies=(),
            diet_restrictions=(),
            excluded_ingredients=(),
        )
        if planner.filter_recipes(relaxed_safety_request):
            causes.append("Allergy, diet, or excluded-ingredient filters leave too few safe recipes.")
    if request.cuisine_preferences and planner.filter_recipes(replace(request, cuisine_preferences=())):
        causes.append("Cuisine preferences are narrowing the recipe pool too far.")
    if request.max_prep_time_minutes < 30 and planner.filter_recipes(replace(request, max_prep_time_minutes=180)):
        causes.append("The prep-time limit is too strict for the current filters.")
    if not causes:
        causes.append("Too few recipes match the current safety and planning constraints.")
    return causes


def diagnose_plan_failure(planner: WeeklyMealPlanner, request: PlannerRequest) -> tuple[str, list[str]]:
    filtered_recipes = planner.filter_recipes(request)
    if not filtered_recipes:
        return (
            "No safe recipes matched the current settings.",
            diagnose_no_match_constraints(planner, request),
        )

    causes: list[str] = []
    if len(filtered_recipes) < request.meals_per_day * 3:
        causes.append(
            f"Only {len(filtered_recipes)} recipes match the current filters, which is a small pool for {request.meals_per_day} meals per day."
        )
    if request.daily_calorie_target_max - request.daily_calorie_target_min < request.meals_per_day * 150:
        causes.append("The selected calorie target range is narrow for the requested number of meals.")
    if request.variety_preference != "low":
        try:
            planner.create_plan(replace(request, variety_preference="low"))
            causes.append("Variety settings are limiting repeats. Switching to Low variety would open more feasible plans.")
        except PlannerError:
            pass
    try:
        planner.create_plan(
            replace(
                request,
                daily_calorie_target_min=1200,
                daily_calorie_target_max=3500,
            )
        )
        causes.append("The calorie target range is restrictive enough to block an otherwise feasible plan.")
    except PlannerError:
        pass
    try:
        planner.create_plan(
            replace(
                request,
                cuisine_preferences=(),
                diet_restrictions=(),
                excluded_ingredients=(),
                max_prep_time_minutes=180,
            )
        )
        causes.append("Cuisine, diet, exclusion, or prep-time filters are tighter than the current dataset can support.")
    except PlannerError:
        pass
    try:
        planner.create_plan(replace(request, weekly_budget=max(request.weekly_budget + 25.0, request.weekly_budget * 1.5)))
        causes.append("The weekly budget is likely too low for the selected constraints and package-based pricing.")
    except PlannerError:
        pass

    if not causes:
        causes.append("The current mix of budget, calories, and recipe filters is too restrictive for a 7-day plan.")
    return (
        "PantryPilot could not build a full week from the current settings.",
        causes,
    )


def render_meal_plan(
    request: PlannerRequest,
    plan,
    planner: WeeklyMealPlanner,
    pricing_context,
    pantry_inventory,
) -> None:
    pricing_header = "Mock pricing" if plan.pricing_source == "mock" else "Kroger or Fry's pricing"
    remaining_budget = request.weekly_budget - plan.estimated_total_cost
    weekly_calorie_summary = summarize_calories(plan.meals)
    weekly_nutrition_summary = summarize_weekly_nutrition(plan.meals)
    selection_diagnostics = planner.latest_selection_diagnostics()
    diagnostic_lookup = meal_selection_lookup(selection_diagnostics)
    calorie_target_text = format_calorie_target(
        request.daily_calorie_target_min,
        request.daily_calorie_target_max,
    )
    personal_target_summary = format_personal_target_summary(request)
    day_summaries = build_day_plan_summaries(request, plan)
    shopping_sections = build_grouped_shopping_sections(plan)

    st.divider()
    if st.session_state.get("plan_feedback"):
        st.success(st.session_state["plan_feedback"])
    if st.session_state.get("plan_error"):
        st.error(st.session_state["plan_error"])
    if st.session_state.get("pantry_feedback"):
        st.info(st.session_state["pantry_feedback"])
    st.subheader("Weekly Summary")
    summary_cards = st.columns(5)
    with summary_cards[0].container(border=True):
        st.caption("Weekly Shopping Total")
        st.metric("Estimated Spend", f"${plan.estimated_total_cost:.2f}", f"${remaining_budget:.2f} remaining")
    with summary_cards[1].container(border=True):
        st.caption("Weekly Nutrition Summary")
        st.write(format_weekly_nutrition_summary(weekly_nutrition_summary))
        st.caption(f"Calories: {format_calorie_total_metric(weekly_calorie_summary)} total")
    with summary_cards[2].container(border=True):
        st.caption("Carryover Used")
        st.write(summarize_carryover_usage(plan))
        st.caption("Carryover stays separated from newly purchased ingredients.")
    with summary_cards[3].container(border=True):
        st.caption("Plan Balance Summary")
        st.write(summarize_plan_balance(selection_diagnostics))
        st.caption("Anchors, complementary sides, and week-level variety stay visible here.")
    with summary_cards[4].container(border=True):
        st.caption("Target Summary")
        st.write(personal_target_summary[0] if personal_target_summary is not None else calorie_target_text)
        st.caption(
            personal_target_summary[1]
            if personal_target_summary is not None
            else "Manual calorie targets are active for this plan."
        )

    meta_left, meta_right = st.columns((3, 2))
    with meta_left.container(border=True):
        st.markdown("**Run Snapshot**")
        st.caption(f"Pricing source: {pricing_header}")
        if plan.selected_store:
            st.caption(f"Store: {plan.selected_store}")
        st.caption(f"Pantry carryover file: `{DEFAULT_PANTRY_CARRYOVER_PATH}`")
        st.caption(f"Meal structure: {' + '.join(value.title() for value in request.meal_structure or ('meal',))}")
        st.caption(f"Variety preference: {request.variety_preference.title()}")
        st.caption(f"Leftovers mode: {request.leftovers_mode.title()}")
        coverage_note = format_calorie_coverage_note(weekly_calorie_summary)
        if coverage_note:
            st.caption(coverage_note)
        if weekly_nutrition_summary.is_partial:
            st.caption(f"Nutrition is partial for {weekly_nutrition_summary.unknown_meal_count} meal(s).")
    with meta_right.container(border=True):
        budget_status = "Within budget" if remaining_budget >= 0 else "Over budget"
        st.markdown(f"**{budget_status}**")
        st.caption("Consumed cost estimates ingredient usage. Added shopping reflects whole-package purchases added to the cart.")
        st.caption("Confidence labels stay compact on each meal card. Deeper reasoning is hidden until expanded.")

    export_text = build_plan_text_export(
        request,
        plan,
        calorie_target_text,
        repeat_label_getter=lambda meal: meal_repeat_label(request, plan, meal),
        selection_diagnostics=selection_diagnostics,
    )
    weekly_tab, shopping_tab, carryover_tab, diagnostics_tab = st.tabs(
        ("Weekly Plan", "Shopping List", "Pantry Carryover", "Diagnostics / Planner Reasoning")
    )

    with weekly_tab:
        st.caption("The weekly board keeps daily summaries visible first. Meal-level rationale and nutrient diagnostics stay hidden until expanded.")
        day_tabs = st.tabs(tuple(summary.label for summary in day_summaries))
        for day_tab, day_summary in zip(day_tabs, day_summaries):
            day_meals = [meal for meal in plan.meals if meal.day == day_summary.day]
            with day_tab:
                day_metrics = st.columns(5)
                day_metrics[0].metric("Meals", str(day_summary.meal_count))
                day_metrics[1].metric("Daily Calories", day_summary.calorie_display)
                day_metrics[2].metric("Status", day_summary.status_label)
                day_metrics[3].metric(
                    "Consumed Cost",
                    format_compact_currency_total(
                        day_summary.consumed_cost_known_total,
                        partial=day_summary.consumed_cost_is_partial,
                    ),
                )
                day_metrics[4].metric("Added Shopping", f"${day_summary.added_shopping_total:.2f}")
                st.caption(day_summary.status_help)
                st.caption(f"Target range: {calorie_target_text}")

                for meal in day_meals:
                    meal_calories = meal_total_calories(meal)
                    meal_nutrition = meal_total_nutrition(meal)
                    diagnostic = diagnostic_lookup.get((meal.day, meal.slot, meal.meal_role))
                    repeat_badge = meal_repeat_label(request, plan, meal)
                    with st.container(border=True):
                        meal_header, meal_stats = st.columns((3, 2))
                        with meal_header:
                            st.markdown(
                                f"**{slot_label(request.meals_per_day, meal.slot, request.meal_structure)} {meal.slot}**"
                                f" - **{meal.meal_role.replace('_', ' ').title()}**"
                            )
                            st.write(meal.recipe.title)
                            meta_bits = [meal.recipe.cuisine.title()]
                            if meal.recipe.diet_tags:
                                meta_bits.append(", ".join(sorted(meal.recipe.diet_tags)))
                            if repeat_badge is not None:
                                meta_bits.append(f"{repeat_badge[0]}: {repeat_badge[1]}")
                            st.caption(" | ".join(meta_bits))
                            st.caption(compact_selection_rationale(diagnostic))
                            st.caption(f"Confidence: {format_estimate_confidence_label(meal, diagnostic)}")
                        with meal_stats:
                            stat_cols = st.columns(4)
                            stat_cols[0].metric("Calories", "Unknown" if meal_calories is None else f"{meal_calories:,}")
                            stat_cols[1].metric("Consumed", format_optional_currency(meal.consumed_cost))
                            stat_cols[2].metric("Added", format_optional_currency(meal.incremental_cost))
                            stat_cols[3].metric("Prep", format_optional_minutes(meal.recipe.prep_time_minutes))
                        replace_button_key = f"replace-{meal.day}-{meal.slot}-{meal.recipe.recipe_id}"
                        if meal.meal_role != "side" and st.button("Replace Main", key=replace_button_key, use_container_width=False):
                            try:
                                updated_plan = planner.replace_meal(request, plan, meal.day, meal.slot)
                                st.session_state["current_plan"] = updated_plan
                                st.session_state["current_request"] = request
                                st.session_state["plan_feedback"] = (
                                    f"Updated {day_name(meal.day)} "
                                    f"{slot_label(request.meals_per_day, meal.slot, request.meal_structure).lower()}."
                                )
                                st.session_state["plan_error"] = ""
                                st.rerun()
                            except PlannerError as exc:
                                st.session_state["plan_error"] = str(exc)
                                st.session_state["plan_feedback"] = ""
                                st.rerun()

                        with st.expander(f"Meal Details - {meal.recipe.title}"):
                            note = confidence_note(meal, diagnostic)
                            if note:
                                st.info(note)
                            st.caption(f"Meal nutrition: {format_optional_nutrition(meal_nutrition)}")
                            st.caption(
                                "Estimated calories per serving: "
                                + format_optional_calories_per_serving(meal.recipe.estimated_calories_per_serving)
                            )
                            detail_left, detail_right = st.columns(2)
                            scale = meal.scaled_servings / meal.recipe.base_servings
                            with detail_left:
                                st.markdown("**Ingredients**")
                                for ingredient in meal.recipe.ingredients:
                                    st.write(f"- {round(ingredient.quantity * scale, 2)} {ingredient.unit} {ingredient.name}")
                            with detail_right:
                                st.markdown("**Steps**")
                                for index, step in enumerate(meal.recipe.steps, start=1):
                                    st.write(f"{index}. {step}")

                        with st.expander(f"Planning Rationale - {meal.recipe.title}"):
                            st.write(compact_selection_rationale(diagnostic))
                            if diagnostic is not None:
                                st.caption(f"Daily state before: {format_daily_nutrient_state(diagnostic.daily_state_before)}")
                                st.caption(f"Daily state after: {format_daily_nutrient_state(diagnostic.daily_state_after)}")
                                st.caption(
                                    "Remaining deficits before: "
                                    + format_daily_nutrient_deficits(diagnostic.daily_deficits_before)
                                )
                                st.caption(
                                    "Remaining deficits after: "
                                    + format_daily_nutrient_deficits(diagnostic.daily_deficits_after)
                                )
                                if diagnostic.meal_role == "side":
                                    st.caption(
                                        "Main composition: "
                                        + format_meal_composition_profile(diagnostic.anchor_composition_profile)
                                    )
                                    st.caption(
                                        "Side composition: "
                                        + format_meal_composition_profile(diagnostic.selected_composition_profile)
                                    )
                                    if diagnostic.runner_up_title:
                                        st.caption(f"Runner-up side: {diagnostic.runner_up_title}")
                                    if diagnostic.runner_up_loss_reasons:
                                        st.caption(
                                            "Runner-up lost because: "
                                            + ", ".join(diagnostic.runner_up_loss_reasons)
                                        )

    with shopping_tab:
        st.caption("Shopping is grouped for scanning first. Amounts, carryover reuse, leftover estimates, and shopping-cost semantics remain unchanged.")
        for section in shopping_sections:
            with st.expander(f"{section.title} ({len(section.rows)})", expanded=section.title in {"Produce", "Protein"}):
                st.dataframe(
                    [
                        {
                            "Ingredient": row.ingredient,
                            "Amount Needed": row.amount_needed,
                            "Carryover Used": row.carryover_used,
                            "Amount Being Bought": row.amount_being_bought,
                            "Leftover After Plan": row.leftover_after_plan,
                            "Package Count": row.package_count,
                            "Estimated Cost": row.estimated_cost,
                            "Price Source": row.price_source,
                        }
                        for row in section.rows
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

    with carryover_tab:
        carryover_summary, inventory_card = st.columns((3, 2))
        with carryover_summary.container(border=True):
            st.markdown("**Carryover Summary**")
            st.write(summarize_carryover_usage(plan))
            st.caption("Needed amount is recipe usage. Carryover used shows pantry reuse before any new packages are bought.")
            if pantry_inventory:
                st.caption(
                    "Carryover currently on hand: "
                    + ", ".join(f"{item.name} ({round(item.quantity, 2)} {item.unit})" for item in pantry_inventory[:8])
                    + (" ..." if len(pantry_inventory) > 8 else "")
                )
            else:
                st.caption("Carryover currently on hand: none")
        with inventory_card.container(border=True):
            st.markdown("**Pantry Controls**")
            if st.button("Apply Plan To Pantry Carryover", use_container_width=True):
                updated_inventory = PANTRY_CARRYOVER_STORE.apply_plan(plan)
                st.session_state["pantry_feedback"] = (
                    f"Stored pantry carryover for {len(updated_inventory)} ingredient(s)."
                )
                st.rerun()
            if st.button("Reset Pantry Carryover", use_container_width=True):
                PANTRY_CARRYOVER_STORE.reset()
                st.session_state["pantry_feedback"] = "Cleared pantry carryover."
                st.rerun()

    with diagnostics_tab:
        if pricing_context.note or plan.notes:
            with st.container(border=True):
                st.markdown("**Planner Notes**")
                if pricing_context.note:
                    st.warning(pricing_context.note)
                for note in plan.notes:
                    st.info(note)
        else:
            st.caption("No planner notes for this run.")

        export_col, text_col, csv_col = st.columns(3)
        with export_col:
            favorite_name = st.text_input(
                "Favorite name",
                key="favorite_name_input",
                placeholder="Weeknight Favorites",
                label_visibility="collapsed",
            )
            if st.button("Save As Favorite", use_container_width=True):
                saved_record = FAVORITES_STORE.save_plan(
                    name=favorite_name or "Saved PantryPilot Plan",
                    saved_at=datetime.now().isoformat(timespec="seconds"),
                    request=request,
                    plan=plan,
                )
                st.session_state["plan_feedback"] = f"Saved plan as favorite: {saved_record.name}."
                st.session_state["favorite_name_input"] = ""
                st.rerun()
        text_col.download_button(
            "Download Weekly Plan (.txt)",
            data=export_text,
            file_name="pantrypilot_weekly_plan.txt",
            mime="text/plain",
            use_container_width=True,
        )
        csv_col.download_button(
            "Download Shopping List (.csv)",
            data=build_shopping_list_csv(plan),
            file_name="pantrypilot_shopping_list.csv",
            mime="text/csv",
            use_container_width=True,
        )

        with st.expander("Full Planner Export"):
            st.code(export_text, language="text")


initialize_form_state()

with st.container(border=True):
    st.subheader("Plan Setup")
    st.caption("Choose a preset for a fast demo start, then edit anything you want before generating the plan.")
    preset_col, action_col, target_col = st.columns((2, 1, 2))
    with preset_col:
        preset_name = st.selectbox(
            "Preset Scenario",
            tuple(PRESET_SCENARIOS.keys()),
            key="preset_selector",
        )
    with action_col:
        st.write("")
        st.write("")
        if st.button("Apply Preset", use_container_width=True):
            apply_preset(preset_name)
            st.session_state["current_plan"] = None
            st.session_state["current_request"] = None
            st.session_state["plan_feedback"] = ""
            st.session_state["plan_error"] = ""
            st.rerun()
    with target_col:
        calorie_target_range = st.slider(
            "Daily Calorie Target Range",
            min_value=1200,
            max_value=3500,
            value=(
                st.session_state["calorie_target_min_input"],
                st.session_state["calorie_target_max_input"],
            ),
            step=50,
        )
        st.session_state["calorie_target_min_input"], st.session_state["calorie_target_max_input"] = calorie_target_range
        st.caption(
            f"Selected target: {st.session_state['calorie_target_min_input']:,} to "
            f"{st.session_state['calorie_target_max_input']:,} calories per day"
        )
        profile_preview = None
        _, preview_targets = current_profile_targets(meals_per_day=len(meal_structure_for_label(st.session_state["meal_structure_input"])))
        if preview_targets is not None:
            profile_preview = summarize_targets(preview_targets)
        if profile_preview is not None:
            st.caption(
                "Personal targets are enabled. This run will use "
                + profile_preview.calorie_target_text
                + " instead of the manual slider."
            )
        else:
            st.caption("The planner uses this range to favor days that land closer to the target.")

st.subheader("Pricing")
pricing_mode = st.radio(
    "Pricing source",
    ("Mock pricing", "Real store"),
    horizontal=True,
    key="pricing_mode_input",
)
zip_code = st.text_input(
    "ZIP code for Kroger or Fry's",
    key="zip_code_input",
    help="Only used when real store pricing is selected.",
)

location_options: dict[str, str] = {}
selected_store_label = ""
pricing_discovery = None

if normalize_name(pricing_mode) == "real store":
    if zip_code.strip():
        pricing_discovery = get_kroger_locations(zip_code.strip())
        if pricing_discovery.note:
            st.caption(pricing_discovery.note)
        if pricing_discovery.locations:
            location_options = {
                format_location_label(location): location.location_id for location in pricing_discovery.locations
            }
            selected_store_label = st.selectbox(
                "Nearby Kroger or Fry's store",
                tuple(location_options.keys()),
            )
        else:
            st.caption("No Kroger or Fry's stores were found for that ZIP code. Mock pricing will be used.")
    else:
        st.caption("Enter a ZIP code to look up nearby Kroger or Fry's stores.")


with st.form("weekly-planner-form"):
    st.subheader("Planning Inputs")
    st.caption("Budget, preferences, pantry, and calorie targets all stay editable after you apply a preset.")
    top_left, top_right = st.columns(2)
    with top_left:
        st.markdown("**Budget And Schedule**")
        weekly_budget = st.number_input(
            "Weekly budget ($)",
            min_value=10.0,
            max_value=500.0,
            step=5.0,
            key="weekly_budget_input",
            help="Target spend for the week using package-based purchase estimates.",
        )
        servings = st.number_input(
            "Servings per meal",
            min_value=1,
            max_value=8,
            step=1,
            key="servings_input",
        )
        meal_structure_label = st.selectbox(
            "Meal structure",
            tuple(MEAL_STRUCTURE_OPTIONS.keys()),
            key="meal_structure_input",
            help="Choose which meal slots PantryPilot should plan each day.",
        )
        selected_meal_structure = meal_structure_for_label(meal_structure_label)
        st.caption("Daily slots: " + " + ".join(value.title() for value in selected_meal_structure))
        max_prep_time = st.number_input(
            "Max prep time (minutes)",
            min_value=10,
            max_value=180,
            step=5,
            key="max_prep_time_input",
        )
    with top_right:
        st.markdown("**Preferences And Safety**")
        cuisine_preferences = st.text_input(
            "Cuisine preferences",
            key="cuisine_preferences_input",
            help="Comma-separated cuisines, for example: mediterranean, mexican, american",
        )
        diet_restrictions = st.text_input("Diet restrictions", key="diet_restrictions_input")
        allergies = st.text_input(
            "Allergies",
            key="allergies_input",
            help="Unknown allergen data is still treated as unsafe.",
        )
        excluded_ingredients = st.text_input("Excluded ingredients", key="excluded_ingredients_input")

    st.divider()
    pantry_col, calorie_col = st.columns(2)
    with pantry_col:
        st.markdown("**Pantry**")
        pantry_staples = st.text_input(
            "Pantry staples",
            key="pantry_staples_input",
            help="Comma-separated ingredients assumed to already be on hand.",
        )
    with calorie_col:
        st.markdown("**Calories, Variety, And Leftovers**")
        st.markdown(
            "Daily target range: **"
            + format_calorie_target(
                st.session_state["calorie_target_min_input"],
                st.session_state["calorie_target_max_input"],
            )
            + "**"
        )
        variety_preference = st.selectbox(
            "Variety preference",
            ("Low", "Balanced", "High"),
            key="variety_preference_input",
            help="Higher variety makes repeats less likely, but still stays deterministic for the same settings.",
        )
        leftovers_mode = st.selectbox(
            "Leftovers mode",
            LEFTOVERS_MODE_OPTIONS,
            key="leftovers_mode_input",
            help="Higher leftovers mode intentionally allows more repeated meals to cut down cooking across the week.",
        )
        if leftovers_mode != "Off":
            st.caption("Leftovers mode is enabled. PantryPilot will intentionally allow more controlled meal reuse.")
        st.caption(
            "Calories, variety, and leftovers all influence selection. Allergy filtering and budget checks still apply first."
        )

    st.divider()
    st.markdown("**Personal Target Guidance**")
    use_personal_targets = st.checkbox(
        "Use personal planning targets",
        key="use_personal_targets_input",
        help="Generate estimated calorie, macro, and food-group targets from a simple profile. This is planning guidance, not medical advice.",
    )
    if use_personal_targets:
        profile_left, profile_mid, profile_right = st.columns(3)
        with profile_left:
            st.number_input("Age", min_value=18, max_value=90, step=1, key="profile_age_input")
            st.selectbox("Sex", ("Female", "Male"), key="profile_sex_input")
        with profile_mid:
            st.number_input("Height (cm)", min_value=120.0, max_value=230.0, step=1.0, key="profile_height_cm_input")
            st.number_input("Weight (kg)", min_value=35.0, max_value=250.0, step=1.0, key="profile_weight_kg_input")
        with profile_right:
            st.selectbox("Activity level", PROFILE_ACTIVITY_OPTIONS, key="profile_activity_input")
            st.selectbox("Planning goal", PROFILE_GOAL_OPTIONS, key="profile_goal_input")

        _, preview_targets = current_profile_targets(meals_per_day=len(selected_meal_structure))
        preview_summary = summarize_targets(preview_targets)
        if preview_summary is not None:
            st.caption("Estimated personal target: " + preview_summary.calorie_target_text)
            st.caption("Macro guidance: " + preview_summary.macro_target_text)
            st.caption("Food-group guidance: " + preview_summary.food_group_target_text)
            st.caption(preview_summary.guidance_note)

    submitted = st.form_submit_button("Create 7-day plan", use_container_width=True)


if submitted:
    _, submitted_targets = current_profile_targets(meals_per_day=len(selected_meal_structure))
    validation_calorie_min = (
        submitted_targets.calorie_target_min
        if submitted_targets is not None
        else st.session_state["calorie_target_min_input"]
    )
    validation_calorie_max = (
        submitted_targets.calorie_target_max
        if submitted_targets is not None
        else st.session_state["calorie_target_max_input"]
    )
    validation_errors, validation_warnings = validate_request_inputs(
        weekly_budget=float(weekly_budget),
        max_prep_time=int(max_prep_time),
        meals_per_day=len(selected_meal_structure),
        calorie_target_min=validation_calorie_min,
        calorie_target_max=validation_calorie_max,
        csv_inputs={
            "Cuisine preferences": cuisine_preferences,
            "Diet restrictions": diet_restrictions,
            "Allergies": allergies,
            "Excluded ingredients": excluded_ingredients,
            "Pantry staples": pantry_staples,
        },
    )

    for warning in validation_warnings:
        st.warning(warning)

    if validation_errors:
        st.error("Please fix the input issues before generating a plan.")
        for error_message in validation_errors:
            st.write(f"- {error_message}")
        st.stop()

    user_profile, personal_targets = current_profile_targets(meals_per_day=len(selected_meal_structure))
    effective_calorie_min = (
        personal_targets.calorie_target_min
        if personal_targets is not None
        else st.session_state["calorie_target_min_input"]
    )
    effective_calorie_max = (
        personal_targets.calorie_target_max
        if personal_targets is not None
        else st.session_state["calorie_target_max_input"]
    )

    request = PlannerRequest(
        weekly_budget=float(weekly_budget),
        servings=int(servings),
        cuisine_preferences=parse_csv_list(cuisine_preferences),
        allergies=parse_csv_list(allergies),
        excluded_ingredients=parse_csv_list(excluded_ingredients),
        diet_restrictions=parse_csv_list(diet_restrictions),
        pantry_staples=parse_csv_list(pantry_staples),
        max_prep_time_minutes=int(max_prep_time),
        meals_per_day=len(selected_meal_structure),
        meal_structure=selected_meal_structure,
        zip_code=zip_code.strip(),
        pricing_mode=normalize_name(pricing_mode),
        store_location_id=location_options.get(selected_store_label, ""),
        daily_calorie_target_min=effective_calorie_min,
        daily_calorie_target_max=effective_calorie_max,
        variety_preference=normalize_name(variety_preference),
        leftovers_mode=normalize_name(leftovers_mode),
        user_profile=user_profile,
        personal_targets=personal_targets,
    )
    progress_header = st.empty()
    progress_detail = st.empty()
    progress_bar = st.progress(0, text="Starting PantryPilot planner...")

    def update_progress(progress) -> None:
        progress_header.info(f"{progress.label}")
        if progress.detail:
            progress_detail.caption(progress.detail)
        progress_bar.progress(
            min(max(int(progress.percent * 100), 0), 100),
            text=f"{progress.stage.title()}: {progress.label}",
        )

    try:
        planner, pricing_context, pantry_inventory = build_planner_and_context(
            request,
            progress_callback=update_progress,
        )
        plan = planner.create_plan(request)
        progress_header.success("Weekly plan ready.")
        progress_detail.caption("Planning finished successfully.")
        progress_bar.progress(100, text="Complete: weekly plan ready")
        st.session_state["current_request"] = request
        st.session_state["current_plan"] = plan
        st.session_state["plan_feedback"] = ""
        st.session_state["plan_error"] = ""
    except PlannerError as exc:
        current_plan_exists = (
            st.session_state.get("current_request") is not None
            and st.session_state.get("current_plan") is not None
        )
        if is_transient_runtime_failure(str(exc)):
            headline, likely_causes = build_runtime_failure_feedback(
                str(exc),
                has_saved_plan=current_plan_exists,
            )
        else:
            _, likely_causes = diagnose_plan_failure(planner, request)
            headline, likely_causes = build_failure_feedback(str(exc), likely_causes)
        progress_header.error("Planning stopped before a full week was built.")
        progress_detail.caption("The progress state above shows the last completed planning stage.")
        st.session_state["plan_error"] = headline
        st.session_state["plan_feedback"] = (
            "Showing the last successful plan while this request is retried."
            if current_plan_exists
            else ""
        )
        st.error(headline)
        if likely_causes:
            with st.container(border=True):
                st.markdown("**Likely Causes**")
                for cause in likely_causes:
                    st.write(f"- {cause}")
        if is_transient_runtime_failure(str(exc)):
            st.info("Retry the same request in a moment. This currently looks like a temporary system problem, not a planner-settings problem.")
        else:
            st.info(
                "Try increasing the budget, widening the calorie target, loosening cuisine or diet filters, "
                "or reducing meals per day."
            )
    except Exception as exc:
        current_plan_exists = (
            st.session_state.get("current_request") is not None
            and st.session_state.get("current_plan") is not None
        )
        headline, likely_causes = build_runtime_failure_feedback(
            str(exc),
            has_saved_plan=current_plan_exists,
        )
        progress_header.error("Planning stopped because of a runtime error.")
        progress_detail.caption("The progress state above shows the last completed planning stage.")
        st.session_state["plan_error"] = headline
        st.session_state["plan_feedback"] = (
            "Showing the last successful plan while this request is retried."
            if current_plan_exists
            else ""
        )
        st.error(headline)
        with st.container(border=True):
            st.markdown("**Likely Causes**")
            for cause in likely_causes:
                st.write(f"- {cause}")
        st.info("Retry the same request first. If the error repeats consistently, then treat it as a real app/runtime issue.")
else:
    st.caption(
        "Pick a preset or enter your own constraints, then generate a plan. The planner remains deterministic for "
        "the same settings, and calories now influence selection rather than acting as display-only reporting."
    )

stored_request = st.session_state.get("current_request")
stored_plan = st.session_state.get("current_plan")
if stored_request is not None and stored_plan is not None:
    planner, pricing_context, pantry_inventory = build_planner_and_context(stored_request)
    render_meal_plan(stored_request, stored_plan, planner, pricing_context, pantry_inventory)
render_saved_plans()

