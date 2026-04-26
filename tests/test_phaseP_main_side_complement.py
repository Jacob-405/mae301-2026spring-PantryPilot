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


class ComplementAwareSideProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="starch-main",
                title="Creamy Pasta Plate",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=340,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegetarian"}),
                allergens=frozenset({"dairy", "gluten"}),
                ingredients=(
                    RecipeIngredient("pasta", 8.0, "oz"),
                    RecipeIngredient("butter", 2.0, "tbsp"),
                ),
                steps=("Cook it.",),
                estimated_nutrition_per_serving=NutritionEstimate(
                    calories=340,
                    protein_grams=7.0,
                    carbs_grams=42.0,
                    fat_grams=14.0,
                ),
            ),
            Recipe(
                recipe_id="veg-side",
                title="Broccoli Salad",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=95,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free", "vegetarian"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("broccoli", 2.0, "cup"),),
                steps=("Toss it.",),
                estimated_nutrition_per_serving=NutritionEstimate(
                    calories=95,
                    protein_grams=4.0,
                    carbs_grams=10.0,
                    fat_grams=4.0,
                ),
            ),
            Recipe(
                recipe_id="starch-side",
                title="Lemon Rice",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=105,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free", "vegetarian"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("rice", 1.0, "cup"),),
                steps=("Cook it.",),
                estimated_nutrition_per_serving=NutritionEstimate(
                    calories=105,
                    protein_grams=2.0,
                    carbs_grams=22.0,
                    fat_grams=1.0,
                ),
            ),
            Recipe(
                recipe_id="protein-side",
                title="Egg Salad",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=120,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free", "vegetarian"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("eggs", 4.0, "item"),),
                steps=("Mix it.",),
                estimated_nutrition_per_serving=NutritionEstimate(
                    calories=120,
                    protein_grams=16.0,
                    carbs_grams=2.0,
                    fat_grams=8.0,
                ),
            ),
            Recipe(
                recipe_id="produce-lunch",
                title="Garden Lunch Bowl",
                cuisine="mediterranean",
                base_servings=2,
                estimated_calories_per_serving=210,
                prep_time_minutes=15,
                meal_types=("lunch",),
                diet_tags=frozenset({"gluten-free", "vegetarian"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("broccoli", 2.0, "cup"),
                    RecipeIngredient("tomato", 2.0, "item"),
                ),
                steps=("Cook it.",),
                estimated_nutrition_per_serving=NutritionEstimate(
                    calories=210,
                    protein_grams=5.0,
                    carbs_grams=18.0,
                    fat_grams=6.0,
                ),
            ),
        )


class MainSideComplementPhaseTests(unittest.TestCase):
    def setUp(self) -> None:
        WeeklyMealPlanner.reset_request_cycle_offsets()
        self.provider = ComplementAwareSideProvider()
        self.planner = WeeklyMealPlanner(
            recipe_provider=self.provider,
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "pasta": GroceryProduct("pasta", 8.0, "oz", 1.0),
                    "butter": GroceryProduct("butter", 2.0, "tbsp", 0.4),
                    "broccoli": GroceryProduct("broccoli", 2.0, "cup", 1.1),
                    "rice": GroceryProduct("rice", 1.0, "cup", 0.7),
                    "eggs": GroceryProduct("eggs", 4.0, "item", 1.0),
                    "tomato": GroceryProduct("tomato", 2.0, "item", 0.8),
                }
            ),
        )
        profile = UserNutritionProfile(
            age_years=34,
            sex="female",
            height_cm=168.0,
            weight_kg=72.0,
            activity_level="Low Active",
            planning_goal="High Protein Preference",
        )
        targets = generate_personal_targets(profile, meals_per_day=2)
        self.request = PlannerRequest(
            weekly_budget=90.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=2,
            meal_structure=("lunch", "dinner"),
            daily_calorie_target_min=targets.calorie_target_min,
            daily_calorie_target_max=targets.calorie_target_max,
            user_profile=profile,
            personal_targets=targets,
        )
        self.recipes = {recipe.title: recipe for recipe in self.provider.list_recipes()}

    def _select_dinner_side(
        self,
        prior_meals: list[PlannedMeal],
    ):
        all_candidates = self.provider.list_recipes()
        candidate_groups = self.planner._slot_recipe_groups(all_candidates, self.request, 2)
        purchased_quantities = {}
        pantry_inventory = frozenset()
        for meal in prior_meals:
            self.planner._apply_recipe(purchased_quantities, meal.recipe, self.request, pantry_inventory)
        main_recipe = self.recipes["Creamy Pasta Plate"]
        self.planner._apply_recipe(purchased_quantities, main_recipe, self.request, pantry_inventory)
        meals = list(prior_meals) + [
            PlannedMeal(
                day=1,
                slot=2,
                recipe=main_recipe,
                scaled_servings=2,
                incremental_cost=1.4,
                meal_role="main",
            )
        ]
        return self.planner._select_side_recipe(
            all_candidates=all_candidates,
            candidate_groups=candidate_groups,
            request=self.request,
            pantry_inventory=pantry_inventory,
            variety_profile=self.planner._variety_profile(self.request),
            purchased_quantities=purchased_quantities,
            meals=meals,
            day_number=1,
            slot_number=2,
        )

    def test_starch_heavy_main_avoids_redundant_starch_side_when_vegetable_side_exists(self) -> None:
        selection = self._select_dinner_side(prior_meals=[])
        self.assertIsNotNone(selection)
        if selection is None:
            self.fail("Expected a side choice.")
        selected_recipe, _, diagnostic = selection

        self.assertEqual(selected_recipe.title, "Broccoli Salad")
        self.assertIn("penalty:produce-poor-pairing", diagnostic.runner_up_loss_reasons)
        self.assertIn("complements-main-produce-gap", diagnostic.reasons)
        self.assertNotEqual(selected_recipe.title, "Lemon Rice")

    def test_same_main_gets_different_side_when_daily_deficits_change(self) -> None:
        produce_gap_selection = self._select_dinner_side(prior_meals=[])
        protein_gap_selection = self._select_dinner_side(
            prior_meals=[
                PlannedMeal(
                    day=1,
                    slot=1,
                    recipe=self.recipes["Garden Lunch Bowl"],
                    scaled_servings=2,
                    incremental_cost=1.9,
                    meal_role="main",
                ),
                PlannedMeal(
                    day=1,
                    slot=1,
                    recipe=self.recipes["Broccoli Salad"],
                    scaled_servings=2,
                    incremental_cost=1.1,
                    meal_role="side",
                )
            ]
        )

        self.assertIsNotNone(produce_gap_selection)
        self.assertIsNotNone(protein_gap_selection)
        if produce_gap_selection is None or protein_gap_selection is None:
            self.fail("Expected both side choices.")
        self.assertEqual(produce_gap_selection[0].title, "Broccoli Salad")
        self.assertEqual(protein_gap_selection[0].title, "Egg Salad")
        self.assertIn("target:protein-gap", protein_gap_selection[2].reasons)
        self.assertIn("target:protein-priority", protein_gap_selection[2].reasons)
        self.assertGreater(
            protein_gap_selection[2].daily_deficits_before.protein_grams,
            protein_gap_selection[2].daily_deficits_after.protein_grams,
        )

    def test_side_diagnostics_show_complement_and_runner_up_loss(self) -> None:
        selection = self._select_dinner_side(prior_meals=[])
        self.assertIsNotNone(selection)
        if selection is None:
            self.fail("Expected a side choice.")
        _, _, diagnostic = selection

        self.assertIsNotNone(diagnostic.anchor_composition_profile)
        self.assertIsNotNone(diagnostic.selected_composition_profile)
        self.assertIn("complements-main-produce-gap", diagnostic.reasons)
        self.assertIn("target:produce-gap", diagnostic.reasons)
        self.assertTrue(any(reason.startswith("runner-up-lost:") for reason in diagnostic.runner_up_loss_reasons))


if __name__ == "__main__":
    unittest.main()
