import unittest
from collections import Counter

from pantry_pilot.models import GroceryLocation, GroceryProduct, PlannerRequest, Recipe, RecipeIngredient
from pantry_pilot.normalization import normalize_name
from pantry_pilot.planner import PlannerError, WeeklyMealPlanner
from pantry_pilot.providers import LocalRecipeProvider


class FixedPriceGroceryProvider:
    provider_name = "mock"

    def __init__(self, catalog: dict[str, GroceryProduct]) -> None:
        self._catalog = {normalize_name(name): product for name, product in catalog.items()}

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        return ()

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        return self._catalog.get(normalize_name(ingredient_name))


class CalorieChoiceRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="light-dinner",
                title="Light Dinner",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=350,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("safe base", 1.0, "item"),),
                steps=("Cook the base ingredient.",),
            ),
            Recipe(
                recipe_id="target-dinner",
                title="Target Dinner",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=750,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("safe base", 1.0, "item"),),
                steps=("Cook the base ingredient.",),
            ),
        )


class VarietyRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="cheap-rice-bowl",
                title="Cheap Rice Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=520,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan", "gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("cheap staple", 1.0, "item"),),
                steps=("Cook the staple.",),
            ),
            Recipe(
                recipe_id="broccoli-plate",
                title="Broccoli Plate",
                cuisine="mediterranean",
                base_servings=2,
                estimated_calories_per_serving=540,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan", "gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("expensive vegetable", 1.0, "item"),),
                steps=("Roast the vegetable.",),
            ),
            Recipe(
                recipe_id="lentil-stew",
                title="Lentil Stew",
                cuisine="indian",
                base_servings=2,
                estimated_calories_per_serving=560,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan", "gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("expensive legume", 1.0, "item"),),
                steps=("Simmer the legume.",),
            ),
            Recipe(
                recipe_id="pasta-skillet",
                title="Pasta Skillet",
                cuisine="italian",
                base_servings=2,
                estimated_calories_per_serving=580,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"vegan"}),
                allergens=frozenset({"gluten"}),
                ingredients=(RecipeIngredient("expensive grain", 1.0, "item"),),
                steps=("Boil the grain.",),
            ),
        )


class AllergySafetyRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="peanut-bowl",
                title="Peanut Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=800,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset({"peanut"}),
                ingredients=(RecipeIngredient("peanut ingredient", 1.0, "item"),),
                steps=("Serve the peanut ingredient.",),
            ),
            Recipe(
                recipe_id="safe-bowl",
                title="Safe Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=620,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("safe base", 1.0, "item"),),
                steps=("Serve the safe ingredient.",),
            ),
        )


class ReplacementRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="target-bowl",
                title="Target Bowl",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=650,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("base", 1.0, "item"),),
                steps=("Cook the base.",),
            ),
            Recipe(
                recipe_id="swap-bowl",
                title="Swap Bowl",
                cuisine="mexican",
                base_servings=2,
                estimated_calories_per_serving=660,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("base", 1.0, "item"),),
                steps=("Cook the swap.",),
            ),
            Recipe(
                recipe_id="peanut-swap",
                title="Peanut Swap",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=655,
                prep_time_minutes=20,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset({"peanut"}),
                ingredients=(RecipeIngredient("peanut ingredient", 1.0, "item"),),
                steps=("Cook the peanut meal.",),
            ),
        )


class SingleRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        return (
            Recipe(
                recipe_id="only-dinner",
                title="Only Dinner",
                cuisine="american",
                base_servings=2,
                estimated_calories_per_serving=420,
                prep_time_minutes=15,
                meal_types=("dinner",),
                diet_tags=frozenset({"gluten-free"}),
                allergens=frozenset(),
                ingredients=(RecipeIngredient("safe base", 1.0, "item"),),
                steps=("Cook the only dinner.",),
            ),
        )


class PlanningPhase6Tests(unittest.TestCase):
    def test_daily_calorie_target_changes_recipe_selection(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=CalorieChoiceRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {"safe base": GroceryProduct("safe base", 1.0, "item", 2.0)}
            ),
        )
        lower_target_request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=650,
            daily_calorie_target_max=850,
        )
        higher_target_request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1450,
            daily_calorie_target_max=1650,
        )

        lower_target_plan = planner.create_plan(lower_target_request)
        higher_target_plan = planner.create_plan(higher_target_request)

        self.assertEqual(lower_target_plan.meals[0].recipe.title, "Light Dinner")
        self.assertEqual(higher_target_plan.meals[0].recipe.title, "Target Dinner")

    def test_high_variety_avoids_cheap_repeats_more_than_low_variety(self) -> None:
        provider = FixedPriceGroceryProvider(
            {
                "cheap staple": GroceryProduct("cheap staple", 1.0, "item", 1.0),
                "expensive vegetable": GroceryProduct("expensive vegetable", 1.0, "item", 7.0),
                "expensive legume": GroceryProduct("expensive legume", 1.0, "item", 7.0),
                "expensive grain": GroceryProduct("expensive grain", 1.0, "item", 7.0),
            }
        )
        planner = WeeklyMealPlanner(
            recipe_provider=VarietyRecipeProvider(),
            grocery_provider=provider,
        )
        common_kwargs = {
            "weekly_budget": 60.0,
            "servings": 2,
            "cuisine_preferences": (),
            "allergies": (),
            "excluded_ingredients": (),
            "diet_restrictions": (),
            "pantry_staples": (),
            "max_prep_time_minutes": 30,
            "meals_per_day": 1,
            "daily_calorie_target_min": 900,
            "daily_calorie_target_max": 1300,
        }
        low_variety_plan = planner.create_plan(
            PlannerRequest(**common_kwargs, variety_preference="low")
        )
        high_variety_plan = planner.create_plan(
            PlannerRequest(**common_kwargs, variety_preference="high")
        )

        low_titles = [meal.recipe.title for meal in low_variety_plan.meals]
        high_titles = [meal.recipe.title for meal in high_variety_plan.meals]
        low_counts = Counter(low_titles)
        high_counts = Counter(high_titles)

        self.assertEqual(low_titles[0], "Cheap Rice Bowl")
        self.assertEqual(low_titles[1], "Cheap Rice Bowl")
        self.assertNotEqual(high_titles[1], "Cheap Rice Bowl")
        self.assertGreater(low_counts["Cheap Rice Bowl"], high_counts["Cheap Rice Bowl"])

    def test_planner_stays_deterministic_for_same_variety_setting(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=VarietyRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "cheap staple": GroceryProduct("cheap staple", 1.0, "item", 1.0),
                    "expensive vegetable": GroceryProduct("expensive vegetable", 1.0, "item", 7.0),
                    "expensive legume": GroceryProduct("expensive legume", 1.0, "item", 7.0),
                    "expensive grain": GroceryProduct("expensive grain", 1.0, "item", 7.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=60.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=900,
            daily_calorie_target_max=1300,
            variety_preference="high",
        )

        first_plan = planner.create_plan(request)
        second_plan = planner.create_plan(request)

        self.assertEqual(
            [meal.recipe.recipe_id for meal in first_plan.meals],
            [meal.recipe.recipe_id for meal in second_plan.meals],
        )
        self.assertEqual(first_plan.shopping_list, second_plan.shopping_list)
        self.assertEqual(first_plan.estimated_total_cost, second_plan.estimated_total_cost)

    def test_allergy_filtering_still_blocks_better_calorie_fit(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=AllergySafetyRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "peanut ingredient": GroceryProduct("peanut ingredient", 1.0, "item", 2.0),
                    "safe base": GroceryProduct("safe base", 1.0, "item", 2.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=("peanut",),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1500,
            daily_calorie_target_max=1700,
        )

        filtered_titles = {recipe.title for recipe in planner.filter_recipes(request)}
        plan = planner.create_plan(request)

        self.assertNotIn("Peanut Bowl", filtered_titles)
        self.assertEqual(plan.meals[0].recipe.title, "Safe Bowl")

    def test_budget_checks_still_apply_with_calorie_targets_and_variety(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=VarietyRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "cheap staple": GroceryProduct("cheap staple", 1.0, "item", 4.0),
                    "expensive vegetable": GroceryProduct("expensive vegetable", 1.0, "item", 9.0),
                    "expensive legume": GroceryProduct("expensive legume", 1.0, "item", 9.0),
                    "expensive grain": GroceryProduct("expensive grain", 1.0, "item", 9.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=10.0,
            servings=2,
            cuisine_preferences=(),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=900,
            daily_calorie_target_max=1300,
            variety_preference="high",
        )

        with self.assertRaises(PlannerError):
            planner.create_plan(request)

    def test_replace_meal_preserves_other_slots_and_avoids_same_recipe_when_possible(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=ReplacementRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "base": GroceryProduct("base", 1.0, "item", 2.0),
                    "peanut ingredient": GroceryProduct("peanut ingredient", 1.0, "item", 2.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=(),
            allergies=("peanut",),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1200,
            daily_calorie_target_max=1400,
            variety_preference="balanced",
        )
        original_plan = planner.create_plan(request)

        replaced_plan = planner.replace_meal(request, original_plan, day_number=1, slot_number=1)

        self.assertEqual(original_plan.meals[0].recipe.title, "Target Bowl")
        self.assertEqual(replaced_plan.meals[0].recipe.title, "Swap Bowl")
        self.assertEqual(
            [(meal.day, meal.slot, meal.recipe.recipe_id) for meal in original_plan.meals[1:]],
            [(meal.day, meal.slot, meal.recipe.recipe_id) for meal in replaced_plan.meals[1:]],
        )
        self.assertLessEqual(replaced_plan.estimated_total_cost, request.weekly_budget)

    def test_replace_meal_still_respects_allergy_filters(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=ReplacementRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {
                    "base": GroceryProduct("base", 1.0, "item", 2.0),
                    "peanut ingredient": GroceryProduct("peanut ingredient", 1.0, "item", 2.0),
                }
            ),
        )
        request = PlannerRequest(
            weekly_budget=40.0,
            servings=2,
            cuisine_preferences=(),
            allergies=("peanut",),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=1200,
            daily_calorie_target_max=1400,
        )
        original_plan = planner.create_plan(request)

        replaced_plan = planner.replace_meal(request, original_plan, day_number=1, slot_number=1)

        self.assertNotEqual(replaced_plan.meals[0].recipe.title, "Peanut Swap")

    def test_replace_meal_keeps_same_recipe_when_no_alternative_is_viable(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=SingleRecipeProvider(),
            grocery_provider=FixedPriceGroceryProvider(
                {"safe base": GroceryProduct("safe base", 1.0, "item", 2.0)}
            ),
        )
        request = PlannerRequest(
            weekly_budget=30.0,
            servings=2,
            cuisine_preferences=("american",),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=("gluten-free",),
            pantry_staples=(),
            max_prep_time_minutes=30,
            meals_per_day=1,
            daily_calorie_target_min=650,
            daily_calorie_target_max=850,
        )
        original_plan = planner.create_plan(request)

        replaced_plan = planner.replace_meal(request, original_plan, day_number=1, slot_number=1)

        self.assertEqual(replaced_plan.meals[0].recipe.title, original_plan.meals[0].recipe.title)
        self.assertIn("same recipe was kept", replaced_plan.notes[-1].lower())


if __name__ == "__main__":
    unittest.main()
