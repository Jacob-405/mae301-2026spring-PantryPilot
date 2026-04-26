import unittest

from pantry_pilot.ingredient_catalog import lookup_ingredient_metadata
from pantry_pilot.normalization import convert_unit_quantity, normalize_ingredient_name, normalize_unit
from pantry_pilot.sample_data import _derive_allergens


class Phase9IngredientCatalogTests(unittest.TestCase):
    def test_alias_normalization_uses_canonical_catalog_names(self) -> None:
        self.assertEqual(normalize_ingredient_name("yellow onion"), "onion")
        self.assertEqual(normalize_ingredient_name("garlic cloves"), "garlic")
        self.assertEqual(normalize_ingredient_name("black beans canned"), "black beans")

    def test_unit_normalization_preserves_supported_existing_aliases(self) -> None:
        self.assertEqual(normalize_unit("tablespoons"), "tbsp")
        self.assertEqual(normalize_unit("ounces"), "oz")
        self.assertEqual(normalize_unit("items"), "item")

    def test_explicit_unit_conversions_remain_conservative(self) -> None:
        self.assertEqual(convert_unit_quantity(2.0, "tbsp", "tsp"), 6.0)
        self.assertIsNone(convert_unit_quantity(1.0, "item", "cup"))

    def test_ingredient_metadata_lookup_returns_allergen_and_diet_flags(self) -> None:
        yogurt = lookup_ingredient_metadata("yogurt")
        tofu = lookup_ingredient_metadata("tofu")

        self.assertIsNotNone(yogurt)
        self.assertEqual(yogurt.allergens, frozenset({"dairy"}))
        self.assertTrue(yogurt.diet_flags.animal_product)
        self.assertFalse(yogurt.diet_flags.meat)

        self.assertIsNotNone(tofu)
        self.assertEqual(tofu.allergens, frozenset({"soy"}))
        self.assertFalse(tofu.diet_flags.animal_product)

    def test_unknown_ingredient_metadata_keeps_allergen_status_unsafe(self) -> None:
        self.assertIsNone(lookup_ingredient_metadata("mystery powder"))
        self.assertIsNone(_derive_allergens(("rice", "mystery powder")))


if __name__ == "__main__":
    unittest.main()
