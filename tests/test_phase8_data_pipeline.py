import unittest

from pantry_pilot.data_pipeline import (
    AllergenAssessment,
    AllergenCompleteness,
    CalorieEstimate,
    DataQualitySeverity,
    DiversityMetadata,
    IngredientRecord,
    NormalizedRecipe,
    SchemaValidationError,
    SourceMetadata,
    assert_valid_recipe,
    assert_valid_recipe_collection,
    validate_recipe,
    validate_recipe_collection,
)


def build_recipe(**overrides) -> NormalizedRecipe:
    base_recipe = NormalizedRecipe(
        recipe_id="mediterranean-chickpea-bowl",
        title="Mediterranean Chickpea Bowl",
        source=SourceMetadata(
            source_id="demo-source",
            source_name="Demo Source",
            source_type="local-file",
            file_path="mvp/data/raw/demo-source/sample.json",
            citation="Demo recipe export",
        ),
        source_recipe_id="demo-001",
        cuisine="mediterranean",
        meal_types=("lunch", "dinner"),
        diet_tags=frozenset({"vegetarian"}),
        allergens=AllergenAssessment(
            allergens=frozenset({"sesame"}),
            completeness=AllergenCompleteness.COMPLETE,
            unsafe_if_unknown=True,
        ),
        ingredients=(
            IngredientRecord(
                ingredient_id="chickpeas-can",
                display_name="Chickpeas",
                canonical_name="chickpeas",
                quantity=2.0,
                unit="cans",
            ),
            IngredientRecord(
                ingredient_id="rice-white",
                display_name="Rice",
                canonical_name="rice",
                quantity=2.0,
                unit="cups",
            ),
        ),
        steps=("Cook rice.", "Warm chickpeas.", "Assemble bowls."),
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        total_time_minutes=30,
        calories=CalorieEstimate(
            calories_per_serving=420,
            source="manual-estimate",
            confidence=0.8,
        ),
        diversity=DiversityMetadata(
            primary_proteins=("chickpeas",),
            primary_carbs=("rice",),
            vegetables=("cucumber", "tomato"),
            cooking_methods=("stovetop",),
            flavor_tags=("bright", "savory"),
        ),
        normalized_search_text="mediterranean chickpea rice bowl cucumber tomato",
    )
    return NormalizedRecipe(**{**base_recipe.__dict__, **overrides})


class Phase8DataPipelineTests(unittest.TestCase):
    def test_valid_recipe_has_no_issues(self) -> None:
        self.assertEqual(validate_recipe(build_recipe()), ())

    def test_unknown_allergen_metadata_stays_unsafe(self) -> None:
        recipe = build_recipe(
            allergens=AllergenAssessment(
                allergens=None,
                completeness=AllergenCompleteness.UNKNOWN,
                unsafe_if_unknown=True,
            )
        )

        self.assertEqual(validate_recipe(recipe), ())

    def test_incomplete_allergen_metadata_cannot_be_marked_safe(self) -> None:
        recipe = build_recipe(
            allergens=AllergenAssessment(
                allergens=None,
                completeness=AllergenCompleteness.PARTIAL,
                unsafe_if_unknown=False,
            )
        )

        issues = validate_recipe(recipe)

        self.assertTrue(
            any(
                issue.field == "allergens.unsafe_if_unknown"
                and issue.severity is DataQualitySeverity.ERROR
                for issue in issues
            )
        )

    def test_invalid_ingredient_and_blank_step_are_reported(self) -> None:
        recipe = build_recipe(
            ingredients=(
                IngredientRecord(
                    ingredient_id="",
                    display_name="Rice",
                    canonical_name="rice",
                    quantity=0.0,
                    unit="cups",
                ),
            ),
            steps=("Cook rice.", " "),
        )

        issues = validate_recipe(recipe)
        fields = {issue.field for issue in issues}

        self.assertIn("ingredients[0].ingredient_id", fields)
        self.assertIn("ingredients[0].quantity", fields)
        self.assertIn("steps[1]", fields)

    def test_duplicate_recipe_ids_fail_collection_validation(self) -> None:
        first = build_recipe()
        second = build_recipe(
            source_recipe_id="demo-002",
            recipe_id="mediterranean-chickpea-bowl",
            title="Mediterranean Chickpea Bowl Copy",
        )

        issues = validate_recipe_collection((first, second))

        self.assertTrue(any("Duplicate recipe_id" in issue.message for issue in issues))

    def test_duplicate_source_identity_fails_collection_validation(self) -> None:
        first = build_recipe()
        second = build_recipe(
            recipe_id="mediterranean-chickpea-bowl-2",
            title="Mediterranean Chickpea Bowl Variant",
        )

        with self.assertRaises(SchemaValidationError):
            assert_valid_recipe_collection((first, second))

    def test_assert_valid_recipe_raises_on_schema_errors(self) -> None:
        recipe = build_recipe(servings=0)

        with self.assertRaises(SchemaValidationError):
            assert_valid_recipe(recipe)


if __name__ == "__main__":
    unittest.main()
