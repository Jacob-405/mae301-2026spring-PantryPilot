from dataclasses import replace

import streamlit as st

from pantry_pilot.models import PlannerRequest
from pantry_pilot.normalization import normalize_name, parse_csv_list
from pantry_pilot.planner import PlannerError, WeeklyMealPlanner, day_name, slot_label
from pantry_pilot.providers import build_pricing_context, discover_kroger_locations, format_location_label


st.set_page_config(page_title="PantryPilot", layout="wide")
st.title("PantryPilot")
st.write("Build a deterministic 7-day meal plan from local recipes and grocery prices.")

MEAL_STRUCTURE_OPTIONS = {
    "Breakfast + Lunch + Dinner": ("breakfast", "lunch", "dinner"),
    "Lunch + Dinner": ("lunch", "dinner"),
    "Dinner Only": ("dinner",),
}
LEFTOVERS_MODE_OPTIONS = ("Off", "Moderate", "Frequent")

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


def apply_preset(preset_name: str) -> None:
    preset = PRESET_SCENARIOS[preset_name]
    for key, value in preset.items():
        st.session_state[key] = value


def build_planner_and_context(request: PlannerRequest) -> tuple[WeeklyMealPlanner, object]:
    pricing_context = build_pricing_context(
        pricing_mode=request.pricing_mode,
        zip_code=request.zip_code,
        store_location_id=request.store_location_id,
    )
    planner = WeeklyMealPlanner(
        grocery_provider=pricing_context.provider,
        pricing_source=pricing_context.pricing_source,
        selected_store=pricing_context.selected_store,
    )
    return planner, pricing_context


def calorie_status_label(daily_calories: int, minimum: int, maximum: int) -> tuple[str, str]:
    if daily_calories < minimum:
        return "Below target", "Daily calories are under the selected target range."
    if daily_calories > maximum:
        return "Above target", "Daily calories are above the selected target range."
    return "Within target", "Daily calories are within the selected target range."


def format_calorie_target(minimum: int, maximum: int) -> str:
    return f"{minimum:,} to {maximum:,} calories per day"


def meal_structure_for_label(label: str) -> tuple[str, ...]:
    return MEAL_STRUCTURE_OPTIONS[label]


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


def render_meal_plan(request: PlannerRequest, plan, planner: WeeklyMealPlanner, pricing_context) -> None:
    pricing_header = "Mock pricing" if plan.pricing_source == "mock" else "Kroger or Fry's pricing"
    remaining_budget = request.weekly_budget - plan.estimated_total_cost
    weekly_calories = sum(meal.recipe.estimated_calories_per_serving * meal.scaled_servings for meal in plan.meals)
    average_daily_calories = round(weekly_calories / 7)
    calorie_target_text = format_calorie_target(
        request.daily_calorie_target_min,
        request.daily_calorie_target_max,
    )

    st.divider()
    st.subheader("Planner Notes")
    if st.session_state.get("plan_feedback"):
        st.success(st.session_state["plan_feedback"])
    if st.session_state.get("plan_error"):
        st.error(st.session_state["plan_error"])
    if pricing_context.note or plan.notes:
        notes_container = st.container(border=True)
        with notes_container:
            if pricing_context.note:
                st.warning(pricing_context.note)
            for note in plan.notes:
                st.info(note)
    else:
        st.caption("No planner notes for this run.")

    st.divider()
    st.subheader("Budget And Calories")
    top_metrics = st.columns(3)
    top_metrics[0].metric("Weekly Budget", f"${request.weekly_budget:.2f}")
    top_metrics[1].metric("Estimated Spend", f"${plan.estimated_total_cost:.2f}")
    top_metrics[2].metric("Remaining", f"${remaining_budget:.2f}")
    calorie_metrics = st.columns(2)
    calorie_metrics[0].metric("Weekly Calories", f"{weekly_calories:,}")
    calorie_metrics[1].metric("Average Per Day", f"{average_daily_calories:,}")
    summary_left, summary_right = st.columns((3, 2))
    with summary_left:
        st.caption(f"Pricing source: {pricing_header}")
        if plan.selected_store:
            st.caption(f"Store: {plan.selected_store}")
        st.caption(f"Variety preference: {request.variety_preference.title()}")
        st.caption(f"Leftovers mode: {request.leftovers_mode.title()}")
        st.caption("Meal structure: " + " + ".join(value.title() for value in request.meal_structure or ("meal",)))
    with summary_right:
        budget_status = "Within budget" if remaining_budget >= 0 else "Over budget"
        with st.container(border=True):
            st.markdown(f"**{budget_status}**")
            st.write("The shopping list estimate reflects pantry subtraction and package-based purchase costs.")
            st.markdown(f"Daily calorie target: **{calorie_target_text}**")

    st.divider()
    st.subheader("Weekly Plan")
    st.caption("Each day shows meals, calorie totals, and whether the day lands inside the selected calorie target range.")
    for day in range(1, 8):
        day_meals = [meal for meal in plan.meals if meal.day == day]
        daily_calories = sum(meal.recipe.estimated_calories_per_serving * meal.scaled_servings for meal in day_meals)
        day_status, day_status_help = calorie_status_label(
            daily_calories,
            request.daily_calorie_target_min,
            request.daily_calorie_target_max,
        )
        with st.container(border=True):
            day_header, day_metrics = st.columns((2, 3))
            day_header.markdown(f"### {day_name(day)}")
            day_metric_cols = day_metrics.columns((1, 2, 2))
            day_metric_cols[0].metric("Daily Calories", f"{daily_calories:,}")
            day_metric_cols[1].markdown(f"**Target Range**  \n{calorie_target_text}")
            day_metric_cols[2].markdown(f"**Status**  \n{day_status}")
            st.caption(day_status_help)

            for meal in day_meals:
                meal_title, meal_stats = st.columns((3, 2))
                with meal_title:
                    st.markdown(
                        f"**{slot_label(request.meals_per_day, meal.slot, request.meal_structure)} {meal.slot}**: {meal.recipe.title}"
                    )
                    st.caption(
                        "Cuisine: "
                        + meal.recipe.cuisine.title()
                        + " | Tags: "
                        + ", ".join(sorted(meal.recipe.diet_tags))
                    )
                with meal_stats:
                    prep_col, cost_col, calorie_col = st.columns(3)
                    prep_col.metric("Prep Time", f"{meal.recipe.prep_time_minutes} min")
                    cost_col.metric("Meal Cost", f"${meal.incremental_cost:.2f}")
                    calorie_col.metric(
                        "Calories",
                        f"{meal.recipe.estimated_calories_per_serving * meal.scaled_servings:,}",
                    )
                    st.caption(f"Estimated calories per serving: {meal.recipe.estimated_calories_per_serving:,}")
                    replace_button_key = f"replace-{meal.day}-{meal.slot}-{meal.recipe.recipe_id}"
                    if st.button("Replace Meal", key=replace_button_key, use_container_width=True):
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

                with st.expander(f"Ingredients and steps for {meal.recipe.title}"):
                    scale = meal.scaled_servings / meal.recipe.base_servings
                    detail_left, detail_right = st.columns(2)
                    with detail_left:
                        st.markdown("**Ingredients**")
                        for ingredient in meal.recipe.ingredients:
                            st.write(f"- {round(ingredient.quantity * scale, 2)} {ingredient.unit} {ingredient.name}")
                    with detail_right:
                        st.markdown("**Steps**")
                        for index, step in enumerate(meal.recipe.steps, start=1):
                            st.write(f"{index}. {step}")
                st.divider()

    st.subheader("Shopping List")
    st.caption("Needed amounts are recipe usage. Buying and package count reflect whole-package purchases.")
    shopping_rows = [
        {
            "Ingredient": item.name,
            "Amount Needed": f"{item.quantity} {item.unit}",
            "Amount Being Bought": (
                "N/A"
                if item.purchased_quantity == 0
                else f"{item.purchased_quantity} {item.package_unit}"
            ),
            "Package Count": item.estimated_packages,
            "Estimated Cost": "N/A" if item.estimated_cost is None else f"${item.estimated_cost:.2f}",
        }
        for item in plan.shopping_list
    ]
    st.dataframe(shopping_rows, use_container_width=True, hide_index=True)


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
        st.caption("The planner now uses this range to favor days that land closer to the target.")

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

    submitted = st.form_submit_button("Create 7-day plan", use_container_width=True)


if submitted:
    validation_errors, validation_warnings = validate_request_inputs(
        weekly_budget=float(weekly_budget),
        max_prep_time=int(max_prep_time),
        meals_per_day=len(selected_meal_structure),
        calorie_target_min=st.session_state["calorie_target_min_input"],
        calorie_target_max=st.session_state["calorie_target_max_input"],
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
        daily_calorie_target_min=st.session_state["calorie_target_min_input"],
        daily_calorie_target_max=st.session_state["calorie_target_max_input"],
        variety_preference=normalize_name(variety_preference),
        leftovers_mode=normalize_name(leftovers_mode),
    )
    planner, pricing_context = build_planner_and_context(request)

    try:
        plan = planner.create_plan(request)
        st.session_state["current_request"] = request
        st.session_state["current_plan"] = plan
        st.session_state["plan_feedback"] = ""
        st.session_state["plan_error"] = ""
    except PlannerError as exc:
        headline, likely_causes = diagnose_plan_failure(planner, request)
        st.error(headline)
        st.caption(str(exc))
        with st.container(border=True):
            st.markdown("**Likely Causes**")
            for cause in likely_causes:
                st.write(f"- {cause}")
        st.info(
            "Try increasing the budget, widening the calorie target, loosening cuisine or diet filters, "
            "or reducing meals per day."
        )
else:
    st.caption(
        "Pick a preset or enter your own constraints, then generate a plan. The planner remains deterministic for "
        "the same settings, and calories now influence selection rather than acting as display-only reporting."
    )

stored_request = st.session_state.get("current_request")
stored_plan = st.session_state.get("current_plan")
if stored_request is not None and stored_plan is not None:
    planner, pricing_context = build_planner_and_context(stored_request)
    render_meal_plan(stored_request, stored_plan, planner, pricing_context)
