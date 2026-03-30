import os
import unittest
from unittest.mock import patch

from pantry_pilot.models import GroceryProduct, PlannerRequest
from pantry_pilot.planner import WeeklyMealPlanner
from pantry_pilot.providers import (
    FallbackGroceryProvider,
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


if __name__ == "__main__":
    unittest.main()
