import unittest
from unittest.mock import patch

from pantry_pilot.acceptance import AcceptanceResult, render_acceptance_text, run_acceptance


class PhaseJAcceptanceTests(unittest.TestCase):
    def test_single_scenario_acceptance_payload_is_selectable(self) -> None:
        fake_result = AcceptanceResult(
            scenario_id="balanced_week",
            name="Standard Balanced Week",
            passed=True,
            details={"seconds": 1.23, "meal_count": 7},
        )
        with patch("pantry_pilot.acceptance._run_balanced_week", return_value=fake_result):
            with patch.dict(
                "pantry_pilot.acceptance.SCENARIO_HANDLERS",
                {"balanced_week": lambda store: fake_result},
                clear=False,
            ):
                payload = run_acceptance(("balanced_week",))

        self.assertEqual(len(payload["scenarios"]), 1)
        self.assertEqual(payload["scenarios"][0]["scenario_id"], "balanced_week")
        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["scenario_id"], "balanced_week")
        self.assertIn("seconds", payload["results"][0]["details"])
        self.assertIn("runtime_contract", payload)
        self.assertIn("runtime_coverage", payload)

    def test_render_acceptance_text_includes_frozen_runtime(self) -> None:
        text = render_acceptance_text(
            {
                "all_passed": True,
                "results": [
                    {
                        "name": "Standard Balanced Week",
                        "passed": True,
                        "details": {"meal_count": 7},
                    }
                ],
                "runtime_contract": {
                    "active_recipe_corpus_path": "recipes.json",
                    "nutrition_mappings_path": "nutrition-mappings.json",
                    "nutrition_records_path": "nutrition-records.json",
                    "guidance_path": "guidance.json",
                    "default_pricing_source": "mock",
                },
                "known_limitations": ["Example limitation."],
            }
        )

        self.assertIn("Overall result: PASS", text)
        self.assertIn("Frozen Runtime", text)
        self.assertIn("Active recipe corpus: recipes.json", text)
        self.assertIn("Known Limitations", text)


if __name__ == "__main__":
    unittest.main()
