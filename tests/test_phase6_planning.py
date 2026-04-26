import unittest
from collections import Counter

from pantry_pilot.models import GroceryLocation, GroceryProduct, PlannerRequest, Recipe, RecipeIngredient
from pantry_pilot.normalization import normalize_name
from pantry_pilot.planner import PlannerError, WeeklyMealPlanner
from pantry_pilot.providers import LocalRecipeProvider


class FixedPriceGroceryProvider:
    provider_name = "mock"

    def __init__(self, catalog: dict[str, GroceryProduct]) -> None:
        self._catalog = {normalize_name(name): product for name, product in catalog.items()}

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        return ()

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        return self._catalog.get(normalize_name(ingredient_name))


class CalorieChoiceRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="light-dinner",
                title="Light Dinner",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=350,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("safe base", 1.0, "item"),),
                steps=("Cook the base ingredient.",),
            ),
            Recipe(
                recipe_id="target-dinner",
                title="Target Dinner",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=750,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("safe base", 1.0, "item"),),
                steps=("Cook the base ingredient.",),
            ),
        )


class UnknownCalorieRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="unknown-dinner",
                title="Unknown Dinner",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=None,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("safe base", 1.0, "item"),),
                steps=("Cook the base ingredient.",),
            ),
        )


class BudgetChoiceRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="cheap-dinner",
                title="Cheap Dinner",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=350,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("cheap base", 1.0, "item"),),
                steps=("Cook the cheap base ingredient.",),
            ),
            Recipe(
                recipe_id="target-dinner",
                title="Budget Target Dinner",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=750,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("target base", 1.0, "item"),),
                steps=("Cook the target base ingredient.",),
            ),
        )


class UnknownPriceRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="unpriced-dinner",
                title="Unpriced Dinner",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=700,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("mystery spice", 1.0, "pinch"),),
                steps=("Cook the unpriced ingredient.",),
            ),
        )


class MealReasonablenessRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="garlic-aioli",
                title="Garlic Aioli (Dipping Sauce for French Fries)",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=250,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("garlic", 2.0, "clove"),
                    RecipeIngredient("mayonnaise", 0.5, "cup"),
                    RecipeIngredient("lemon", 1.0, "item"),
                    RecipeIngredient("paprika", 1.0, "tsp"),
                ),
                steps=("Whisk the ingredients together.",),
            ),
            Recipe(
                recipe_id="onion-relish",
                title="Indian Onion Relish",
                cuisine="indian",
                base_servings=2,
                estimated_calories_per_serving=180,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free", "vegan"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("onion", 1.0, "item"),
                    RecipeIngredient("lime", 1.0, "item"),
                    RecipeIngredient("cilantro", 1.0, "tbsp"),
                    RecipeIngredient("salt", 1.0, "tsp"),
                ),
                steps=("Mix and chill.",),
            ),
            Recipe(
                recipe_id="guacamole",
                title="Authentic Mexican Guacamole",
                cuisine="mexican",
                base_servings=2,
                estimated_calories_per_serving=220,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free", "vegan"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("avocado", 2.0, "item"),
                    RecipeIngredient("tomato", 1.0, "item"),
                    RecipeIngredient("onion", 0.5, "item"),
                    RecipeIngredient("lime", 1.0, "item"),
                ),
                steps=("Mash and mix.",),
            ),
            Recipe(
                recipe_id="chicken-skillet",
                title="Lemon Chicken Skillet",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=650,
                prep_time_minutes=25,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("chicken breast", 1.0, "lb"),
                    RecipeIngredient("rice", 1.0, "cup"),
                    RecipeIngredient("broccoli", 2.0, "cup"),
                    RecipeIngredient("lemon", 1.0, "item"),
                    RecipeIngredient("garlic", 2.0, "clove"),
                ),
                steps=("Cook the chicken and vegetables in a skillet.",),
            ),
            Recipe(
                recipe_id="bean-chili",
                title="Black Bean Chili Bowl",
                cuisine="mexican",
                base_servings=2,
                estimated_calories_per_serving=640,
                prep_time_minutes=25,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free", "vegan"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("black beans", 1.0, "can"),
                    RecipeIngredient("rice", 1.0, "cup"),
                    RecipeIngredient("tomato", 2.0, "item"),
                    RecipeIngredient("onion", 1.0, "item"),
                    RecipeIngredient("cumin", 1.0, "tsp"),
                ),
                steps=("Simmer the chili and serve in bowls.",),
            ),
        )


class VarietyRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="cheap-rice-bowl",
                title="Cheap Rice Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=520,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan", "gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("cheap staple", 1.0, "item"),),
                steps=("Cook the staple.",),
            ),
            Recipe(
                recipe_id="broccoli-plate",
                title="Broccoli Plate",
                cuisine="mediterranean",
                base_servings=2,
                estimated_calories_per_serving=540,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan", "gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("expensive vegetable", 1.0, "item"),),
                steps=("Roast the vegetable.",),
            ),
            Recipe(
                recipe_id="lentil-stew",
                title="Lentil Stew",
                cuisine="indian",
                base_servings=2,
                estimated_calories_per_serving=560,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan", "gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("expensive legume", 1.0, "item"),),
                steps=("Simmer the legume.",),
            ),
            Recipe(
                recipe_id="pasta-skillet",
                title="Pasta Skillet",
                cuisine="italian",
                base_servings=2,
                estimated_calories_per_serving=580,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan"}),
                allergens=frozenset({"gluten"}),
                ingredients=(RecipeIngredient("expensive grain", 1.0, "item"),),
                steps=("Boil the grain.",),
            ),
        )


class AllergySafetyRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="peanut-bowl",
                title="Peanut Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=800,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset({"peanut"}),
                ingredients=(RecipeIngredient("peanut ingredient", 1.0, "item"),),
                steps=("Serve the peanut ingredient.",),
            ),
            Recipe(
                recipe_id="safe-bowl",
                title="Safe Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=620,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("safe base", 1.0, "item"),),
                steps=("Serve the safe ingredient.",),
            ),
        )


class ReplacementRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="target-bowl",
                title="Target Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=650,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("base", 1.0, "item"),),
                steps=("Cook the base.",),
            ),
            Recipe(
                recipe_id="swap-bowl",
                title="Swap Bowl",
                cuisine="mexican",
                base_servings=2,
                estimated_calories_per_serving=660,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("base", 1.0, "item"),),
                steps=("Cook the swap.",),
            ),
            Recipe(
                recipe_id="peanut-swap",
                title="Peanut Swap",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=655,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset({"peanut"}),
                ingredients=(RecipeIngredient("peanut ingredient", 1.0, "item"),),
                steps=("Cook the peanut meal.",),
            ),
        )


class SingleRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="only-dinner",
                title="Only Dinner",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=420,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("safe base", 1.0, "item"),),
                steps=("Cook the only dinner.",),
            ),
        )


class MealStructureRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="breakfast-only",
                title="Breakfast Only",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=300,
                prep_time_minutes=10,
                meal_types=("breakfast",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("breakfast base", 1.0, "item"),),
                steps=("Cook breakfast.",),
            ),
            Recipe(
                recipe_id="lunch-only",
                title="Lunch Only",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=450,
                prep_time_minutes=15,
                meal_types=("lunch",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("lunch base", 1.0, "item"),),
                steps=("Cook lunch.",),
            ),
            Recipe(
                recipe_id="dinner-only",
                title="Dinner Only",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=700,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("dinner base", 1.0, "item"),),
                steps=("Cook dinner.",),
            ),
        )


class NearDuplicateRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="chickpea-rice-bowl",
                title="Chickpea Rice Bowl",
                cuisine="mediterranean",
                base_servings=2,
                estimated_calories_per_serving=540,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan", "gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("chickpeas", 1.0, "can"),
                    RecipeIngredient("rice", 1.0, "cup"),
                    RecipeIngredient("cucumber", 1.0, "item"),
                    RecipeIngredient("tomato", 1.0, "item"),
                ),
                steps=("Cook the rice and assemble the bowl.",),
            ),
            Recipe(
                recipe_id="lemon-chickpea-bowl",
                title="Lemon Chickpea Bowl",
                cuisine="mediterranean",
                base_servings=2,
                estimated_calories_per_serving=540,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan", "gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("chickpeas", 1.0, "can"),
                    RecipeIngredient("rice", 1.0, "cup"),
                    RecipeIngredient("spinach", 1.0, "cup"),
                    RecipeIngredient("lemon", 1.0, "item"),
                ),
                steps=("Cook the rice and assemble the lemon bowl.",),
            ),
            Recipe(
                recipe_id="stuffed-pepper-bake",
                title="Stuffed Pepper Bake",
                cuisine="mediterranean",
                base_servings=2,
                estimated_calories_per_serving=540,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free", "vegetarian"}),
                allergens=frozenset({"dairy"}),
                ingredients=(
                    RecipeIngredient("bell pepper", 2.0, "item"),
                    RecipeIngredient("rice", 1.0, "cup"),
                    RecipeIngredient("feta", 0.5, "cup"),
                    RecipeIngredient("tomato", 1.0, "item"),
                ),
                steps=("Bake the stuffed peppers until tender.",),
            ),
        )


class ExpandedVarietyRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe("dinner-1", "Herby Rice Bowl", "mediterranean", 2, 540, 20, ("dinner",), frozenset({"vegan", "gluten-free"}), frozenset(), (RecipeIngredient("base ingredient 1", 1.0, "item"),), ("Cook dinner 1.",)),
            Recipe("dinner-2", "Tomato Chickpea Skillet", "mediterranean", 2, 550, 20, ("dinner",), frozenset({"vegan", "gluten-free"}), frozenset(), (RecipeIngredient("base ingredient 2", 1.0, "item"),), ("Cook dinner 2.",)),
            Recipe("dinner-3", "Lemon Lentil Plate", "indian", 2, 560, 20, ("dinner",), frozenset({"vegan", "gluten-free"}), frozenset(), (RecipeIngredient("base ingredient 3", 1.0, "item"),), ("Cook dinner 3.",)),
            Recipe("dinner-4", "Roasted Corn Bowl", "mexican", 2, 545, 20, ("dinner",), frozenset({"vegan", "gluten-free"}), frozenset(), (RecipeIngredient("base ingredient 4", 1.0, "item"),), ("Cook dinner 4.",)),
            Recipe("dinner-5", "Cumin Bean Dinner", "mexican", 2, 535, 20, ("dinner",), frozenset({"vegan", "gluten-free"}), frozenset(), (RecipeIngredient("base ingredient 5", 1.0, "item"),), ("Cook dinner 5.",)),
            Recipe("dinner-6", "Ginger Veggie Plate", "asian", 2, 555, 20, ("dinner",), frozenset({"vegan", "gluten-free"}), frozenset(), (RecipeIngredient("base ingredient 6", 1.0, "item"),), ("Cook dinner 6.",)),
            Recipe("dinner-7", "Paprika Potato Bowl", "american", 2, 548, 20, ("dinner",), frozenset({"vegan", "gluten-free"}), frozenset(), (RecipeIngredient("base ingredient 7", 1.0, "item"),), ("Cook dinner 7.",)),
            Recipe("dinner-8", "Coconut Curry Bowl", "thai", 2, 552, 20, ("dinner",), frozenset({"vegan", "gluten-free"}), frozenset(), (RecipeIngredient("base ingredient 8", 1.0, "item"),), ("Cook dinner 8.",)),
        )


class DessertAndDrinkRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe("candy", "Mash Potato Candy", "american", 2, 500, 20, ("dinner",), frozenset({"gluten-free"}), frozenset(), (RecipeIngredient("potato", 1.0, "item"),), ("Cook.",)),
            Recipe("limeade", "Thai Limeade", "thai", 2, 450, 15, ("dinner",), frozenset({"vegan", "gluten-free"}), frozenset(), (RecipeIngredient("lime", 2.0, "item"),), ("Mix.",)),
            Recipe("jam", "Tomato Jam", "american", 2, 420, 20, ("dinner",), frozenset({"vegan", "gluten-free"}), frozenset(), (RecipeIngredient("tomato", 2.0, "item"),), ("Cook.",)),
            Recipe("fry-bread", "Indian Fry Bread", "indian", 2, 600, 25, ("dinner",), frozenset(), frozenset({"gluten"}), (RecipeIngredient("flour", 2.0, "cup"),), ("Fry.",)),
            Recipe("taco-bread", "Fry Bread For Indian Tacos", "indian", 2, 650, 25, ("dinner",), frozenset(), frozenset({"gluten"}), (RecipeIngredient("flour", 2.0, "cup"), RecipeIngredient("ground beef", 1.0, "lb")), ("Cook.",)),
            Recipe("meal", "Chicken Rice Bowl", "american", 2, 700, 25, ("dinner",), frozenset({"gluten-free"}), frozenset(), (RecipeIngredient("chicken breast", 1.0, "lb"), RecipeIngredient("rice", 1.0, "cup")), ("Cook.",)),
        )


class PancakeCostRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                "pancakes",
                "Weeknight Pancakes",
                "american",
                2,
                350,
                15,
                ("breakfast",),
                frozenset({"vegetarian"}),
                frozenset({"dairy", "egg", "gluten"}),
                (RecipeIngredient("pancake mix", 0.5, "cup"),),
                ("Cook the pancakes.",),
            ),
        )


class PlanningPhase6Tests(unittest.TestCase):
    def setUp(self) -> None:
        WeeklyMealPlanner.reset_request_cycle_offsets()

    def test_daily_calorie_target_changes_recipe_selection(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=CalorieChoiceRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {"safe base": GroceryProduct("safe base", 1.0, "item", 2.0)}
            ),
        )
        lower_target_request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=650,
            daily_calorie_target_max=850,
        )
        higher_target_request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1450,
            daily_calorie_target_max=1650,
        )

        lower_target_plan = planner.create_plan(lower_target_request)
        higher_target_plan = planner.create_plan(higher_target_request)

        self.assertEqual(lower_target_plan.meals[0].recipe.title, "Light Dinner")
        self.assertEqual(higher_target_plan.meals[0].recipe.title, "Target Dinner")

    def test_weekly_budget_changes_recipe_selection_when_costs_differ(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=BudgetChoiceRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "cheap base": GroceryProduct("cheap base", 1.0, "item", 1.0),
                    "target base": GroceryProduct("target base", 1.0, "item", 4.0),
                }
            ),
        )
        low_budget_request = PlannerRequest(
            weekly_budget=10.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1450,
            daily_calorie_target_max=1650,
        )
        high_budget_request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1450,
            daily_calorie_target_max=1650,
        )

        low_budget_plan = planner.create_plan(low_budget_request)
        high_budget_plan = planner.create_plan(high_budget_request)

        self.assertEqual(low_budget_plan.meals[0].recipe.title, "Cheap Dinner")
        self.assertEqual(high_budget_plan.meals[0].recipe.title, "Budget Target Dinner")

    def test_unknown_calorie_data_fails_with_clear_message(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=UnknownCalorieRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {"safe base": GroceryProduct("safe base", 1.0, "item", 2.0)}
            ),
        )
        request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1450,
            daily_calorie_target_max=1650,
        )

        with self.assertRaisesRegex(PlannerError, "known calorie estimates.*calorie target cannot be satisfied"):
            planner.create_plan(request)

    def test_unknown_price_data_fails_with_clear_message(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=UnknownPriceRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider({}),
        )
        request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1200,
            daily_calorie_target_max=1600,
        )

        with self.assertRaisesRegex(PlannerError, "fully priced recipes.*weekly budget cannot be verified"):
            planner.create_plan(request)

    def test_non_meal_titles_are_filtered_out_of_dinner_candidates(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=MealReasonablenessRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "avocado": GroceryProduct("avocado", 1.0, "item", 1.0),
                    "black beans": GroceryProduct("black beans", 1.0, "can", 1.0),
                    "broccoli": GroceryProduct("broccoli", 1.0, "cup", 1.0),
                    "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 4.0),
                    "cilantro": GroceryProduct("cilantro", 1.0, "tbsp", 1.0),
                    "cumin": GroceryProduct("cumin", 1.0, "tsp", 1.0),
                    "garlic": GroceryProduct("garlic", 1.0, "clove", 1.0),
                    "lemon": GroceryProduct("lemon", 1.0, "item", 1.0),
                    "lime": GroceryProduct("lime", 1.0, "item", 1.0),
                    "mayonnaise": GroceryProduct("mayonnaise", 1.0, "cup", 2.0),
                    "onion": GroceryProduct("onion", 1.0, "item", 1.0),
                    "paprika": GroceryProduct("paprika", 1.0, "tsp", 1.0),
                    "rice": GroceryProduct("rice", 1.0, "cup", 1.0),
                    "salt": GroceryProduct("salt", 1.0, "tsp", 1.0),
                    "tomato": GroceryProduct("tomato", 1.0, "item", 1.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=1200,
            daily_calorie_target_max=1600,
        )

        dinner_candidates = planner._recipes_for_slot(planner.filter_recipes(request), request, 1)

        self.assertEqual(
            [recipe.title for recipe in dinner_candidates],
            ["Black Bean Chili Bowl", "Lemon Chicken Skillet"],
        )

    def test_dinner_filter_keeps_multiple_valid_meal_candidates(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=MealReasonablenessRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "avocado": GroceryProduct("avocado", 1.0, "item", 1.0),
                    "black beans": GroceryProduct("black beans", 1.0, "can", 1.0),
                    "broccoli": GroceryProduct("broccoli", 1.0, "cup", 1.0),
                    "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 4.0),
                    "cilantro": GroceryProduct("cilantro", 1.0, "tbsp", 1.0),
                    "cumin": GroceryProduct("cumin", 1.0, "tsp", 1.0),
                    "garlic": GroceryProduct("garlic", 1.0, "clove", 1.0),
                    "lemon": GroceryProduct("lemon", 1.0, "item", 1.0),
                    "lime": GroceryProduct("lime", 1.0, "item", 1.0),
                    "mayonnaise": GroceryProduct("mayonnaise", 1.0, "cup", 2.0),
                    "onion": GroceryProduct("onion", 1.0, "item", 1.0),
                    "paprika": GroceryProduct("paprika", 1.0, "tsp", 1.0),
                    "rice": GroceryProduct("rice", 1.0, "cup", 1.0),
                    "salt": GroceryProduct("salt", 1.0, "tsp", 1.0),
                    "tomato": GroceryProduct("tomato", 1.0, "item", 1.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=1200,
            daily_calorie_target_max=1600,
        )

        dinner_candidates = planner._recipes_for_slot(planner.filter_recipes(request), request, 1)

        self.assertEqual(len(dinner_candidates), 2)
        self.assertEqual(
            {recipe.title for recipe in dinner_candidates},
            {"Lemon Chicken Skillet", "Black Bean Chili Bowl"},
        )

    def test_high_variety_avoids_cheap_repeats_more_than_low_variety(self) -> None:
        provider = FixedPriceGroceryProvider(
            {
                "cheap staple": GroceryProduct("cheap staple", 1.0, "item", 1.0),
                "expensive vegetable": GroceryProduct("expensive vegetable", 1.0, "item", 7.0),
                "expensive legume": GroceryProduct("expensive legume", 1.0, "item", 7.0),
                "expensive grain": GroceryProduct("expensive grain", 1.0, "item", 7.0),
            }
        )
        planner = WeeklyMealPlanner(
            recipe_provider=VarietyRecipeProvider(),
            grocery_provider=provider,
        )
        common_kwargs = {
            "weekly_budget": 60.0,
            "servings": 2,
            "cuisine_preferences": (),
            "allergies": (),
            "excluded_ingredients": (),
            "diet_restrictions": (),
            "pantry_staples": (),
            "max_prep_time_minutes": 30,
            "meals_per_day": 1,
            "daily_calorie_target_min": 900,
            "daily_calorie_target_max": 1300,
        }
        low_variety_plan = planner.create_plan(
            PlannerRequest(**common_kwargs, variety_preference="low")
        )
        high_variety_plan = planner.create_plan(
            PlannerRequest(**common_kwargs, variety_preference="high")
        )

        low_titles = [meal.recipe.title for meal in low_variety_plan.meals]
        high_titles = [meal.recipe.title for meal in high_variety_plan.meals]
        low_counts = Counter(low_titles)
        high_counts = Counter(high_titles)

        self.assertEqual(low_titles[0], "Cheap Rice Bowl")
        self.assertEqual(low_titles[1], "Cheap Rice Bowl")
        self.assertNotEqual(high_titles[1], "Cheap Rice Bowl")
        self.assertGreater(low_counts["Cheap Rice Bowl"], high_counts["Cheap Rice Bowl"])

    def test_leftovers_off_avoids_duplicate_meals_when_unique_options_exist(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=ExpandedVarietyRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    **{
                        f"base ingredient {index}": GroceryProduct(f"base ingredient {index}", 1.0, "item", 3.0)
                        for index in range(1, 9)
                    },
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=900,
            daily_calorie_target_max=1300,
            variety_preference="balanced",
            leftovers_mode="off",
        )

        plan = planner.create_plan(request)
        titles = [meal.recipe.title for meal in plan.meals]

        self.assertEqual(len(titles), 7)
        self.assertEqual(len(titles), len(set(titles)))

    def test_repeated_identical_requests_rotate_among_near_equal_weekly_plans(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=ExpandedVarietyRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    **{
                        f"base ingredient {index}": GroceryProduct(f"base ingredient {index}", 1.0, "item", 3.0)
                        for index in range(1, 9)
                    },
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=900,
            daily_calorie_target_max=1300,
            variety_preference="balanced",
            leftovers_mode="off",
        )

        first_plan = planner.create_plan(request)
        second_plan = planner.create_plan(request)

        self.assertNotEqual(
            [meal.recipe.recipe_id for meal in first_plan.meals],
            [meal.recipe.recipe_id for meal in second_plan.meals],
        )
        self.assertLessEqual(first_plan.estimated_total_cost, request.weekly_budget)
        self.assertLessEqual(second_plan.estimated_total_cost, request.weekly_budget)

    def test_real_dataset_budget_and_calorie_constrained_plan_still_succeeds_with_variety_controls(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=LocalRecipeProvider(),
        )
        request = PlannerRequest(
            weekly_budget=140.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=35,
            meals_per_day=1,
            meal_structure=("dinner",),
            pricing_mode="mock",
            daily_calorie_target_min=800,
            daily_calorie_target_max=1200,
            variety_preference="balanced",
            leftovers_mode="off",
        )

        plan = planner.create_plan(request)

        self.assertEqual(sum(meal.meal_role == "main" for meal in plan.meals), 7)
        self.assertLessEqual(plan.estimated_total_cost, request.weekly_budget)
        self.assertTrue(all(meal.recipe.estimated_calories_per_serving is not None for meal in plan.meals))
        self.assertTrue(all(item.estimated_cost is not None for item in plan.shopping_list))

    def test_dessert_and_drink_titles_are_filtered_out_of_dinner_candidates(self) -> None:
        planner = WeeklyMealPlanner(recipe_provider=DessertAndDrinkRecipeProvider())
        request = PlannerRequest(
            weekly_budget=120.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=35,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=800,
            daily_calorie_target_max=1200,
        )

        dinner_candidates = planner._recipes_for_slot(planner.filter_recipes(request), request, 1)
        dinner_titles = {recipe.title for recipe in dinner_candidates}

        self.assertNotIn("Mash Potato Candy", dinner_titles)
        self.assertNotIn("Thai Limeade", dinner_titles)
        self.assertNotIn("Tomato Jam", dinner_titles)
        self.assertNotIn("Indian Fry Bread", dinner_titles)
        self.assertIn("Fry Bread For Indian Tacos", dinner_titles)
        self.assertIn("Chicken Rice Bowl", dinner_titles)

    def test_meal_consumed_cost_is_distinct_from_added_shopping_cost(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=PancakeCostRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "pancake mix": GroceryProduct("pancake mix", 2.0, "cup", 8.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("breakfast",),
            daily_calorie_target_min=600,
            daily_calorie_target_max=900,
        )

        plan = planner.create_plan(request)
        meal = plan.meals[0]

        self.assertEqual(meal.incremental_cost, 8.0)
        self.assertEqual(meal.consumed_cost, 2.0)

    def test_repeat_warning_is_not_triggered_when_unique_under_budget_options_exist(self) -> None:
        planner = WeeklyMealPlanner(recipe_provider=LocalRecipeProvider())
        request = PlannerRequest(
            weekly_budget=300.0,
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
            daily_calorie_target_min=1600,
            daily_calorie_target_max=2200,
            variety_preference="balanced",
            leftovers_mode="off",
        )

        diagnostics = planner.diagnose_request_support(request)
        plan = planner.create_plan(request)

        self.assertEqual(diagnostics.forced_repeat_slots, 0)
        self.assertTrue(diagnostics.repeat_message_truthful)
        self.assertFalse(any("repeat more than the weekly cap" in note for note in plan.notes))

    def test_near_duplicate_penalty_prefers_distinct_second_meal(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=NearDuplicateRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "chickpeas": GroceryProduct("chickpeas", 1.0, "can", 2.0),
                    "rice": GroceryProduct("rice", 1.0, "cup", 2.0),
                    "cucumber": GroceryProduct("cucumber", 1.0, "item", 2.0),
                    "tomato": GroceryProduct("tomato", 1.0, "item", 2.0),
                    "spinach": GroceryProduct("spinach", 1.0, "cup", 2.0),
                    "lemon": GroceryProduct("lemon", 1.0, "item", 2.0),
                    "bell pepper": GroceryProduct("bell pepper", 2.0, "item", 2.0),
                    "feta": GroceryProduct("feta", 0.5, "cup", 2.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=("mediterranean",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=25,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=1000,
            daily_calorie_target_max=1200,
            variety_preference="balanced",
        )

        plan = planner.create_plan(request)
        first_two_titles = [meal.recipe.title for meal in plan.meals[:2]]

        self.assertEqual(first_two_titles[0], "Chickpea Rice Bowl")
        self.assertEqual(first_two_titles[1], "Stuffed Pepper Bake")

    def test_allergy_filtering_still_blocks_better_calorie_fit(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=AllergySafetyRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "peanut ingredient": GroceryProduct("peanut ingredient", 1.0, "item", 2.0),
                    "safe base": GroceryProduct("safe base", 1.0, "item", 2.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=("peanut",),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1500,
            daily_calorie_target_max=1700,
        )

        filtered_titles = {recipe.title for recipe in planner.filter_recipes(request)}
        plan = planner.create_plan(request)

        self.assertNotIn("Peanut Bowl", filtered_titles)
        self.assertEqual(plan.meals[0].recipe.title, "Safe Bowl")

    def test_budget_checks_still_apply_with_calorie_targets_and_variety(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=VarietyRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "cheap staple": GroceryProduct("cheap staple", 1.0, "item", 4.0),
                    "expensive vegetable": GroceryProduct("expensive vegetable", 1.0, "item", 9.0),
                    "expensive legume": GroceryProduct("expensive legume", 1.0, "item", 9.0),
                    "expensive grain": GroceryProduct("expensive grain", 1.0, "item", 9.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=10.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=900,
            daily_calorie_target_max=1300,
            variety_preference="high",
        )

        with self.assertRaises(PlannerError):
            planner.create_plan(request)

    def test_replace_meal_preserves_other_slots_and_avoids_same_recipe_when_possible(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=ReplacementRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "base": GroceryProduct("base", 1.0, "item", 2.0),
                    "peanut ingredient": GroceryProduct("peanut ingredient", 1.0, "item", 2.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=(),
            allergies=("peanut",),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1200,
            daily_calorie_target_max=1400,
            variety_preference="balanced",
        )
        original_plan = planner.create_plan(request)

        replaced_plan = planner.replace_meal(request, original_plan, day_number=1, slot_number=1)

        self.assertEqual(original_plan.meals[0].recipe.title, "Target Bowl")
        self.assertEqual(replaced_plan.meals[0].recipe.title, "Swap Bowl")
        self.assertEqual(
            [(meal.day, meal.slot, meal.recipe.recipe_id) for meal in original_plan.meals[1:]],
            [(meal.day, meal.slot, meal.recipe.recipe_id) for meal in replaced_plan.meals[1:]],
        )
        self.assertLessEqual(replaced_plan.estimated_total_cost, request.weekly_budget)

    def test_replace_meal_still_respects_allergy_filters(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=ReplacementRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "base": GroceryProduct("base", 1.0, "item", 2.0),
                    "peanut ingredient": GroceryProduct("peanut ingredient", 1.0, "item", 2.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=(),
            allergies=("peanut",),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1200,
            daily_calorie_target_max=1400,
        )
        original_plan = planner.create_plan(request)

        replaced_plan = planner.replace_meal(request, original_plan, day_number=1, slot_number=1)

        self.assertNotEqual(replaced_plan.meals[0].recipe.title, "Peanut Swap")

    def test_replace_meal_keeps_same_recipe_when_no_alternative_is_viable(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=SingleRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {"safe base": GroceryProduct("safe base", 1.0, "item", 2.0)}
            ),
        )
        request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=650,
            daily_calorie_target_max=850,
        )
        original_plan = planner.create_plan(request)

        replaced_plan = planner.replace_meal(request, original_plan, day_number=1, slot_number=1)

        self.assertEqual(replaced_plan.meals[0].recipe.title, original_plan.meals[0].recipe.title)
        self.assertIn("same recipe was kept", replaced_plan.notes[-1].lower())

    def test_breakfast_lunch_dinner_structure_uses_matching_meal_types(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=MealStructureRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "breakfast base": GroceryProduct("breakfast base", 1.0, "item", 1.0),
                    "lunch base": GroceryProduct("lunch base", 1.0, "item", 1.0),
                    "dinner base": GroceryProduct("dinner base", 1.0, "item", 1.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=3,
            meal_structure=("breakfast", "lunch", "dinner"),
            daily_calorie_target_min=1400,
            daily_calorie_target_max=1600,
        )

        plan = planner.create_plan(request)

        self.assertEqual(plan.meals[0].recipe.title, "Breakfast Only")
        self.assertEqual(plan.meals[1].recipe.title, "Lunch Only")
        self.assertEqual(plan.meals[2].recipe.title, "Dinner Only")

    def test_lunch_dinner_structure_excludes_breakfast_only_recipes(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=MealStructureRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "breakfast base": GroceryProduct("breakfast base", 1.0, "item", 1.0),
                    "lunch base": GroceryProduct("lunch base", 1.0, "item", 1.0),
                    "dinner base": GroceryProduct("dinner base", 1.0, "item", 1.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=2,
            meal_structure=("lunch", "dinner"),
            daily_calorie_target_min=1000,
            daily_calorie_target_max=1400,
        )

        plan = planner.create_plan(request)

        self.assertTrue(all(meal.recipe.title != "Breakfast Only" for meal in plan.meals))

    def test_leftovers_mode_allows_more_controlled_reuse(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=VarietyRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "cheap staple": GroceryProduct("cheap staple", 1.0, "item", 1.0),
                    "expensive vegetable": GroceryProduct("expensive vegetable", 1.0, "item", 7.0),
                    "expensive legume": GroceryProduct("expensive legume", 1.0, "item", 7.0),
                    "expensive grain": GroceryProduct("expensive grain", 1.0, "item", 7.0),
                }
            ),
        )
        common_kwargs = {
            "weekly_budget": 60.0,
            "servings": 2,
            "cuisine_preferences": (),
            "allergies": (),
            "excluded_ingredients": (),
            "diet_restrictions": (),
            "pantry_staples": (),
            "max_prep_time_minutes": 30,
            "meals_per_day": 1,
            "meal_structure": ("dinner",),
            "daily_calorie_target_min": 900,
            "daily_calorie_target_max": 1300,
            "variety_preference": "balanced",
        }
        off_plan = planner.create_plan(
            PlannerRequest(**common_kwargs, leftovers_mode="off")
        )
        frequent_plan = planner.create_plan(
            PlannerRequest(**common_kwargs, leftovers_mode="frequent")
        )

        off_counts = Counter(meal.recipe.title for meal in off_plan.meals)
        frequent_counts = Counter(meal.recipe.title for meal in frequent_plan.meals)

        self.assertGreater(
            frequent_counts["Cheap Rice Bowl"],
            off_counts["Cheap Rice Bowl"],
        )

    def test_leftovers_mode_preserves_budget_and_allergy_safety(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=ReplacementRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "base": GroceryProduct("base", 1.0, "item", 2.0),
                    "peanut ingredient": GroceryProduct("peanut ingredient", 1.0, "item", 2.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=(),
            allergies=("peanut",),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=1200,
            daily_calorie_target_max=1400,
            leftovers_mode="frequent",
        )

        plan = planner.create_plan(request)

        self.assertTrue(all("Peanut" not in meal.recipe.title for meal in plan.meals))
        self.assertLessEqual(plan.estimated_total_cost, request.weekly_budget)


if __name__ == "__main__":
    unittest.main()
