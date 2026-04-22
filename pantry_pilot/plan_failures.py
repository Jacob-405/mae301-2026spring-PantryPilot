from __future__ import annotations


GENERIC_PLAN_FAILURE_HEADLINE = "PantryPilot could not build a full week from the current settings."
GENERIC_RUNTIME_FAILURE_HEADLINE = "PantryPilot hit a temporary runtime problem while generating the plan."
TRANSIENT_RUNTIME_MARKERS = (
    "high demand",
    "temporary error",
    "temporarily unavailable",
    "timed out",
    "timeout",
    "connection reset",
    "connection aborted",
    "service unavailable",
    "rate limit",
    "try again",
)


def build_failure_feedback(planner_error_message: str, likely_causes: list[str]) -> tuple[str, list[str]]:
    primary_message = planner_error_message.strip() or GENERIC_PLAN_FAILURE_HEADLINE
    filtered_causes = [
        cause
        for cause in likely_causes
        if cause.strip() and cause.strip() != primary_message and cause.strip() != GENERIC_PLAN_FAILURE_HEADLINE
    ]
    return primary_message, filtered_causes


def is_transient_runtime_failure(error_message: str) -> bool:
    normalized = error_message.strip().lower()
    return any(marker in normalized for marker in TRANSIENT_RUNTIME_MARKERS)


def build_runtime_failure_feedback(
    error_message: str,
    *,
    has_saved_plan: bool,
) -> tuple[str, list[str]]:
    primary_message = error_message.strip() or GENERIC_RUNTIME_FAILURE_HEADLINE
    if is_transient_runtime_failure(primary_message):
        causes = [
            "The app or model backend appears temporarily overloaded or unavailable.",
            "Retrying the same request in a moment may succeed without changing your settings.",
        ]
        if has_saved_plan:
            causes.append("The last successful plan is still shown below so you do not lose your current result.")
        return GENERIC_RUNTIME_FAILURE_HEADLINE, causes
    causes = [
        "An unexpected runtime error interrupted plan generation.",
        "Retry the same request first. If it repeats, inspect the error details before changing planner settings.",
    ]
    if has_saved_plan:
        causes.append("The last successful plan is still shown below.")
    return primary_message, causes
