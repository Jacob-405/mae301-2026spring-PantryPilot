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

    if pricing_context.note:
        st.warning(pricing_context.note)

    if plan.notes:
        for note in plan.notes:
            st.info(note)

    pricing_header = "Mock pricing" if plan.pricing_source == "mock" else "Kroger or Fry's pricing"
    st.subheader(f"Weekly Plan ({pricing_header})")

    for day in range(1, 8):
        day_meals = [meal for meal in plan.meals if meal.day == day]
        with st.container(border=True):
            st.markdown(f"**{day_name(day)}**")
            for meal in day_meals:
                st.markdown(
                    f"{slot_label(request.meals_per_day, meal.slot)} {meal.slot}: **{meal.recipe.title}**  "
                    f"({meal.recipe.cuisine.title()}, {meal.recipe.prep_time_minutes} min)"
                )
                st.caption(
                    "Tags: "
                    + ", ".join(sorted(meal.recipe.diet_tags))
                    + f" | Estimated added cost: ${meal.incremental_cost:.2f}"
                )
                with st.expander(f"Show ingredients and steps for {meal.recipe.title}"):
                    scale = meal.scaled_servings / meal.recipe.base_servings
                    st.markdown("**Ingredients**")
                    for ingredient in meal.recipe.ingredients:
                        st.write(f"- {round(ingredient.quantity * scale, 2)} {ingredient.unit} {ingredient.name}")
                    st.markdown("**Steps**")
                    for index, step in enumerate(meal.recipe.steps, start=1):
                        st.write(f"{index}. {step}")

    st.subheader("Shopping List")
    if plan.selected_store:
        st.write(f"Store: **{plan.selected_store}**")
    st.write(f"Estimated total cost: **${plan.estimated_total_cost:.2f}**")
    st.write(f"Weekly budget: **${request.weekly_budget:.2f}**")
    st.write(f"Remaining budget: **${request.weekly_budget - plan.estimated_total_cost:.2f}**")

    shopping_rows = [
        {
            "Ingredient": item.name,
            "Needed": f"{item.quantity} {item.unit}",
            "Buying": (
                "N/A"
                if item.estimated_packages == 0
                else f"{item.estimated_packages} x {item.package_quantity} {item.package_unit}"
            ),
            "Purchased": (
                "N/A"
                if item.purchased_quantity == 0
                else f"{item.purchased_quantity} {item.package_unit}"
            ),
            "Est. Cost": "N/A" if item.estimated_cost is None else f"${item.estimated_cost:.2f}",
            "Price Source": item.pricing_source,
        }
        for item in plan.shopping_list
    ]
    st.table(shopping_rows)


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
