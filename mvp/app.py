import streamlit as st

from pantry_pilot.models import PlannerRequest
from pantry_pilot.normalization import normalize_name, parse_csv_list
from pantry_pilot.planner import PlannerError, WeeklyMealPlanner, day_name, slot_label
from pantry_pilot.providers import build_pricing_context, discover_kroger_locations, format_location_label


st.set_page_config(page_title="PantryPilot", layout="wide")
st.title("PantryPilot")
st.write("Build a deterministic 7-day meal plan from local recipes and grocery prices.")


@st.cache_data(show_spinner=False)
def get_kroger_locations(zip_code: str):
    return discover_kroger_locations(zip_code)


def render_meal_plan(request: PlannerRequest) -> None:
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
    st.subheader("Budget Summary")
    summary_left, summary_right = st.columns((2, 1))
    with summary_left:
        metric_cols = st.columns(4)
        metric_cols[0].metric("Weekly Budget", f"${request.weekly_budget:.2f}")
        metric_cols[1].metric("Estimated Spend", f"${plan.estimated_total_cost:.2f}")
        metric_cols[2].metric("Remaining", f"${remaining_budget:.2f}")
        metric_cols[3].metric("Weekly Calories", f"{weekly_calories:,}")
        st.caption(f"Pricing source: {pricing_header}")
        if plan.selected_store:
            st.caption(f"Store: {plan.selected_store}")
    with summary_right:
        status_label = "Within budget"
        if remaining_budget < 0:
            status_label = "Over budget"
        with st.container(border=True):
            st.markdown(f"**{status_label}**")
            st.write(
                "The shopping list estimate reflects pantry subtraction and package-based purchase costs."
            )

    st.divider()
    st.subheader("Weekly Plan")
    st.caption("Each meal shows the recipe, timing, and estimated added cost for that selection.")
    for day in range(1, 8):
        day_meals = [meal for meal in plan.meals if meal.day == day]
        daily_calories = sum(meal.recipe.estimated_calories_per_serving * meal.scaled_servings for meal in day_meals)
        with st.container(border=True):
            day_header, day_meta = st.columns((3, 1))
            day_header.markdown(f"### {day_name(day)}")
            day_meta.metric("Daily Calories", f"{daily_calories:,}")
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
    st.dataframe(
        shopping_rows,
        use_container_width=True,
        hide_index=True,
    )


st.subheader("Pricing")
pricing_mode = st.radio("Pricing source", ("Mock pricing", "Real store"), horizontal=True)
zip_code = st.text_input("ZIP code for Kroger or Fry's", value=st.session_state.get("zip_code_input", ""), key="zip_code_input")

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
    col1, col2 = st.columns(2)
    with col1:
        weekly_budget = st.number_input("Weekly budget ($)", min_value=10.0, max_value=500.0, value=90.0, step=5.0)
        servings = st.number_input("Servings per meal", min_value=1, max_value=8, value=2, step=1)
        cuisine_preferences = st.text_input("Cuisine preferences", value="mediterranean, mexican, american")
        allergies = st.text_input("Allergies", value="")
        excluded_ingredients = st.text_input("Excluded ingredients", value="")
    with col2:
        diet_restrictions = st.text_input("Diet restrictions", value="")
        pantry_staples = st.text_input("Pantry staples", value="olive oil, cinnamon")
        max_prep_time = st.number_input("Max prep time (minutes)", min_value=10, max_value=180, value=35, step=5)
        meals_per_day = st.number_input("Meals per day", min_value=1, max_value=3, value=2, step=1)

    submitted = st.form_submit_button("Create 7-day plan")


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
        render_meal_plan(request)
    except PlannerError as exc:
        st.error(str(exc))
        st.info("Try increasing the budget, loosening cuisine filters, or reducing meals per day.")
else:
    st.caption(
        "Enter your constraints, then generate a plan. Unknown allergen data is treated as unsafe, "
        "and the planner caps each recipe at 2 uses per week unless no other safe under-budget option exists."
    )
