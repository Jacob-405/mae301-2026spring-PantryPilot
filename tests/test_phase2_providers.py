import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pantry_pilot.models import GroceryProduct, PlannerRequest
from pantry_pilot.planner import WeeklyMealPlanner
from pantry_pilot.providers import (
    FallbackGroceryProvider,
    LocalRecipeProvider,
    MockGroceryProvider,
    ProviderRequestError,
    build_pricing_context,
)


class MissingPricePrimaryProvider:
    provider_name = "kroger"

    def lookup_locations(self, zip_code: str):
        return ()

    def get_product(self, ingredient_name: str):
        if ingredient_name == "rice":
            return GroceryProduct(
                name="rice",
                package_quantity=8.0,
                unit="cup",
                package_price=None,
                source=self.provider_name,
            )
        return GroceryProduct(
            name=ingredient_name,
            package_quantity=1.0,
            unit="item",
            package_price=9.99,
            source=self.provider_name,
        )


class FailingPrimaryProvider:
    provider_name = "kroger"

    def lookup_locations(self, zip_code: str):
        return ()

    def get_product(self, ingredient_name: str):
        raise ProviderRequestError("network down")


class Phase2ProviderTests(unittest.TestCase):
    def test_local_recipe_provider_falls_back_to_sample_data_when_processed_file_missing(self) -> None:
        provider = LocalRecipeProvider(processed_dataset_path="C:\\missing\\recipes.imported.json")

        recipes = provider.list_recipes()

        self.assertTrue(recipes)
        self.assertIn("Avocado Toast", {recipe.title for recipe in recipes})

    def test_local_recipe_provider_prefers_processed_dataset_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_path = Path(tmpdir) / "recipes.imported.json"
            processed_path.write_text(
                json.dumps(
                    {
                        "recipes": [
                            {
                                "recipe_id": "processed-rice-bowl",
                                "title": "Processed Rice Bowl",
                                "cuisine": "mediterranean",
                                "servings": 2,
                                "prep_time_minutes": 15,
                                "meal_types": ["dinner"],
                                "diet_tags": ["vegan", "gluten-free"],
                                "allergens": {"allergens": [], "completeness": "complete"},
                                "ingredients": [
                                    {"canonical_name": "rice", "quantity": 2, "unit": "cups"},
                                    {"canonical_name": "tomato", "quantity": 2, "unit": "items"},
                                ],
                                "steps": ["Cook rice.", "Top with tomato."],
                                "calories": {"calories_per_serving": 420},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            provider = LocalRecipeProvider(processed_dataset_path=processed_path)

            recipes = provider.list_recipes()

            self.assertEqual(len(recipes), 1)
            self.assertEqual(recipes[0].title, "Processed Rice Bowl")

    def test_missing_credentials_fall_back_to_mock_provider(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            context = build_pricing_context(
                pricing_mode="real store",
                zip_code="85004",
                store_location_id="12345",
            )

        self.assertEqual(context.pricing_source, "mock")
        self.assertIn("KROGER_CLIENT_ID", context.note)
        self.assertIsNotNone(context.provider.get_product("rice"))

    def test_missing_real_price_uses_mock_fallback_price(self) -> None:
        provider = FallbackGroceryProvider(MissingPricePrimaryProvider(), MockGroceryProvider())

        rice = provider.get_product("rice")
        salsa = provider.get_product("salsa")

        self.assertIsNotNone(rice)
        self.assertEqual(rice.source, "mock")
        self.assertEqual(rice.package_price, 4.0)
        self.assertEqual(salsa.source, "kroger")
        self.assertEqual(salsa.package_price, 9.99)

    def test_api_failure_falls_back_to_mock_for_planner_costs(self) -> None:
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=("mexican",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=35,
            meals_per_day=1,
        )
        planner = WeeklyMealPlanner(
            grocery_provider=FallbackGroceryProvider(FailingPrimaryProvider(), MockGroceryProvider()),
            pricing_source="kroger",
        )

        plan = planner.create_plan(request)
        shopping_map = {item.name: item for item in plan.shopping_list}

        self.assertGreater(plan.estimated_total_cost, 0.0)
        self.assertEqual(shopping_map["rice"].pricing_source, "mock")

    def test_processed_dataset_path_preserves_safety_and_budget_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_path = Path(tmpdir) / "recipes.imported.json"
            processed_path.write_text(
                json.dumps(
                    {
                        "recipes": [
                            {
                                "recipe_id": "safe-rice-bowl",
                                "title": "Safe Rice Bowl",
                                "cuisine": "mediterranean",
                                "servings": 2,
                                "prep_time_minutes": 15,
                                "meal_types": ["dinner"],
                                "diet_tags": ["vegan", "gluten-free"],
                                "allergens": {"allergens": [], "completeness": "complete"},
                                "ingredients": [
                                    {"canonical_name": "rice", "quantity": 2, "unit": "cups"},
                                    {"canonical_name": "tomato", "quantity": 2, "unit": "items"},
                                ],
                                "steps": ["Cook rice.", "Top with tomato."],
                                "calories": {"calories_per_serving": 420},
                            },
                            {
                                "recipe_id": "unsafe-peanut-bowl",
                                "title": "Unsafe Peanut Bowl",
                                "cuisine": "mediterranean",
                                "servings": 2,
                                "prep_time_minutes": 15,
                                "meal_types": ["dinner"],
                                "diet_tags": ["vegan", "gluten-free"],
                                "allergens": {"allergens": ["peanut"], "completeness": "complete"},
                                "ingredients": [
                                    {"canonical_name": "rice", "quantity": 2, "unit": "cups"},
                                    {"canonical_name": "peanut butter", "quantity": 2, "unit": "tbsp"},
                                ],
                                "steps": ["Cook rice.", "Top with peanut sauce."],
                                "calories": {"calories_per_serving": 500},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            planner = WeeklyMealPlanner(
                recipe_provider=LocalRecipeProvider(processed_dataset_path=processed_path),
                grocery_provider=MockGroceryProvider(),
            )
            request = PlannerRequest(
                weekly_budget=40.0,
                servings=2,
                cuisine_preferences=("mediterranean",),
                allergies=("peanut",),
                excluded_ingredients=(),
                diet_restrictions=("vegan",),
                pantry_staples=(),
                max_prep_time_minutes=20,
                meals_per_day=1,
            )

            filtered = planner.filter_recipes(request)
            plan = planner.create_plan(request)

            self.assertEqual([recipe.title for recipe in filtered], ["Safe Rice Bowl"])
            self.assertLessEqual(plan.estimated_total_cost, request.weekly_budget)


if __name__ == "__main__":
    unittest.main()
