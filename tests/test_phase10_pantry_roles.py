import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from pantry_pilot.app_runtime import build_plan_snapshot
from pantry_pilot.models import GroceryLocation, GroceryProduct, PlannerRequest, Recipe, RecipeIngredient
from pantry_pilot.normalization import normalize_name
from pantry_pilot.pantry_carryover import PantryCarryoverStore, PantryInventoryItem
from pantry_pilot.planner import AggregatedIngredient, WeeklyMealPlanner
from pantry_pilot.providers import LocalRecipeProvider


class FixedPriceGroceryProvider:
    provider_name = "mock"

    def __init__(self, catalog: dict[str, GroceryProduct]) -> None:
        self._catalog = {normalize_name(name): product for name, product in catalog.items()}

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        return ()

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        return self._catalog.get(normalize_name(ingredient_name))


class CarryoverRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        recipes: list[Recipe] = []
        for index in range(1, 8):
            recipes.append(
                Recipe(
                    recipe_id=f"carryover-{index}",
                    title=f"Carryover Bowl {index}",
                    cuisine="american",
                    base_servings=2,
                    estimated_calories_per_serving=450,
                    prep_time_minutes=20,
                    meal_types=("dinner",),
                    diet_tags=frozenset({"gluten-free"}),
                    allergens=frozenset(),
                    ingredients=(RecipeIngredient("boxed staple", 6 / 7, "item"),),
                    steps=("Cook it.",),
                )
            )
        return tuple(recipes)


class MainSideRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        mains = [
            Recipe(
                recipe_id=f"main-{index}",
                title=title,
                cuisine="mediterranean" if index % 2 else "american",
                base_servings=2,
                estimated_calories_per_serving=420 + (index * 10),
                prep_time_minutes=25,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient(f"main ingredient {index}", 1.0, "item"),),
                steps=("Cook the main.",),
            )
            for index, title in enumerate(
                (
                    "Chicken Skillet",
                    "Bean Rice Bowl",
                    "Herby Pasta Plate",
                    "Stuffed Peppers",
                    "Tomato Lentil Stew",
                    "Turkey Taco Bowl",
                    "Curry Chickpea Main",
                ),
                start=1,
            )
        ]
        sides = [
            Recipe(
                recipe_id=f"side-{index}",
                title=title,
                cuisine="mediterranean",
                base_servings=2,
                estimated_calories_per_serving=140 + (index * 10),
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient(f"side ingredient {index}", 1.0, "item"),),
                steps=("Cook the side.",),
            )
            for index, title in enumerate(
                (
                    "Lemon Rice",
                    "Broccoli Salad",
                    "Roasted Potatoes",
                    "Herb Beans",
                ),
                start=1,
            )
        ]
        extras = [
            Recipe(
                recipe_id="dessert",
                title="Chocolate Cake",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=300,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegetarian"}),
                allergens=frozenset({"dairy", "gluten"}),
                ingredients=(RecipeIngredient("cake ingredient", 1.0, "item"),),
                steps=("Bake the cake.",),
            ),
            Recipe(
                recipe_id="drink",
                title="Berry Smoothie",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=220,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegetarian"}),
                allergens=frozenset({"dairy"}),
                ingredients=(RecipeIngredient("smoothie ingredient", 1.0, "item"),),
                steps=("Blend it.",),
            ),
            Recipe(
                recipe_id="condiment",
                title="Garlic Sauce",
                cuisine="mediterranean",
                base_servings=2,
                estimated_calories_per_serving=120,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegetarian"}),
                allergens=frozenset({"dairy"}),
                ingredients=(RecipeIngredient("garlic", 1.0, "item"),),
                steps=("Mix it.",),
            ),
        ]
        return tuple(mains + sides + extras)


class CuisineSoftPreferenceProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="mexican-main",
                title="Mexican Rice Bowl",
                cuisine="mexican",
                base_servings=2,
                estimated_calories_per_serving=480,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("mexican base", 1.0, "item"),),
                steps=("Cook the mexican meal.",),
            ),
            Recipe(
                recipe_id="american-main",
                title="American Rice Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=470,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("american base", 1.0, "item"),),
                steps=("Cook the american meal.",),
            ),
        )


class PantryRolesPhaseTests(unittest.TestCase):
    def setUp(self) -> None:
        WeeklyMealPlanner.reset_request_cycle_offsets()

    def test_leftover_package_quantity_reduces_added_shopping_cost_in_later_plan(self) -> None:
        provider = CarryoverRecipeProvider()
        grocery_provider = FixedPriceGroceryProvider(
            {
                "boxed staple": GroceryProduct("boxed staple", 5.0, "item", 10.0),
            }
        )
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=800,
            daily_calorie_target_max=1000,
            leftovers_mode="off",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PantryCarryoverStore(Path(tmpdir) / "carryover.json")
            first_planner = WeeklyMealPlanner(recipe_provider=provider, grocery_provider=grocery_provider)
            first_plan = first_planner.create_plan(request)
            store.apply_plan(first_plan)
            inventory = store.load_inventory()

            second_planner = WeeklyMealPlanner(
                recipe_provider=provider,
                grocery_provider=grocery_provider,
                carryover_inventory={
                    item.name: AggregatedIngredient(quantity=item.quantity, unit=item.unit)
                    for item in inventory
                },
            )
            second_plan = second_planner.create_plan(request)

        self.assertEqual(first_plan.estimated_total_cost, 20.0)
        self.assertEqual(second_plan.estimated_total_cost, 10.0)
        self.assertAlmostEqual(first_plan.shopping_list[0].leftover_quantity_remaining, 4.0)
        self.assertAlmostEqual(second_plan.shopping_list[0].carryover_used_quantity, 4.0)

    def test_pantry_reset_clears_carryover_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = PantryCarryoverStore(Path(tmpdir) / "carryover.json")
            store.save_inventory(
                (
                    PantryInventoryItem(name="rice", quantity=2.0, unit="cup"),
                )
            )
            store.reset()
            self.assertEqual(store.load_inventory(), ())

    def test_lunch_dinner_selects_main_and_can_add_side_when_feasible(self) -> None:
        grocery_catalog = {
            **{
                f"main ingredient {index}": GroceryProduct(f"main ingredient {index}", 1.0, "item", 3.0)
                for index in range(1, 8)
            },
            **{
                f"side ingredient {index}": GroceryProduct(f"side ingredient {index}", 1.0, "item", 1.0)
                for index in range(1, 5)
            },
            "cake ingredient": GroceryProduct("cake ingredient", 1.0, "item", 2.0),
            "smoothie ingredient": GroceryProduct("smoothie ingredient", 1.0, "item", 2.0),
            "garlic": GroceryProduct("garlic", 1.0, "item", 1.0),
        }
        planner = WeeklyMealPlanner(
            recipe_provider=MainSideRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(grocery_catalog),
        )
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=35,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=1000,
            daily_calorie_target_max=1200,
            leftovers_mode="off",
        )

        plan = planner.create_plan(request)
        day_roles: dict[int, set[str]] = defaultdict(set)
        for meal in plan.meals:
            day_roles[meal.day].add(meal.meal_role)

        self.assertTrue(any({"main", "side"}.issubset(roles) for roles in day_roles.values()))
        self.assertTrue(all("main" in roles for roles in day_roles.values()))

    def test_desserts_condiments_and_beverages_do_not_fill_main_dinner_slots(self) -> None:
        planner = WeeklyMealPlanner(recipe_provider=MainSideRecipeProvider())
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=35,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=700,
            daily_calorie_target_max=1200,
        )

        groups = planner._slot_recipe_groups(planner.filter_recipes(request), request, 1)
        main_titles = {recipe.title for recipe in groups.mains}
        side_titles = {recipe.title for recipe in groups.sides}

        self.assertNotIn("Chocolate Cake", main_titles)
        self.assertNotIn("Berry Smoothie", main_titles)
        self.assertNotIn("Garlic Sauce", main_titles)
        self.assertIn("Broccoli Salad", side_titles)
        self.assertIn("Chicken Skillet", main_titles)

    def test_cuisine_preferences_are_soft_preference_not_hard_pool_filter(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=CuisineSoftPreferenceProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "mexican base": GroceryProduct("mexican base", 1.0, "item", 2.0),
                    "american base": GroceryProduct("american base", 1.0, "item", 2.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=("mexican",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=800,
            daily_calorie_target_max=1100,
        )

        filtered_titles = {recipe.title for recipe in planner.filter_recipes(request)}
        plan = planner.create_plan(request)

        self.assertEqual(filtered_titles, {"Mexican Rice Bowl", "American Rice Bowl"})
        self.assertEqual(plan.meals[0].recipe.title, "Mexican Rice Bowl")

    def test_app_runtime_smoke_remains_render_safe_with_role_and_carryover_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot = build_plan_snapshot(
                PlannerRequest(
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
                ),
                pantry_store=PantryCarryoverStore(Path(tmpdir) / "carryover.json"),
            )

        self.assertIn("Carryover Used", snapshot.shopping_list_csv)
        self.assertIn("(main)", snapshot.export_text)
        self.assertIn("Why chosen:", snapshot.export_text)
        self.assertIn("Confidence:", snapshot.export_text)


if __name__ == "__main__":
    unittest.main()
