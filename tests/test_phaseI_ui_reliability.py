import unittest

from pantry_pilot.plan_failures import (
    build_runtime_failure_feedback,
    is_transient_runtime_failure,
)


class PhaseIUiReliabilityTests(unittest.TestCase):
    def test_transient_runtime_failures_are_classified_honestly(self) -> None:
        message = "We're currently experiencing high demand, which may cause temporary errors."

        headline, causes = build_runtime_failure_feedback(message, has_saved_plan=True)

        self.assertTrue(is_transient_runtime_failure(message))
        self.assertEqual(
            headline,
            "PantryPilot hit a temporary runtime problem while generating the plan.",
        )
        self.assertTrue(any("temporarily overloaded" in cause for cause in causes))
        self.assertTrue(any("last successful plan" in cause.lower() for cause in causes))


if __name__ == "__main__":
    unittest.main()
