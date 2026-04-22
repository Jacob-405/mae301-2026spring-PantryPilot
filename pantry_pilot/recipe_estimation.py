from __future__ import annotations

from dataclasses import dataclass

from pantry_pilot.ingredient_catalog import convert_ingredient_unit_quantity, ingredient_calorie_reference
from pantry_pilot.models import NutritionEstimate, RecipeIngredient
from pantry_pilot.nutrition import lookup_ingredient_nutrition_candidates


@dataclass(frozen=True)
class IngredientNutritionContribution:
    ingredient_name: str
    quantity: float
    unit: str
    reference_unit: str = ""
    converted_quantity: float | None = None
    nutrition: NutritionEstimate | None = None
    issue: str = ""


@dataclass(frozen=True)
class RecipeNutritionComputation:
    servings: int
    per_serving: NutritionEstimate | None
    total: NutritionEstimate | None
    contributions: tuple[IngredientNutritionContribution, ...]

    @property
    def is_complete(self) -> bool:
        return self.per_serving is not None

    @property
    def missing_ingredients(self) -> tuple[str, ...]:
        return tuple(
            contribution.ingredient_name
            for contribution in self.contributions
            if contribution.nutrition is None
        )


def estimate_recipe_nutrition(
    ingredients: tuple[RecipeIngredient, ...],
    servings: int,
    *,
    use_usda_full: bool = True,
    use_usda_pilot: bool = True,
) -> RecipeNutritionComputation:
    if servings <= 0 or not ingredients:
        return RecipeNutritionComputation(
            servings=servings,
            per_serving=None,
            total=None,
            contributions=(),
        )

    contributions: list[IngredientNutritionContribution] = []
    total_calories = 0.0
    total_protein = 0.0
    total_carbs = 0.0
    total_fat = 0.0

    for ingredient in ingredients:
        candidate_records = lookup_ingredient_nutrition_candidates(
            ingredient.name,
            include_usda_full=use_usda_full,
            include_usda_pilot=use_usda_pilot,
        )
        if not candidate_records:
            contributions.append(
                IngredientNutritionContribution(
                    ingredient_name=ingredient.name,
                    quantity=ingredient.quantity,
                    unit=ingredient.unit,
                    issue="unsupported ingredient nutrition mapping",
                )
            )
            return RecipeNutritionComputation(
                servings=servings,
                per_serving=None,
                total=None,
                contributions=tuple(contributions),
            )
        converted_quantity = None
        record = None
        for candidate_record in candidate_records:
            attempted_quantity = convert_ingredient_unit_quantity(
                ingredient.name,
                ingredient.quantity,
                ingredient.unit,
                candidate_record.reference_unit,
            )
            if attempted_quantity is not None:
                record = candidate_record
                converted_quantity = attempted_quantity
                break
        if record is None or converted_quantity is None:
            contributions.append(
                IngredientNutritionContribution(
                    ingredient_name=ingredient.name,
                    quantity=ingredient.quantity,
                    unit=ingredient.unit,
                    reference_unit=candidate_records[0].reference_unit,
                    issue="unsupported nutrition unit conversion",
                )
            )
            return RecipeNutritionComputation(
                servings=servings,
                per_serving=None,
                total=None,
                contributions=tuple(contributions),
            )
        ingredient_nutrition = _build_nutrition_estimate(
            calories=converted_quantity * record.calories,
            protein_grams=converted_quantity * record.protein_grams,
            carbs_grams=converted_quantity * record.carbs_grams,
            fat_grams=converted_quantity * record.fat_grams,
        )
        contributions.append(
            IngredientNutritionContribution(
                ingredient_name=ingredient.name,
                quantity=ingredient.quantity,
                unit=ingredient.unit,
                reference_unit=record.reference_unit,
                converted_quantity=round(converted_quantity, 3),
                nutrition=ingredient_nutrition,
            )
        )
        total_calories += converted_quantity * record.calories
        total_protein += converted_quantity * record.protein_grams
        total_carbs += converted_quantity * record.carbs_grams
        total_fat += converted_quantity * record.fat_grams

    total_estimate = _build_nutrition_estimate(
        calories=total_calories,
        protein_grams=total_protein,
        carbs_grams=total_carbs,
        fat_grams=total_fat,
    )
    per_serving_estimate = _build_nutrition_estimate(
        calories=total_calories / servings,
        protein_grams=total_protein / servings,
        carbs_grams=total_carbs / servings,
        fat_grams=total_fat / servings,
    )
    return RecipeNutritionComputation(
        servings=servings,
        per_serving=per_serving_estimate,
        total=total_estimate,
        contributions=tuple(contributions),
    )


def estimate_calories_per_serving(
    ingredients: tuple[RecipeIngredient, ...],
    servings: int,
    *,
    use_usda_full: bool = True,
    use_usda_pilot: bool = True,
) -> int | None:
    nutrition = estimate_recipe_nutrition(
        ingredients,
        servings,
        use_usda_full=use_usda_full,
        use_usda_pilot=use_usda_pilot,
    )
    if nutrition.per_serving is not None:
        return nutrition.per_serving.calories
    if servings <= 0 or not ingredients:
        return None
    total_calories = 0.0
    for ingredient in ingredients:
        reference = ingredient_calorie_reference(ingredient.name)
        if reference is None:
            return None
        calories_per_unit, calorie_unit = reference
        converted_quantity = convert_ingredient_unit_quantity(
            ingredient.name,
            ingredient.quantity,
            ingredient.unit,
            calorie_unit,
        )
        if converted_quantity is None:
            return None
        total_calories += converted_quantity * calories_per_unit
    return max(int(round(total_calories / servings)), 0)


def _build_nutrition_estimate(
    *,
    calories: float,
    protein_grams: float,
    carbs_grams: float,
    fat_grams: float,
) -> NutritionEstimate:
    return NutritionEstimate(
        calories=max(int(round(calories)), 0),
        protein_grams=round(max(protein_grams, 0.0), 1),
        carbs_grams=round(max(carbs_grams, 0.0), 1),
        fat_grams=round(max(fat_grams, 0.0), 1),
    )
