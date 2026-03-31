import unittest
from collections import Counter

from pantry_pilot.models import PlannerRequest
from pantry_pilot.planner import PlannerError, WeeklyMealPlanner


class PlannerPhase1Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.planner = WeeklyMealPlanner()

    def test_unknown_allergen_recipe_is_filtered_out(self) -> None:
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("vegetarian",),
            pantry_staples=("olive oil",),
            max_prep_time_minutes=40,
            meals_per_day=1,
        )

        recipe_titles = {recipe.title for recipe in self.planner.filter_recipes(request)}

        self.assertNotIn("Mystery Curry", recipe_titles)

    def test_shopping_list_aggregates_repeated_ingredients(self) -> None:
        request = PlannerRequest(
            weekly_budget=50.0,
            servings=2,
            cuisine_preferences=("mediterranean",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("vegan",),
            pantry_staples=("olive oil",),
            max_prep_time_minutes=35,
            meals_per_day=1,
        )

        plan = self.planner.create_plan(request)
        shopping_map = {item.name: item for item in plan.shopping_list}

        self.assertIn("chickpeas", shopping_map)
        self.assertIn("tomato", shopping_map)
        self.assertGreater(shopping_map["chickpeas"].quantity, 2.0)
        self.assertGreater(shopping_map["tomato"].quantity, 2.0)

    def test_budget_compliance_and_failure_when_budget_too_low(self) -> None:
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=(),
            allergies=("peanut", "soy"),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=("olive oil", "cinnamon"),
            max_prep_time_minutes=35,
            meals_per_day=2,
        )

        plan = self.planner.create_plan(request)
        self.assertLessEqual(plan.estimated_total_cost, request.weekly_budget)

        impossible_request = PlannerRequest(
            weekly_budget=5.0,
            servings=2,
            cuisine_preferences=(),
            allergies=("peanut", "soy"),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=35,
            meals_per_day=2,
        )

        with self.assertRaises(PlannerError):
            self.planner.create_plan(impossible_request)

    def test_default_weekly_recipe_cap_limits_repetition_when_variety_exists(self) -> None:
        request = PlannerRequest(
            weekly_budget=120.0,
            servings=2,
            cuisine_preferences=(),
            allergies=("peanut", "soy"),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=("olive oil", "cinnamon"),
            max_prep_time_minutes=35,
            meals_per_day=2,
        )

        plan = self.planner.create_plan(request)
        counts = Counter(meal.recipe.title for meal in plan.meals)
        dinner_titles = {meal.recipe.title for meal in plan.meals if meal.slot == 2}

        self.assertTrue(counts)
        self.assertLessEqual(max(counts.values()), 2)
        self.assertGreater(len(dinner_titles), 1)
        self.assertEqual(plan.notes, ())

    def test_repetition_note_appears_when_cap_must_be_relaxed(self) -> None:
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=("bread", "avocado", "banana", "yogurt", "granola", "milk", "peanut butter"),
            diet_restrictions=("vegan",),
            pantry_staples=("olive oil",),
            max_prep_time_minutes=20,
            meals_per_day=1,
        )

        plan = self.planner.create_plan(request)
        counts = Counter(meal.recipe.title for meal in plan.meals)

        self.assertGreater(max(counts.values()), 2)
        self.assertTrue(plan.notes)
        self.assertIn("safe under-budget options", plan.notes[0])


if __name__ == "__main__":
    unittest.main()
