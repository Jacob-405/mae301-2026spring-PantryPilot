import unittest

from pantry_pilot.models import RecipeIngredient
from pantry_pilot.nutrition import (
    lookup_ingredient_nutrition,
    pilot_nutrition_mapping_keys,
    pilot_nutrition_record_keys,
)
from pantry_pilot.recipe_estimation import estimate_recipe_nutrition


class UsdaNutritionPilotPhaseTests(unittest.TestCase):
    def test_pilot_mapped_ingredients_resolve_deterministically(self) -> None:
        self.assertGreaterEqual(len(pilot_nutrition_mapping_keys()), 9)
        self.assertGreaterEqual(len(pilot_nutrition_record_keys()), 9)

        for ingredient_name in (
            "broccoli",
            "cheddar cheese",
            "cilantro",
            "cream cheese",
            "cream of mushroom soup",
            "granola",
            "olive oil",
            "sour cream",
            "soy sauce",
        ):
            first = lookup_ingredient_nutrition(ingredient_name)
            second = lookup_ingredient_nutrition(ingredient_name)
            self.assertIsNotNone(first)
            self.assertEqual(first, second)
            if first is None:
                self.fail(f"Expected USDA pilot nutrition for {ingredient_name}.")
            self.assertEqual(first.source, "usda-fdc-pilot")
            self.assertTrue(first.pilot)
            self.assertIsNotNone(first.source_food_id)
            self.assertTrue(first.source_dataset)

    def test_unsupported_ingredients_stay_unknown(self) -> None:
        self.assertIsNone(lookup_ingredient_nutrition("garam masala"))

        nutrition = estimate_recipe_nutrition(
            (RecipeIngredient("garam masala", 1.0, "tbsp"),),
            servings=1,
        )

        self.assertIsNone(nutrition.per_serving)
        self.assertEqual(nutrition.missing_ingredients, ("garam masala",))

    def test_recipe_level_nutrition_improves_for_pilot_covered_real_examples(self) -> None:
        examples = (
            (
                "Guacamole Dip",
                (
                    RecipeIngredient("avocado", 1.0, "item"),
                    RecipeIngredient("sour cream", 0.5, "cup"),
                    RecipeIngredient("tomato", 1.0, "item"),
                    RecipeIngredient("lemon juice", 1.0, "tbsp"),
                ),
                2,
                (251, 4.0, 12.8, 21.9),
            ),
            (
                "Hot Onion Dip",
                (
                    RecipeIngredient("cream cheese", 1.0, "cup"),
                    RecipeIngredient("onion", 1.0, "item"),
                    RecipeIngredient("parmesan", 2.0, "tbsp"),
                    RecipeIngredient("mayonnaise", 2.0, "tbsp"),
                ),
                4,
                (275, 4.8, 5.5, 26.0),
            ),
            (
                "\"Great\" Meat Loaf",
                (
                    RecipeIngredient("ground beef", 1.0, "lb"),
                    RecipeIngredient("cream of mushroom soup", 1.0, "can"),
                    RecipeIngredient("bread crumbs", 1.0, "cup"),
                    RecipeIngredient("onion", 1.0, "item"),
                    RecipeIngredient("eggs", 2.0, "item"),
                ),
                6,
                (336, 18.2, 18.4, 20.6),
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
                    self.fail(f"Expected pilot nutrition estimate for {title}.")
                self.assertEqual(
                    (
                        after.per_serving.calories,
                        after.per_serving.protein_grams,
                        after.per_serving.carbs_grams,
                        after.per_serving.fat_grams,
                    ),
                    expected,
                )


if __name__ == "__main__":
    unittest.main()
