import json
import tempfile
import unittest
from pathlib import Path

from pantry_pilot.models import RecipeIngredient
from pantry_pilot.providers import LocalRecipeProvider
from pantry_pilot.recipe_estimation import estimate_recipe_nutrition


class NutritionPhase11Tests(unittest.TestCase):
    def test_supported_ingredients_produce_nutrition_estimates(self) -> None:
        nutrition = estimate_recipe_nutrition(
            (
                RecipeIngredient("rice", 2.0, "cup"),
                RecipeIngredient("black beans", 1.0, "can"),
            ),
            servings=2,
        )

        self.assertIsNotNone(nutrition.per_serving)
        if nutrition.per_serving is None:
            self.fail("Expected per-serving nutrition estimate for supported ingredients.")
        self.assertEqual(nutrition.per_serving.calories, 320)
        self.assertEqual(nutrition.per_serving.protein_grams, 11.9)
        self.assertEqual(nutrition.per_serving.carbs_grams, 65.4)
        self.assertEqual(nutrition.per_serving.fat_grams, 0.9)
        self.assertEqual(nutrition.missing_ingredients, ())

    def test_unsupported_ingredients_stay_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_path = Path(tmpdir) / "recipes.imported.json"
            processed_path.write_text(
                json.dumps(
                    {
                        "recipes": [
                            {
                                "recipe_id": "unknown-nutrition-bowl",
                                "title": "Unknown Nutrition Bowl",
                                "cuisine": "american",
                                "servings": 2,
                                "prep_time_minutes": 10,
                                "meal_types": ["dinner"],
                                "diet_tags": ["vegan"],
                                "allergens": {"allergens": [], "completeness": "complete"},
                                "ingredients": [
                                    {"canonical_name": "mystery ingredient", "quantity": 2, "unit": "cups"},
                                ],
                                "steps": ["Mix and serve."],
                                "calories": {"calories_per_serving": None},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            recipe = LocalRecipeProvider(processed_dataset_path=processed_path).list_recipes()[0]

            self.assertIsNone(recipe.estimated_calories_per_serving)
            self.assertIsNone(recipe.estimated_nutrition_per_serving)

    def test_real_recipe_example_gets_ingredient_level_nutrition(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            processed_path = Path(tmpdir) / "recipes.imported.json"
            processed_path.write_text(
                json.dumps(
                    {
                        "recipes": [
                            {
                                "recipe_id": "real-guacamole",
                                "title": "Authentic Mexican Guacamole",
                                "cuisine": "mexican",
                                "servings": 2,
                                "prep_time_minutes": 10,
                                "meal_types": ["dinner"],
                                "diet_tags": ["vegan", "gluten-free"],
                                "allergens": {"allergens": [], "completeness": "complete"},
                                "ingredients": [
                                    {"canonical_name": "avocado", "quantity": 2, "unit": "item"},
                                    {"canonical_name": "tomato", "quantity": 1, "unit": "item"},
                                    {"canonical_name": "onion", "quantity": 0.5, "unit": "item"},
                                    {"canonical_name": "lime", "quantity": 1, "unit": "item"},
                                ],
                                "steps": ["Mash and season."],
                                "calories": {"calories_per_serving": None},
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            recipe = LocalRecipeProvider(processed_dataset_path=processed_path).list_recipes()[0]

            self.assertEqual(recipe.estimated_calories_per_serving, 272)
            self.assertIsNotNone(recipe.estimated_nutrition_per_serving)
            if recipe.estimated_nutrition_per_serving is None:
                self.fail("Expected nutrition estimate for real RecipeNLG example.")
            self.assertEqual(recipe.estimated_nutrition_per_serving.protein_grams, 4.1)
            self.assertEqual(recipe.estimated_nutrition_per_serving.carbs_grams, 21.3)
            self.assertEqual(recipe.estimated_nutrition_per_serving.fat_grams, 22.2)


if __name__ == "__main__":
    unittest.main()
