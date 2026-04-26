import unittest

from pantry_pilot.models import GroceryLocation, GroceryProduct, PlannerRequest, Recipe, RecipeIngredient
from pantry_pilot.normalization import normalize_name
from pantry_pilot.planner import PlanningProgress, WeeklyMealPlanner
from pantry_pilot.providers import LocalRecipeProvider


class FixedPriceGroceryProvider:
    provider_name = "mock"

    def __init__(self, catalog: dict[str, GroceryProduct]) -> None:
        self._catalog = {normalize_name(name): product for name, product in catalog.items()}

    def lookup_locations(self, zip_code: str) -> tuple[GroceryLocation, ...]:
        return ()

    def get_product(self, ingredient_name: str) -> GroceryProduct | None:
        return self._catalog.get(normalize_name(ingredient_name))


class MondayLunchDiagnosisRecipeProvider(LocalRecipeProvider):
    def list_recipes(self) -> tuple[Recipe, ...]:
        recipes: list[Recipe] = []
        for index in range(120):
            recipes.append(
                Recipe(
                    recipe_id=f"lunch-main-{index}",
                    title=f"Chicken Rice Bowl {index}",
                    cuisine="american" if index % 2 == 0 else "mexican",
                    base_servings=2,
                    estimated_calories_per_serving=520 + (index % 40),
                    prep_time_minutes=20,
                    meal_types=("lunch", "dinner"),
                    diet_tags=frozenset({"gluten-free"}),
                    allergens=frozenset(),
                    ingredients=(
                        RecipeIngredient("chicken breast", 1.0, "lb"),
                        RecipeIngredient("rice", 1.0, "cup"),
                        RecipeIngredient("broccoli", 2.0, "cup"),
                    ),
                    steps=("Cook it.",),
                )
            )
        for index in range(20):
            recipes.append(
                Recipe(
                    recipe_id=f"lunch-side-{index}",
                    title=f"Broccoli Salad {index}",
                    cuisine="american",
                    base_servings=2,
                    estimated_calories_per_serving=140 + index,
                    prep_time_minutes=10,
                    meal_types=("lunch", "dinner"),
                    diet_tags=frozenset({"gluten-free"}),
                    allergens=frozenset(),
                    ingredients=(
                        RecipeIngredient("broccoli", 2.0, "cup"),
                        RecipeIngredient("olive oil", 1.0, "tbsp"),
                    ),
                    steps=("Mix it.",),
                )
            )
        return tuple(recipes)


class PhaseNMondayLunchDiagnosisTests(unittest.TestCase):
    def setUp(self) -> None:
        WeeklyMealPlanner.reset_request_cycle_offsets()
        self.request = PlannerRequest(
            weekly_budget=120.0,
            servings=2,
            cuisine_preferences=("american", "mexican"),
            allergies=(),
            excluded_ingredients=(),
            diet_restrictions=(),
            pantry_staples=("olive oil",),
            max_prep_time_minutes=30,
            meals_per_day=2,
            meal_structure=("lunch", "dinner"),
            daily_calorie_target_min=1600,
            daily_calorie_target_max=2200,
            variety_preference="balanced",
            leftovers_mode="off",
        )
        self.provider = MondayLunchDiagnosisRecipeProvider()
        self.grocery_provider = FixedPriceGroceryProvider(
            {
                "chicken breast": GroceryProduct("chicken breast", 1.0, "lb", 3.0),
                "rice": GroceryProduct("rice", 1.0, "cup", 0.8),
                "broccoli": GroceryProduct("broccoli", 2.0, "cup", 1.0),
            }
        )

    def test_intra_slot_progress_updates_report_candidate_batches(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=self.provider,
            grocery_provider=self.grocery_provider,
            same_recipe_weekly_cap=7,
            selection_profiling_enabled=True,
        )
        updates: list[PlanningProgress] = []
        planner.set_progress_callback(updates.append)

        candidates = planner.filter_recipes(self.request)
        pantry_inventory = planner._normalized_pantry_inventory(self.request)
        planner._warm_recipe_feature_caches(candidates, self.request)
        slot_groups = planner._slot_recipe_groups(candidates, self.request, 1)
        planner._set_active_slot_progress(label="Planning Monday lunch", completed=1, total=17)
        outcome = planner._best_choice(
            all_candidates=candidates,
            candidates=slot_groups.mains,
            request=self.request,
            pantry_inventory=pantry_inventory,
            variety_profile=planner._variety_profile(self.request),
            purchased_quantities={},
            meals=[],
            day_number=1,
            slot_number=1,
            current_total=0.0,
            request_cycle_offset=planner._next_request_cycle_offset(self.request),
            candidate_role="main",
            anchor_recipe=None,
            enforce_repeat_cap=True,
        )

        self.assertIsNotNone(outcome)
        batch_updates = [
            update
            for update in updates
            if update.stage == "selection"
            and update.label == "Planning Monday lunch"
            and "hard constraints" in update.detail.lower()
        ]
        self.assertGreaterEqual(len(batch_updates), 2)
        self.assertTrue(any("50/" in update.detail or "100/" in update.detail for update in batch_updates))
        self.assertGreater(outcome.timing.total_seconds, 0.0)

    def test_average_slot_calories_cache_avoids_repeated_slot_group_scans(self) -> None:
        planner = WeeklyMealPlanner(
            recipe_provider=self.provider,
            grocery_provider=self.grocery_provider,
        )
        candidates = planner.filter_recipes(self.request)
        call_counter = {"count": 0}
        original = planner._slot_recipe_groups

        def counted_slot_groups(*args, **kwargs):
            call_counter["count"] += 1
            return original(*args, **kwargs)

        planner._slot_recipe_groups = counted_slot_groups  # type: ignore[method-assign]

        first = planner._average_slot_calories(candidates, self.request, 2, self.request.servings)
        second = planner._average_slot_calories(candidates, self.request, 2, self.request.servings)

        self.assertEqual(first, second)
        self.assertEqual(call_counter["count"], 1)


if __name__ == "__main__":
    unittest.main()
