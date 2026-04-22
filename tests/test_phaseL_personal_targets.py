import unittest

from pantry_pilot.models import (
    GroceryLocation,
    GroceryProduct,
    NutritionEstimate,
    PlannerRequest,
    Recipe,
    RecipeIngredient,
    UserNutritionProfile,
)
from pantry_pilot.normalization import normalize_name
from pantry_pilot.personal_targets import generate_personal_targets
from pantry_pilot.plan_display import build_plan_text_export
from pantry_pilot.planner import WeeklyMealPlanner
from pantry_pilot.providers import LocalRecipeProvider


class FixedPriceGroceryProvider:
    provider_name = "mock"

    def __init__(self, catalog: dict[str, GroceryProduct]) -> None:
        self._catalog = {normalize_name(name): product for name, product in catalog.items()}

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        return ()

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        return self._catalog.get(normalize_name(ingredient_name))


class PersonalTargetRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="protein-bowl",
                title="Chicken Protein Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=760,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset({"dairy"}),
                ingredients=(
                    RecipeIngredient("chicken breast", 1.0, "lb"),
                    RecipeIngredient("broccoli", 2.0, "cup"),
                    RecipeIngredient("cream cheese", 2.0, "tbsp"),
                ),
                steps=("Cook it.",),
                estimated_nutrition_per_serving=NutritionEstimate(
                    calories=760,
                    protein_grams=54.0,
                    carbs_grams=18.0,
                    fat_grams=50.0,
                ),
            ),
            Recipe(
                recipe_id="light-bowl",
                title="Garden Rice Bowl",
                cuisine="mediterranean",
                base_servings=2,
                estimated_calories_per_serving=320,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free", "vegetarian"}),
                allergens=frozenset(),
                ingredients=(
                    RecipeIngredient("rice", 1.0, "cup"),
                    RecipeIngredient("tomato", 2.0, "item"),
                    RecipeIngredient("zucchini", 2.0, "cup"),
                ),
                steps=("Cook it.",),
                estimated_nutrition_per_serving=NutritionEstimate(
                    calories=320,
                    protein_grams=9.0,
                    carbs_grams=58.0,
                    fat_grams=6.0,
                ),
            ),
        )


class PersonalTargetPhaseTests(unittest.TestCase):
    def setUp(self) -> None:
        WeeklyMealPlanner.reset_request_cycle_offsets()
        self.grocery_provider = FixedPriceGroceryProvider(
            {
                "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 1.5),
                "broccoli": GroceryProduct("broccoli", 2.0, "cup", 0.8),
                "cream cheese": GroceryProduct("cream cheese", 1.0, "package", 0.4),
                "rice": GroceryProduct("rice", 1.0, "cup", 0.8),
                "tomato": GroceryProduct("tomato", 2.0, "item", 0.9),
                "zucchini": GroceryProduct("zucchini", 2.0, "cup", 1.0),
            }
        )
        self.planner = WeeklyMealPlanner(
            recipe_provider=PersonalTargetRecipeProvider(),
            grocery_provider=self.grocery_provider,
        )

    def test_target_generation_is_consistent_for_same_profile(self) -> None:
        profile = UserNutritionProfile(
            age_years=34,
            sex="female",
            height_cm=168.0,
            weight_kg=72.0,
            activity_level="Low Active",
            planning_goal="Maintain",
        )

        first = generate_personal_targets(profile, meals_per_day=1)
        second = generate_personal_targets(profile, meals_per_day=1)

        self.assertEqual(first, second)
        self.assertGreater(first.protein_target_min_grams, 50.0)
        self.assertGreater(first.produce_target_cups, 3.0)

    def test_distinct_profiles_produce_distinct_targets(self) -> None:
        lighter_profile = UserNutritionProfile(
            age_years=30,
            sex="female",
            height_cm=160.0,
            weight_kg=58.0,
            activity_level="Sedentary",
            planning_goal="Mild Deficit",
        )
        larger_profile = UserNutritionProfile(
            age_years=30,
            sex="male",
            height_cm=188.0,
            weight_kg=92.0,
            activity_level="Active",
            planning_goal="High Protein Preference",
        )

        lighter_targets = generate_personal_targets(lighter_profile, meals_per_day=1)
        larger_targets = generate_personal_targets(larger_profile, meals_per_day=1)

        self.assertLess(lighter_targets.estimated_daily_calories, larger_targets.estimated_daily_calories)
        self.assertLess(lighter_targets.protein_target_min_grams, larger_targets.protein_target_min_grams)
        self.assertLessEqual(lighter_targets.grains_target_ounces, larger_targets.grains_target_ounces)

    def test_planner_changes_meaningfully_across_profiles(self) -> None:
        lower_energy_profile = UserNutritionProfile(
            age_years=30,
            sex="female",
            height_cm=160.0,
            weight_kg=58.0,
            activity_level="Sedentary",
            planning_goal="Mild Deficit",
        )
        high_protein_profile = UserNutritionProfile(
            age_years=34,
            sex="female",
            height_cm=168.0,
            weight_kg=72.0,
            activity_level="Low Active",
            planning_goal="High Protein Preference",
        )
        lower_energy_targets = generate_personal_targets(lower_energy_profile, meals_per_day=2)
        high_protein_targets = generate_personal_targets(high_protein_profile, meals_per_day=2)

        lower_energy_request = PlannerRequest(
            weekly_budget=70.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=2,
            meal_structure=("lunch", "dinner"),
            daily_calorie_target_min=lower_energy_targets.calorie_target_min,
            daily_calorie_target_max=lower_energy_targets.calorie_target_max,
            user_profile=lower_energy_profile,
            personal_targets=lower_energy_targets,
        )
        high_protein_request = PlannerRequest(
            weekly_budget=70.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=2,
            meal_structure=("lunch", "dinner"),
            daily_calorie_target_min=high_protein_targets.calorie_target_min,
            daily_calorie_target_max=high_protein_targets.calorie_target_max,
            user_profile=high_protein_profile,
            personal_targets=high_protein_targets,
        )

        recipes = PersonalTargetRecipeProvider().list_recipes()
        lower_energy_scores = {
            recipe.title: self.planner._evaluate_candidate(
                all_candidates=recipes,
                recipe=recipe,
                request=lower_energy_request,
                pantry_inventory=frozenset(),
                variety_profile=self.planner._variety_profile(lower_energy_request),
                purchased_quantities={},
                meals=[],
                day_number=1,
                slot_number=1,
                current_total=0.0,
                candidate_role="main",
                anchor_recipe=None,
                enforce_repeat_cap=True,
                desired_slot="lunch",
            )
            for recipe in recipes
        }
        high_protein_scores = {
            recipe.title: self.planner._evaluate_candidate(
                all_candidates=recipes,
                recipe=recipe,
                request=high_protein_request,
                pantry_inventory=frozenset(),
                variety_profile=self.planner._variety_profile(high_protein_request),
                purchased_quantities={},
                meals=[],
                day_number=1,
                slot_number=1,
                current_total=0.0,
                candidate_role="main",
                anchor_recipe=None,
                enforce_repeat_cap=True,
                desired_slot="lunch",
            )
            for recipe in recipes
        }

        lower_energy_gap = (
            lower_energy_scores["Chicken Protein Bowl"].final_score
            - lower_energy_scores["Garden Rice Bowl"].final_score
        )
        high_protein_gap = (
            high_protein_scores["Chicken Protein Bowl"].final_score
            - high_protein_scores["Garden Rice Bowl"].final_score
        )

        self.assertGreater(high_protein_gap, lower_energy_gap)
        self.assertIn("target:goal-high-protein", high_protein_scores["Chicken Protein Bowl"].reasons)
        self.assertIn("target:protein-range", high_protein_scores["Chicken Protein Bowl"].reasons)
        self.assertIn("target:calorie-guidance", lower_energy_scores["Chicken Protein Bowl"].reasons)

    def test_export_includes_personal_target_guidance(self) -> None:
        profile = UserNutritionProfile(
            age_years=34,
            sex="female",
            height_cm=168.0,
            weight_kg=72.0,
            activity_level="Low Active",
            planning_goal="Maintain",
        )
        targets = generate_personal_targets(profile, meals_per_day=1)
        request = PlannerRequest(
            weekly_budget=70.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            meal_structure=("dinner",),
            daily_calorie_target_min=targets.calorie_target_min,
            daily_calorie_target_max=targets.calorie_target_max,
            user_profile=profile,
            personal_targets=targets,
        )

        plan = self.planner.create_plan(request)
        export_text = build_plan_text_export(
            request,
            plan,
            f"{targets.calorie_target_min:,} to {targets.calorie_target_max:,} calories per day",
            selection_diagnostics=self.planner.latest_selection_diagnostics(),
        )

        self.assertIn("Personal target guidance:", export_text)
        self.assertIn("Protein", export_text)


if __name__ == "__main__":
    unittest.main()
