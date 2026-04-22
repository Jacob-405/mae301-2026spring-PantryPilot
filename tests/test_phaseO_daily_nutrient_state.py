import unittest

from pantry_pilot.models import (
    GroceryLocation,
    GroceryProduct,
    NutritionEstimate,
    PlannedMeal,
    PlannerRequest,
    Recipe,
    RecipeIngredient,
    UserNutritionProfile,
)
from pantry_pilot.normalization import normalize_name
from pantry_pilot.personal_targets import generate_personal_targets
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


class DailyStateRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="chicken-plate",
                title="Chicken Plate",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=280,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("chicken breast", 1.0, "lb"),),
                steps=("Cook it.",),
                estimated_nutrition_per_serving=NutritionEstimate(
                    calories=280,
                    protein_grams=34.0,
                    carbs_grams=4.0,
                    fat_grams=10.0,
                ),
            ),
            Recipe(
                recipe_id="broccoli-salad",
                title="Broccoli Salad",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=110,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("broccoli", 2.0, "cup"),
                    RecipeIngredient("olive oil", 1.0, "tbsp"),
                ),
                steps=("Toss it.",),
                estimated_nutrition_per_serving=NutritionEstimate(
                    calories=110,
                    protein_grams=3.0,
                    carbs_grams=9.0,
                    fat_grams=7.0,
                ),
            ),
            Recipe(
                recipe_id="lemon-rice",
                title="Lemon Rice",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=120,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("rice", 1.0, "cup"),),
                steps=("Cook it.",),
                estimated_nutrition_per_serving=NutritionEstimate(
                    calories=120,
                    protein_grams=2.0,
                    carbs_grams=24.0,
                    fat_grams=1.0,
                ),
            ),
        )


class DailyNutrientStatePhaseTests(unittest.TestCase):
    def setUp(self) -> None:
        WeeklyMealPlanner.reset_request_cycle_offsets()
        self.provider = DailyStateRecipeProvider()
        self.planner = WeeklyMealPlanner(
            recipe_provider=self.provider,
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 3.5),
                    "broccoli": GroceryProduct("broccoli", 2.0, "cup", 1.1),
                    "rice": GroceryProduct("rice", 1.0, "cup", 0.7),
                    "olive oil": GroceryProduct("olive oil", 1.0, "tbsp", 0.2),
                }
            ),
        )
        profile = UserNutritionProfile(
            age_years=34,
            sex="female",
            height_cm=168.0,
            weight_kg=72.0,
            activity_level="Low Active",
            planning_goal="Maintain",
        )
        self.targets = generate_personal_targets(profile, meals_per_day=1)
        self.request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=self.targets.calorie_target_min,
            daily_calorie_target_max=self.targets.calorie_target_max,
            user_profile=profile,
            personal_targets=self.targets,
        )
        self.recipes = {recipe.title: recipe for recipe in self.provider.list_recipes()}

    def test_daily_nutrient_state_updates_after_adding_meals(self) -> None:
        before = self.planner.current_day_nutrient_state((), 1)
        after_main = self.planner.current_day_nutrient_state(
            (
                PlannedMeal(
                    day=1,
                    slot=1,
                    recipe=self.recipes["Chicken Plate"],
                    scaled_servings=2,
                    incremental_cost=3.5,
                    meal_role="main",
                ),
            ),
            1,
        )
        after_side = self.planner.current_day_nutrient_state(
            (
                PlannedMeal(
                    day=1,
                    slot=1,
                    recipe=self.recipes["Chicken Plate"],
                    scaled_servings=2,
                    incremental_cost=3.5,
                    meal_role="main",
                ),
                PlannedMeal(
                    day=1,
                    slot=1,
                    recipe=self.recipes["Broccoli Salad"],
                    scaled_servings=2,
                    incremental_cost=1.1,
                    meal_role="side",
                ),
            ),
            1,
        )

        self.assertEqual(before.calories, 0.0)
        self.assertGreater(after_main.calories, before.calories)
        self.assertGreater(after_side.produce_support, after_main.produce_support)
        self.assertGreater(after_side.carbs_grams, after_main.carbs_grams)

    def test_manual_and_profile_targets_produce_different_daily_deficits(self) -> None:
        state = self.planner.current_day_nutrient_state(
            (
                PlannedMeal(
                    day=1,
                    slot=1,
                    recipe=self.recipes["Chicken Plate"],
                    scaled_servings=2,
                    incremental_cost=3.5,
                    meal_role="main",
                ),
            ),
            1,
        )
        manual_request = PlannerRequest(
            **{
                **self.request.__dict__,
                "daily_calorie_target_min": 1400,
                "daily_calorie_target_max": 1700,
                "user_profile": None,
                "personal_targets": None,
            }
        )

        profile_deficits = self.planner.day_nutrient_deficits(state, self.request)
        manual_deficits = self.planner.day_nutrient_deficits(state, manual_request)

        self.assertNotEqual(profile_deficits.calories_below_min, manual_deficits.calories_below_min)
        self.assertNotEqual(profile_deficits.protein_grams, manual_deficits.protein_grams)
        self.assertNotEqual(profile_deficits.grains_starches_support, manual_deficits.grains_starches_support)

    def test_selection_diagnostics_expose_day_state_and_remaining_gaps_for_side_logic(self) -> None:
        plan = self.planner.create_plan(self.request)
        diagnostics = self.planner.latest_selection_diagnostics()
        side_diagnostic = next(diagnostic for diagnostic in diagnostics if diagnostic.meal_role == "side")

        self.assertIn("Broccoli Salad", [meal.recipe.title for meal in plan.meals])
        self.assertIsNotNone(side_diagnostic.daily_state_before)
        self.assertIsNotNone(side_diagnostic.daily_state_after)
        self.assertIsNotNone(side_diagnostic.daily_deficits_before)
        self.assertIsNotNone(side_diagnostic.daily_deficits_after)
        self.assertGreater(side_diagnostic.daily_state_before.calories, 0.0)
        self.assertGreater(
            side_diagnostic.daily_deficits_before.produce_support,
            side_diagnostic.daily_deficits_after.produce_support,
        )
        self.assertIn("target:produce-gap", side_diagnostic.reasons)
        self.assertEqual(side_diagnostic.runner_up_title, "Lemon Rice")


if __name__ == "__main__":
    unittest.main()
