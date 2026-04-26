import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pantry_pilot.data_pipeline.importer import ImportConfig, import_recipenlg_dataset


class Phase13RecipeNLGImportTests(unittest.TestCase):
    def test_recipenlg_row_uses_ner_for_catalog_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "RecipeNLG_dataset.csv"
            raw_path.write_text(
                "\n".join(
                    [
                        ",title,ingredients,directions,link,source,NER",
                        '0,Blueberry Muffins,"[""2 c. all-purpose flour"", ""1 c. white sugar"", ""2 eggs"", ""1 c. milk"", ""1 c. fresh blueberries""]","[""Mix ingredients."", ""Bake for 20 minutes. Yields 6 servings.""]",https://example.com,Test,"[""flour"", ""sugar"", ""eggs"", ""milk"", ""blueberries""]"',
                    ]
                ),
                encoding="utf-8",
            )

            result = import_recipenlg_dataset(raw_path, config=ImportConfig(max_output_recipes=10))

            self.assertEqual(result.stats["accepted_count"], 1)
            recipe = result.imported_recipes[0]
            self.assertEqual(recipe.meal_types, ("breakfast",))
            self.assertEqual(recipe.servings, 6)
            self.assertEqual(recipe.ingredients[-1].canonical_name, "blueberries")

    def test_recipenlg_dessert_rows_stay_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "RecipeNLG_dataset.csv"
            raw_path.write_text(
                "\n".join(
                    [
                        ",title,ingredients,directions,link,source,NER",
                        '0,Chocolate Cake,"[""2 c. flour"", ""1 c. sugar"", ""1 c. milk""]","[""Mix and bake.""]",https://example.com,Test,"[""flour"", ""sugar"", ""milk""]"',
                    ]
                ),
                encoding="utf-8",
            )

            result = import_recipenlg_dataset(raw_path, config=ImportConfig(max_output_recipes=10))

            self.assertEqual(result.imported_recipes, ())
            self.assertTrue(any("Meal type could not be mapped" in item["reason"] for item in result.stats["common_reject_reasons"]))

    def test_recipenlg_row_limit_and_checkpoint_support_sample_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "RecipeNLG_dataset.csv"
            output_path = Path(tmpdir) / "recipenlg.sample.json"
            raw_path.write_text(
                "\n".join(
                    [
                        ",title,ingredients,directions,link,source,NER",
                        '0,Blueberry Muffins,"[""2 c. all-purpose flour"", ""1 c. white sugar"", ""2 eggs"", ""1 c. milk"", ""1 c. fresh blueberries""]","[""Mix ingredients."", ""Bake for 20 minutes. Yields 6 servings.""]",https://example.com/1,Test,"[""flour"", ""sugar"", ""eggs"", ""milk"", ""blueberries""]"',
                        '1,Chicken Dinner,"[""2 chicken breasts"", ""1 c. rice"", ""1 c. chicken broth""]","[""Cook and serve.""]",https://example.com/2,Test,"[""chicken breasts"", ""rice"", ""chicken broth""]"',
                    ]
                ),
                encoding="utf-8",
            )

            result = import_recipenlg_dataset(
                raw_path,
                processed_path=output_path,
                config=ImportConfig(
                    row_limit=1,
                    max_output_recipes=10,
                    progress_every_rows=1,
                    checkpoint_every_rows=1,
                ),
            )

            checkpoint_path = output_path.with_suffix(".checkpoint.json")
            checkpoint_payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))

            self.assertEqual(result.stats["raw_count"], 1)
            self.assertEqual(result.stats["accepted_count"], 1)
            self.assertEqual(len(result.imported_recipes), 1)
            self.assertEqual(checkpoint_payload["status"], "completed")
            self.assertEqual(checkpoint_payload["row_limit"], 1)

    def test_recipenlg_active_lock_prevents_silent_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "RecipeNLG_dataset.csv"
            output_path = Path(tmpdir) / "recipenlg.sample.json"
            output_path.write_text('{"recipes":["trusted"]}', encoding="utf-8")
            raw_path.write_text(
                "\n".join(
                    [
                        ",title,ingredients,directions,link,source,NER",
                        '0,Blueberry Muffins,"[""2 c. all-purpose flour"", ""1 c. white sugar"", ""2 eggs"", ""1 c. milk"", ""1 c. fresh blueberries""]","[""Mix ingredients."", ""Bake for 20 minutes. Yields 6 servings.""]",https://example.com/1,Test,"[""flour"", ""sugar"", ""eggs"", ""milk"", ""blueberries""]"',
                    ]
                ),
                encoding="utf-8",
            )
            lock_path = output_path.with_suffix(".lock.json")
            lock_path.write_text(
                json.dumps({"pid": os.getpid(), "run_id": "active-test", "output_path": str(output_path)}),
                encoding="utf-8",
            )

            with self.assertRaises(RuntimeError):
                import_recipenlg_dataset(raw_path, processed_path=output_path, config=ImportConfig(row_limit=1))

            self.assertEqual(output_path.read_text(encoding="utf-8"), '{"recipes":["trusted"]}')

    def test_recipenlg_stale_lock_recovers_cleanly_on_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "RecipeNLG_dataset.csv"
            output_path = Path(tmpdir) / "recipenlg.sample.json"
            raw_path.write_text(
                "\n".join(
                    [
                        ",title,ingredients,directions,link,source,NER",
                        '0,Blueberry Muffins,"[""2 c. all-purpose flour"", ""1 c. white sugar"", ""2 eggs"", ""1 c. milk"", ""1 c. fresh blueberries""]","[""Mix ingredients."", ""Bake for 20 minutes. Yields 6 servings.""]",https://example.com/1,Test,"[""flour"", ""sugar"", ""eggs"", ""milk"", ""blueberries""]"',
                    ]
                ),
                encoding="utf-8",
            )
            lock_path = output_path.with_suffix(".lock.json")
            lock_path.write_text(
                json.dumps({"pid": 424242, "run_id": "stale-test", "output_path": str(output_path)}),
                encoding="utf-8",
            )

            with (
                patch("pantry_pilot.data_pipeline.importer.os.name", "nt"),
                patch("pantry_pilot.data_pipeline.importer._is_pid_running_windows", return_value=False),
            ):
                result = import_recipenlg_dataset(
                    raw_path,
                    processed_path=output_path,
                    config=ImportConfig(row_limit=1, max_output_recipes=10),
                )

            self.assertEqual(result.stats["status"], "completed")
            self.assertFalse(lock_path.exists())
            stale_locks = list(output_path.parent.glob("recipenlg.sample.lock.stale-*.json"))
            self.assertEqual(len(stale_locks), 1)
            self.assertTrue(Path(result.output_path).exists())

    def test_recipenlg_checkpoint_marks_similarity_stage_before_annotation_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            raw_path = Path(tmpdir) / "RecipeNLG_dataset.csv"
            output_path = Path(tmpdir) / "recipenlg.sample.json"
            raw_path.write_text(
                "\n".join(
                    [
                        ",title,ingredients,directions,link,source,NER",
                        '0,Blueberry Muffins,"[""2 c. all-purpose flour"", ""1 c. white sugar"", ""2 eggs"", ""1 c. milk"", ""1 c. fresh blueberries""]","[""Mix ingredients."", ""Bake for 20 minutes. Yields 6 servings.""]",https://example.com/1,Test,"[""flour"", ""sugar"", ""eggs"", ""milk"", ""blueberries""]"',
                    ]
                ),
                encoding="utf-8",
            )

            def fake_similarity(recipes, **kwargs):
                checkpoint_payload = json.loads(output_path.with_suffix(".checkpoint.json").read_text(encoding="utf-8"))
                self.assertEqual(checkpoint_payload["stage"], "annotating_similarity")
                self.assertEqual(checkpoint_payload["status"], "running")
                return recipes

            with patch("pantry_pilot.data_pipeline.importer.annotate_recipe_similarity", side_effect=fake_similarity):
                result = import_recipenlg_dataset(
                    raw_path,
                    processed_path=output_path,
                    config=ImportConfig(max_output_recipes=10, checkpoint_every_rows=1, progress_every_rows=1),
                )

            self.assertEqual(result.stats["status"], "completed")
            checkpoint_payload = json.loads(output_path.with_suffix(".checkpoint.json").read_text(encoding="utf-8"))
            self.assertEqual(checkpoint_payload["status"], "completed")


if __name__ == "__main__":
    unittest.main()
