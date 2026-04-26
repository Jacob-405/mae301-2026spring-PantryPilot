import unittest

from pantry_pilot.models import GroceryLocation, GroceryProduct, PlannerRequest, Recipe, RecipeIngredient
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


class StrongVsWeakMainProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="strong-main",
                title="Chicken Broccoli Rice Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=510,
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
            ),
            Recipe(
                recipe_id="weak-main",
                title="Buttered Pasta",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=510,
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


class SideReasoningProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="main",
                title="Chicken Plate",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=220,
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
                estimated_calories_per_serving=90,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("broccoli", 2.0, "cup"),),
                steps=("Toss it.",),
            ),
            Recipe(
                recipe_id="starch-side",
                title="Lemon Rice",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=90,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("rice", 1.0, "cup"),),
                steps=("Cook it.",),
            ),
        )


class NearEqualMainProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="close-a",
                title="Chicken Rice Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=500,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("chicken breast", 1.0, "lb"),
                    RecipeIngredient("broccoli", 1.0, "cup"),
                    RecipeIngredient("rice", 1.0, "cup"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="close-b",
                title="Turkey Rice Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=500,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("chicken breast", 1.0, "lb"),
                    RecipeIngredient("broccoli", 1.0, "cup"),
                    RecipeIngredient("rice", 1.0, "cup"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="close-c",
                title="Herby Rice Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=500,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("chicken breast", 1.0, "lb"),
                    RecipeIngredient("broccoli", 1.0, "cup"),
                    RecipeIngredient("rice", 1.0, "cup"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="weak",
                title="Buttered Pasta",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=500,
                prep_time_minutes=20,
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


class PlannerDeliberationPhaseTests(unittest.TestCase):
    def setUp(self) -> None:
        WeeklyMealPlanner.reset_request_cycle_offsets()

    def test_strong_mains_outrank_weak_mains(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=StrongVsWeakMainProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 4.0),
                    "broccoli": GroceryProduct("broccoli", 2.0, "cup", 1.0),
                    "rice": GroceryProduct("rice", 1.0, "cup", 0.8),
                    "pasta": GroceryProduct("pasta", 8.0, "oz", 0.8),
                    "butter": GroceryProduct("butter", 2.0, "tbsp", 0.4),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=60.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=450,
            daily_calorie_target_max=650,
        )

        plan = planner.create_plan(request)
        diagnostics = planner.latest_selection_diagnostics()[0]

        self.assertEqual(plan.meals[0].recipe.title, "Chicken Broccoli Rice Bowl")
        self.assertIn("main-anchor:strong", diagnostics.reasons)
        self.assertEqual(diagnostics.role_gate_count, 1)
        self.assertEqual(diagnostics.selected_title, "Chicken Broccoli Rice Bowl")

    def test_side_pairing_reasoning_is_visible(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=SideReasoningProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 4.0),
                    "broccoli": GroceryProduct("broccoli", 2.0, "cup", 1.2),
                    "rice": GroceryProduct("rice", 1.0, "cup", 0.7),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=50.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=500,
            daily_calorie_target_max=700,
        )

        plan = planner.create_plan(request)
        diagnostics = planner.latest_selection_diagnostics()
        side_diagnostic = next(diagnostic for diagnostic in diagnostics if diagnostic.meal_role == "side")
        stage_labels = {label for label, _ in side_diagnostic.stage_scores}

        self.assertIn("Broccoli Salad", [meal.recipe.title for meal in plan.meals])
        self.assertIn("complements-main", side_diagnostic.reasons)
        self.assertIn("side-candidate-ranking", stage_labels)
        self.assertEqual(side_diagnostic.runner_up_title, "Lemon Rice")
        self.assertGreater(side_diagnostic.runner_up_margin or 0.0, 0.0)

    def test_repeated_identical_requests_only_vary_among_near_equal_plans(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=NearEqualMainProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 4.0),
                    "broccoli": GroceryProduct("broccoli", 1.0, "cup", 0.8),
                    "rice": GroceryProduct("rice", 1.0, "cup", 0.8),
                    "pasta": GroceryProduct("pasta", 8.0, "oz", 0.8),
                    "butter": GroceryProduct("butter", 2.0, "tbsp", 0.4),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=70.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=450,
            daily_calorie_target_max=650,
        )

        first_titles = []
        for _ in range(3):
            plan = planner.create_plan(request)
            first_titles.append(plan.meals[0].recipe.title)

        self.assertTrue(set(first_titles).issubset({"Chicken Rice Bowl", "Turkey Rice Bowl", "Herby Rice Bowl"}))
        self.assertNotIn("Buttered Pasta", first_titles)
        self.assertGreaterEqual(len(set(first_titles)), 2)


if __name__ == "__main__":
    unittest.main()
