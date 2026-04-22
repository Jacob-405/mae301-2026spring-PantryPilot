import unittest

from pantry_pilot.models import Recipe, RecipeIngredient
from pantry_pilot.nutrition import (
    guidance_mapping_keys,
    lookup_ingredient_guidance,
    lookup_ingredient_nutrition,
    pilot_nutrition_mapping_keys,
    pilot_nutrition_record_keys,
)
from pantry_pilot.planner import WeeklyMealPlanner
from pantry_pilot.recipe_estimation import estimate_recipe_nutrition


class PhaseEUsdaExpansionAndGuidanceTests(unittest.TestCase):
    def test_expanded_usda_mappings_resolve_deterministically(self) -> None:
        self.assertGreaterEqual(len(pilot_nutrition_mapping_keys()), 24)
        self.assertGreaterEqual(len(pilot_nutrition_record_keys()), 24)
        self.assertGreaterEqual(len(guidance_mapping_keys()), 30)

        for ingredient_name in (
            "bacon",
            "baking powder",
            "baking soda",
            "cocoa",
            "cream of chicken soup",
            "evaporated milk",
            "green onion",
            "heavy cream",
            "mustard",
            "nutmeg",
            "thyme",
        ):
            first = lookup_ingredient_nutrition(ingredient_name)
            second = lookup_ingredient_nutrition(ingredient_name)
            self.assertIsNotNone(first)
            self.assertEqual(first, second)
            if first is None:
                self.fail(f"Expected expanded USDA pilot nutrition for {ingredient_name}.")
            self.assertEqual(first.source, "usda-fdc-pilot")
            self.assertTrue(first.pilot)

    def test_unknowns_remain_unknown_when_mapping_is_weak(self) -> None:
        self.assertIsNone(lookup_ingredient_nutrition("garam masala"))
        self.assertIsNone(lookup_ingredient_guidance("garam masala"))

        nutrition = estimate_recipe_nutrition(
            (
                RecipeIngredient("garam masala", 1.0, "tbsp"),
                RecipeIngredient("chicken breast", 1.0, "lb"),
            ),
            servings=2,
        )

        self.assertIsNone(nutrition.per_serving)
        self.assertEqual(nutrition.missing_ingredients, ("garam masala",))

    def test_recipe_level_nutrition_improves_for_phase_e_examples(self) -> None:
        examples = (
            (
                "Savory Chicken Bake",
                (
                    RecipeIngredient("chicken breast", 1.0, "lb"),
                    RecipeIngredient("cream of chicken soup", 1.0, "can"),
                    RecipeIngredient("heavy cream", 2.0, "tbsp"),
                ),
                4,
                (274, 28.6, 5.0, 10.7),
            ),
            (
                "Bacon Potato Hash",
                (
                    RecipeIngredient("bacon", 4.0, "slice"),
                    RecipeIngredient("potato", 2.0, "item"),
                    RecipeIngredient("green onion", 0.5, "cup"),
                ),
                2,
                (256, 10.8, 39.0, 6.8),
            ),
            (
                "Cocoa Spice Muffins",
                (
                    RecipeIngredient("cocoa", 4.0, "tbsp"),
                    RecipeIngredient("nutmeg", 1.0, "tsp"),
                    RecipeIngredient("baking powder", 2.0, "tsp"),
                    RecipeIngredient("baking soda", 1.0, "tsp"),
                    RecipeIngredient("flour", 2.0, "cup"),
                    RecipeIngredient("milk", 1.0, "cup"),
                ),
                8,
                (140, 4.7, 27.1, 1.7),
            ),
        )

        for title, ingredients, servings, expected in examples:
            with self.subTest(title=title):
                before = estimate_recipe_nutrition(
                    ingredients,
                    servings,
                    use_usda_pilot=False,
                )
                after = estimate_recipe_nutrition(
                    ingredients,
                    servings,
                    use_usda_pilot=True,
                )

                self.assertIsNone(before.per_serving)
                self.assertIsNotNone(after.per_serving)
                if after.per_serving is None:
                    self.fail(f"Expected expanded nutrition estimate for {title}.")
                self.assertEqual(
                    (
                        after.per_serving.calories,
                        after.per_serving.protein_grams,
                        after.per_serving.carbs_grams,
                        after.per_serving.fat_grams,
                    ),
                    expected,
                )

    def test_balance_scoring_uses_guidance_signals(self) -> None:
        recipe = Recipe(
            recipe_id="guidance-main",
            title="Bacon Potato Skillet",
            cuisine="american",
            base_servings=2,
            estimated_calories_per_serving=300,
            prep_time_minutes=20,
            meal_types=("dinner",),
            diet_tags=frozenset(),
            allergens=frozenset(),
            ingredients=(
                RecipeIngredient("bacon", 4.0, "slice"),
                RecipeIngredient("potato", 2.0, "item"),
            ),
            steps=("Cook it.",),
        )

        without_guidance = WeeklyMealPlanner(balance_scoring_enabled=True, meal_guidance_enabled=False)
        with_guidance = WeeklyMealPlanner(balance_scoring_enabled=True, meal_guidance_enabled=True)

        unguided_score = without_guidance._meal_balance_score(recipe, "dinner", "main", None)
        guided_score = with_guidance._meal_balance_score(recipe, "dinner", "main", None)

        self.assertGreater(guided_score.total, unguided_score.total)
        self.assertIn("guidance:protein_foods", guided_score.reasons)
        self.assertIn("guidance:vegetables", guided_score.reasons)
        self.assertIn("guidance:grains_starches", guided_score.reasons)
        self.assertIn("protein", guided_score.components)
        self.assertIn("carb", guided_score.components)


if __name__ == "__main__":
    unittest.main()
