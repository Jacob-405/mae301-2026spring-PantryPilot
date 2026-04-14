from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pantry_pilot.data_pipeline.schema import (
    AllergenCompleteness,
    IngredientRecord,
    NormalizedRecipe,
    SourceMetadata,
)


class DataQualitySeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class ValidationIssue:
    severity: DataQualitySeverity
    field: str
    message: str


class SchemaValidationError(ValueError):
    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = issues
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        formatted = ", ".join(f"{issue.severity}:{issue.field}" for issue in self.issues)
        return f"Recipe dataset validation failed: {formatted}"


def validate_recipe(recipe: NormalizedRecipe) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    _validate_source(recipe.source, issues)
    _require_non_empty(recipe.recipe_id, "recipe_id", issues)
    _require_non_empty(recipe.title, "title", issues)
    _require_non_empty(recipe.source_recipe_id, "source_recipe_id", issues)
    _require_non_empty(recipe.cuisine, "cuisine", issues)

    if recipe.servings <= 0:
        issues.append(_error("servings", "Servings must be greater than zero."))
    if recipe.prep_time_minutes < 0:
        issues.append(_error("prep_time_minutes", "Prep time cannot be negative."))
    if recipe.cook_time_minutes < 0:
        issues.append(_error("cook_time_minutes", "Cook time cannot be negative."))
    if recipe.total_time_minutes < 0:
        issues.append(_error("total_time_minutes", "Total time cannot be negative."))
    expected_total = recipe.prep_time_minutes + recipe.cook_time_minutes
    if recipe.total_time_minutes not in (0, expected_total):
        issues.append(
            _warning(
                "total_time_minutes",
                "Total time should be zero as a placeholder or equal prep plus cook time.",
            )
        )

    if not recipe.meal_types:
        issues.append(_error("meal_types", "At least one meal type is required."))
    if not recipe.ingredients:
        issues.append(_error("ingredients", "At least one ingredient is required."))
    if not recipe.steps:
        issues.append(_error("steps", "At least one preparation step is required."))

    for index, ingredient in enumerate(recipe.ingredients):
        _validate_ingredient(ingredient, index, issues)

    for index, step in enumerate(recipe.steps):
        if not step.strip():
            issues.append(_error(f"steps[{index}]", "Steps must not be blank."))

    calories = recipe.calories.calories_per_serving
    if calories is not None and calories <= 0:
        issues.append(_error("calories.calories_per_serving", "Calories per serving must be positive when provided."))
    if recipe.calories.confidence is not None and not 0.0 <= recipe.calories.confidence <= 1.0:
        issues.append(_error("calories.confidence", "Calorie confidence must be between 0.0 and 1.0."))

    if recipe.allergens.completeness is AllergenCompleteness.UNKNOWN and recipe.allergens.allergens is not None:
        issues.append(
            _warning(
                "allergens",
                "Unknown allergen completeness should normally keep allergens unset so it is treated as unsafe.",
            )
        )
    if recipe.allergens.completeness is AllergenCompleteness.COMPLETE and recipe.allergens.allergens is None:
        issues.append(_error("allergens", "Complete allergen data must provide an allergen set, even if empty."))
    if recipe.allergens.completeness is not AllergenCompleteness.COMPLETE and not recipe.allergens.unsafe_if_unknown:
        issues.append(_error("allergens.unsafe_if_unknown", "Incomplete allergen data must remain unsafe."))

    return tuple(issues)


def validate_recipe_collection(recipes: tuple[NormalizedRecipe, ...]) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []
    seen_recipe_ids: set[str] = set()
    seen_source_pairs: set[tuple[str, str]] = set()

    for index, recipe in enumerate(recipes):
        for issue in validate_recipe(recipe):
            issues.append(
                ValidationIssue(
                    severity=issue.severity,
                    field=f"recipes[{index}].{issue.field}",
                    message=issue.message,
                )
            )

        if recipe.recipe_id in seen_recipe_ids:
            issues.append(_error(f"recipes[{index}].recipe_id", f"Duplicate recipe_id '{recipe.recipe_id}'."))
        seen_recipe_ids.add(recipe.recipe_id)

        source_key = (recipe.source.source_id, recipe.source_recipe_id)
        if source_key in seen_source_pairs:
            issues.append(
                _error(
                    f"recipes[{index}].source_recipe_id",
                    "Duplicate source record identity for source_id/source_recipe_id.",
                )
            )
        seen_source_pairs.add(source_key)

    return tuple(issues)


def assert_valid_recipe(recipe: NormalizedRecipe) -> None:
    issues = validate_recipe(recipe)
    errors = tuple(issue for issue in issues if issue.severity is DataQualitySeverity.ERROR)
    if errors:
        raise SchemaValidationError(errors)


def assert_valid_recipe_collection(recipes: tuple[NormalizedRecipe, ...]) -> None:
    issues = validate_recipe_collection(recipes)
    errors = tuple(issue for issue in issues if issue.severity is DataQualitySeverity.ERROR)
    if errors:
        raise SchemaValidationError(errors)


def _validate_source(source: SourceMetadata, issues: list[ValidationIssue]) -> None:
    _require_non_empty(source.source_id, "source.source_id", issues)
    _require_non_empty(source.source_name, "source.source_name", issues)
    _require_non_empty(source.source_type, "source.source_type", issues)


def _validate_ingredient(
    ingredient: IngredientRecord,
    index: int,
    issues: list[ValidationIssue],
) -> None:
    prefix = f"ingredients[{index}]"
    _require_non_empty(ingredient.ingredient_id, f"{prefix}.ingredient_id", issues)
    _require_non_empty(ingredient.display_name, f"{prefix}.display_name", issues)
    _require_non_empty(ingredient.canonical_name, f"{prefix}.canonical_name", issues)
    _require_non_empty(ingredient.unit, f"{prefix}.unit", issues)
    if ingredient.quantity <= 0:
        issues.append(_error(f"{prefix}.quantity", "Ingredient quantity must be greater than zero."))


def _require_non_empty(value: str, field: str, issues: list[ValidationIssue]) -> None:
    if not value.strip():
        issues.append(_error(field, "Field must not be blank."))


def _error(field: str, message: str) -> ValidationIssue:
    return ValidationIssue(severity=DataQualitySeverity.ERROR, field=field, message=message)


def _warning(field: str, message: str) -> ValidationIssue:
    return ValidationIssue(severity=DataQualitySeverity.WARNING, field=field, message=message)
