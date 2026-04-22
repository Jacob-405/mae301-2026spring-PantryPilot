import unittest

from pantry_pilot.models import RecipeIngredient
from pantry_pilot.nutrition import (
    lookup_ingredient_nutrition,
    runtime_nutrition_mapping_keys,
    runtime_nutrition_record_keys,
)
from pantry_pilot.providers import LocalRecipeProvider
from pantry_pilot.recipe_estimation import estimate_recipe_nutrition
from pantry_pilot.usda_build import CompactFoodRecord, ranked_candidates_for_ingredient, resolve_ingredient_mapping


class PhaseKFullUsdaBuildTests(unittest.TestCase):
    def test_runtime_mappings_resolve_deterministically(self) -> None:
        self.assertGreaterEqual(len(runtime_nutrition_mapping_keys()), 80)
        self.assertGreaterEqual(len(runtime_nutrition_record_keys()), 80)

        for ingredient_name in (
            "flour",
            "eggs",
            "onion",
            "potato",
            "rice",
            "sour cream",
            "tomato",
            "vegetable oil",
        ):
            first = lookup_ingredient_nutrition(ingredient_name)
            second = lookup_ingredient_nutrition(ingredient_name)
            self.assertIsNotNone(first)
            self.assertEqual(first, second)
            if first is None:
                self.fail(f"Expected USDA runtime nutrition for {ingredient_name}.")
            self.assertEqual(first.source, "usda-fdc")
            self.assertFalse(first.pilot)

    def test_ambiguous_mapping_stays_unresolved(self) -> None:
        foods = (
            CompactFoodRecord(
                dataset="foundation",
                release="2025-12-18",
                food_id=1,
                description="Flour, almond",
                normalized_description="flour, almond",
                calories_per_100g=500.0,
                protein_per_100g=20.0,
                carbs_per_100g=10.0,
                fat_per_100g=30.0,
                portion_grams={"oz": 28.3495},
            ),
            CompactFoodRecord(
                dataset="foundation",
                release="2025-12-18",
                food_id=2,
                description="Flour, barley",
                normalized_description="flour, barley",
                calories_per_100g=350.0,
                protein_per_100g=11.0,
                carbs_per_100g=70.0,
                fat_per_100g=2.0,
                portion_grams={"oz": 28.3495},
            ),
        )

        candidates = ranked_candidates_for_ingredient("mystery flour", foods)
        decision = resolve_ingredient_mapping("mystery flour", candidates)

        self.assertEqual(decision["mapping_status"], "ambiguous")
        self.assertTrue(decision["top_candidates"])

    def test_real_recipe_nutrition_changes_on_real_examples(self) -> None:
        recipes = LocalRecipeProvider().list_recipes()
        titles = {
            "French Toast Variation Of Eggs In A Basket",
            "Kagianas (Greek Eggs And Tomato)",
            "Toasted Pasta",
        }
        selected = [recipe for recipe in recipes if recipe.title in titles]
        self.assertEqual(len(selected), 3)

        changed = 0
        for recipe in selected:
            before = estimate_recipe_nutrition(
                recipe.ingredients,
                recipe.base_servings,
                use_usda_full=False,
                use_usda_pilot=True,
            )
            after = estimate_recipe_nutrition(
                recipe.ingredients,
                recipe.base_servings,
                use_usda_full=True,
                use_usda_pilot=True,
            )
            self.assertIsNotNone(after.per_serving)
            if after.per_serving is None:
                self.fail(f"Expected full USDA nutrition estimate for {recipe.title}.")
            self.assertIsNotNone(before.per_serving)
            if before.per_serving != after.per_serving:
                changed += 1

        self.assertGreaterEqual(changed, 2)

    def test_unresolved_unknowns_stay_unknown(self) -> None:
        self.assertIsNone(lookup_ingredient_nutrition("garam masala", include_usda_full=True, include_usda_pilot=False, include_heuristic=False))

        nutrition = estimate_recipe_nutrition(
            (RecipeIngredient("garam masala", 1.0, "tbsp"),),
            servings=1,
            use_usda_full=True,
            use_usda_pilot=False,
        )

        self.assertIsNone(nutrition.per_serving)
        self.assertEqual(nutrition.missing_ingredients, ("garam masala",))


if __name__ == "__main__":
    unittest.main()
