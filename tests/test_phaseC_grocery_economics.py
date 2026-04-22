import tempfile
import unittest
from pathlib import Path

from pantry_pilot.models import GroceryLocation, GroceryProduct, PlannerRequest, Recipe, RecipeIngredient
from pantry_pilot.normalization import normalize_name
from pantry_pilot.pantry_carryover import PantryCarryoverStore
from pantry_pilot.planner import AggregatedIngredient, WeeklyMealPlanner
from pantry_pilot.providers import MockGroceryProvider


class FixedPriceGroceryProvider:
    provider_name = "mock"

    def __init__(self, catalog: dict[str, GroceryProduct]) -> None:
        self._catalog = {normalize_name(name): product for name, product in catalog.items()}

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        return ()

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        return self._catalog.get(normalize_name(ingredient_name))


class SourCreamCarryoverRecipeProvider:
    def list_recipes(self) -> tuple[Recipe, ...]:
        return tuple(
            Recipe(
                recipe_id=f"sour-cream-bowl-{index}",
                title=f"Sour Cream Bowl {index}",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=320,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegetarian", "gluten-free"}),
                allergens=frozenset({"dairy"}),
                ingredients=(RecipeIngredient("sour cream", 1.0, "cup"),),
                steps=("Serve chilled.",),
            )
            for index in range(1, 8)
        )


class GroceryEconomicsPhaseCTests(unittest.TestCase):
    def test_common_conversion_case_sour_cream_item_to_cup_prices_correctly(self) -> None:
        planner = WeeklyMealPlanner(grocery_provider=MockGroceryProvider())

        shopping_list, total_cost = planner._build_shopping_list(
            {"sour cream": AggregatedIngredient(quantity=1.0, unit="item")}
        )
        sour_cream = shopping_list[0]

        self.assertEqual(sour_cream.estimated_packages, 1)
        self.assertEqual(sour_cream.package_quantity, 2.0)
        self.assertEqual(sour_cream.package_unit, "cup")
        self.assertEqual(sour_cream.purchased_quantity, 2.0)
        self.assertEqual(sour_cream.estimated_cost, 2.8)
        self.assertEqual(total_cost, 2.8)

    def test_common_conversion_case_cream_cheese_package_prices_correctly(self) -> None:
        planner = WeeklyMealPlanner(grocery_provider=MockGroceryProvider())

        shopping_list, total_cost = planner._build_shopping_list(
            {"cream cheese": AggregatedIngredient(quantity=1.0, unit="package")}
        )
        cream_cheese = shopping_list[0]

        self.assertEqual(cream_cheese.estimated_packages, 1)
        self.assertEqual(cream_cheese.package_quantity, 1.0)
        self.assertEqual(cream_cheese.package_unit, "item")
        self.assertEqual(cream_cheese.purchased_quantity, 1.0)
        self.assertEqual(cream_cheese.estimated_cost, 2.5)
        self.assertEqual(total_cost, 2.5)

    def test_multi_step_conversion_case_prices_correctly(self) -> None:
        planner = WeeklyMealPlanner(
            grocery_provider=FixedPriceGroceryProvider(
                {"cream cheese": GroceryProduct("cream cheese", 8.0, "oz", 2.5)}
            )
        )

        shopping_list, total_cost = planner._build_shopping_list(
            {"cream cheese": AggregatedIngredient(quantity=1.0, unit="package")}
        )
        cream_cheese = shopping_list[0]

        self.assertEqual(cream_cheese.estimated_packages, 1)
        self.assertEqual(cream_cheese.package_quantity, 8.0)
        self.assertEqual(cream_cheese.package_unit, "oz")
        self.assertEqual(cream_cheese.purchased_quantity, 8.0)
        self.assertEqual(cream_cheese.estimated_cost, 2.5)
        self.assertEqual(total_cost, 2.5)

    def test_package_reuse_across_weeks_keeps_consumed_and_added_cost_separate(self) -> None:
        grocery_provider = FixedPriceGroceryProvider(
            {
                "sour cream": GroceryProduct("sour cream", 2.0, "cup", 2.8),
            }
        )
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("vegetarian", "gluten-free"),
            pantry_staples=(),
            max_prep_time_minutes=20,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=600,
            daily_calorie_target_max=900,
            leftovers_mode="off",
        )
        provider = SourCreamCarryoverRecipeProvider()

        with tempfile.TemporaryDirectory() as tmpdir:
            pantry_store = PantryCarryoverStore(Path(tmpdir) / "carryover.json")
            first_plan = WeeklyMealPlanner(
                recipe_provider=provider,
                grocery_provider=grocery_provider,
            ).create_plan(request)
            pantry_store.apply_plan(first_plan)
            inventory = pantry_store.load_inventory()

            second_plan = WeeklyMealPlanner(
                recipe_provider=provider,
                grocery_provider=grocery_provider,
                carryover_inventory={
                    item.name: AggregatedIngredient(quantity=item.quantity, unit=item.unit)
                    for item in inventory
                },
            ).create_plan(request)

        self.assertEqual(first_plan.shopping_list[0].estimated_packages, 4)
        self.assertEqual(first_plan.shopping_list[0].leftover_quantity_remaining, 1.0)
        self.assertEqual(first_plan.estimated_total_cost, 11.2)
        self.assertEqual(first_plan.meals[0].incremental_cost, 2.8)
        self.assertEqual(first_plan.meals[0].consumed_cost, 1.4)

        self.assertEqual(second_plan.shopping_list[0].estimated_packages, 3)
        self.assertEqual(second_plan.shopping_list[0].carryover_used_quantity, 1.0)
        self.assertEqual(second_plan.estimated_total_cost, 8.4)
        self.assertEqual(second_plan.meals[0].incremental_cost, 0.0)
        self.assertEqual(second_plan.meals[0].consumed_cost, 1.4)

    def test_meal_cost_presentation_does_not_collapse_to_whole_package_cost(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=SourCreamCarryoverRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {"sour cream": GroceryProduct("sour cream", 2.0, "cup", 2.8)}
            ),
        )
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("vegetarian", "gluten-free"),
            pantry_staples=(),
            max_prep_time_minutes=20,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=600,
            daily_calorie_target_max=900,
            leftovers_mode="off",
        )

        plan = planner.create_plan(request)
        first_meal = plan.meals[0]

        self.assertEqual(first_meal.incremental_cost, 2.8)
        self.assertEqual(first_meal.consumed_cost, 1.4)
        self.assertLess(first_meal.consumed_cost, first_meal.incremental_cost)


if __name__ == "__main__":
    unittest.main()
