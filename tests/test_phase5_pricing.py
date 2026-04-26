import unittest

from pantry_pilot.models import PlannerRequest, Recipe, RecipeIngredient
from pantry_pilot.planner import AggregatedIngredient, PlannerError, WeeklyMealPlanner
from pantry_pilot.providers import LocalRecipeProvider, MockGroceryProvider


class PackageCostRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="tiny-spice-bowl",
                title="Tiny Spice Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=180,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan", "gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("chili powder", 1.0, "tsp"),
                    RecipeIngredient("rice", 1.0, "cup"),
                ),
                steps=("Cook rice.", "Season with chili powder."),
            ),
        )


class PricingPhase5Tests(unittest.TestCase):
    def test_buying_one_whole_package_when_only_part_is_used(self) -> None:
        planner = WeeklyMealPlanner(grocery_provider=MockGroceryProvider())

        shopping_list, total_cost = planner._build_shopping_list(
            {"pasta": AggregatedIngredient(quantity=8.0, unit="oz")}
        )
        pasta = shopping_list[0]

        self.assertEqual(pasta.estimated_packages, 1)
        self.assertEqual(pasta.package_quantity, 16.0)
        self.assertEqual(pasta.purchased_quantity, 16.0)
        self.assertEqual(pasta.estimated_cost, 1.8)
        self.assertEqual(total_cost, 1.8)

    def test_multiple_recipe_usage_can_share_one_purchased_package(self) -> None:
        planner = WeeklyMealPlanner(grocery_provider=MockGroceryProvider())

        shopping_list, total_cost = planner._build_shopping_list(
            {"garlic": AggregatedIngredient(quantity=4.0, unit="clove")}
        )
        garlic = shopping_list[0]

        self.assertEqual(garlic.estimated_packages, 1)
        self.assertEqual(garlic.package_quantity, 8.0)
        self.assertEqual(garlic.purchased_quantity, 8.0)
        self.assertEqual(total_cost, 0.8)

    def test_unit_normalization_affects_pricing_correctly(self) -> None:
        planner = WeeklyMealPlanner(grocery_provider=MockGroceryProvider())

        shopping_list, total_cost = planner._build_shopping_list(
            {"olive oil": AggregatedIngredient(quantity=1.0, unit="cup")}
        )
        olive_oil = shopping_list[0]

        self.assertEqual(olive_oil.estimated_packages, 1)
        self.assertEqual(olive_oil.package_quantity, 32.0)
        self.assertEqual(olive_oil.package_unit, "tbsp")
        self.assertEqual(olive_oil.purchased_quantity, 32.0)
        self.assertEqual(total_cost, 6.4)

    def test_pantry_subtraction_interacts_correctly_with_package_purchases(self) -> None:
        request_without_pantry = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("vegan",),
            pantry_staples=(),
            max_prep_time_minutes=20,
            meals_per_day=1,
        )
        request_with_pantry = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("vegan",),
            pantry_staples=("olive oil",),
            max_prep_time_minutes=20,
            meals_per_day=1,
        )
        planner = WeeklyMealPlanner()

        plan_without_pantry = planner.create_plan(request_without_pantry)
        plan_with_pantry = planner.create_plan(request_with_pantry)

        self.assertLess(plan_with_pantry.estimated_total_cost, plan_without_pantry.estimated_total_cost)
        self.assertNotIn("olive oil", {item.name for item in plan_with_pantry.shopping_list})

    def test_budget_checks_use_purchase_cost_not_raw_usage_cost(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=PackageCostRecipeProvider(),
            grocery_provider=MockGroceryProvider(),
        )
        request = PlannerRequest(
            weekly_budget=5.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("vegan",),
            pantry_staples=(),
            max_prep_time_minutes=15,
            meals_per_day=1,
        )

        with self.assertRaises(PlannerError):
            planner.create_plan(request)

    def test_unknown_conversion_cost_does_not_show_as_zero(self) -> None:
        planner = WeeklyMealPlanner(grocery_provider=MockGroceryProvider())

        shopping_list, total_cost = planner._build_shopping_list(
            {"apple": AggregatedIngredient(quantity=1.0, unit="lb")}
        )
        apple = shopping_list[0]

        self.assertIsNone(apple.estimated_cost)
        self.assertEqual(total_cost, 0.0)

    def test_common_item_to_cup_gap_now_uses_estimated_purchase_cost(self) -> None:
        planner = WeeklyMealPlanner(grocery_provider=MockGroceryProvider())

        shopping_list, total_cost = planner._build_shopping_list(
            {"apple": AggregatedIngredient(quantity=2.5, unit="cup")}
        )
        apple = shopping_list[0]

        self.assertEqual(apple.estimated_packages, 2)
        self.assertEqual(apple.package_quantity, 1.0)
        self.assertEqual(apple.package_unit, "item")
        self.assertEqual(apple.estimated_cost, 1.5)
        self.assertEqual(total_cost, 1.5)


if __name__ == "__main__":
    unittest.main()
