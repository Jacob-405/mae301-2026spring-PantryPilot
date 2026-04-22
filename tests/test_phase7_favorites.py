import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from pantry_pilot.favorites import FavoritePlanStore
from pantry_pilot.models import MealPlan, PlannedMeal, PlannerRequest, Recipe, RecipeIngredient, ShoppingListItem


class FavoritePlanStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.storage_path = Path(self.tempdir.name) / "saved_plans.json"
        self.store = FavoritePlanStore(self.storage_path)
        self.request = PlannerRequest(
            weekly_budget=90.0,
            servings=2,
            cuisine_preferences=("mediterranean",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=("olive oil",),
            max_prep_time_minutes=30,
            meals_per_day=2,
            meal_structure=("lunch", "dinner"),
            daily_calorie_target_min=1600,
            daily_calorie_target_max=2200,
            variety_preference="balanced",
            leftovers_mode="moderate",
        )
        recipe = Recipe(
            recipe_id="test-recipe",
            title="Test Recipe",
            cuisine="mediterranean",
            base_servings=2,
            estimated_calories_per_serving=500,
            prep_time_minutes=20,
            meal_types=("dinner",),
            diet_tags=frozenset({"vegetarian"}),
            allergens=frozenset(),
            ingredients=(RecipeIngredient("chickpeas", 1.0, "can"),),
            steps=("Cook it.",),
        )
        self.plan = MealPlan(
            meals=(
                PlannedMeal(day=1, slot=1, recipe=recipe, scaled_servings=2, incremental_cost=3.5, consumed_cost=1.75),
            ),
            shopping_list=(
                ShoppingListItem(
                    name="chickpeas",
                    quantity=1.0,
                    unit="can",
                    estimated_packages=1,
                    package_quantity=1.0,
                    package_unit="can",
                    purchased_quantity=1.0,
                    estimated_cost=1.1,
                    pricing_source="mock",
                ),
            ),
            estimated_total_cost=3.5,
            notes=("Saved note",),
            pricing_source="mock",
            selected_store="",
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_save_and_load_round_trip(self) -> None:
        saved = self.store.save_plan(
            name="Week I Like",
            saved_at=datetime(2026, 3, 31, 12, 0, 0).isoformat(),
            request=self.request,
            plan=self.plan,
        )

        loaded, warning = self.store.load_plan(saved.plan_id)

        self.assertIsNone(warning)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "Week I Like")
        self.assertEqual(loaded.request, self.request)
        self.assertEqual(loaded.plan, self.plan)

    def test_missing_file_is_safe(self) -> None:
        records, warning = self.store.list_saved_plans()

        self.assertEqual(records, ())
        self.assertIsNone(warning)

    def test_corrupt_file_returns_warning_and_empty_list(self) -> None:
        self.storage_path.write_text("{not valid json", encoding="utf-8")

        records, warning = self.store.list_saved_plans()

        self.assertEqual(records, ())
        self.assertIsNotNone(warning)
        self.assertIn("could not be read", warning.lower())


if __name__ == "__main__":
    unittest.main()
