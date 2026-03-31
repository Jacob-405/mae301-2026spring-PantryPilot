import streamlit as st

from pantry_pilot.models import PlannerRequest
from pantry_pilot.normalization import normalize_name, parse_csv_list
from pantry_pilot.planner import PlannerError, WeeklyMealPlanner, day_name, slot_label
from pantry_pilot.providers import build_pricing_context, discover_kroger_locations, format_location_label


st.set_page_config(page_title="PantryPilot", layout="wide")
st.title("PantryPilot")
st.write("Build a deterministic 7-day meal plan from local recipes and grocery prices.")

FIELD_DEFAULTS = {
    "weekly_budget_input": 90.0,
    "servings_input": 2,
    "cuisine_preferences_input": "mediterranean, mexican, american",
    "allergies_input": "",
    "excluded_ingredients_input": "",
    "diet_restrictions_input": "",
    "pantry_staples_input": "olive oil, cinnamon",
    "max_prep_time_input": 35,
    "meals_per_day_input": 2,
    "zip_code_input": "",
    "pricing_mode_input": "Mock pricing",
    "calorie_target_min_input": 1600,
    "calorie_target_max_input": 2200,
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
        "meals_per_day_input": 2,
        "pricing_mode_input": "Mock pricing",
        "calorie_target_min_input": 1800,
        "calorie_target_max_input": 2300,
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
        "meals_per_day_input": 2,
        "pricing_mode_input": "Mock pricing",
        "calorie_target_min_input": 1700,
        "calorie_target_max_input": 2200,
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
        "meals_per_day_input": 2,
        "pricing_mode_input": "Mock pricing",
        "calorie_target_min_input": 1700,
        "calorie_target_max_input": 2300,
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
        "meals_per_day_input": 2,
        "pricing_mode_input": "Mock pricing",
        "calorie_target_min_input": 1800,
        "calorie_target_max_input": 2400,
    },
}


@st.cache_data(show_spinner=False)
def get_kroger_locations(zip_code: str):
    return discover_kroger_locations(zip_code)


def initialize_form_state() -> None:
    for key, value in FIELD_DEFAULTS.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("preset_selector", "Balanced Budget Week")


def apply_preset(preset_name: str) -> None:
    preset = PRESET_SCENARIOS[preset_name]
    for key, value in preset.items():
        st.session_state[key] = value


def calorie_status_label(daily_calories: int, minimum: int, maximum: int) -> tuple[str, str]:
    if daily_calories < minimum:
        return "Below target", "Daily calories are under the selected target range."
    if daily_calories > maximum:
        return "Above target", "Daily calories are above the selected target range."
    return "Within target", "Daily calories are within the selected target range."


def render_meal_plan(request: PlannerRequest, calorie_target_min: int, calorie_target_max: int) -> None:
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
    plan = planner.create_plan(request)

    pricing_header = "Mock pricing" if plan.pricing_source == "mock" else "Kroger or Fry's pricing"
    remaining_budget = request.weekly_budget - plan.estimated_total_cost
    weekly_calories = sum(meal.recipe.estimated_calories_per_serving * meal.scaled_servings for meal in plan.meals)
    average_daily_calories = round(weekly_calories / 7)

    st.divider()
    st.subheader("Planner Notes")
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
    summary_left, summary_right = st.columns((3, 2))
    with summary_left:
        metric_cols = st.columns(5)
        metric_cols[0].metric("Weekly Budget", f"${request.weekly_budget:.2f}")
        metric_cols[1].metric("Estimated Spend", f"${plan.estimated_total_cost:.2f}")
        metric_cols[2].metric("Remaining", f"${remaining_budget:.2f}")
        metric_cols[3].metric("Weekly Calories", f"{weekly_calories:,}")
        metric_cols[4].metric("Avg / Day", f"{average_daily_calories:,}")
        st.caption(f"Pricing source: {pricing_header}")
        if plan.selected_store:
            st.caption(f"Store: {plan.selected_store}")
    with summary_right:
        budget_status = "Within budget" if remaining_budget >= 0 else "Over budget"
        with st.container(border=True):
            st.markdown(f"**{budget_status}**")
            st.write("The shopping list estimate reflects pantry subtraction and package-based purchase costs.")
            st.caption(f"Daily calorie target: {calorie_target_min:,} to {calorie_target_max:,}")

    st.divider()
    st.subheader("Weekly Plan")
    st.caption("Each day shows meals, calorie totals, and whether the day lands inside the selected calorie target range.")
    for day in range(1, 8):
        day_meals = [meal for meal in plan.meals if meal.day == day]
        daily_calories = sum(meal.recipe.estimated_calories_per_serving * meal.scaled_servings for meal in day_meals)
        day_status, day_status_help = calorie_status_label(daily_calories, calorie_target_min, calorie_target_max)
        with st.container(border=True):
            day_header, day_metrics = st.columns((2, 3))
            day_header.markdown(f"### {day_name(day)}")
            metrics_row = day_metrics.columns(3)
            metrics_row[0].metric("Daily Calories", f"{daily_calories:,}")
            metrics_row[1].metric("Target Range", f"{calorie_target_min:,} - {calorie_target_max:,}")
            metrics_row[2].metric("Status", day_status)
            st.caption(day_status_help)

            for meal in day_meals:
                meal_title, meal_stats = st.columns((3, 2))
                with meal_title:
                    st.markdown(
                        f"**{slot_label(request.meals_per_day, meal.slot)} {meal.slot}**: {meal.recipe.title}"
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
                        f"{meal.recipe.estimated_calories_per_serving} per serving",
                    )

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
        meals_per_day = st.number_input(
            "Meals per day",
            min_value=1,
            max_value=3,
            step=1,
            key="meals_per_day_input",
        )
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
        st.markdown("**Calorie Target**")
        st.write(
            f"Daily target range: **{st.session_state['calorie_target_min_input']:,} to "
            f"{st.session_state['calorie_target_max_input']:,} calories**"
        )
        st.caption("The planner reports against this range after generation. It does not optimize for calories yet.")

    submitted = st.form_submit_button("Create 7-day plan", use_container_width=True)


if submitted:
    request = PlannerRequest(
        weekly_budget=float(weekly_budget),
        servings=int(servings),
        cuisine_preferences=parse_csv_list(cuisine_preferences),
        allergies=parse_csv_list(allergies),
        excluded_ingredients=parse_csv_list(excluded_ingredients),
        diet_restrictions=parse_csv_list(diet_restrictions),
        pantry_staples=parse_csv_list(pantry_staples),
        max_prep_time_minutes=int(max_prep_time),
        meals_per_day=int(meals_per_day),
        zip_code=zip_code.strip(),
        pricing_mode=normalize_name(pricing_mode),
        store_location_id=location_options.get(selected_store_label, ""),
    )

    try:
        render_meal_plan(
            request,
            calorie_target_min=st.session_state["calorie_target_min_input"],
            calorie_target_max=st.session_state["calorie_target_max_input"],
        )
    except PlannerError as exc:
        st.error(str(exc))
        st.info("Try increasing the budget, loosening cuisine filters, or reducing meals per day.")
else:
    st.caption(
        "Pick a preset or enter your own constraints, then generate a plan. The planner remains deterministic, "
        "and calorie targets are reported after generation rather than optimized during planning."
    )
