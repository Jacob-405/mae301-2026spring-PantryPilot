import unittest

from pantry_pilot.models import PlannerRequest, Recipe, RecipeIngredient
from pantry_pilot.planner import PlannerError, WeeklyMealPlanner
from pantry_pilot.providers import LocalRecipeProvider, MockGroceryProvider


class PantryPreferenceRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="pantry-win",
                title="Pantry Pasta",
                cuisine="italian",
                base_servings=2,
                estimated_calories_per_serving=380,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan"}),
                allergens=frozenset({"gluten"}),
                ingredients=(
                    RecipeIngredient("pasta", 8.0, "oz"),
                    RecipeIngredient("olive oil", 1.0, "tbsp"),
                    RecipeIngredient("garlic", 2.0, "clove"),
                ),
                steps=("Cook pasta.", "Toss with oil and garlic."),
            ),
            Recipe(
                recipe_id="pantry-lose",
                title="Rice Bowl",
                cuisine="italian",
                base_servings=2,
                estimated_calories_per_serving=320,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan", "gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("rice", 2.0, "cup"),
                    RecipeIngredient("tomato", 2.0, "item"),
                ),
                steps=("Cook rice.", "Top with tomato."),
            ),
        )


class PantryPhase4Tests(unittest.TestCase):
    def test_pantry_ingredient_normalization_and_matching(self) -> None:
        request = PlannerRequest(
            weekly_budget=120.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=("yellow onion", "garlic cloves", "olive oil"),
            max_prep_time_minutes=35,
            meals_per_day=1,
        )

        plan = WeeklyMealPlanner().create_plan(request)
        shopping_names = {item.name for item in plan.shopping_list}

        self.assertNotIn("onion", shopping_names)
        self.assertNotIn("garlic", shopping_names)
        self.assertNotIn("olive oil", shopping_names)

    def test_pantry_subtraction_skips_fully_covered_shopping_items(self) -> None:
        without_pantry = PlannerRequest(
            weekly_budget=90.0,
            servings=2,
            cuisine_preferences=("mediterranean",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=35,
            meals_per_day=1,
        )
        with_pantry = PlannerRequest(
            weekly_budget=90.0,
            servings=2,
            cuisine_preferences=("mediterranean",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=("chickpeas", "tomatoes", "olive oil"),
            max_prep_time_minutes=35,
            meals_per_day=1,
        )

        planner = WeeklyMealPlanner()
        plan_without_pantry = planner.create_plan(without_pantry)
        plan_with_pantry = planner.create_plan(with_pantry)
        shopping_names = {item.name for item in plan_with_pantry.shopping_list}

        self.assertLess(plan_with_pantry.estimated_total_cost, plan_without_pantry.estimated_total_cost)
        self.assertNotIn("chickpeas", shopping_names)
        self.assertNotIn("tomato", shopping_names)
        self.assertNotIn("olive oil", shopping_names)

    def test_planner_deterministically_prefers_pantry_friendly_recipe(self) -> None:
        request = PlannerRequest(
            weekly_budget=20.0,
            servings=2,
            cuisine_preferences=("italian",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("vegan",),
            pantry_staples=("olive oil", "garlic"),
            max_prep_time_minutes=25,
            meals_per_day=1,
        )
        planner = WeeklyMealPlanner(
            recipe_provider=PantryPreferenceRecipeProvider(),
            grocery_provider=MockGroceryProvider(),
        )

        first_plan = planner.create_plan(request)
        second_plan = planner.create_plan(request)

        self.assertEqual(first_plan.meals[0].recipe.title, "Pantry Pasta")
        self.assertEqual(
            [meal.recipe.recipe_id for meal in first_plan.meals],
            [meal.recipe.recipe_id for meal in second_plan.meals],
        )

    def test_allergy_filtering_is_preserved_with_pantry_items(self) -> None:
        request = PlannerRequest(
            weekly_budget=120.0,
            servings=2,
            cuisine_preferences=(),
            allergies=("peanut",),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=("peanut butter", "olive oil"),
            max_prep_time_minutes=40,
            meals_per_day=1,
        )

        filtered_titles = {recipe.title for recipe in WeeklyMealPlanner().filter_recipes(request)}

        self.assertNotIn("Overnight Oats Bowl", filtered_titles)

    def test_budget_checks_use_post_pantry_shopping_list(self) -> None:
        planner = WeeklyMealPlanner()
        request_without_pantry = PlannerRequest(
            weekly_budget=20.0,
            servings=2,
            cuisine_preferences=("mexican",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
        )
        request_with_pantry = PlannerRequest(
            weekly_budget=20.0,
            servings=2,
            cuisine_preferences=("mexican",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=("rice", "black beans", "corn", "salsa"),
            max_prep_time_minutes=30,
            meals_per_day=1,
        )

        with self.assertRaises(PlannerError):
            planner.create_plan(request_without_pantry)

        plan = planner.create_plan(request_with_pantry)
        self.assertLessEqual(plan.estimated_total_cost, request_with_pantry.weekly_budget)


if __name__ == "__main__":
    unittest.main()
