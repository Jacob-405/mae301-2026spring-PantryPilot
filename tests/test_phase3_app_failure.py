import unittest

from pantry_pilot.plan_failures import GENERIC_PLAN_FAILURE_HEADLINE, build_failure_feedback


class Phase3AppFailureTests(unittest.TestCase):
    def test_specific_planner_error_becomes_primary_app_message(self) -> None:
        headline, causes = build_failure_feedback(
            "No recipes with known calorie estimates are available for dinner, so the calorie target cannot be satisfied.",
            [
                "The calorie target range is restrictive enough to block an otherwise feasible plan.",
                GENERIC_PLAN_FAILURE_HEADLINE,
            ],
        )

        self.assertEqual(
            headline,
            "No recipes with known calorie estimates are available for dinner, so the calorie target cannot be satisfied.",
        )
        self.assertEqual(
            causes,
            ["The calorie target range is restrictive enough to block an otherwise feasible plan."],
        )

    def test_generic_fallback_is_used_when_no_specific_error_exists(self) -> None:
        headline, causes = build_failure_feedback("", ["The weekly budget is likely too low for the selected constraints."])

        self.assertEqual(headline, GENERIC_PLAN_FAILURE_HEADLINE)
        self.assertEqual(causes, ["The weekly budget is likely too low for the selected constraints."])


if __name__ == "__main__":
    unittest.main()
