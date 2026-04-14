import unittest

from pantry_pilot.data_pipeline import (
    AllergenAssessment,
    AllergenCompleteness,
    CalorieEstimate,
    IngredientRecord,
    NormalizedRecipe,
    SourceMetadata,
    annotate_recipe_similarity,
    build_diversity_metadata,
    compare_recipes,
)


def build_recipe(
    recipe_id: str,
    title: str,
    cuisine: str,
    ingredient_names: tuple[str, ...],
    meal_types: tuple[str, ...] = ("dinner",),
) -> NormalizedRecipe:
    base = NormalizedRecipe(
        recipe_id=recipe_id,
        title=title,
        source=SourceMetadata(source_id="demo", source_name="demo.json", source_type="json"),
        source_recipe_id=recipe_id,
        cuisine=cuisine,
        meal_types=meal_types,
        diet_tags=frozenset({"vegetarian"}),
        allergens=AllergenAssessment(allergens=frozenset(), completeness=AllergenCompleteness.COMPLETE),
        ingredients=tuple(
            IngredientRecord(
                ingredient_id=f"{name}-{index}",
                display_name=name,
                canonical_name=name,
                quantity=1.0,
                unit="item" if name in {"tomato", "onion"} else "cup",
            )
            for index, name in enumerate(ingredient_names, start=1)
        ),
        steps=("Cook.", "Serve."),
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        total_time_minutes=30,
        calories=CalorieEstimate(calories_per_serving=400),
    )
    return base


class Phase11DeduplicationTests(unittest.TestCase):
    def test_exact_duplicate_detection_is_deterministic(self) -> None:
        left = build_recipe("a-recipe", "Tomato Rice Bowl", "mediterranean", ("rice", "tomato", "chickpeas"))
        right = build_recipe("b-recipe", "Tomato Rice Bowl", "mediterranean", ("rice", "tomato", "chickpeas"))

        compared = compare_recipes(
            build_recipe("a-recipe", "Tomato Rice Bowl", "mediterranean", ("rice", "tomato", "chickpeas"),),
            build_recipe("b-recipe", "Tomato Rice Bowl", "mediterranean", ("rice", "tomato", "chickpeas"),),
        )

        self.assertTrue(compared.exact_duplicate)
        self.assertGreaterEqual(compared.score, 0.99)

    def test_near_duplicate_detection_uses_explainable_signals(self) -> None:
        left = build_recipe("a-recipe", "Tomato Rice Bowl", "mediterranean", ("rice", "tomato", "chickpeas"))
        right = build_recipe("b-recipe", "Greek Rice Bowl", "mediterranean", ("rice", "tomato", "chickpeas", "feta"))
        left = left.__class__(**{**left.__dict__, "diversity": build_diversity_metadata(left)})
        right = right.__class__(**{**right.__dict__, "diversity": build_diversity_metadata(right)})

        compared = compare_recipes(left, right)

        self.assertFalse(compared.exact_duplicate)
        self.assertGreaterEqual(compared.score, 0.72)
        self.assertIn("shared-cuisine", compared.signals)
        self.assertTrue(any(signal.startswith("ingredient-overlap:") for signal in compared.signals))

    def test_similarity_annotation_writes_cluster_metadata(self) -> None:
        first = build_recipe("a-recipe", "Tomato Rice Bowl", "mediterranean", ("rice", "tomato", "chickpeas"))
        second = build_recipe("b-recipe", "Tomato Rice Bowl", "mediterranean", ("rice", "tomato", "chickpeas"))
        third = build_recipe("c-recipe", "Greek Rice Bowl", "mediterranean", ("rice", "tomato", "chickpeas", "feta"))
        recipes = tuple(
            recipe.__class__(**{**recipe.__dict__, "diversity": build_diversity_metadata(recipe)})
            for recipe in (first, second, third)
        )

        annotated = annotate_recipe_similarity(recipes)
        by_id = {recipe.recipe_id: recipe for recipe in annotated}

        self.assertEqual(by_id["a-recipe"].similarity.cluster_id, "cluster-a-recipe")
        self.assertEqual(by_id["b-recipe"].similarity.exact_duplicate_of, "a-recipe")
        self.assertEqual(by_id["c-recipe"].similarity.representative_recipe_id, "a-recipe")
        self.assertIn("b-recipe", by_id["a-recipe"].similarity.related_recipe_ids)
        self.assertIn("c-recipe", by_id["a-recipe"].similarity.related_recipe_ids)

    def test_distinct_recipes_do_not_cluster(self) -> None:
        first = build_recipe("a-recipe", "Berry Yogurt Parfait", "american", ("yogurt", "banana", "granola"), ("breakfast",))
        second = build_recipe("b-recipe", "Turkey Chili", "american", ("ground turkey", "black beans", "canned tomatoes"))
        recipes = tuple(
            recipe.__class__(**{**recipe.__dict__, "diversity": build_diversity_metadata(recipe)})
            for recipe in (first, second)
        )

        annotated = annotate_recipe_similarity(recipes)

        self.assertEqual(annotated[0].similarity.cluster_id, "")
        self.assertEqual(annotated[1].similarity.cluster_id, "")


if __name__ == "__main__":
    unittest.main()
