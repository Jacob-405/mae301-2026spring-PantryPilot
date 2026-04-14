import json
import tempfile
import unittest
from pathlib import Path

from pantry_pilot.data_pipeline.importer import ImportConfig, import_recipes_from_file


class Phase10ImportPipelineTests(unittest.TestCase):
    def test_json_import_normalizes_and_writes_processed_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "recipes.json"
            processed_path = Path(tmpdir) / "recipes.processed.json"
            raw_payload = {
                "recipes": [
                    {
                        "source_recipe_id": "demo-1",
                        "title": "Tomato Rice Bowl",
                        "cuisine": "Mediterranean",
                        "meal_types": "lunch,dinner",
                        "diet_tags": "vegetarian",
                        "servings": 4,
                        "prep_time_minutes": 10,
                        "cook_time_minutes": 20,
                        "total_time_minutes": 30,
                        "calories_per_serving": 410,
                        "allergen_completeness": "complete",
                        "allergens": [],
                        "ingredients": [
                            {"name": "tomatoes", "quantity": 2, "unit": "items"},
                            {"name": "rice", "quantity": 2, "unit": "cups"},
                        ],
                        "instructions": ["Cook rice.", "Top with tomato."],
                    }
                ]
            }
            raw_path.write_text(json.dumps(raw_payload), encoding="utf-8")

            result = import_recipes_from_file(raw_path, processed_path=processed_path)

            self.assertEqual(len(result.imported_recipes), 1)
            self.assertEqual(result.rejected_rows, ())
            recipe = result.imported_recipes[0]
            self.assertEqual(recipe.ingredients[0].canonical_name, "tomato")
            self.assertEqual(recipe.ingredients[0].unit, "item")
            self.assertEqual(recipe.calories.calories_per_serving, 410)
            self.assertTrue(processed_path.exists())
            self.assertTrue(Path(result.stats_path).exists())
            self.assertEqual(result.stats["raw_count"], 1)
            self.assertEqual(result.stats["accepted_count"], 1)
            self.assertEqual(result.stats["rejected_count"], 0)

            written = json.loads(processed_path.read_text(encoding="utf-8"))
            self.assertEqual(written["recipes"][0]["title"], "Tomato Rice Bowl")
            self.assertIn("similarity", written["recipes"][0])
            self.assertIn("diversity", written["recipes"][0])

    def test_import_assigns_duplicate_cluster_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "recipes.json"
            processed_path = Path(tmpdir) / "recipes.processed.json"
            raw_payload = {
                "recipes": [
                    {
                        "source_recipe_id": "demo-1",
                        "title": "Tomato Rice Bowl",
                        "cuisine": "Mediterranean",
                        "meal_types": "lunch,dinner",
                        "servings": 4,
                        "allergen_completeness": "complete",
                        "allergens": [],
                        "ingredients": [
                            {"name": "tomatoes", "quantity": 2, "unit": "items"},
                            {"name": "rice", "quantity": 2, "unit": "cups"},
                        ],
                        "instructions": ["Cook rice.", "Top with tomato."],
                    },
                    {
                        "source_recipe_id": "demo-2",
                        "title": "Tomato Rice Bowl",
                        "cuisine": "Mediterranean",
                        "meal_types": "lunch,dinner",
                        "servings": 4,
                        "allergen_completeness": "complete",
                        "allergens": [],
                        "ingredients": [
                            {"name": "tomatoes", "quantity": 2, "unit": "items"},
                            {"name": "rice", "quantity": 2, "unit": "cups"},
                        ],
                        "instructions": ["Cook rice.", "Top with tomato."],
                    },
                ]
            }
            raw_path.write_text(json.dumps(raw_payload), encoding="utf-8")

            result = import_recipes_from_file(raw_path, processed_path=processed_path)

            self.assertEqual(len(result.imported_recipes), 2)
            cluster_ids = {recipe.similarity.cluster_id for recipe in result.imported_recipes}
            self.assertEqual(len(cluster_ids), 1)
            duplicate_recipe = next(recipe for recipe in result.imported_recipes if recipe.similarity.exact_duplicate_of)
            self.assertTrue(duplicate_recipe.similarity.exact_duplicate_of)

    def test_csv_import_supports_json_encoded_nested_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "recipes.csv"
            processed_path = Path(tmpdir) / "recipes.processed.json"
            ingredients = json.dumps(
                [
                    {"name": "black beans canned", "quantity": 2, "unit": "cans"},
                    {"name": "rice", "quantity": 2, "unit": "cups"},
                ]
            )
            instructions = json.dumps(["Cook rice.", "Warm beans.", "Serve together."])
            raw_path.write_text(
                "\n".join(
                    [
                        "source_recipe_id,title,cuisine,meal_types,servings,allergen_completeness,allergens,ingredients,instructions",
                        f'demo-2,"Bean Bowl",mexican,"lunch,dinner",4,complete,"[]","{ingredients.replace(chr(34), chr(34) * 2)}","{instructions.replace(chr(34), chr(34) * 2)}"',
                    ]
                ),
                encoding="utf-8",
            )

            result = import_recipes_from_file(raw_path, processed_path=processed_path)

            self.assertEqual(len(result.imported_recipes), 1)
            recipe = result.imported_recipes[0]
            self.assertEqual(recipe.ingredients[0].canonical_name, "black beans")
            self.assertEqual(recipe.steps[-1], "Serve together.")

    def test_import_rejects_missing_ingredients_or_instructions(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "recipes.json"
            raw_path.write_text(
                json.dumps(
                    {
                        "recipes": [
                            {
                                "source_recipe_id": "bad-1",
                                "title": "No Steps",
                                "servings": 2,
                                "allergen_completeness": "complete",
                                "allergens": [],
                                "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup"}],
                                "instructions": [],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = import_recipes_from_file(raw_path)

            self.assertEqual(result.imported_recipes, ())
            self.assertEqual(len(result.rejected_rows), 1)
            self.assertIn("Missing instructions.", result.rejected_rows[0].reasons)
            self.assertEqual(result.stats["rejected_count"], 1)
            self.assertTrue(any(item["reason"] == "Missing instructions." for item in result.stats["common_reject_reasons"]))

    def test_import_rejects_too_many_unmapped_ingredients(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "recipes.json"
            raw_path.write_text(
                json.dumps(
                    {
                        "recipes": [
                            {
                                "source_recipe_id": "bad-2",
                                "title": "Mystery Stew",
                                "servings": 2,
                                "allergen_completeness": "complete",
                                "allergens": [],
                                "ingredients": [
                                    {"name": "mystery root", "quantity": 1, "unit": "item"},
                                    {"name": "dragon dust", "quantity": 2, "unit": "tbsp"},
                                    {"name": "rice", "quantity": 1, "unit": "cup"},
                                ],
                                "instructions": ["Cook everything."],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = import_recipes_from_file(raw_path, config=ImportConfig(max_unmapped_ingredient_fraction=0.25))

            self.assertEqual(result.imported_recipes, ())
            self.assertTrue(any("mapped" in reason for reason in result.rejected_rows[0].reasons))

    def test_import_rejects_unsafe_allergen_completeness(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "recipes.json"
            raw_path.write_text(
                json.dumps(
                    {
                        "recipes": [
                            {
                                "source_recipe_id": "bad-3",
                                "title": "Unknown Allergens",
                                "servings": 2,
                                "allergen_completeness": "unknown",
                                "ingredients": [{"name": "rice", "quantity": 1, "unit": "cup"}],
                                "instructions": ["Cook rice."],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = import_recipes_from_file(raw_path)

            self.assertEqual(result.imported_recipes, ())
            self.assertIn("Allergen completeness is missing or unsafe.", result.rejected_rows[0].reasons)

    def test_import_rejects_unusable_units_for_mapped_ingredient(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "recipes.json"
            raw_path.write_text(
                json.dumps(
                    {
                        "recipes": [
                            {
                                "source_recipe_id": "bad-4",
                                "title": "Tomato Soup",
                                "servings": 2,
                                "allergen_completeness": "complete",
                                "allergens": [],
                                "ingredients": [{"name": "tomatoes", "quantity": 2, "unit": "cups"}],
                                "instructions": ["Cook tomatoes."],
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            result = import_recipes_from_file(raw_path)

            self.assertEqual(result.imported_recipes, ())
            self.assertTrue(any("unusable" in reason for reason in result.rejected_rows[0].reasons))


if __name__ == "__main__":
    unittest.main()
