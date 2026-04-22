import json
import tempfile
import unittest
from pathlib import Path

from pantry_pilot.app_runtime import build_plan_snapshot
from pantry_pilot.models import GroceryLocation, GroceryProduct, PlannerRequest, Recipe, RecipeIngredient
from pantry_pilot.normalization import normalize_name
from pantry_pilot.pantry_carryover import PantryCarryoverStore
from pantry_pilot.planner import WeeklyMealPlanner
from pantry_pilot.providers import DEFAULT_PROCESSED_RECIPES_PATH, LocalRecipeProvider


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


class PlannerRegressionPhase6Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.real_request = PlannerRequest(
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
        cls.real_snapshot = build_plan_snapshot(
            cls.real_request,
            pantry_store=PantryCarryoverStore(Path(cls.tempdir.name) / "carryover.json"),
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tempdir.cleanup()

    def test_default_path_points_to_full_recipenlg_dataset(self) -> None:
        self.assertEqual(
            DEFAULT_PROCESSED_RECIPES_PATH.as_posix(),
            "mvp/data/processed/recipenlg-full-20260416T0625Z.json",
        )

    def test_processed_dataset_large_pool_loads_from_default_path(self) -> None:
        recipes = LocalRecipeProvider().list_recipes()

        self.assertGreaterEqual(len(recipes), 20000)

    def test_unsupported_unknown_metadata_stays_unknown_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_path = Path(tmpdir) / "recipes.imported.json"
            processed_path.write_text(
                json.dumps(
                    {
                        "recipes": [
                            {
                                "recipe_id": "unknown-metadata-bowl",
                                "title": "Unknown Metadata Bowl",
                                "cuisine": "mediterranean",
                                "servings": 2,
                                "prep_time_minutes": 0,
                                "meal_types": ["dinner"],
                                "diet_tags": ["vegan", "gluten-free"],
                                "allergens": {"allergens": [], "completeness": "complete"},
                                "ingredients": [
                                    {"canonical_name": "mystery ingredient", "quantity": 2, "unit": "cups"},
                                ],
                                "steps": ["Cook it."],
                                "calories": {"calories_per_serving": None},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            recipe = LocalRecipeProvider(processed_dataset_path=processed_path).list_recipes()[0]

            self.assertIsNone(recipe.estimated_calories_per_serving)
            self.assertIsNone(recipe.prep_time_minutes)

    def test_calorie_target_materially_changes_output(self) -> None:
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
            meal_structure=("dinner",),
            daily_calorie_target_min=600,
            daily_calorie_target_max=900,
        )
        higher_target_request = PlannerRequest(
            **{
                **lower_target_request.__dict__,
                "daily_calorie_target_min": 1400,
                "daily_calorie_target_max": 1700,
            }
        )

        lower_target_plan = planner.create_plan(lower_target_request)
        higher_target_plan = planner.create_plan(higher_target_request)

        self.assertEqual(lower_target_plan.meals[0].recipe.title, "Light Dinner")
        self.assertEqual(higher_target_plan.meals[0].recipe.title, "Target Dinner")

    def test_weekly_budget_materially_changes_output(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=BudgetChoiceRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "cheap base": GroceryProduct("cheap base", 1.0, "item", 2.0),
                    "target base": GroceryProduct("target base", 1.0, "item", 4.0),
                }
            ),
        )
        low_budget_request = PlannerRequest(
            weekly_budget=20.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=600,
            daily_calorie_target_max=900,
        )
        high_budget_request = PlannerRequest(
            **{
                **low_budget_request.__dict__,
                "weekly_budget": 35.0,
                "daily_calorie_target_min": 1400,
                "daily_calorie_target_max": 1700,
            }
        )

        low_budget_plan = planner.create_plan(low_budget_request)
        high_budget_plan = planner.create_plan(high_budget_request)

        self.assertEqual(low_budget_plan.meals[0].recipe.title, "Cheap Dinner")
        self.assertEqual(high_budget_plan.meals[0].recipe.title, "Budget Target Dinner")

    def test_known_bad_real_titles_are_excluded_from_dinner_candidates(self) -> None:
        planner = WeeklyMealPlanner(recipe_provider=LocalRecipeProvider())
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
            daily_calorie_target_min=800,
            daily_calorie_target_max=1200,
        )

        recipes = planner.filter_recipes(request)
        bad_titles = (
            "Garlic Aioli (Dipping Sauce for French Fries)",
            "Indian Onion Relish",
            "Authentic Mexican Guacamole",
        )

        results = {
            title: next(
                planner._is_reasonable_meal_for_slot(recipe, "dinner")
                for recipe in recipes
                if recipe.title == title
            )
            for title in bad_titles
        }

        self.assertEqual(results, {title: False for title in bad_titles})

    def test_real_dataset_constrained_plan_succeeds_with_supported_costs(self) -> None:
        snapshot = self.real_snapshot

        self.assertEqual(sum(meal.meal_role == "main" for meal in snapshot.plan.meals), 7)
        self.assertLessEqual(snapshot.plan.estimated_total_cost, snapshot.request.weekly_budget)
        self.assertTrue(all(meal.recipe.estimated_calories_per_serving is not None for meal in snapshot.plan.meals))
        self.assertTrue(all(item.estimated_cost is not None for item in snapshot.plan.shopping_list))

    def test_app_runtime_smoke_builds_plan_exports_without_crashing(self) -> None:
        snapshot = self.real_snapshot

        self.assertIn("Weekly calories:", snapshot.export_text)
        self.assertIn(
            "Ingredient,Amount Needed,Carryover Used,Amount Being Bought,Leftover After Plan,Package Count,Estimated Cost,Price Source",
            snapshot.shopping_list_csv,
        )
        self.assertEqual(snapshot.pricing_context.pricing_source, "mock")


if __name__ == "__main__":
    unittest.main()
