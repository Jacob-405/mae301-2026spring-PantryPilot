import unittest

from pantry_pilot.models import PlannerRequest
from pantry_pilot.planner import WeeklyMealPlanner
from pantry_pilot.sample_data import RAW_RECIPES, REQUIRED_RECIPE_FIELDS, sample_recipes


class Phase3RecipeDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = WeeklyMealPlanner()

    def test_allergens_none_is_unsafe_when_allergy_filtering_is_active(self) -> None:
        request = PlannerRequest(
            weekly_budget=120.0,
            servings=2,
            cuisine_preferences=(),
            allergies=("peanut",),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=40,
            meals_per_day=1,
        )

        recipes = {recipe.title: recipe for recipe in sample_recipes()}
        filtered_titles = {recipe.title for recipe in self.planner.filter_recipes(request)}

        self.assertIsNone(recipes["Mystery Curry"].allergens)
        self.assertNotIn("Mystery Curry", filtered_titles)

    def test_excluded_ingredient_alias_matches_canonical_recipe_ingredients(self) -> None:
        request = PlannerRequest(
            weekly_budget=120.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=("tomatoes",),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=35,
            meals_per_day=1,
        )

        titles = {recipe.title for recipe in self.planner.filter_recipes(request)}

        self.assertNotIn("Tomato Avocado Toast", titles)
        self.assertNotIn("Greek Chickpea Salad", titles)
        self.assertIn("Veggie Egg Scramble", titles)

    def test_dataset_schema_is_consistent_across_all_raw_recipes(self) -> None:
        for record in RAW_RECIPES:
            self.assertEqual(set(REQUIRED_RECIPE_FIELDS) - set(record.keys()), set())
            self.assertIsInstance(record["title"], str)
            self.assertIsInstance(record["ingredients"], tuple)
            self.assertIsInstance(record["steps"], tuple)
            self.assertTrue(record["ingredients"])
            self.assertTrue(record["steps"])
            for ingredient in record["ingredients"]:
                self.assertEqual(set(ingredient.keys()), {"name", "quantity", "unit"})

    def test_recipe_ids_are_unique(self) -> None:
        recipe_ids = [recipe.recipe_id for recipe in sample_recipes()]
        self.assertEqual(len(recipe_ids), len(set(recipe_ids)))

    def test_diet_derivation_is_conservative_for_unknown_metadata(self) -> None:
        recipes = {recipe.title: recipe for recipe in sample_recipes()}
        mystery_curry = recipes["Mystery Curry"]

        self.assertIsNone(mystery_curry.allergens)
        self.assertNotIn("vegan", mystery_curry.diet_tags)
        self.assertNotIn("gluten-free", mystery_curry.diet_tags)

    def test_deterministic_planner_behavior_is_preserved(self) -> None:
        request = PlannerRequest(
            weekly_budget=90.0,
            servings=2,
            cuisine_preferences=("mediterranean", "mexican", "american"),
            allergies=("peanut", "soy"),
            excluded_ingredients=("tomatoes",),
            diet_restrictions=(),
            pantry_staples=("olive oil", "cinnamon"),
            max_prep_time_minutes=35,
            meals_per_day=2,
        )

        first_plan = self.planner.create_plan(request)
        second_plan = self.planner.create_plan(request)

        self.assertEqual(
            [(meal.day, meal.slot, meal.recipe.recipe_id) for meal in first_plan.meals],
            [(meal.day, meal.slot, meal.recipe.recipe_id) for meal in second_plan.meals],
        )
        self.assertEqual(first_plan.estimated_total_cost, second_plan.estimated_total_cost)
        self.assertEqual(first_plan.shopping_list, second_plan.shopping_list)


if __name__ == "__main__":
    unittest.main()
