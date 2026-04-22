import tempfile
import unittest
from pathlib import Path

from pantry_pilot.providers import DEFAULT_PROCESSED_RECIPES_PATH, resolve_recipe_runtime
from pantry_pilot.runtime_audit import (
    build_runtime_coverage_audit,
    build_runtime_data_contract,
    render_runtime_audit_text,
)


class PhaseFRuntimeContractTests(unittest.TestCase):
    def test_runtime_contract_reports_active_processed_dataset_and_local_support_files(self) -> None:
        contract = build_runtime_data_contract()

        self.assertEqual(
            Path(contract.active_recipe_corpus_path),
            DEFAULT_PROCESSED_RECIPES_PATH.resolve(),
        )
        self.assertEqual(contract.active_recipe_source, "processed-dataset")
        self.assertFalse(contract.recipe_fallback_active)
        self.assertTrue(contract.nutrition_manifest_exists)
        self.assertTrue(contract.nutrition_records_exists)
        self.assertTrue(contract.nutrition_mappings_exists)
        self.assertTrue(contract.guidance_exists)
        self.assertEqual(contract.default_pricing_source, "mock")
        self.assertGreater(contract.mock_price_catalog_count, 50)
        self.assertTrue(contract.runtime_local_only_for_nutrition)
        self.assertTrue(contract.runtime_local_only_for_guidance)

    def test_runtime_audit_reports_current_coverage_without_recipe_fallback(self) -> None:
        audit = build_runtime_coverage_audit()

        self.assertGreaterEqual(audit.total_recipes, 20000)
        self.assertFalse(audit.recipe_fallback_active)
        self.assertEqual(audit.active_recipe_source, "processed-dataset")
        self.assertGreaterEqual(audit.usda_mapped_ingredient_count, 80)
        self.assertGreaterEqual(audit.guidance_mapping_count, 30)
        self.assertGreater(audit.nutrition_recipe_count, 20000)
        self.assertGreater(audit.priced_recipe_count, 15000)
        self.assertGreater(audit.nutrition_unknown_count, 0)
        self.assertGreater(audit.price_unknown_count, 0)
        self.assertGreater(audit.weak_main_count, 0)

        text = render_runtime_audit_text(build_runtime_data_contract(), audit)
        self.assertIn("Active recipe source: processed-dataset", text)
        self.assertIn("Total recipes:", text)
        self.assertIn("Weak main count:", text)

    def test_missing_dataset_reports_sample_fallback_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = Path(tmpdir) / "missing-recipes.json"

            recipes, status = resolve_recipe_runtime(missing_path)

            self.assertTrue(recipes)
            self.assertEqual(status.active_source, "sample-fallback")
            self.assertTrue(status.fallback_active)
            self.assertEqual(status.processed_recipe_count, 0)
            self.assertEqual(status.fallback_reason, "processed dataset path does not exist")
            self.assertGreater(status.sample_recipe_count, 0)


if __name__ == "__main__":
    unittest.main()
