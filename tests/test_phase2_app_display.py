import unittest

from pantry_pilot.models import MealPlan, NutritionEstimate, PlannedMeal, PlannerRequest, Recipe, RecipeIngredient, ShoppingListItem
from pantry_pilot.plan_display import (
    build_day_plan_summaries,
    build_grouped_shopping_sections,
    build_plan_text_export,
    build_shopping_list_csv,
    calorie_status_label,
    compact_selection_rationale,
    confidence_note,
    format_average_calorie_metric,
    format_calorie_coverage_note,
    format_calorie_total_metric,
    format_estimate_confidence_label,
    format_optional_nutrition,
    format_weekly_nutrition_summary,
    summarize_carryover_usage,
    summarize_calories,
    summarize_plan_balance,
    summarize_weekly_nutrition,
    shopping_category_for_item,
)
from pantry_pilot.planner import MealSelectionDiagnostic


def _recipe(
    recipe_id: str,
    *,
    calories: int | None,
    prep_time: int | None,
    nutrition: NutritionEstimate | None = None,
) -> Recipe:
    return Recipe(
        recipe_id=recipe_id,
        title=f"Recipe {recipe_id}",
        cuisine="mediterranean",
        base_servings=2,
        estimated_calories_per_serving=calories,
        prep_time_minutes=prep_time,
        meal_types=("dinner",),
        diet_tags=frozenset({"vegetarian"}),
        allergens=frozenset(),
        ingredients=(RecipeIngredient("rice", 1.0, "cup"),),
        steps=("Cook it.",),
        estimated_nutrition_per_serving=nutrition,
    )


class Phase2AppDisplayTests(unittest.TestCase):
    def test_calorie_summary_marks_partial_totals_and_unknown_status(self) -> None:
        known_meal = PlannedMeal(
            day=1,
            slot=1,
            recipe=_recipe("known", calories=450, prep_time=20),
            scaled_servings=2,
            incremental_cost=4.5,
            consumed_cost=2.25,
        )
        unknown_meal = PlannedMeal(
            day=1,
            slot=2,
            recipe=_recipe("unknown", calories=None, prep_time=None),
            scaled_servings=2,
            incremental_cost=3.0,
            consumed_cost=None,
        )

        summary = summarize_calories((known_meal, unknown_meal))
        status, help_text = calorie_status_label(summary, 1600, 2200)

        self.assertEqual(summary.known_total, 900)
        self.assertEqual(summary.unknown_meal_count, 1)
        self.assertEqual(format_calorie_total_metric(summary), "900 known")
        self.assertEqual(format_average_calorie_metric(summary), "129 known")
        self.assertEqual(status, "Unknown")
        self.assertIn("unknown calorie estimates", help_text)
        self.assertIn("1 meal", format_calorie_coverage_note(summary))

    def test_export_helpers_render_unknown_values_without_crashing(self) -> None:
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=35,
            meals_per_day=1,
            meal_structure=("dinner",),
        )
        plan = MealPlan(
            meals=(
                PlannedMeal(
                    day=1,
                    slot=1,
                    recipe=_recipe("unknown", calories=None, prep_time=None),
                    scaled_servings=2,
                    incremental_cost=3.25,
                    consumed_cost=None,
                ),
            ),
            shopping_list=(
                ShoppingListItem(
                    name="apple",
                    quantity=2.5,
                    unit="cup",
                    estimated_packages=0,
                    package_quantity=0.0,
                    package_unit="cup",
                    purchased_quantity=0.0,
                    estimated_cost=None,
                    pricing_source="mock",
                ),
            ),
            estimated_total_cost=3.25,
            notes=(),
            pricing_source="mock",
            selected_store="",
        )

        export_text = build_plan_text_export(request, plan, "1,600 to 2,200 calories per day")
        shopping_csv = build_shopping_list_csv(plan)

        self.assertIn("Weekly calories: Unknown", export_text)
        self.assertIn("Average calories per day: Unknown", export_text)
        self.assertIn("Daily calories: Unknown (Unknown)", export_text)
        self.assertIn("Recipe unknown (main) | Unknown | consumed Unknown | added shopping $3.25 | Unknown calories", export_text)
        self.assertIn("estimated cost Unknown", export_text)
        self.assertIn(
            "Ingredient,Amount Needed,Carryover Used,Amount Being Bought,Leftover After Plan,Package Count,Estimated Cost,Price Source",
            shopping_csv,
        )
        self.assertIn("apple,2.5 cup,N/A,N/A,N/A,0,Unknown,mock", shopping_csv)

    def test_trust_helpers_render_rationale_nutrition_and_uncertainty(self) -> None:
        diagnostic = MealSelectionDiagnostic(
            day=1,
            slot_number=1,
            slot_label="dinner",
            meal_role="main",
            selected_title="Recipe known",
            hard_constraint_count=4,
            role_gate_count=3,
            diversity_peer_count=1,
            used_repeat_fallback=False,
            runner_up_title="Runner Up",
            runner_up_margin=0.4,
            stage_scores=(("main-candidate-ranking", 7.2),),
            reasons=("main-anchor:strong", "weekly:produce-variety", "calorie-alignment"),
        )
        known_meal = PlannedMeal(
            day=1,
            slot=1,
            recipe=_recipe(
                "known",
                calories=420,
                prep_time=20,
                nutrition=NutritionEstimate(calories=420, protein_grams=22.0, carbs_grams=30.0, fat_grams=14.0),
            ),
            scaled_servings=2,
            incremental_cost=4.5,
            consumed_cost=2.25,
        )
        partial_meal = PlannedMeal(
            day=1,
            slot=2,
            recipe=_recipe("partial", calories=None, prep_time=None, nutrition=None),
            scaled_servings=2,
            incremental_cost=3.0,
            consumed_cost=None,
            meal_role="side",
        )
        plan = MealPlan(
            meals=(known_meal, partial_meal),
            shopping_list=(
                ShoppingListItem(
                    name="rice",
                    quantity=1.0,
                    unit="cup",
                    estimated_packages=1,
                    package_quantity=1.0,
                    package_unit="cup",
                    purchased_quantity=1.0,
                    carryover_used_quantity=0.5,
                    leftover_quantity_remaining=0.25,
                    estimated_cost=1.2,
                    pricing_source="mock",
                ),
            ),
            estimated_total_cost=4.5,
            notes=(),
            pricing_source="mock",
            selected_store="",
        )

        weekly_nutrition = summarize_weekly_nutrition(plan.meals)
        export_text = build_plan_text_export(
            PlannerRequest(
                weekly_budget=80.0,
                servings=2,
                cuisine_preferences=(),
                allergies=(),
                excluded_ingredients=(),
                diet_restrictions=(),
                pantry_staples=(),
                max_prep_time_minutes=35,
                meals_per_day=1,
                meal_structure=("dinner",),
            ),
            plan,
            "1,600 to 2,200 calories per day",
            selection_diagnostics=(diagnostic,),
        )

        self.assertEqual(format_optional_nutrition(None), "Unknown")
        self.assertEqual(
            format_optional_nutrition(NutritionEstimate(840, 44.0, 60.0, 28.0)),
            "840 cal | P 44.0g | C 60.0g | F 28.0g",
        )
        self.assertEqual(format_estimate_confidence_label(partial_meal, None), "Partial estimate")
        self.assertIn("strong anchor", compact_selection_rationale(diagnostic))
        self.assertIn("partially known", confidence_note(partial_meal, None))
        self.assertIn("Weekly nutrition:", export_text)
        self.assertIn("Carryover summary:", export_text)
        self.assertIn("Plan balance summary:", export_text)
        self.assertIn("Confidence: Estimated", export_text)
        self.assertIn("Confidence: Partial estimate", export_text)
        self.assertIn("Why chosen: strong anchor, adds produce variety, fits calorie target.", export_text)
        self.assertIn("Nutrition note: 1 meal(s) still have partial or unknown nutrition.", export_text)
        self.assertIn("Pantry carryover used on 1 ingredient(s)", summarize_carryover_usage(plan))
        self.assertIn("strong-anchor meals", summarize_plan_balance((diagnostic,)))
        self.assertIn("840 cal known", format_weekly_nutrition_summary(weekly_nutrition))

    def test_day_plan_summaries_keep_weekly_view_data_compact_and_safe(self) -> None:
        request = PlannerRequest(
            weekly_budget=80.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=35,
            meals_per_day=2,
            meal_structure=("lunch", "dinner"),
            daily_calorie_target_min=1600,
            daily_calorie_target_max=2200,
        )
        plan = MealPlan(
            meals=(
                PlannedMeal(
                    day=1,
                    slot=1,
                    recipe=_recipe("known", calories=400, prep_time=15),
                    scaled_servings=2,
                    incremental_cost=3.0,
                    consumed_cost=1.5,
                ),
                PlannedMeal(
                    day=1,
                    slot=2,
                    recipe=_recipe("unknown", calories=None, prep_time=25),
                    scaled_servings=2,
                    incremental_cost=4.0,
                    consumed_cost=None,
                    meal_role="side",
                ),
            ),
            shopping_list=(),
            estimated_total_cost=7.0,
            notes=(),
            pricing_source="mock",
            selected_store="",
        )

        summaries = build_day_plan_summaries(request, plan)

        self.assertEqual(len(summaries), 7)
        self.assertEqual(summaries[0].label, "Monday")
        self.assertEqual(summaries[0].meal_count, 2)
        self.assertEqual(summaries[0].calorie_display, "800 known (partial)")
        self.assertTrue(summaries[0].consumed_cost_is_partial)
        self.assertEqual(summaries[0].added_shopping_total, 7.0)
        self.assertEqual(summaries[1].meal_count, 0)

    def test_grouped_shopping_sections_improve_readability_without_losing_fields(self) -> None:
        plan = MealPlan(
            meals=(),
            shopping_list=(
                ShoppingListItem(
                    name="broccoli",
                    quantity=2.0,
                    unit="cup",
                    estimated_packages=1,
                    package_quantity=1.0,
                    package_unit="head",
                    purchased_quantity=1.0,
                    carryover_used_quantity=0.0,
                    leftover_quantity_remaining=0.0,
                    estimated_cost=2.5,
                    pricing_source="mock",
                ),
                ShoppingListItem(
                    name="chicken breast",
                    quantity=1.5,
                    unit="lb",
                    estimated_packages=2,
                    package_quantity=1.0,
                    package_unit="lb",
                    purchased_quantity=2.0,
                    carryover_used_quantity=0.5,
                    leftover_quantity_remaining=0.5,
                    estimated_cost=8.5,
                    pricing_source="mock",
                ),
                ShoppingListItem(
                    name="rice",
                    quantity=2.0,
                    unit="cup",
                    estimated_packages=1,
                    package_quantity=1.0,
                    package_unit="bag",
                    purchased_quantity=1.0,
                    carryover_used_quantity=0.0,
                    leftover_quantity_remaining=0.25,
                    estimated_cost=1.9,
                    pricing_source="mock",
                ),
            ),
            estimated_total_cost=12.9,
            notes=(),
            pricing_source="mock",
            selected_store="",
        )

        sections = build_grouped_shopping_sections(plan)
        titles = [section.title for section in sections]

        self.assertEqual(shopping_category_for_item("broccoli"), "Produce")
        self.assertEqual(shopping_category_for_item("chicken breast"), "Protein")
        self.assertEqual(shopping_category_for_item("rice"), "Grains And Starches")
        self.assertEqual(titles, ["Produce", "Protein", "Grains And Starches"])
        protein_row = sections[1].rows[0]
        self.assertEqual(protein_row.ingredient, "chicken breast")
        self.assertEqual(protein_row.carryover_used, "0.5 lb")
        self.assertEqual(protein_row.leftover_after_plan, "0.5 lb")


if __name__ == "__main__":
    unittest.main()
