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


class WeeklyVarietyRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        mains = (
            Recipe(
                recipe_id="chicken-rice-bowl",
                title="Chicken Rice Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=220,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("chicken breast", 1.0, "lb"),
                    RecipeIngredient("rice", 1.0, "cup"),
                    RecipeIngredient("broccoli", 1.0, "cup"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="turkey-rice-bowl",
                title="Turkey Rice Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=215,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("ground turkey", 1.0, "lb"),
                    RecipeIngredient("rice", 1.0, "cup"),
                    RecipeIngredient("bell pepper", 1.0, "cup"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="beef-rice-skillet",
                title="Beef Rice Skillet",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=225,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("ground beef", 1.0, "lb"),
                    RecipeIngredient("rice", 1.0, "cup"),
                    RecipeIngredient("onion", 1.0, "item"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="tofu-rice-stir-fry",
                title="Tofu Rice Stir-Fry",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=210,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free", "vegetarian"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("tofu", 1.0, "item"),
                    RecipeIngredient("rice", 1.0, "cup"),
                    RecipeIngredient("zucchini", 1.0, "cup"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="beef-potato-plate",
                title="Beef Potato Plate",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=225,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("ground beef", 1.0, "lb"),
                    RecipeIngredient("potato", 2.0, "item"),
                    RecipeIngredient("green onion", 0.5, "cup"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="lentil-tomato-stew",
                title="Lentil Tomato Stew",
                cuisine="mediterranean",
                base_servings=2,
                estimated_calories_per_serving=205,
                prep_time_minutes=25,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free", "vegan"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("lentils", 1.0, "cup"),
                    RecipeIngredient("tomato", 2.0, "item"),
                    RecipeIngredient("carrot", 1.0, "cup"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="chicken-pasta-plate",
                title="Chicken Pasta Plate",
                cuisine="italian",
                base_servings=2,
                estimated_calories_per_serving=230,
                prep_time_minutes=25,
                meal_types=("dinner",),
                diet_tags=frozenset(),
                allergens=frozenset({"gluten"}),
                ingredients=(
                    RecipeIngredient("chicken breast", 1.0, "lb"),
                    RecipeIngredient("pasta", 8.0, "oz"),
                    RecipeIngredient("tomato", 1.0, "item"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="bean-taco-bowl",
                title="Bean Taco Bowl",
                cuisine="mexican",
                base_servings=2,
                estimated_calories_per_serving=210,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegetarian"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("black beans", 1.0, "cup"),
                    RecipeIngredient("flour tortillas", 2.0, "item"),
                    RecipeIngredient("tomato", 1.0, "item"),
                ),
                steps=("Cook it.",),
            ),
            Recipe(
                recipe_id="turkey-potato-hash",
                title="Turkey Potato Hash",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=220,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("ground turkey", 1.0, "lb"),
                    RecipeIngredient("potato", 2.0, "item"),
                    RecipeIngredient("bell pepper", 1.0, "cup"),
                ),
                steps=("Cook it.",),
            ),
        )
        sides = (
            Recipe(
                recipe_id="broccoli-side",
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
                recipe_id="tomato-side",
                title="Tomato Salad",
                cuisine="mediterranean",
                base_servings=2,
                estimated_calories_per_serving=65,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("tomato", 2.0, "item"),),
                steps=("Toss it.",),
            ),
            Recipe(
                recipe_id="green-bean-side",
                title="Green Bean Salad",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=60,
                prep_time_minutes=10,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("green onion", 1.0, "cup"),),
                steps=("Toss it.",),
            ),
            Recipe(
                recipe_id="rice-side",
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
        return mains + sides


class WeeklyBalancePhaseTests(unittest.TestCase):
    def setUp(self) -> None:
        WeeklyMealPlanner.reset_request_cycle_offsets()
        catalog = {
            "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 2.8),
            "ground turkey": GroceryProduct("ground turkey", 1.0, "lb", 2.8),
            "ground beef": GroceryProduct("ground beef", 1.0, "lb", 2.8),
            "tofu": GroceryProduct("tofu", 1.0, "item", 2.8),
            "lentils": GroceryProduct("lentils", 1.0, "cup", 2.9),
            "black beans": GroceryProduct("black beans", 1.0, "cup", 2.9),
            "rice": GroceryProduct("rice", 1.0, "cup", 0.6),
            "potato": GroceryProduct("potato", 2.0, "item", 0.8),
            "pasta": GroceryProduct("pasta", 8.0, "oz", 0.9),
            "flour tortillas": GroceryProduct("flour tortillas", 2.0, "item", 0.9),
            "broccoli": GroceryProduct("broccoli", 2.0, "cup", 0.9),
            "bell pepper": GroceryProduct("bell pepper", 1.0, "cup", 0.8),
            "onion": GroceryProduct("onion", 1.0, "item", 0.6),
            "zucchini": GroceryProduct("zucchini", 1.0, "cup", 0.8),
            "green onion": GroceryProduct("green onion", 1.0, "cup", 0.8),
            "tomato": GroceryProduct("tomato", 2.0, "item", 0.9),
            "carrot": GroceryProduct("carrot", 1.0, "cup", 0.7),
        }
        self.grocery_provider = FixedPriceGroceryProvider(catalog)
        self.request = PlannerRequest(
            weekly_budget=90.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=420,
            daily_calorie_target_max=620,
        )

    def _planner(self) -> WeeklyMealPlanner:
        return WeeklyMealPlanner(
            recipe_provider=WeeklyVarietyRecipeProvider(),
            grocery_provider=self.grocery_provider,
            week_balance_enabled=True,
        )

    def _recipes(self) -> dict[str, Recipe]:
        return {recipe.title: recipe for recipe in WeeklyVarietyRecipeProvider().list_recipes()}

    def test_reduced_week_level_repetition(self) -> None:
        planner = self._planner()
        recipes = self._recipes()
        history = [
            PlannedMeal(day=1, slot=1, recipe=recipes["Chicken Rice Bowl"], scaled_servings=2, incremental_cost=3.4, meal_role="main"),
            PlannedMeal(day=2, slot=1, recipe=recipes["Turkey Rice Bowl"], scaled_servings=2, incremental_cost=3.4, meal_role="main"),
            PlannedMeal(day=3, slot=1, recipe=recipes["Beef Rice Skillet"], scaled_servings=2, incremental_cost=3.4, meal_role="main"),
        ]

        repeated_score = planner._weekly_variety_score(
            recipe=recipes["Chicken Rice Bowl"],
            candidate_role="main",
            anchor_recipe=None,
            meals=history,
            variety_profile=planner._variety_profile(self.request),
        )
        varied_score = planner._weekly_variety_score(
            recipe=recipes["Beef Potato Plate"],
            candidate_role="main",
            anchor_recipe=None,
            meals=history,
            variety_profile=planner._variety_profile(self.request),
        )

        self.assertGreater(varied_score.total, repeated_score.total)
        self.assertIn("weekly:repeated-starch", repeated_score.reasons)
        self.assertIn("weekly:repeated-anchor-pattern", repeated_score.reasons)

    def test_improved_variety_across_the_week(self) -> None:
        planner = self._planner()
        recipes = self._recipes()
        history = [
            PlannedMeal(day=1, slot=1, recipe=recipes["Chicken Rice Bowl"], scaled_servings=2, incremental_cost=3.4, meal_role="main"),
            PlannedMeal(day=2, slot=1, recipe=recipes["Beef Potato Plate"], scaled_servings=2, incremental_cost=3.6, meal_role="main"),
            PlannedMeal(day=3, slot=1, recipe=recipes["Chicken Pasta Plate"], scaled_servings=2, incremental_cost=3.7, meal_role="main"),
        ]

        repeated_candidate = planner._weekly_variety_score(
            recipe=recipes["Turkey Rice Bowl"],
            candidate_role="main",
            anchor_recipe=None,
            meals=history,
            variety_profile=planner._variety_profile(self.request),
        )
        varied_candidate = planner._weekly_variety_score(
            recipe=recipes["Lentil Tomato Stew"],
            candidate_role="main",
            anchor_recipe=None,
            meals=history,
            variety_profile=planner._variety_profile(self.request),
        )

        self.assertGreater(varied_candidate.total, repeated_candidate.total)
        self.assertIn("weekly:protein-variety", varied_candidate.reasons)
        self.assertIn("weekly:produce-variety", varied_candidate.reasons)

    def test_better_side_diversity(self) -> None:
        planner = self._planner()
        recipes = self._recipes()
        history = [
            PlannedMeal(day=1, slot=1, recipe=recipes["Chicken Rice Bowl"], scaled_servings=2, incremental_cost=3.4, meal_role="main"),
            PlannedMeal(day=1, slot=1, recipe=recipes["Broccoli Salad"], scaled_servings=2, incremental_cost=0.9, meal_role="side"),
            PlannedMeal(day=2, slot=1, recipe=recipes["Turkey Rice Bowl"], scaled_servings=2, incremental_cost=3.4, meal_role="main"),
            PlannedMeal(day=2, slot=1, recipe=recipes["Broccoli Salad"], scaled_servings=2, incremental_cost=0.9, meal_role="side"),
        ]

        repeated_side = planner._weekly_variety_score(
            recipe=recipes["Broccoli Salad"],
            candidate_role="side",
            anchor_recipe=recipes["Beef Potato Plate"],
            meals=history,
            variety_profile=planner._variety_profile(self.request),
        )
        varied_side = planner._weekly_variety_score(
            recipe=recipes["Tomato Salad"],
            candidate_role="side",
            anchor_recipe=recipes["Beef Potato Plate"],
            meals=history,
            variety_profile=planner._variety_profile(self.request),
        )

        self.assertGreater(varied_side.total, repeated_side.total)
        self.assertIn("weekly:repeated-side-structure", repeated_side.reasons)
        self.assertIn("weekly:side-produce-variety", varied_side.reasons)


if __name__ == "__main__":
    unittest.main()
