import tempfile
import unittest
from pathlib import Path

from pantry_pilot.app_runtime import build_planner_and_context
from pantry_pilot.models import GroceryLocation, GroceryProduct, PlannerRequest, Recipe, RecipeIngredient
from pantry_pilot.normalization import normalize_name
from pantry_pilot.pantry_carryover import PantryCarryoverStore
from pantry_pilot.planner import PlanningProgress, WeeklyMealPlanner
from pantry_pilot.providers import LocalRecipeProvider


class FixedPriceGroceryProvider:
    provider_name = "mock"

    def __init__(self, catalog: dict[str, GroceryProduct]) -> None:
        self._catalog = {normalize_name(name): product for name, product in catalog.items()}

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        return ()

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        return self._catalog.get(normalize_name(ingredient_name))


class ProgressRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        recipes = []
        for index in range(7):
            recipes.append(
                Recipe(
                    recipe_id=f"main-{index}",
                    title=f"Chicken Bowl {index}",
                    cuisine="american",
                    base_servings=2,
                    estimated_calories_per_serving=520 + index,
                    prep_time_minutes=20,
                    meal_types=("dinner",),
                    diet_tags=frozenset({"gluten-free"}),
                    allergens=frozenset(),
                    ingredients=(
                        RecipeIngredient("chicken breast", 1.0, "lb"),
                        RecipeIngredient("broccoli", 2.0, "cup"),
                        RecipeIngredient("rice", 1.0, "cup"),
                    ),
                    steps=("Cook it.",),
                )
            )
        return tuple(recipes)


class PhaseMPerformanceProgressTests(unittest.TestCase):
    def setUp(self) -> None:
        WeeklyMealPlanner.reset_request_cycle_offsets()
        self.request = PlannerRequest(
            weekly_budget=120.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=800,
            daily_calorie_target_max=1200,
        )
        self.grocery_provider = FixedPriceGroceryProvider(
            {
                "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 3.0),
                "broccoli": GroceryProduct("broccoli", 2.0, "cup", 1.0),
                "rice": GroceryProduct("rice", 1.0, "cup", 0.8),
            }
        )

    def test_recipe_feature_caches_reuse_objects(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=ProgressRecipeProvider(),
            grocery_provider=self.grocery_provider,
        )
        recipe = ProgressRecipeProvider().list_recipes()[0]

        first_core = planner._core_ingredient_names(recipe)
        second_core = planner._core_ingredient_names(recipe)
        first_components = planner._meal_component_tags(recipe)
        second_components = planner._meal_component_tags(recipe)

        self.assertIs(first_core, second_core)
        self.assertIs(first_components, second_components)
        self.assertEqual(len(planner._core_ingredient_names_cache), 1)
        self.assertEqual(len(planner._meal_component_tags_cache), 1)

    def test_progress_callback_reports_stages_in_order(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=ProgressRecipeProvider(),
            grocery_provider=self.grocery_provider,
            same_recipe_weekly_cap=7,
        )
        updates: list[PlanningProgress] = []
        planner.set_progress_callback(updates.append)

        plan = planner.create_plan(self.request)

        self.assertEqual(len(plan.meals), 7)
        self.assertGreaterEqual(len(updates), 4)
        self.assertEqual(updates[0].stage, "setup")
        self.assertEqual(updates[-1].stage, "complete")
        self.assertTrue(any(update.stage == "selection" for update in updates))
        self.assertTrue(any(update.stage == "finalize" for update in updates))
        percents = [update.percent for update in updates]
        self.assertEqual(percents[-1], 1.0)
        self.assertTrue(all(left <= right for left, right in zip(percents, percents[1:])))

    def test_build_planner_and_context_forwards_progress_callback(self) -> None:
        updates: list[PlanningProgress] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            planner, pricing_context, pantry_inventory = build_planner_and_context(
                self.request,
                pantry_store=PantryCarryoverStore(Path(tmpdir) / "carryover.json"),
                progress_callback=updates.append,
            )

        self.assertIsNotNone(planner._progress_callback)
        planner._progress_callback(PlanningProgress("setup", "Loading", 0, 1, 0.0, ""))
        self.assertEqual(len(updates), 1)
        self.assertEqual(pricing_context.pricing_source, "mock")
        self.assertEqual(pantry_inventory, ())


if __name__ == "__main__":
    unittest.main()
