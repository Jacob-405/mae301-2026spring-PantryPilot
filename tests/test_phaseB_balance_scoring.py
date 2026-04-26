import unittest

from pantry_pilot.models import GroceryLocation, GroceryProduct, PlannedMeal, PlannerRequest, Recipe, RecipeIngredient
from pantry_pilot.normalization import normalize_name
from pantry_pilot.planner import WeeklyMealPlanner
from pantry_pilot.providers import LocalRecipeProvider


class FixedPriceGroceryProvider:
    provider_name = "mock"

    def __init__(self, catalog: dict[str, GroceryProduct]) -> None:
        self._catalog = {normalize_name(name): product for name, product in catalog.items()}

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        return ()

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        return self._catalog.get(normalize_name(ingredient_name))


class BalancedVsWeakRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="balanced-main",
                title="Chicken Rice Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=520,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("chicken breast", 1.0, "lb"),
                    RecipeIngredient("rice", 1.0, "cup"),
                    RecipeIngredient("broccoli", 2.0, "cup"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="weak-main",
                title="Buttered Pasta",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=520,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegetarian"}),
                allergens=frozenset({"dairy", "gluten"}),
                ingredients=(
                    RecipeIngredient("pasta", 8.0, "oz"),
                    RecipeIngredient("butter", 2.0, "tbsp"),
                ),
                steps=("Cook it.",),
            ),
        )


class SidePairingRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="main",
                title="Chicken Cutlet",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=170,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("chicken breast", 1.0, "lb"),),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="veg-side",
                title="Broccoli Salad",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=70,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("broccoli", 2.0, "cup"),),
                steps=("Toss it.",),
            ),
            Recipe(
                recipe_id="carb-side",
                title="Lemon Rice",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=70,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("rice", 1.0, "cup"),),
                steps=("Cook it.",),
            ),
        )


class MainGuardrailRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        mains = tuple(
            Recipe(
                recipe_id=f"main-{index}",
                title=title,
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=420 + (index * 10),
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient(f"main ingredient {index}", 1.0, "item"),),
                steps=("Cook it.",),
            )
            for index, title in enumerate(
                (
                    "Chicken Skillet",
                    "Bean Rice Bowl",
                    "Turkey Taco Bowl",
                    "Broccoli Pasta Plate",
                    "Stuffed Peppers",
                    "Lentil Curry Bowl",
                    "Veggie Chicken Soup",
                ),
                start=1,
            )
        )
        extras = (
            Recipe(
                recipe_id="dessert",
                title="Chocolate Cake",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=260,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegetarian"}),
                allergens=frozenset({"dairy", "gluten"}),
                ingredients=(RecipeIngredient("sugar", 1.0, "cup"),),
                steps=("Bake it.",),
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
                ingredients=(RecipeIngredient("milk", 1.0, "cup"),),
                steps=("Blend it.",),
            ),
            Recipe(
                recipe_id="condiment",
                title="Garlic Sauce",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=120,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegetarian"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("garlic", 2.0, "clove"),),
                steps=("Mix it.",),
            ),
        )
        return mains + extras


class BalanceScoringPhaseTests(unittest.TestCase):
    def setUp(self) -> None:
        WeeklyMealPlanner.reset_request_cycle_offsets()

    def test_balanced_meals_score_above_weak_meals(self) -> None:
        provider = BalancedVsWeakRecipeProvider()
        planner = WeeklyMealPlanner(recipe_provider=provider)
        recipes = provider.list_recipes()

        balanced_score = planner._meal_balance_score(recipes[0], "dinner", "main", None)
        weak_score = planner._meal_balance_score(recipes[1], "dinner", "main", None)

        self.assertGreater(balanced_score.total, weak_score.total)
        self.assertIn("protein-support", balanced_score.reasons)
        self.assertIn("vegetable-support", balanced_score.reasons)
        self.assertIn("penalty:weak-anchor", weak_score.reasons)

    def test_side_pairing_improves_meal_composition(self) -> None:
        provider = SidePairingRecipeProvider()
        grocery_provider = FixedPriceGroceryProvider(
            {
                "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 4.0),
                "broccoli": GroceryProduct("broccoli", 2.0, "cup", 1.2),
                "rice": GroceryProduct("rice", 1.0, "cup", 0.6),
            }
        )
        balanced_planner = WeeklyMealPlanner(
            recipe_provider=provider,
            grocery_provider=grocery_provider,
            balance_scoring_enabled=True,
        )
        request = PlannerRequest(
            weekly_budget=20.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=450,
            daily_calorie_target_max=550,
        )
        all_candidates = provider.list_recipes()
        candidate_groups = balanced_planner._slot_recipe_groups(all_candidates, request, 1)
        main_recipe = candidate_groups.mains[0]
        broccoli_side = next(recipe for recipe in candidate_groups.sides if recipe.title == "Broccoli Salad")
        rice_side = next(recipe for recipe in candidate_groups.sides if recipe.title == "Lemon Rice")
        pantry_inventory = frozenset()
        meals = (
            PlannedMeal(
                day=1,
                slot=1,
                recipe=main_recipe,
                scaled_servings=2,
                incremental_cost=4.0,
                meal_role="main",
            ),
        )

        balanced_quantities = {}
        balanced_planner._apply_recipe(balanced_quantities, main_recipe, request, pantry_inventory)

        broccoli_score = balanced_planner._meal_balance_score(
            broccoli_side,
            "dinner",
            "side",
            main_recipe,
        )
        rice_score = balanced_planner._meal_balance_score(
            rice_side,
            "dinner",
            "side",
            main_recipe,
        )

        balanced_side = balanced_planner._select_side_recipe(
            all_candidates=all_candidates,
            candidate_groups=candidate_groups,
            request=request,
            pantry_inventory=pantry_inventory,
            variety_profile=balanced_planner._variety_profile(request),
            purchased_quantities=balanced_quantities,
            meals=list(meals),
            day_number=1,
            slot_number=1,
        )

        self.assertGreater(broccoli_score.total, rice_score.total)
        self.assertIsNotNone(balanced_side)
        if balanced_side is None:
            self.fail("Expected the planner to find a side.")
        self.assertEqual(balanced_side[0].title, "Broccoli Salad")

    def test_dessert_drink_and_condiment_titles_are_not_chosen_as_main_lunch_dinner_meals(self) -> None:
        grocery_provider = FixedPriceGroceryProvider(
            {
                **{
                    f"main ingredient {index}": GroceryProduct(f"main ingredient {index}", 1.0, "item", 2.0)
                    for index in range(1, 8)
                },
                "sugar": GroceryProduct("sugar", 1.0, "cup", 1.0),
                "milk": GroceryProduct("milk", 1.0, "cup", 1.0),
                "garlic": GroceryProduct("garlic", 2.0, "clove", 1.0),
            }
        )
        planner = WeeklyMealPlanner(
            recipe_provider=MainGuardrailRecipeProvider(),
            grocery_provider=grocery_provider,
        )
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=700,
            daily_calorie_target_max=1000,
            leftovers_mode="off",
        )

        plan = planner.create_plan(request)
        main_titles = {meal.recipe.title for meal in plan.meals if meal.meal_role == "main"}

        self.assertNotIn("Chocolate Cake", main_titles)
        self.assertNotIn("Berry Smoothie", main_titles)
        self.assertNotIn("Garlic Sauce", main_titles)


if __name__ == "__main__":
    unittest.main()
