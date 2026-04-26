from __future__ import annotations

import hashlib
import math
import time
from dataclasses import dataclass
from typing import Iterable

from pantry_pilot.ingredient_catalog import convert_ingredient_unit_quantity
from pantry_pilot.models import MealPlan, PersonalNutritionTargets, PlannedMeal, PlannerRequest, Recipe, ShoppingListItem
from pantry_pilot.normalization import normalize_ingredient_name, normalize_name, normalize_unit
from pantry_pilot.nutrition import lookup_ingredient_guidance
from pantry_pilot.personal_targets import targets_from_manual_calorie_range
from pantry_pilot.providers import GroceryProvider, LocalRecipeProvider, MockGroceryProvider


DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SLOT_LABELS = {
    1: ("meal",),
    2: ("breakfast", "dinner"),
    3: ("breakfast", "lunch", "dinner"),
}
LOW_SIGNAL_INGREDIENTS = frozenset(
    {
        "olive oil",
        "garlic",
        "onion",
        "lemon",
        "lime",
        "vegetable broth",
        "cinnamon",
        "honey",
    }
)
MEAL_STYLE_KEYWORDS = frozenset(
    {
        "bowl",
        "salad",
        "toast",
        "soup",
        "skillet",
        "pasta",
        "stir-fry",
        "scramble",
        "parfait",
        "chili",
        "curry",
        "stuffed",
        "fried",
        "oatmeal",
    }
)
NON_MEAL_TITLE_KEYWORDS = frozenset(
    {
        "aioli",
        "condiment",
        "condiments",
        "dip",
        "dips",
        "dressing",
        "dressings",
        "gravy",
        "guacamole",
        "marinade",
        "marinades",
        "relish",
        "salsa",
        "sauce",
        "sauces",
        "snack",
        "snacks",
        "spread",
        "spreads",
        "syrup",
        "topping",
    }
)
HARD_NON_MEAL_TITLE_KEYWORDS = frozenset(
    {
        "condiment",
        "condiments",
        "dip",
        "dips",
        "dressing",
        "dressings",
        "guacamole",
        "marinade",
        "marinades",
        "relish",
        "salsa",
        "sauce",
        "sauces",
        "snack",
        "snacks",
        "spread",
        "spreads",
        "syrup",
        "topping",
    }
)
SUBSTANTIAL_MEAL_KEYWORDS = frozenset(
    {
        "bake",
        "bowl",
        "breakfast",
        "burger",
        "burrito",
        "casserole",
        "chicken",
        "chili",
        "curry",
        "dinner",
        "egg",
        "eggs",
        "frittata",
        "lunch",
        "meatball",
        "meatballs",
        "omelet",
        "omelette",
        "pancake",
        "pancakes",
        "pasta",
        "plate",
        "pizza",
        "roast",
        "salad",
        "sandwich",
        "scramble",
        "skillet",
        "soup",
        "stew",
        "stir fry",
        "stuffed",
        "taco",
        "toast",
        "wrap",
    }
)
NON_MEAL_LUNCH_DINNER_KEYWORDS = frozenset(
    {
        "bar",
        "bars",
        "beverage",
        "brownie",
        "brownies",
        "cake",
        "cakes",
        "candy",
        "candied",
        "cocktail",
        "cookie",
        "cookies",
        "crisp",
        "dessert",
        "desserts",
        "doughnut",
        "doughnuts",
        "donut",
        "donuts",
        "drink",
        "drinks",
        "fudge",
        "ice cream",
        "jam",
        "jelly",
        "juice",
        "lemonade",
        "limeade",
        "marmalade",
        "muffin",
        "muffins",
        "pie",
        "pies",
        "pudding",
        "punch",
        "sherbet",
        "smoothie",
        "sorbet",
        "water ice",
        "bread",
    }
)
SIDE_TITLE_KEYWORDS = frozenset(
    {
        "beans",
        "fries",
        "greens",
        "pilaf",
        "potato",
        "potatoes",
        "rice",
        "salad",
        "slaw",
        "vegetable",
        "vegetables",
        "veggie",
        "veggies",
        "zucchini",
    }
)
BREAKFAST_TITLE_KEYWORDS = frozenset(
    {
        "breakfast",
        "eggs",
        "frittata",
        "granola",
        "hash",
        "oatmeal",
        "omelet",
        "omelette",
        "pancake",
        "pancakes",
        "scramble",
        "toast",
        "waffle",
        "waffles",
        "yogurt",
    }
)
PROTEIN_SUPPORT_INGREDIENTS = frozenset(
    {
        "black beans",
        "cheddar cheese",
        "chicken",
        "chicken breast",
        "chickpeas",
        "eggs",
        "feta",
        "ground beef",
        "ground turkey",
        "lentils",
        "mozzarella cheese",
        "parmesan",
        "peanut butter",
        "tofu",
        "yogurt",
    }
)
VEGETABLE_SUPPORT_INGREDIENTS = frozenset(
    {
        "avocado",
        "bell pepper",
        "broccoli",
        "carrot",
        "celery",
        "cucumber",
        "green onion",
        "mushroom",
        "onion",
        "spinach",
        "tomato",
        "zucchini",
    }
)
CARB_SUPPORT_INGREDIENTS = frozenset(
    {
        "black beans",
        "bread",
        "chickpeas",
        "corn",
        "flour tortillas",
        "lentils",
        "pasta",
        "potato",
        "rice",
        "rolled oats",
    }
)
STARCH_PATTERN_INGREDIENTS = frozenset(
    {
        "bread",
        "corn",
        "flour tortillas",
        "pasta",
        "potato",
        "rice",
        "rolled oats",
    }
)


@dataclass
class AggregatedIngredient:
    quantity: float
    unit: str


@dataclass(frozen=True)
class CostEstimate:
    total_cost: float
    unknown_item_count: int


@dataclass(frozen=True)
class PurchaseDecision:
    packages: int
    purchased_quantity: float
    carryover_used_quantity: float
    consumed_purchase_quantity: float
    leftover_quantity_remaining: float
    cost: float | None


@dataclass(frozen=True)
class VarietyProfile:
    same_recipe_weekly_cap: int
    repetition_penalty: float
    slot_repetition_penalty: float
    recent_repeat_penalty: float
    cuisine_repetition_penalty: float
    recent_cuisine_penalty: float
    near_duplicate_penalty: float
    calorie_target_weight: float
    budget_guardrail_weight: float
    leftovers_bonus: float
    protein_variety_bonus: float
    produce_variety_bonus: float
    repeated_starch_penalty: float
    repeated_meal_structure_penalty: float
    repeated_anchor_pattern_penalty: float
    side_diversity_bonus: float
    repeated_side_pairing_penalty: float


@dataclass(frozen=True)
class CandidateDeliberation:
    recipe: Recipe
    candidate_role: str
    incremental_cost: float
    within_slot_budget: bool
    stage_scores: tuple[tuple[str, float], ...]
    reasons: tuple[str, ...]
    final_score: float
    repeat_count: int
    slot_repeat_count: int
    recent_repeat_count: int
    cuisine_repeat_count: int
    recent_cuisine_count: int
    near_duplicate_penalty: float
    pantry_match_count: int
    daily_state_before: DailyNutrientState | None
    daily_state_after: DailyNutrientState | None
    daily_deficits_before: DailyNutrientDeficits | None
    daily_deficits_after: DailyNutrientDeficits | None
    sort_key: tuple[float | int | str, ...]


@dataclass(frozen=True)
class MealSelectionDiagnostic:
    day: int
    slot_number: int
    slot_label: str
    meal_role: str
    selected_title: str
    hard_constraint_count: int
    role_gate_count: int
    diversity_peer_count: int
    used_repeat_fallback: bool
    runner_up_title: str | None
    runner_up_margin: float | None
    stage_scores: tuple[tuple[str, float], ...]
    reasons: tuple[str, ...]
    daily_state_before: DailyNutrientState | None = None
    daily_state_after: DailyNutrientState | None = None
    daily_deficits_before: DailyNutrientDeficits | None = None
    daily_deficits_after: DailyNutrientDeficits | None = None
    anchor_composition_profile: MealCompositionProfile | None = None
    selected_composition_profile: MealCompositionProfile | None = None
    runner_up_loss_reasons: tuple[str, ...] = ()


@dataclass(frozen=True)
class SelectionOutcome:
    selected: CandidateDeliberation
    hard_constraint_count: int
    role_gate_count: int
    diversity_peer_count: int
    runner_up_title: str | None
    runner_up_margin: float | None
    timing: "ChoiceTimingBreakdown"
    runner_up: CandidateDeliberation | None = None


@dataclass(frozen=True)
class ChoiceTimingBreakdown:
    candidate_role: str
    candidate_count: int
    viable_candidate_count: int
    role_gated_candidate_count: int
    hard_constraint_seconds: float
    role_gating_seconds: float
    candidate_ranking_seconds: float
    weekly_balance_seconds: float
    personal_target_seconds: float
    pantry_cost_seconds: float
    calorie_projection_seconds: float
    diagnostics_seconds: float = 0.0
    total_seconds: float = 0.0


@dataclass
class ChoiceTimingAccumulator:
    candidate_role: str
    candidate_count: int
    viable_candidate_count: int = 0
    role_gated_candidate_count: int = 0
    hard_constraint_seconds: float = 0.0
    role_gating_seconds: float = 0.0
    candidate_ranking_seconds: float = 0.0
    weekly_balance_seconds: float = 0.0
    personal_target_seconds: float = 0.0
    pantry_cost_seconds: float = 0.0
    calorie_projection_seconds: float = 0.0
    diagnostics_seconds: float = 0.0
    total_seconds: float = 0.0

    def freeze(self) -> ChoiceTimingBreakdown:
        return ChoiceTimingBreakdown(
            candidate_role=self.candidate_role,
            candidate_count=self.candidate_count,
            viable_candidate_count=self.viable_candidate_count,
            role_gated_candidate_count=self.role_gated_candidate_count,
            hard_constraint_seconds=round(self.hard_constraint_seconds, 4),
            role_gating_seconds=round(self.role_gating_seconds, 4),
            candidate_ranking_seconds=round(self.candidate_ranking_seconds, 4),
            weekly_balance_seconds=round(self.weekly_balance_seconds, 4),
            personal_target_seconds=round(self.personal_target_seconds, 4),
            pantry_cost_seconds=round(self.pantry_cost_seconds, 4),
            calorie_projection_seconds=round(self.calorie_projection_seconds, 4),
            diagnostics_seconds=round(self.diagnostics_seconds, 4),
            total_seconds=round(self.total_seconds, 4),
        )


@dataclass(frozen=True)
class MealBalanceScore:
    total: float
    components: frozenset[str]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class WeeklyVarietyScore:
    total: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class PersonalTargetScore:
    total: float
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class DailyNutrientState:
    calories: float
    protein_grams: float
    carbs_grams: float
    fat_grams: float
    produce_support: float
    grains_starches_support: float
    dairy_support: float


@dataclass(frozen=True)
class DailyNutrientDeficits:
    calories_below_min: float
    calories_above_max: float
    protein_grams: float
    carbs_grams: float
    fat_grams: float
    produce_support: float
    grains_starches_support: float
    dairy_support: float


@dataclass(frozen=True)
class MealCompositionProfile:
    protein_support: float
    vegetable_support: float
    starch_support: float
    dairy_support: float
    dominant_component: str
    heaviness: str
    density_score: float
    components: frozenset[str]


@dataclass(frozen=True)
class MealGuidanceProfile:
    food_group_tags: frozenset[str]
    component_tags: frozenset[str]


@dataclass(frozen=True)
class PlanningProgress:
    stage: str
    label: str
    completed: int
    total: int
    percent: float
    detail: str = ""


@dataclass(frozen=True)
class SlotSelectionDiagnostics:
    day: int
    slot_number: int
    slot_label: str
    slot_match_count: int
    reasonable_count: int
    calorie_supported_count: int
    price_supported_count: int
    under_budget_count: int
    under_cap_count: int
    rejection_counts: tuple[tuple[str, int], ...]
    chosen_title: str | None
    used_repeat_fallback: bool


@dataclass(frozen=True)
class PlanSelectionDiagnostics:
    slot_diagnostics: tuple[SlotSelectionDiagnostics, ...]
    top_rejection_reasons: tuple[tuple[str, int], ...]
    forced_repeat_slots: int
    repeat_message_truthful: bool


@dataclass(frozen=True)
class SlotRecipeGroups:
    mains: tuple[Recipe, ...]
    sides: tuple[Recipe, ...]


class PlannerError(Exception):
    pass


class WeeklyMealPlanner:
    _request_cycle_offsets: dict[str, int] = {}

    def __init__(
        self,
        recipe_provider: LocalRecipeProvider | None = None,
        grocery_provider: GroceryProvider | None = None,
        carryover_inventory: dict[str, AggregatedIngredient] | None = None,
        pricing_source: str = "mock",
        selected_store: str = "",
        same_recipe_weekly_cap: int = 2,
        repetition_penalty: float = 4.0,
        slot_repetition_penalty: float = 2.5,
        recent_repeat_penalty: float = 1.5,
        pantry_preference_bonus: float = 0.35,
        budget_guardrail_weight: float = 1.2,
        balance_scoring_enabled: bool = True,
        meal_guidance_enabled: bool = True,
        week_balance_enabled: bool = True,
        selection_profiling_enabled: bool = False,
    ) -> None:
        self.recipe_provider = recipe_provider or LocalRecipeProvider()
        self.grocery_provider = grocery_provider or MockGroceryProvider()
        self.carryover_inventory = {
            normalize_ingredient_name(name): AggregatedIngredient(quantity=value.quantity, unit=normalize_unit(value.unit))
            for name, value in (carryover_inventory or {}).items()
            if value.quantity > 0
        }
        self.pricing_source = pricing_source
        self.selected_store = selected_store
        self.same_recipe_weekly_cap = same_recipe_weekly_cap
        self.repetition_penalty = repetition_penalty
        self.slot_repetition_penalty = slot_repetition_penalty
        self.recent_repeat_penalty = recent_repeat_penalty
        self.pantry_preference_bonus = pantry_preference_bonus
        self.budget_guardrail_weight = budget_guardrail_weight
        self.balance_scoring_enabled = balance_scoring_enabled
        self.meal_guidance_enabled = meal_guidance_enabled
        self.week_balance_enabled = week_balance_enabled
        self.selection_profiling_enabled = selection_profiling_enabled
        self._latest_selection_diagnostics: tuple[MealSelectionDiagnostic, ...] = ()
        self._progress_callback = None
        self._core_ingredient_names_cache: dict[str, frozenset[str]] = {}
        self._meal_style_markers_cache: dict[str, frozenset[str]] = {}
        self._meal_guidance_profile_cache: dict[str, MealGuidanceProfile] = {}
        self._meal_component_tags_cache: dict[str, frozenset[str]] = {}
        self._meal_composition_profile_cache: dict[tuple[str, int], MealCompositionProfile] = {}
        self._primary_protein_key_cache: dict[str, str | None] = {}
        self._produce_keys_cache: dict[str, frozenset[str]] = {}
        self._primary_starch_key_cache: dict[str, str | None] = {}
        self._meal_structure_pattern_key_cache: dict[str, str] = {}
        self._anchor_pattern_key_cache: dict[str, str] = {}
        self._recipe_role_cache: dict[tuple[str, str], str] = {}
        self._carryover_quantity_cache: dict[tuple[str, str], float] = {}
        self._unit_conversion_factor_cache: dict[tuple[str, str, str], float | None] = {}
        self._average_slot_calories_cache: dict[tuple[str, tuple[str, ...], int, int], float] = {}
        self._active_slot_progress_label: str | None = None
        self._active_slot_progress_completed = 0
        self._active_slot_progress_total = 1

    def set_progress_callback(self, callback) -> None:
        self._progress_callback = callback

    def create_plan(self, request: PlannerRequest) -> MealPlan:
        total_slots = 7 * request.meals_per_day
        progress_total = total_slots + 3
        self._average_slot_calories_cache.clear()
        self._report_progress("setup", "Loading candidates", 0, progress_total, "Reading and filtering recipes.")
        candidates = self._filter_recipes(request)
        if not candidates:
            raise PlannerError("No recipes match the current safety and planning filters.")

        self._latest_selection_diagnostics = ()
        pantry_inventory = self._normalized_pantry_inventory(request)
        self._validate_constraint_support(candidates, request, pantry_inventory)
        variety_profile = self._variety_profile(request)
        request_cycle_offset = self._next_request_cycle_offset(request)
        self._warm_recipe_feature_caches(candidates, request)
        self._report_progress("setup", "Candidates ready", 1, progress_total, f"{len(candidates)} safe candidates loaded.")
        purchased_quantities: dict[str, AggregatedIngredient] = {}
        meals: list[PlannedMeal] = []
        notes: list[str] = []
        forced_repeat_slots = 0
        selection_diagnostics: list[MealSelectionDiagnostic] = []

        for slot_index in range(total_slots):
            slot_number = (slot_index % request.meals_per_day) + 1
            day_number = (slot_index // request.meals_per_day) + 1
            slot_gathering_started_at = time.perf_counter()
            slot_recipe_groups = self._slot_recipe_groups(candidates, request, slot_number)
            slot_label_text = slot_label(request.meals_per_day, slot_number, request.meal_structure).lower()
            self._report_progress(
                "selection",
                f"Planning {day_name(day_number)} {slot_label_text}",
                slot_index + 1,
                progress_total,
                (
                    f"{len(slot_recipe_groups.mains)} main candidates, {len(slot_recipe_groups.sides)} side candidates. "
                    f"Candidate gathering {round(time.perf_counter() - slot_gathering_started_at, 2)}s."
                ),
            )
            self._set_active_slot_progress(
                label=f"Planning {day_name(day_number)} {slot_label_text}",
                completed=slot_index + 1,
                total=progress_total,
            )
            selected = self._select_recipe(
                all_candidates=candidates,
                candidate_groups=slot_recipe_groups,
                request=request,
                pantry_inventory=pantry_inventory,
                variety_profile=variety_profile,
                purchased_quantities=purchased_quantities,
                meals=meals,
                day_number=day_number,
                slot_number=slot_number,
                request_cycle_offset=request_cycle_offset,
            )
            if selected is None:
                self._clear_active_slot_progress()
                raise PlannerError("The planner could not build a full 7-day plan within the weekly budget.")

            recipe, incremental_cost, exceeded_cap, main_diagnostic = selected
            self._apply_recipe(purchased_quantities, recipe, request, pantry_inventory)
            if exceeded_cap:
                forced_repeat_slots += 1
            selection_diagnostics.append(main_diagnostic)
            meals.append(
                PlannedMeal(
                    day=day_number,
                    slot=slot_number,
                    recipe=recipe,
                    scaled_servings=request.servings,
                    incremental_cost=round(incremental_cost, 2),
                    consumed_cost=self._estimate_recipe_consumed_cost(recipe, request, pantry_inventory),
                    meal_role=self._recipe_role(recipe, slot_label_text),
                )
            )
            side_selection = self._select_side_recipe(
                all_candidates=candidates,
                candidate_groups=slot_recipe_groups,
                request=request,
                pantry_inventory=pantry_inventory,
                variety_profile=variety_profile,
                purchased_quantities=purchased_quantities,
                meals=meals,
                day_number=day_number,
                slot_number=slot_number,
            )
            if side_selection is not None:
                side_recipe, side_incremental_cost, side_diagnostic = side_selection
                self._apply_recipe(purchased_quantities, side_recipe, request, pantry_inventory)
                selection_diagnostics.append(side_diagnostic)
                meals.append(
                    PlannedMeal(
                        day=day_number,
                        slot=slot_number,
                        recipe=side_recipe,
                        scaled_servings=request.servings,
                        incremental_cost=round(side_incremental_cost, 2),
                        consumed_cost=self._estimate_recipe_consumed_cost(side_recipe, request, pantry_inventory),
                        meal_role="side",
                    )
                )
            self._clear_active_slot_progress()

        self._report_progress("finalize", "Building shopping list", total_slots + 2, progress_total, "Finalizing package purchases and totals.")
        final_cost = self._estimate_total_cost(purchased_quantities)
        shopping_list, total_cost = self._build_shopping_list(purchased_quantities)
        if final_cost.unknown_item_count:
            raise PlannerError(
                "The generated plan includes ingredients with unknown prices, so the weekly budget cannot be verified."
            )
        if total_cost > request.weekly_budget + 1e-9:
            raise PlannerError("The generated plan exceeds the weekly budget.")

        if forced_repeat_slots:
            notes.append(
                "Some recipes repeat more than the weekly cap because there were no other safe under-budget options for all 7 days."
            )
        if self.pricing_source == "kroger":
            if self.selected_store:
                notes.append(f"Using Kroger or Fry's prices from {self.selected_store}.")
            else:
                notes.append("Using Kroger or Fry's prices when available, with mock prices filling any gaps.")

        self._latest_selection_diagnostics = tuple(selection_diagnostics)
        self._report_progress("complete", "Plan ready", progress_total, progress_total, "Weekly plan completed.")
        return MealPlan(
            meals=tuple(meals),
            shopping_list=shopping_list,
            estimated_total_cost=round(total_cost, 2),
            notes=tuple(notes),
            pricing_source=self.pricing_source,
            selected_store=self.selected_store,
        )

    def filter_recipes(self, request: PlannerRequest) -> tuple[Recipe, ...]:
        return self._filter_recipes(request)

    def latest_selection_diagnostics(self) -> tuple[MealSelectionDiagnostic, ...]:
        return self._latest_selection_diagnostics

    def current_day_nutrient_state(
        self,
        meals: Iterable[PlannedMeal],
        day_number: int,
    ) -> DailyNutrientState:
        return self._current_day_state(list(meals), day_number)

    def day_nutrient_deficits(
        self,
        state: DailyNutrientState,
        request: PlannerRequest,
    ) -> DailyNutrientDeficits:
        return self._daily_nutrient_deficits(state, self._effective_daily_targets(request))

    def _report_progress(
        self,
        stage: str,
        label: str,
        completed: int,
        total: int,
        detail: str = "",
        fractional: float = 0.0,
    ) -> None:
        if self._progress_callback is None:
            return
        bounded_total = max(total, 1)
        bounded_completed = min(max(completed, 0), bounded_total)
        bounded_fractional = min(max(fractional, 0.0), 0.9999)
        self._progress_callback(
            PlanningProgress(
                stage=stage,
                label=label,
                completed=bounded_completed,
                total=bounded_total,
                percent=min((bounded_completed + bounded_fractional) / bounded_total, 1.0),
                detail=detail,
            )
        )

    def _set_active_slot_progress(self, *, label: str, completed: int, total: int) -> None:
        self._active_slot_progress_label = label
        self._active_slot_progress_completed = completed
        self._active_slot_progress_total = total

    def _clear_active_slot_progress(self) -> None:
        self._active_slot_progress_label = None
        self._active_slot_progress_completed = 0
        self._active_slot_progress_total = 1

    def _report_intra_slot_progress(
        self,
        *,
        candidate_role: str,
        stage_label: str,
        processed: int,
        total: int,
        survivors: int = 0,
        slot_fraction: float,
    ) -> None:
        if self._progress_callback is None or self._active_slot_progress_label is None:
            return
        if total <= 0:
            detail = f"{candidate_role.title()} {stage_label}."
        else:
            detail = (
                f"{candidate_role.title()} {stage_label}: {processed:,}/{total:,} candidates "
                f"processed, {survivors:,} still viable."
            )
        self._report_progress(
            "selection",
            self._active_slot_progress_label,
            self._active_slot_progress_completed,
            self._active_slot_progress_total,
            detail,
            fractional=slot_fraction,
        )

    def replace_meal(
        self,
        request: PlannerRequest,
        existing_plan: MealPlan,
        day_number: int,
        slot_number: int,
    ) -> MealPlan:
        ordered_meals = list(sorted(existing_plan.meals, key=lambda meal: (meal.day, meal.slot)))
        target_meal = next(
            (meal for meal in ordered_meals if meal.day == day_number and meal.slot == slot_number),
            None,
        )
        if target_meal is None:
            raise PlannerError("The selected meal could not be found in the current plan.")

        candidates = self._filter_recipes(request)
        if not candidates:
            raise PlannerError("No recipes match the current safety and planning filters.")

        pantry_inventory = self._normalized_pantry_inventory(request)
        variety_profile = self._variety_profile(request)
        fixed_meals = [meal for meal in ordered_meals if meal is not target_meal]
        fixed_quantities = self._quantities_for_meals(fixed_meals, request, pantry_inventory)
        slot_candidates = self._slot_recipe_groups(candidates, request, slot_number).mains

        replacement = self._select_replacement_recipe(
            slot_candidates,
            request,
            pantry_inventory,
            variety_profile,
            fixed_meals,
            fixed_quantities,
            day_number,
            slot_number,
            target_meal.recipe.title,
        )
        if replacement is None:
            raise PlannerError("No viable replacement meal fits the current week and budget constraints.")

        replaced_entries: list[tuple[int, int, Recipe]] = []
        for meal in ordered_meals:
            recipe = replacement if meal is target_meal else meal.recipe
            replaced_entries.append((meal.day, meal.slot, recipe))

        replacement_label = f"{day_name(day_number)} {slot_label(request.meals_per_day, slot_number, request.meal_structure).lower()}"
        notes = list(existing_plan.notes)
        if replacement.title == target_meal.recipe.title:
            notes.append(f"No alternative fit {replacement_label}, so the same recipe was kept.")
        else:
            notes.append(f"Replaced {replacement_label} with {replacement.title}.")
        return self._finalize_meal_plan(request, replaced_entries, tuple(notes))

    def _filter_recipes(self, request: PlannerRequest) -> tuple[Recipe, ...]:
        allergies = {normalize_name(value) for value in request.allergies}
        excluded = {normalize_ingredient_name(value) for value in request.excluded_ingredients}
        required_tags = {normalize_name(value) for value in request.diet_restrictions}

        filtered: list[Recipe] = []
        for recipe in self.recipe_provider.list_recipes():
            if recipe.allergens is None:
                continue
            recipe_allergens = {normalize_name(value) for value in recipe.allergens}
            if allergies & recipe_allergens:
                continue
            ingredient_names = {normalize_ingredient_name(item.name) for item in recipe.ingredients}
            if excluded & ingredient_names:
                continue
            recipe_tags = {normalize_name(value) for value in recipe.diet_tags}
            if required_tags and not required_tags.issubset(recipe_tags):
                continue
            if recipe.prep_time_minutes is not None and recipe.prep_time_minutes > request.max_prep_time_minutes:
                continue
            filtered.append(recipe)

        return tuple(sorted(filtered, key=lambda recipe: recipe.title))

    def _recipe_cache_key(self, recipe: Recipe) -> str:
        return recipe.recipe_id or recipe.title

    def _warm_recipe_feature_caches(self, recipes: tuple[Recipe, ...], request: PlannerRequest) -> None:
        desired_slots = tuple(
            normalize_name(value)
            for value in (request.meal_structure or SLOT_LABELS.get(request.meals_per_day, ("meal",)))
        )
        for recipe in recipes:
            self._core_ingredient_names(recipe)
            self._meal_style_markers(recipe)
            self._meal_guidance_profile(recipe)
            self._meal_component_tags(recipe)
            self._primary_protein_key(recipe)
            self._produce_keys(recipe)
            self._primary_starch_key(recipe)
            self._meal_structure_pattern_key(recipe)
            self._anchor_pattern_key(recipe)
            for desired_slot in desired_slots:
                self._recipe_role(recipe, desired_slot)

    def _select_recipe(
        self,
        *,
        all_candidates: tuple[Recipe, ...],
        candidate_groups: SlotRecipeGroups,
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
        variety_profile: VarietyProfile,
        purchased_quantities: dict[str, AggregatedIngredient],
        meals: list[PlannedMeal],
        day_number: int,
        slot_number: int,
        request_cycle_offset: int,
    ) -> tuple[Recipe, float, bool, MealSelectionDiagnostic] | None:
        current_total = self._estimate_total_cost(purchased_quantities).total_cost
        slot_candidates = candidate_groups.mains
        desired_slot = slot_label(request.meals_per_day, slot_number, request.meal_structure).lower()
        preferred_choice = self._best_choice(
            all_candidates=all_candidates,
            candidates=slot_candidates,
            request=request,
            pantry_inventory=pantry_inventory,
            variety_profile=variety_profile,
            purchased_quantities=purchased_quantities,
            meals=meals,
            day_number=day_number,
            slot_number=slot_number,
            current_total=current_total,
            request_cycle_offset=request_cycle_offset,
            candidate_role="main",
            anchor_recipe=None,
            enforce_repeat_cap=True,
        )
        if preferred_choice is not None:
            return (
                preferred_choice.selected.recipe,
                preferred_choice.selected.incremental_cost,
                False,
                self._build_selection_diagnostic(
                    preferred_choice,
                    day_number,
                    slot_number,
                    request,
                    used_repeat_fallback=False,
                    anchor_recipe=None,
                ),
            )
        fallback_choice = self._best_choice(
            all_candidates=all_candidates,
            candidates=slot_candidates,
            request=request,
            pantry_inventory=pantry_inventory,
            variety_profile=variety_profile,
            purchased_quantities=purchased_quantities,
            meals=meals,
            day_number=day_number,
            slot_number=slot_number,
            current_total=current_total,
            request_cycle_offset=request_cycle_offset,
            candidate_role="main",
            anchor_recipe=None,
            enforce_repeat_cap=False,
        )
        if fallback_choice is None:
            return None
        return (
            fallback_choice.selected.recipe,
            fallback_choice.selected.incremental_cost,
            True,
            self._build_selection_diagnostic(
                fallback_choice,
                day_number,
                slot_number,
                request,
                used_repeat_fallback=True,
                anchor_recipe=None,
            ),
        )

    def _slot_recipe_groups(
        self,
        candidates: tuple[Recipe, ...],
        request: PlannerRequest,
        slot_number: int,
    ) -> SlotRecipeGroups:
        effective_candidates = self._recipes_for_slot(candidates, request, slot_number)
        desired_slot = slot_label(request.meals_per_day, slot_number, request.meal_structure).lower()
        if desired_slot not in {"lunch", "dinner"}:
            return SlotRecipeGroups(mains=effective_candidates, sides=())
        mains = tuple(
            recipe
            for recipe in effective_candidates
            if self._recipe_role(recipe, desired_slot) in {"main", "breakfast_main"}
        )
        sides = tuple(
            recipe
            for recipe in effective_candidates
            if self._recipe_role(recipe, desired_slot) == "side"
        )
        return SlotRecipeGroups(mains=mains, sides=sides)

    def _select_side_recipe(
        self,
        *,
        all_candidates: tuple[Recipe, ...],
        candidate_groups: SlotRecipeGroups,
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
        variety_profile: VarietyProfile,
        purchased_quantities: dict[str, AggregatedIngredient],
        meals: list[PlannedMeal],
        day_number: int,
        slot_number: int,
    ) -> tuple[Recipe, float, MealSelectionDiagnostic] | None:
        desired_slot = slot_label(request.meals_per_day, slot_number, request.meal_structure).lower()
        if desired_slot not in {"lunch", "dinner"}:
            return None
        if not candidate_groups.sides:
            return None
        projected_day_calories = self._projected_day_calories(
            all_candidates,
            meals,
            None,
            request,
            day_number,
            slot_number,
        )
        if projected_day_calories >= request.daily_calorie_target_max:
            return None
        current_total = self._estimate_total_cost(purchased_quantities).total_cost
        current_penalty = self._calorie_target_penalty(
            projected_day_calories,
            request.daily_calorie_target_min,
            request.daily_calorie_target_max,
        )
        anchor_recipe = next(
            (
                meal.recipe
                for meal in reversed(meals)
                if meal.day == day_number and meal.slot == slot_number and meal.meal_role == "main"
            ),
            None,
        )
        side_choice = self._best_choice(
            all_candidates=all_candidates,
            candidates=candidate_groups.sides,
            request=request,
            pantry_inventory=pantry_inventory,
            variety_profile=variety_profile,
            purchased_quantities=purchased_quantities,
            meals=meals,
            day_number=day_number,
            slot_number=slot_number,
            current_total=current_total,
            request_cycle_offset=0,
            candidate_role="side",
            anchor_recipe=anchor_recipe,
            enforce_repeat_cap=False,
        )
        if side_choice is None:
            return None
        side_recipe = side_choice.selected.recipe
        incremental_cost = side_choice.selected.incremental_cost
        side_day_calories = self._projected_day_calories(
            all_candidates,
            meals,
            side_recipe,
            request,
            day_number,
            slot_number,
        )
        side_penalty = self._calorie_target_penalty(
            side_day_calories,
            request.daily_calorie_target_min,
            request.daily_calorie_target_max,
        )
        if side_day_calories > request.daily_calorie_target_max + 200:
            return None
        if side_penalty > current_penalty:
            return None
        return (
            side_recipe,
            incremental_cost,
            self._build_selection_diagnostic(
                side_choice,
                day_number,
                slot_number,
                request,
                used_repeat_fallback=False,
                anchor_recipe=anchor_recipe,
            ),
        )

    def _best_choice(
        self,
        *,
        all_candidates: tuple[Recipe, ...],
        candidates: Iterable[Recipe],
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
        variety_profile: VarietyProfile,
        purchased_quantities: dict[str, AggregatedIngredient],
        meals: list[PlannedMeal],
        day_number: int,
        slot_number: int,
        current_total: float,
        request_cycle_offset: int,
        candidate_role: str,
        anchor_recipe: Recipe | None,
        enforce_repeat_cap: bool,
    ) -> SelectionOutcome | None:
        candidate_pool = tuple(candidates)
        choice_timing = ChoiceTimingAccumulator(
            candidate_role=candidate_role,
            candidate_count=len(candidate_pool),
        )
        profile_choice = self.selection_profiling_enabled
        choice_started_at = time.perf_counter() if profile_choice else 0.0
        hard_constraint_candidates: list[CandidateDeliberation] = []
        desired_slot = slot_label(request.meals_per_day, slot_number, request.meal_structure).lower()
        progress_interval = 50 if len(candidate_pool) <= 1000 else 100
        if candidate_role == "main":
            loop_start_fraction = 0.08
            loop_width = 0.54
            role_gate_fraction = 0.7
            ranking_fraction = 0.78
        else:
            loop_start_fraction = 0.82
            loop_width = 0.1
            role_gate_fraction = 0.94
            ranking_fraction = 0.97

        for candidate_index, recipe in enumerate(candidate_pool, start=1):
            evaluation = self._evaluate_candidate(
                all_candidates=all_candidates,
                recipe=recipe,
                request=request,
                pantry_inventory=pantry_inventory,
                variety_profile=variety_profile,
                purchased_quantities=purchased_quantities,
                meals=meals,
                day_number=day_number,
                slot_number=slot_number,
                current_total=current_total,
                candidate_role=candidate_role,
                anchor_recipe=anchor_recipe,
                enforce_repeat_cap=enforce_repeat_cap,
                desired_slot=desired_slot,
                choice_timing=choice_timing if profile_choice else None,
            )
            if evaluation is None:
                if candidate_index % progress_interval == 0 or candidate_index == len(candidate_pool):
                    self._report_intra_slot_progress(
                        candidate_role=candidate_role,
                        stage_label="hard constraints",
                        processed=candidate_index,
                        total=len(candidate_pool),
                        survivors=len(hard_constraint_candidates),
                        slot_fraction=loop_start_fraction + (loop_width * (candidate_index / max(len(candidate_pool), 1))),
                    )
                continue
            hard_constraint_candidates.append(evaluation)
            choice_timing.viable_candidate_count = len(hard_constraint_candidates)
            if candidate_index % progress_interval == 0 or candidate_index == len(candidate_pool):
                self._report_intra_slot_progress(
                    candidate_role=candidate_role,
                    stage_label="hard constraints",
                    processed=candidate_index,
                    total=len(candidate_pool),
                    survivors=len(hard_constraint_candidates),
                    slot_fraction=loop_start_fraction + (loop_width * (candidate_index / max(len(candidate_pool), 1))),
                )

        if not hard_constraint_candidates:
            if profile_choice:
                choice_timing.total_seconds = time.perf_counter() - choice_started_at
            return None

        role_gate_started_at = time.perf_counter() if profile_choice else 0.0
        role_gated_candidates = tuple(
            evaluation
            for evaluation in hard_constraint_candidates
            if self._passes_candidate_role_gate(evaluation.recipe, desired_slot, candidate_role)
        )
        if profile_choice:
            choice_timing.role_gating_seconds += time.perf_counter() - role_gate_started_at
        choice_timing.role_gated_candidate_count = len(role_gated_candidates)
        self._report_intra_slot_progress(
            candidate_role=candidate_role,
            stage_label="role gating",
            processed=len(hard_constraint_candidates),
            total=len(hard_constraint_candidates),
            survivors=len(role_gated_candidates),
            slot_fraction=role_gate_fraction,
        )
        ranked_candidates = role_gated_candidates or tuple(hard_constraint_candidates)
        ranking_started_at = time.perf_counter() if profile_choice else 0.0
        ranked_candidates = tuple(sorted(ranked_candidates, key=lambda candidate: candidate.sort_key))
        if profile_choice:
            choice_timing.candidate_ranking_seconds += time.perf_counter() - ranking_started_at
        self._report_intra_slot_progress(
            candidate_role=candidate_role,
            stage_label="ranking",
            processed=len(ranked_candidates),
            total=len(ranked_candidates),
            survivors=len(ranked_candidates),
            slot_fraction=ranking_fraction,
        )
        selected_choice, peer_count = self._select_diverse_choice(
            ranked_candidates,
            request_cycle_offset,
        )
        runner_up = ranked_candidates[1] if len(ranked_candidates) > 1 else None
        runner_up_margin = None
        if runner_up is not None:
            runner_up_margin = round(selected_choice.final_score - runner_up.final_score, 4)
        selected_with_diversity = CandidateDeliberation(
            recipe=selected_choice.recipe,
            candidate_role=selected_choice.candidate_role,
            incremental_cost=selected_choice.incremental_cost,
            within_slot_budget=selected_choice.within_slot_budget,
            stage_scores=selected_choice.stage_scores + (("weekly-diversity-peer-count", float(peer_count)),),
            reasons=selected_choice.reasons,
            final_score=selected_choice.final_score,
            repeat_count=selected_choice.repeat_count,
            slot_repeat_count=selected_choice.slot_repeat_count,
            recent_repeat_count=selected_choice.recent_repeat_count,
            cuisine_repeat_count=selected_choice.cuisine_repeat_count,
            recent_cuisine_count=selected_choice.recent_cuisine_count,
            near_duplicate_penalty=selected_choice.near_duplicate_penalty,
            pantry_match_count=selected_choice.pantry_match_count,
            daily_state_before=selected_choice.daily_state_before,
            daily_state_after=selected_choice.daily_state_after,
            daily_deficits_before=selected_choice.daily_deficits_before,
            daily_deficits_after=selected_choice.daily_deficits_after,
            sort_key=selected_choice.sort_key,
        )
        if profile_choice:
            choice_timing.total_seconds = time.perf_counter() - choice_started_at
        return SelectionOutcome(
            selected=selected_with_diversity,
            hard_constraint_count=len(hard_constraint_candidates),
            role_gate_count=len(role_gated_candidates),
            diversity_peer_count=peer_count,
            runner_up_title=runner_up.recipe.title if runner_up is not None else None,
            runner_up_margin=runner_up_margin,
            runner_up=runner_up,
            timing=choice_timing.freeze(),
        )

    def _recipes_for_slot(
        self,
        candidates: tuple[Recipe, ...],
        request: PlannerRequest,
        slot_number: int,
    ) -> tuple[Recipe, ...]:
        desired_types = self._meal_structure(request)
        desired = desired_types[min(slot_number - 1, len(desired_types) - 1)]
        matching = self.slot_match_recipes(candidates, request, slot_number)
        if desired == "meal":
            return matching or candidates
        reasonable = self.slot_reasonable_recipes(candidates, request, slot_number)
        return reasonable or matching or candidates

    def slot_match_recipes(
        self,
        candidates: tuple[Recipe, ...],
        request: PlannerRequest,
        slot_number: int,
    ) -> tuple[Recipe, ...]:
        desired_types = self._meal_structure(request)
        desired = desired_types[min(slot_number - 1, len(desired_types) - 1)]
        if desired == "meal":
            return tuple(candidates)
        if desired == "lunch":
            return tuple(
                recipe
                for recipe in candidates
                if "lunch" in recipe.meal_types or "dinner" in recipe.meal_types
            )
        return tuple(recipe for recipe in candidates if desired in recipe.meal_types)

    def slot_reasonable_recipes(
        self,
        candidates: tuple[Recipe, ...],
        request: PlannerRequest,
        slot_number: int,
    ) -> tuple[Recipe, ...]:
        desired_types = self._meal_structure(request)
        desired = desired_types[min(slot_number - 1, len(desired_types) - 1)]
        matching = self.slot_match_recipes(candidates, request, slot_number)
        if desired == "meal":
            return matching
        return tuple(recipe for recipe in matching if self._is_reasonable_meal_for_slot(recipe, desired))

    def _meal_structure(self, request: PlannerRequest) -> tuple[str, ...]:
        if request.meal_structure:
            return tuple(normalize_name(value) for value in request.meal_structure)
        return SLOT_LABELS.get(request.meals_per_day, ("meal",))

    def _apply_recipe(
        self,
        quantities: dict[str, AggregatedIngredient],
        recipe: Recipe,
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
    ) -> None:
        scale = request.servings / recipe.base_servings
        for ingredient in recipe.ingredients:
            name = normalize_ingredient_name(ingredient.name)
            if name in pantry_inventory:
                continue
            scaled_quantity = ingredient.quantity * scale
            existing = quantities.get(name)
            if existing is None:
                quantities[name] = AggregatedIngredient(
                    quantity=scaled_quantity,
                    unit=ingredient.unit,
                )
            else:
                quantities[name] = AggregatedIngredient(
                    quantity=existing.quantity + scaled_quantity,
                    unit=existing.unit,
                )

    def _normalized_pantry_inventory(self, request: PlannerRequest) -> frozenset[str]:
        return frozenset(normalize_ingredient_name(value) for value in request.pantry_staples)

    def _variety_profile(self, request: PlannerRequest) -> VarietyProfile:
        preference = normalize_name(request.variety_preference) or "balanced"
        if preference == "low":
            profile = VarietyProfile(
                same_recipe_weekly_cap=self.same_recipe_weekly_cap + 1,
                repetition_penalty=self.repetition_penalty * 0.55,
                slot_repetition_penalty=self.slot_repetition_penalty * 0.55,
                recent_repeat_penalty=self.recent_repeat_penalty * 0.55,
                cuisine_repetition_penalty=0.45,
                recent_cuisine_penalty=0.2,
                near_duplicate_penalty=0.7,
                calorie_target_weight=0.85,
                budget_guardrail_weight=self.budget_guardrail_weight * 0.85,
                leftovers_bonus=0.55,
                protein_variety_bonus=0.95,
                produce_variety_bonus=0.7,
                repeated_starch_penalty=0.8,
                repeated_meal_structure_penalty=0.6,
                repeated_anchor_pattern_penalty=0.95,
                side_diversity_bonus=0.75,
                repeated_side_pairing_penalty=0.7,
            )
        elif preference == "high":
            profile = VarietyProfile(
                same_recipe_weekly_cap=max(1, self.same_recipe_weekly_cap - 1),
                repetition_penalty=self.repetition_penalty * 1.8,
                slot_repetition_penalty=self.slot_repetition_penalty * 1.8,
                recent_repeat_penalty=self.recent_repeat_penalty * 1.8,
                cuisine_repetition_penalty=1.2,
                recent_cuisine_penalty=0.8,
                near_duplicate_penalty=1.5,
                calorie_target_weight=1.15,
                budget_guardrail_weight=self.budget_guardrail_weight * 1.15,
                leftovers_bonus=0.15,
                protein_variety_bonus=1.55,
                produce_variety_bonus=1.15,
                repeated_starch_penalty=1.35,
                repeated_meal_structure_penalty=1.0,
                repeated_anchor_pattern_penalty=1.55,
                side_diversity_bonus=1.15,
                repeated_side_pairing_penalty=1.0,
            )
        else:
            profile = VarietyProfile(
                same_recipe_weekly_cap=self.same_recipe_weekly_cap,
                repetition_penalty=self.repetition_penalty * 1.2,
                slot_repetition_penalty=self.slot_repetition_penalty * 1.2,
                recent_repeat_penalty=self.recent_repeat_penalty * 1.2,
                cuisine_repetition_penalty=0.8,
                recent_cuisine_penalty=0.45,
                near_duplicate_penalty=1.05,
                calorie_target_weight=1.0,
                budget_guardrail_weight=self.budget_guardrail_weight,
                leftovers_bonus=0.35,
                protein_variety_bonus=1.25,
                produce_variety_bonus=0.95,
                repeated_starch_penalty=1.25,
                repeated_meal_structure_penalty=0.9,
                repeated_anchor_pattern_penalty=1.35,
                side_diversity_bonus=1.0,
                repeated_side_pairing_penalty=0.9,
            )
        return self._apply_leftovers_mode(profile, request.leftovers_mode)

    def _apply_leftovers_mode(self, profile: VarietyProfile, leftovers_mode: str) -> VarietyProfile:
        mode = normalize_name(leftovers_mode) or "off"
        if mode == "frequent":
            return VarietyProfile(
                same_recipe_weekly_cap=profile.same_recipe_weekly_cap + 2,
                repetition_penalty=profile.repetition_penalty * 0.45,
                slot_repetition_penalty=profile.slot_repetition_penalty * 0.55,
                recent_repeat_penalty=profile.recent_repeat_penalty * 0.6,
                cuisine_repetition_penalty=profile.cuisine_repetition_penalty * 0.75,
                recent_cuisine_penalty=profile.recent_cuisine_penalty * 0.8,
                near_duplicate_penalty=profile.near_duplicate_penalty * 0.7,
                calorie_target_weight=profile.calorie_target_weight,
                budget_guardrail_weight=profile.budget_guardrail_weight * 0.85,
                leftovers_bonus=1.0,
                protein_variety_bonus=profile.protein_variety_bonus * 0.75,
                produce_variety_bonus=profile.produce_variety_bonus * 0.85,
                repeated_starch_penalty=profile.repeated_starch_penalty * 0.7,
                repeated_meal_structure_penalty=profile.repeated_meal_structure_penalty * 0.7,
                repeated_anchor_pattern_penalty=profile.repeated_anchor_pattern_penalty * 0.65,
                side_diversity_bonus=profile.side_diversity_bonus * 0.8,
                repeated_side_pairing_penalty=profile.repeated_side_pairing_penalty * 0.75,
            )
        if mode == "moderate":
            return VarietyProfile(
                same_recipe_weekly_cap=profile.same_recipe_weekly_cap + 1,
                repetition_penalty=profile.repetition_penalty * 0.7,
                slot_repetition_penalty=profile.slot_repetition_penalty * 0.8,
                recent_repeat_penalty=profile.recent_repeat_penalty * 0.85,
                cuisine_repetition_penalty=profile.cuisine_repetition_penalty * 0.9,
                recent_cuisine_penalty=profile.recent_cuisine_penalty * 0.9,
                near_duplicate_penalty=profile.near_duplicate_penalty * 0.85,
                calorie_target_weight=profile.calorie_target_weight,
                budget_guardrail_weight=profile.budget_guardrail_weight * 0.95,
                leftovers_bonus=0.65,
                protein_variety_bonus=profile.protein_variety_bonus * 0.9,
                produce_variety_bonus=profile.produce_variety_bonus * 0.95,
                repeated_starch_penalty=profile.repeated_starch_penalty * 0.9,
                repeated_meal_structure_penalty=profile.repeated_meal_structure_penalty * 0.9,
                repeated_anchor_pattern_penalty=profile.repeated_anchor_pattern_penalty * 0.85,
                side_diversity_bonus=profile.side_diversity_bonus * 0.95,
                repeated_side_pairing_penalty=profile.repeated_side_pairing_penalty * 0.9,
            )
        return VarietyProfile(
            same_recipe_weekly_cap=1,
            repetition_penalty=profile.repetition_penalty,
            slot_repetition_penalty=profile.slot_repetition_penalty,
            recent_repeat_penalty=profile.recent_repeat_penalty,
            cuisine_repetition_penalty=profile.cuisine_repetition_penalty,
            recent_cuisine_penalty=profile.recent_cuisine_penalty,
            near_duplicate_penalty=profile.near_duplicate_penalty,
            calorie_target_weight=profile.calorie_target_weight,
            budget_guardrail_weight=profile.budget_guardrail_weight,
            leftovers_bonus=profile.leftovers_bonus,
            protein_variety_bonus=profile.protein_variety_bonus,
            produce_variety_bonus=profile.produce_variety_bonus,
            repeated_starch_penalty=profile.repeated_starch_penalty,
            repeated_meal_structure_penalty=profile.repeated_meal_structure_penalty,
            repeated_anchor_pattern_penalty=profile.repeated_anchor_pattern_penalty,
            side_diversity_bonus=profile.side_diversity_bonus,
            repeated_side_pairing_penalty=profile.repeated_side_pairing_penalty,
        )

    @classmethod
    def reset_request_cycle_offsets(cls) -> None:
        cls._request_cycle_offsets.clear()

    def _next_request_cycle_offset(self, request: PlannerRequest) -> int:
        request_key = self._request_cycle_key(request)
        offset = self._request_cycle_offsets.get(request_key, 0)
        self._request_cycle_offsets[request_key] = offset + 1
        return offset

    def _request_cycle_key(self, request: PlannerRequest) -> str:
        signature = repr(
            (
                request.weekly_budget,
                request.servings,
                tuple(sorted(normalize_name(value) for value in request.cuisine_preferences)),
                tuple(sorted(normalize_name(value) for value in request.allergies)),
                tuple(sorted(normalize_ingredient_name(value) for value in request.excluded_ingredients)),
                tuple(sorted(normalize_name(value) for value in request.diet_restrictions)),
                tuple(sorted(normalize_ingredient_name(value) for value in request.pantry_staples)),
                request.max_prep_time_minutes,
                request.meals_per_day,
                tuple(normalize_name(value) for value in request.meal_structure),
                normalize_name(request.pricing_mode),
                request.daily_calorie_target_min,
                request.daily_calorie_target_max,
                normalize_name(request.variety_preference),
                normalize_name(request.leftovers_mode),
                None if request.user_profile is None else (
                    request.user_profile.age_years,
                    normalize_name(request.user_profile.sex),
                    round(request.user_profile.height_cm, 2),
                    round(request.user_profile.weight_kg, 2),
                    normalize_name(request.user_profile.activity_level),
                    normalize_name(request.user_profile.planning_goal),
                ),
                None if request.personal_targets is None else (
                    request.personal_targets.estimated_daily_calories,
                    request.personal_targets.calorie_target_min,
                    request.personal_targets.calorie_target_max,
                    round(request.personal_targets.protein_target_min_grams, 1),
                    round(request.personal_targets.carbs_target_min_grams, 1),
                    round(request.personal_targets.fat_target_min_grams, 1),
                    round(request.personal_targets.produce_target_cups, 1),
                    round(request.personal_targets.grains_target_ounces, 1),
                    round(request.personal_targets.protein_foods_target_ounces, 1),
                    None if request.personal_targets.dairy_target_cups is None else round(request.personal_targets.dairy_target_cups, 1),
                ),
                self.pricing_source,
                self.selected_store,
                type(self.recipe_provider).__name__,
                getattr(self.recipe_provider, "processed_dataset_path", ""),
            )
        )
        return hashlib.sha256(signature.encode("utf-8")).hexdigest()

    def _select_diverse_choice(
        self,
        ranked_choices: tuple[CandidateDeliberation, ...],
        request_cycle_offset: int,
    ) -> tuple[CandidateDeliberation, int]:
        best_choice = ranked_choices[0]
        tied_choices = [
            choice
            for choice in ranked_choices
            if self._is_diversity_peer(choice, best_choice)
        ]
        choice_index = request_cycle_offset % len(tied_choices)
        return tied_choices[choice_index], len(tied_choices)

    def _is_diversity_peer(
        self,
        candidate: CandidateDeliberation,
        best: CandidateDeliberation,
    ) -> bool:
        candidate_stage_scores = dict(candidate.stage_scores)
        best_stage_scores = dict(best.stage_scores)
        return (
            candidate.within_slot_budget == best.within_slot_budget
            and candidate.candidate_role == best.candidate_role
            and abs(candidate.final_score - best.final_score) <= 0.8
            and abs(
                candidate_stage_scores.get("weekly-diversity-adjustment", 0.0)
                - best_stage_scores.get("weekly-diversity-adjustment", 0.0)
            )
            <= 0.45
            and abs(
                candidate_stage_scores.get("week-level-balance-adjustment", 0.0)
                - best_stage_scores.get("week-level-balance-adjustment", 0.0)
            )
            <= 0.45
            and abs(
                candidate_stage_scores.get("personal-target-adjustment", 0.0)
                - best_stage_scores.get("personal-target-adjustment", 0.0)
            )
            <= 0.45
            and abs(
                candidate_stage_scores.get("pantry-cost-adjustment", 0.0)
                - best_stage_scores.get("pantry-cost-adjustment", 0.0)
            )
            <= 0.45
            and abs(
                candidate_stage_scores.get("calorie-adjustment", 0.0)
                - best_stage_scores.get("calorie-adjustment", 0.0)
            )
            <= 0.3
        )

    def _runner_up_loss_reasons(
        self,
        selected: CandidateDeliberation,
        runner_up: CandidateDeliberation,
    ) -> tuple[str, ...]:
        selected_stage_scores = dict(selected.stage_scores)
        runner_up_stage_scores = dict(runner_up.stage_scores)
        reasons: list[str] = []
        if (
            selected_stage_scores.get("side-candidate-ranking", 0.0)
            - runner_up_stage_scores.get("side-candidate-ranking", 0.0)
        ) > 0.2:
            reasons.append("runner-up-lost:weaker-main-side-complement")
        if (
            selected_stage_scores.get("personal-target-adjustment", 0.0)
            - runner_up_stage_scores.get("personal-target-adjustment", 0.0)
        ) > 0.15:
            reasons.append("runner-up-lost:weaker-daily-target-fit")
        if (
            selected_stage_scores.get("week-level-balance-adjustment", 0.0)
            - runner_up_stage_scores.get("week-level-balance-adjustment", 0.0)
        ) > 0.15 or (
            selected_stage_scores.get("weekly-diversity-adjustment", 0.0)
            - runner_up_stage_scores.get("weekly-diversity-adjustment", 0.0)
        ) > 0.15:
            reasons.append("runner-up-lost:weaker-week-variety")
        if (
            selected_stage_scores.get("calorie-adjustment", 0.0)
            - runner_up_stage_scores.get("calorie-adjustment", 0.0)
        ) > 0.1:
            reasons.append("runner-up-lost:weaker-calorie-fit")
        for reason in selected.reasons:
            if reason.startswith(("complements-", "target:")) and reason not in runner_up.reasons:
                reasons.append(f"runner-up-missed:{reason}")
            if len(reasons) >= 4:
                break
        for reason in runner_up.reasons:
            if reason.startswith("penalty:") and reason not in selected.reasons:
                reasons.append(reason)
            if len(reasons) >= 5:
                break
        return tuple(reasons)

    def _passes_candidate_role_gate(self, recipe: Recipe, desired_slot: str, candidate_role: str) -> bool:
        if candidate_role == "side":
            return self._recipe_role(recipe, desired_slot) == "side"
        if desired_slot not in {"lunch", "dinner"}:
            return True
        return self._main_anchor_confidence(recipe, desired_slot) >= 0.7

    def _evaluate_candidate(
        self,
        *,
        all_candidates: tuple[Recipe, ...],
        recipe: Recipe,
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
        variety_profile: VarietyProfile,
        purchased_quantities: dict[str, AggregatedIngredient],
        meals: list[PlannedMeal],
        day_number: int,
        slot_number: int,
        current_total: float,
        candidate_role: str,
        anchor_recipe: Recipe | None,
        enforce_repeat_cap: bool,
        desired_slot: str,
        choice_timing: ChoiceTimingAccumulator | None = None,
    ) -> CandidateDeliberation | None:
        hard_constraint_started_at = time.perf_counter()
        if recipe.estimated_calories_per_serving is None:
            if choice_timing is not None:
                choice_timing.hard_constraint_seconds += time.perf_counter() - hard_constraint_started_at
            return None

        repeat_count = self._recipe_count(meals, recipe.title)
        if enforce_repeat_cap and repeat_count >= variety_profile.same_recipe_weekly_cap:
            if choice_timing is not None:
                choice_timing.hard_constraint_seconds += time.perf_counter() - hard_constraint_started_at
            return None
        if choice_timing is not None:
            choice_timing.hard_constraint_seconds += time.perf_counter() - hard_constraint_started_at

        pantry_cost_started_at = time.perf_counter()
        projected_quantities = {
            name: AggregatedIngredient(quantity=value.quantity, unit=value.unit)
            for name, value in purchased_quantities.items()
        }
        self._apply_recipe(projected_quantities, recipe, request, pantry_inventory)
        projected_total = self._estimate_total_cost(projected_quantities)
        if projected_total.unknown_item_count:
            if choice_timing is not None:
                choice_timing.pantry_cost_seconds += time.perf_counter() - pantry_cost_started_at
            return None
        if projected_total.total_cost > request.weekly_budget + 1e-9:
            if choice_timing is not None:
                choice_timing.pantry_cost_seconds += time.perf_counter() - pantry_cost_started_at
            return None
        if choice_timing is not None:
            choice_timing.pantry_cost_seconds += time.perf_counter() - pantry_cost_started_at

        incremental_cost = projected_total.total_cost - current_total
        pantry_match_count = self._pantry_match_count(recipe, pantry_inventory)
        slot_repeat_count = self._slot_recipe_count(meals, recipe.title, slot_number)
        recent_repeat_count = self._recent_repeat_count(meals, recipe.title)
        cuisine_repeat_count = self._cuisine_count(meals, recipe.cuisine)
        recent_cuisine_count = self._recent_cuisine_count(meals, recipe.cuisine)
        near_duplicate_penalty = self._near_duplicate_penalty(meals, recipe, day_number, slot_number)
        leftovers_score = self._leftovers_score(meals, recipe.title, slot_number)
        targets = self._effective_daily_targets(request)
        daily_state_before = self._current_day_state(meals, day_number)
        daily_state_after = self._projected_day_state(meals, recipe, request, day_number)
        daily_deficits_before = self._daily_nutrient_deficits(daily_state_before, targets)
        daily_deficits_after = self._daily_nutrient_deficits(daily_state_after, targets)
        calorie_projection_started_at = time.perf_counter()
        projected_day_calories = self._projected_day_calories(
            all_candidates,
            meals,
            recipe,
            request,
            day_number,
            slot_number,
        )
        if choice_timing is not None:
            choice_timing.calorie_projection_seconds += time.perf_counter() - calorie_projection_started_at
        calorie_penalty = self._calorie_target_penalty(
            projected_day_calories,
            request.daily_calorie_target_min,
            request.daily_calorie_target_max,
        )
        suggested_slot_budget = self._suggested_slot_budget(request, current_total, len(meals))
        within_slot_budget = incremental_cost <= suggested_slot_budget + 1e-9
        budget_pressure = self._budget_pressure_penalty(
            request,
            current_total,
            incremental_cost,
            len(meals),
        )
        ranking_started_at = time.perf_counter()
        balance_score = self._meal_balance_score(
            recipe,
            desired_slot,
            candidate_role,
            anchor_recipe,
        )
        if choice_timing is not None:
            choice_timing.candidate_ranking_seconds += time.perf_counter() - ranking_started_at
        weekly_balance_started_at = time.perf_counter()
        weekly_variety_score = self._weekly_variety_score(
            recipe=recipe,
            candidate_role=candidate_role,
            anchor_recipe=anchor_recipe,
            meals=meals,
            variety_profile=variety_profile,
        )
        if choice_timing is not None:
            choice_timing.weekly_balance_seconds += time.perf_counter() - weekly_balance_started_at
        personal_target_started_at = time.perf_counter()
        personal_target_score = self._personal_target_score(
            recipe=recipe,
            request=request,
            candidate_role=candidate_role,
            anchor_recipe=anchor_recipe,
            meals=meals,
            day_number=day_number,
            daily_state_before=daily_state_before,
            daily_state_after=daily_state_after,
            daily_deficits_before=daily_deficits_before,
            daily_deficits_after=daily_deficits_after,
        )
        if choice_timing is not None:
            choice_timing.personal_target_seconds += time.perf_counter() - personal_target_started_at
        anchor_confidence = self._main_anchor_confidence(recipe, desired_slot) if candidate_role == "main" else 0.0
        main_or_side_ranking = balance_score.total + (anchor_confidence * 2.2 if candidate_role == "main" else 0.0)
        diversity_adjustment = -(
            (repeat_count * variety_profile.repetition_penalty)
            + (slot_repeat_count * variety_profile.slot_repetition_penalty)
            + (recent_repeat_count * variety_profile.recent_repeat_penalty)
            + (cuisine_repeat_count * variety_profile.cuisine_repetition_penalty)
            + (recent_cuisine_count * variety_profile.recent_cuisine_penalty)
            + (near_duplicate_penalty * variety_profile.near_duplicate_penalty)
        ) + (leftovers_score * variety_profile.leftovers_bonus)
        pantry_cost_adjustment = (
            (pantry_match_count * self.pantry_preference_bonus)
            + self._cuisine_preference_bonus(recipe, request)
            - incremental_cost
            - (budget_pressure * variety_profile.budget_guardrail_weight)
        )
        calorie_adjustment = -(calorie_penalty * variety_profile.calorie_target_weight)
        final_score = (
            main_or_side_ranking
            + diversity_adjustment
            + weekly_variety_score.total
            + personal_target_score.total
            + pantry_cost_adjustment
            + calorie_adjustment
        )
        reasons = [
            f"stage:hard-constraints:pass",
            f"stage:role-gating:{'pass' if self._passes_candidate_role_gate(recipe, desired_slot, candidate_role) else 'fallback'}",
        ]
        reasons.extend(balance_score.reasons)
        reasons.extend(weekly_variety_score.reasons)
        reasons.extend(personal_target_score.reasons)
        if candidate_role == "main":
            reasons.append(f"anchor-confidence:{round(anchor_confidence, 3)}")
            if anchor_confidence >= 1.0:
                reasons.append("main-anchor:strong")
            elif anchor_confidence >= 0.7:
                reasons.append("main-anchor:acceptable")
            else:
                reasons.append("main-anchor:weak")
        if pantry_match_count:
            reasons.append("pantry-support")
        if self._cuisine_preference_bonus(recipe, request) > 0:
            reasons.append("preferred-cuisine")
        if repeat_count:
            reasons.append("weekly-repeat-pressure")
        if slot_repeat_count:
            reasons.append("slot-repeat-pressure")
        if recent_repeat_count:
            reasons.append("recent-repeat-pressure")
        if near_duplicate_penalty > 0:
            reasons.append("near-duplicate-pressure")
        if budget_pressure > 0:
            reasons.append("budget-pressure")
        if calorie_penalty > 0:
            reasons.append("calorie-alignment")

        sort_key = (
            0 if within_slot_budget else 1,
            round(-final_score, 4),
            round(budget_pressure, 4),
            round(calorie_penalty, 4),
            round(near_duplicate_penalty, 4),
            -leftovers_score,
            -pantry_match_count,
            repeat_count,
            slot_repeat_count,
            recent_repeat_count,
            cuisine_repeat_count,
            recent_cuisine_count,
            normalize_name(recipe.cuisine),
            recipe.title,
        )
        return CandidateDeliberation(
            recipe=recipe,
            candidate_role=candidate_role,
            incremental_cost=round(incremental_cost, 2),
            within_slot_budget=within_slot_budget,
            stage_scores=(
                ("hard-constraint-filter", 1.0),
                ("role-gating", 1.0 if self._passes_candidate_role_gate(recipe, desired_slot, candidate_role) else 0.0),
                ("main-candidate-ranking" if candidate_role == "main" else "side-candidate-ranking", round(main_or_side_ranking, 4)),
                ("weekly-diversity-adjustment", round(diversity_adjustment, 4)),
                ("week-level-balance-adjustment", round(weekly_variety_score.total, 4)),
                ("personal-target-adjustment", round(personal_target_score.total, 4)),
                ("pantry-cost-adjustment", round(pantry_cost_adjustment, 4)),
                ("calorie-adjustment", round(calorie_adjustment, 4)),
            ),
            reasons=tuple(reasons),
            final_score=round(final_score, 4),
            repeat_count=repeat_count,
            slot_repeat_count=slot_repeat_count,
            recent_repeat_count=recent_repeat_count,
            cuisine_repeat_count=cuisine_repeat_count,
            recent_cuisine_count=recent_cuisine_count,
            near_duplicate_penalty=near_duplicate_penalty,
            pantry_match_count=pantry_match_count,
            daily_state_before=daily_state_before,
            daily_state_after=daily_state_after,
            daily_deficits_before=daily_deficits_before,
            daily_deficits_after=daily_deficits_after,
            sort_key=sort_key,
        )

    def _build_selection_diagnostic(
        self,
        outcome: SelectionOutcome,
        day_number: int,
        slot_number: int,
        request: PlannerRequest,
        *,
        used_repeat_fallback: bool,
        anchor_recipe: Recipe | None = None,
    ) -> MealSelectionDiagnostic:
        evaluation = outcome.selected
        anchor_profile = None
        if anchor_recipe is not None:
            anchor_profile = self._meal_composition_profile(anchor_recipe, request.servings)
        runner_up_loss_reasons = ()
        if outcome.runner_up is not None:
            runner_up_loss_reasons = self._runner_up_loss_reasons(evaluation, outcome.runner_up)
        return MealSelectionDiagnostic(
            day=day_number,
            slot_number=slot_number,
            slot_label=slot_label(request.meals_per_day, slot_number, request.meal_structure).lower(),
            meal_role=evaluation.candidate_role,
            selected_title=evaluation.recipe.title,
            hard_constraint_count=outcome.hard_constraint_count,
            role_gate_count=outcome.role_gate_count,
            diversity_peer_count=outcome.diversity_peer_count,
            used_repeat_fallback=used_repeat_fallback,
            runner_up_title=outcome.runner_up_title,
            runner_up_margin=outcome.runner_up_margin,
            stage_scores=evaluation.stage_scores,
            reasons=evaluation.reasons,
            daily_state_before=evaluation.daily_state_before,
            daily_state_after=evaluation.daily_state_after,
            daily_deficits_before=evaluation.daily_deficits_before,
            daily_deficits_after=evaluation.daily_deficits_after,
            anchor_composition_profile=anchor_profile,
            selected_composition_profile=self._meal_composition_profile(evaluation.recipe, request.servings),
            runner_up_loss_reasons=runner_up_loss_reasons,
        )
    
    def _main_anchor_confidence(self, recipe: Recipe, desired_slot: str) -> float:
        if desired_slot not in {"lunch", "dinner"}:
            return 1.0
        recipe_role = self._recipe_role(recipe, desired_slot)
        components = self._meal_component_tags(recipe)
        normalized_title = normalize_name(recipe.title)
        core_ingredient_count = len(self._core_ingredient_names(recipe))

        confidence = 0.0
        if recipe_role == "main":
            confidence += 0.55
        elif recipe_role == "side":
            confidence -= 0.45
        if len(components) >= 2:
            confidence += 0.45
        elif len(components) == 1:
            confidence -= 0.05
        else:
            confidence -= 0.55
        if "protein" in components:
            confidence += 0.25
        if "protein" not in components and "vegetable" not in components:
            confidence -= 0.55
        if components == frozenset({"carb"}):
            confidence -= 0.4
        if any(keyword in normalized_title for keyword in SUBSTANTIAL_MEAL_KEYWORDS):
            confidence += 0.2
        if any(keyword in normalized_title for keyword in NON_MEAL_LUNCH_DINNER_KEYWORDS):
            confidence -= 0.65
        if core_ingredient_count >= 3:
            confidence += 0.2
        elif core_ingredient_count <= 1:
            confidence -= 0.35
        return round(confidence, 3)

    def _pantry_match_count(self, recipe: Recipe, pantry_inventory: frozenset[str]) -> int:
        return sum(
            1
            for ingredient in recipe.ingredients
            if normalize_ingredient_name(ingredient.name) in pantry_inventory
        )

    def _quantities_for_meals(
        self,
        meals: list[PlannedMeal],
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
    ) -> dict[str, AggregatedIngredient]:
        quantities: dict[str, AggregatedIngredient] = {}
        for meal in meals:
            self._apply_recipe(quantities, meal.recipe, request, pantry_inventory)
        return quantities

    def _select_replacement_recipe(
        self,
        slot_candidates: tuple[Recipe, ...],
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
        variety_profile: VarietyProfile,
        fixed_meals: list[PlannedMeal],
        fixed_quantities: dict[str, AggregatedIngredient],
        day_number: int,
        slot_number: int,
        original_title: str,
    ) -> Recipe | None:
        alternative_candidates = tuple(
            recipe for recipe in slot_candidates if recipe.title != original_title
        )
        replacement = self._best_replacement_choice(
            alternative_candidates,
            request,
            pantry_inventory,
            variety_profile,
            fixed_meals,
            fixed_quantities,
            day_number,
            slot_number,
        )
        if replacement is not None:
            return replacement
        return self._best_replacement_choice(
            slot_candidates,
            request,
            pantry_inventory,
            variety_profile,
            fixed_meals,
            fixed_quantities,
            day_number,
            slot_number,
        )

    def _best_replacement_choice(
        self,
        candidates: tuple[Recipe, ...],
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
        variety_profile: VarietyProfile,
        fixed_meals: list[PlannedMeal],
        fixed_quantities: dict[str, AggregatedIngredient],
        day_number: int,
        slot_number: int,
    ) -> Recipe | None:
        fixed_total = self._estimate_total_cost(fixed_quantities)
        day_fixed_calories = sum(
            self._meal_calories(meal.recipe, meal.scaled_servings)
            for meal in fixed_meals
            if meal.day == day_number
        )
        desired_slot = slot_label(request.meals_per_day, slot_number, request.meal_structure).lower()
        best_choice: tuple[tuple[float, float, int, int, int, int, int, int, str], Recipe] | None = None

        for recipe in candidates:
            if recipe.estimated_calories_per_serving is None:
                continue
            projected_quantities = {
                name: AggregatedIngredient(quantity=value.quantity, unit=value.unit)
                for name, value in fixed_quantities.items()
            }
            self._apply_recipe(projected_quantities, recipe, request, pantry_inventory)
            projected_total = self._estimate_total_cost(projected_quantities)
            if projected_total.unknown_item_count:
                continue
            if projected_total.total_cost > request.weekly_budget + 1e-9:
                continue

            incremental_cost = projected_total.total_cost - fixed_total.total_cost
            pantry_match_count = self._pantry_match_count(recipe, pantry_inventory)
            repeat_count = self._recipe_count(fixed_meals, recipe.title)
            slot_repeat_count = self._slot_recipe_count(fixed_meals, recipe.title, slot_number)
            nearby_repeat_count = self._neighbor_recipe_count(fixed_meals, recipe.title, day_number, slot_number)
            cuisine_repeat_count = self._cuisine_count(fixed_meals, recipe.cuisine)
            nearby_cuisine_count = self._neighbor_cuisine_count(fixed_meals, recipe.cuisine, day_number, slot_number)
            near_duplicate_penalty = self._near_duplicate_penalty(
                fixed_meals,
                recipe,
                day_number,
                slot_number,
            )
            leftovers_score = self._leftovers_score(fixed_meals, recipe.title, slot_number)
            projected_day_calories = day_fixed_calories + self._meal_calories(recipe, request.servings)
            calorie_penalty = self._calorie_target_penalty(
                projected_day_calories,
                request.daily_calorie_target_min,
                request.daily_calorie_target_max,
            )
            suggested_slot_budget = self._suggested_slot_budget(request, fixed_total.total_cost, len(fixed_meals))
            within_slot_budget = incremental_cost <= suggested_slot_budget + 1e-9
            budget_pressure = self._budget_pressure_penalty(
                request,
                fixed_total.total_cost,
                incremental_cost,
                len(fixed_meals),
            )
            balance_score = self._meal_balance_score(
                recipe,
                desired_slot,
                "main",
                None,
            )
            effective_cost = incremental_cost
            effective_cost -= pantry_match_count * self.pantry_preference_bonus
            effective_cost -= balance_score.total
            effective_cost += repeat_count * variety_profile.repetition_penalty
            effective_cost += slot_repeat_count * variety_profile.slot_repetition_penalty
            effective_cost += nearby_repeat_count * variety_profile.recent_repeat_penalty
            effective_cost += cuisine_repeat_count * variety_profile.cuisine_repetition_penalty
            effective_cost += nearby_cuisine_count * variety_profile.recent_cuisine_penalty
            effective_cost += near_duplicate_penalty * variety_profile.near_duplicate_penalty
            effective_cost += calorie_penalty * variety_profile.calorie_target_weight
            effective_cost += budget_pressure * variety_profile.budget_guardrail_weight
            effective_cost -= leftovers_score * variety_profile.leftovers_bonus
            sort_key = (
                0 if within_slot_budget else 1,
                round(effective_cost, 4),
                round(near_duplicate_penalty, 4),
                round(calorie_penalty, 4),
                round(budget_pressure, 4),
                -leftovers_score,
                -pantry_match_count,
                repeat_count,
                slot_repeat_count,
                nearby_repeat_count,
                cuisine_repeat_count,
                nearby_cuisine_count,
                recipe.title,
            )
            if best_choice is None or sort_key < best_choice[0]:
                best_choice = (sort_key, recipe)

        if best_choice is None:
            return None
        return best_choice[1]

    def _finalize_meal_plan(
        self,
        request: PlannerRequest,
        ordered_entries: list[tuple[int, int, Recipe]],
        notes: tuple[str, ...],
    ) -> MealPlan:
        pantry_inventory = self._normalized_pantry_inventory(request)
        purchased_quantities: dict[str, AggregatedIngredient] = {}
        meals: list[PlannedMeal] = []

        for day_number, slot_number, recipe in sorted(ordered_entries, key=lambda entry: (entry[0], entry[1])):
            current_total = self._estimate_total_cost(purchased_quantities)
            self._apply_recipe(purchased_quantities, recipe, request, pantry_inventory)
            projected_total = self._estimate_total_cost(purchased_quantities)
            meals.append(
                PlannedMeal(
                    day=day_number,
                    slot=slot_number,
                    recipe=recipe,
                    scaled_servings=request.servings,
                    incremental_cost=round(projected_total.total_cost - current_total.total_cost, 2),
                    consumed_cost=self._estimate_recipe_consumed_cost(recipe, request, pantry_inventory),
                    meal_role=self._recipe_role(
                        recipe,
                        slot_label(request.meals_per_day, slot_number, request.meal_structure).lower(),
                    ),
                )
            )

        final_cost = self._estimate_total_cost(purchased_quantities)
        shopping_list, total_cost = self._build_shopping_list(purchased_quantities)
        if final_cost.unknown_item_count:
            raise PlannerError(
                "The generated plan includes ingredients with unknown prices, so the weekly budget cannot be verified."
            )
        if total_cost > request.weekly_budget + 1e-9:
            raise PlannerError("The generated plan exceeds the weekly budget.")
        return MealPlan(
            meals=tuple(meals),
            shopping_list=shopping_list,
            estimated_total_cost=round(total_cost, 2),
            notes=notes,
            pricing_source=self.pricing_source,
            selected_store=self.selected_store,
        )

    def _meal_calories(self, recipe: Recipe, servings: int) -> int:
        if recipe.estimated_calories_per_serving is None:
            return 0
        return recipe.estimated_calories_per_serving * servings

    def _current_day_calories(self, meals: list[PlannedMeal], day_number: int) -> int:
        return sum(self._meal_calories(meal.recipe, meal.scaled_servings) for meal in meals if meal.day == day_number)

    def _effective_daily_targets(self, request: PlannerRequest) -> PersonalNutritionTargets:
        if request.personal_targets is not None:
            return request.personal_targets
        return targets_from_manual_calorie_range(
            request.daily_calorie_target_min,
            request.daily_calorie_target_max,
        )

    def _meal_nutrient_state(self, recipe: Recipe, servings: int) -> DailyNutrientState:
        nutrition = recipe.estimated_nutrition_per_serving
        guidance = self._meal_guidance_profile(recipe)
        components = self._meal_component_tags(recipe)
        scale = servings / max(recipe.base_servings, 1)
        produce_support = self._food_group_support(recipe, "produce", guidance, components, scale)
        grains_support = self._food_group_support(recipe, "grains", guidance, components, scale)
        dairy_support = self._food_group_support(recipe, "dairy", guidance, components, scale)
        if nutrition is None:
            return DailyNutrientState(
                calories=float(self._meal_calories(recipe, servings)),
                protein_grams=0.0,
                carbs_grams=0.0,
                fat_grams=0.0,
                produce_support=produce_support,
                grains_starches_support=grains_support,
                dairy_support=dairy_support,
            )
        return DailyNutrientState(
            calories=float(nutrition.calories * scale),
            protein_grams=round(nutrition.protein_grams * scale, 3),
            carbs_grams=round(nutrition.carbs_grams * scale, 3),
            fat_grams=round(nutrition.fat_grams * scale, 3),
            produce_support=produce_support,
            grains_starches_support=grains_support,
            dairy_support=dairy_support,
        )

    def _meal_composition_profile(self, recipe: Recipe, servings: int) -> MealCompositionProfile:
        cache_key = (self._recipe_cache_key(recipe), servings)
        cached = self._meal_composition_profile_cache.get(cache_key)
        if cached is not None:
            return cached
        state = self._meal_nutrient_state(recipe, servings)
        components = self._meal_component_tags(recipe)
        support_map = {
            "protein": state.protein_grams / 18.0 if state.protein_grams > 0 else 0.0,
            "vegetable": state.produce_support,
            "starch": state.grains_starches_support,
            "dairy": state.dairy_support,
        }
        dominant_component = "balanced"
        ordered_support = sorted(support_map.items(), key=lambda item: item[1], reverse=True)
        top_component, top_score = ordered_support[0]
        second_score = ordered_support[1][1]
        if top_score >= 0.9 and top_score >= second_score + 0.35:
            dominant_component = top_component
        density_score = round(
            state.calories / 220.0
            + state.fat_grams / 18.0
            + state.grains_starches_support * 0.35,
            3,
        )
        heaviness = "light"
        if density_score >= 2.4 or state.calories >= 420:
            heaviness = "heavy"
        elif density_score >= 1.25 or state.calories >= 220:
            heaviness = "moderate"
        result = MealCompositionProfile(
            protein_support=round(support_map["protein"], 3),
            vegetable_support=round(support_map["vegetable"], 3),
            starch_support=round(support_map["starch"], 3),
            dairy_support=round(support_map["dairy"], 3),
            dominant_component=dominant_component,
            heaviness=heaviness,
            density_score=density_score,
            components=components,
        )
        self._meal_composition_profile_cache[cache_key] = result
        return result

    def _food_group_support(
        self,
        recipe: Recipe,
        group: str,
        guidance: MealGuidanceProfile | None = None,
        components: frozenset[str] | None = None,
        scale: float = 1.0,
    ) -> float:
        meal_guidance = guidance or self._meal_guidance_profile(recipe)
        meal_components = components or self._meal_component_tags(recipe)
        ingredient_names = self._core_ingredient_names(recipe)
        support = 0.0
        if group == "produce":
            ingredient_hits = sum(
                1
                for ingredient_name in ingredient_names
                if ingredient_name in VEGETABLE_SUPPORT_INGREDIENTS
            )
            if meal_guidance.food_group_tags & {"vegetables", "vegetables_legumes", "vegetables_starchy"}:
                support += 0.8
            if "vegetable" in meal_components:
                support += 0.7
            support += min(ingredient_hits, 3) * 0.3
        elif group == "grains":
            ingredient_hits = sum(
                1
                for ingredient_name in ingredient_names
                if ingredient_name in CARB_SUPPORT_INGREDIENTS
            )
            if meal_guidance.food_group_tags & {"grains", "grains_starches", "vegetables_starchy"}:
                support += 0.75
            if "carb" in meal_components:
                support += 0.65
            support += min(ingredient_hits, 2) * 0.35
        elif group == "dairy":
            if "dairy" in meal_guidance.food_group_tags:
                support += 1.0
        return round(support * min(max(scale, 0.5), 2.0), 3)

    def _combine_daily_states(
        self,
        left: DailyNutrientState,
        right: DailyNutrientState,
    ) -> DailyNutrientState:
        return DailyNutrientState(
            calories=round(left.calories + right.calories, 3),
            protein_grams=round(left.protein_grams + right.protein_grams, 3),
            carbs_grams=round(left.carbs_grams + right.carbs_grams, 3),
            fat_grams=round(left.fat_grams + right.fat_grams, 3),
            produce_support=round(left.produce_support + right.produce_support, 3),
            grains_starches_support=round(left.grains_starches_support + right.grains_starches_support, 3),
            dairy_support=round(left.dairy_support + right.dairy_support, 3),
        )

    def _current_day_state(self, meals: list[PlannedMeal], day_number: int) -> DailyNutrientState:
        state = DailyNutrientState(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        for meal in meals:
            if meal.day != day_number:
                continue
            state = self._combine_daily_states(
                state,
                self._meal_nutrient_state(meal.recipe, meal.scaled_servings),
            )
        return state

    def _projected_day_state(
        self,
        meals: list[PlannedMeal],
        recipe: Recipe | None,
        request: PlannerRequest,
        day_number: int,
    ) -> DailyNutrientState:
        state = self._current_day_state(meals, day_number)
        if recipe is None:
            return state
        return self._combine_daily_states(
            state,
            self._meal_nutrient_state(recipe, request.servings),
        )

    def _daily_nutrient_deficits(
        self,
        state: DailyNutrientState,
        targets: PersonalNutritionTargets,
    ) -> DailyNutrientDeficits:
        return DailyNutrientDeficits(
            calories_below_min=round(max(targets.calorie_target_min - state.calories, 0.0), 3),
            calories_above_max=round(max(state.calories - targets.calorie_target_max, 0.0), 3),
            protein_grams=round(max(targets.protein_target_min_grams - state.protein_grams, 0.0), 3),
            carbs_grams=round(max(targets.carbs_target_min_grams - state.carbs_grams, 0.0), 3),
            fat_grams=round(max(targets.fat_target_min_grams - state.fat_grams, 0.0), 3),
            produce_support=round(max(targets.produce_target_cups - state.produce_support, 0.0), 3),
            grains_starches_support=round(max(targets.grains_target_ounces - state.grains_starches_support, 0.0), 3),
            dairy_support=round(
                max((targets.dairy_target_cups or 0.0) - state.dairy_support, 0.0),
                3,
            ),
        )

    def _projected_day_calories(
        self,
        candidates: tuple[Recipe, ...],
        meals: list[PlannedMeal],
        recipe: Recipe | None,
        request: PlannerRequest,
        day_number: int,
        slot_number: int,
    ) -> float:
        projected_total = self._current_day_calories(meals, day_number)
        if recipe is not None:
            projected_total += self._meal_calories(recipe, request.servings)
        for future_slot_number in range(slot_number + 1, request.meals_per_day + 1):
            projected_total += self._average_slot_calories(
                candidates,
                request,
                future_slot_number,
                request.servings,
            )
        return projected_total

    def _average_slot_calories(
        self,
        candidates: tuple[Recipe, ...],
        request: PlannerRequest,
        slot_number: int,
        servings: int,
    ) -> float:
        cache_key = (
            self._request_cycle_key(request),
            self._meal_structure(request),
            slot_number,
            servings,
        )
        cached = self._average_slot_calories_cache.get(cache_key)
        if cached is not None:
            return cached
        slot_candidates = self._slot_recipe_groups(candidates, request, slot_number).mains
        calorie_known_candidates = [recipe for recipe in slot_candidates if recipe.estimated_calories_per_serving is not None]
        if not calorie_known_candidates:
            self._average_slot_calories_cache[cache_key] = 0.0
            return 0.0
        total = sum(self._meal_calories(recipe, servings) for recipe in calorie_known_candidates)
        average = total / len(calorie_known_candidates)
        self._average_slot_calories_cache[cache_key] = average
        return average

    def _calorie_target_penalty(self, projected_day_calories: float, minimum: int, maximum: int) -> float:
        lower_bound = min(minimum, maximum)
        upper_bound = max(minimum, maximum)
        midpoint = (lower_bound + upper_bound) / 2
        if lower_bound <= projected_day_calories <= upper_bound:
            return abs(projected_day_calories - midpoint) / 600
        if projected_day_calories < lower_bound:
            return (lower_bound - projected_day_calories) / 220
        return (projected_day_calories - upper_bound) / 220

    def _budget_pressure_penalty(
        self,
        request: PlannerRequest,
        current_total: float,
        incremental_cost: float,
        meals_already_planned: int,
    ) -> float:
        suggested_slot_budget = self._suggested_slot_budget(request, current_total, meals_already_planned)
        remaining_slots = max((7 * request.meals_per_day) - meals_already_planned, 1)
        if incremental_cost <= suggested_slot_budget:
            return 0.0
        return ((incremental_cost / max(suggested_slot_budget, 0.5)) - 1.0) * remaining_slots

    def _suggested_slot_budget(
        self,
        request: PlannerRequest,
        current_total: float,
        meals_already_planned: int,
    ) -> float:
        remaining_budget = max(request.weekly_budget - current_total, 0.0)
        remaining_slots = max((7 * request.meals_per_day) - meals_already_planned, 1)
        return remaining_budget / remaining_slots

    def _cuisine_preference_bonus(self, recipe: Recipe, request: PlannerRequest) -> float:
        preferred_cuisines = {normalize_name(value) for value in request.cuisine_preferences}
        if not preferred_cuisines:
            return 0.0
        if normalize_name(recipe.cuisine) in preferred_cuisines:
            return 0.65
        return 0.0

    def _recipe_count(self, meals: list[PlannedMeal], recipe_title: str) -> int:
        return sum(1 for meal in meals if meal.recipe.title == recipe_title)

    def _slot_recipe_count(self, meals: list[PlannedMeal], recipe_title: str, slot_number: int) -> int:
        return sum(1 for meal in meals if meal.recipe.title == recipe_title and meal.slot == slot_number)

    def _recent_repeat_count(self, meals: list[PlannedMeal], recipe_title: str) -> int:
        return sum(1 for meal in meals[-3:] if meal.recipe.title == recipe_title)

    def _leftovers_score(self, meals: list[PlannedMeal], recipe_title: str, slot_number: int) -> int:
        slot_matches = self._slot_recipe_count(meals, recipe_title, slot_number)
        recent_matches = self._recent_repeat_count(meals, recipe_title)
        return (slot_matches * 2) + recent_matches

    def _near_duplicate_penalty(
        self,
        meals: list[PlannedMeal],
        recipe: Recipe,
        day_number: int,
        slot_number: int,
    ) -> float:
        target_index = self._meal_sequence_index(day_number, slot_number)
        penalties: list[float] = []
        for meal in meals:
            similarity = self._recipe_similarity(recipe, meal.recipe)
            if similarity <= 0:
                continue
            distance = abs(self._meal_sequence_index(meal.day, meal.slot) - target_index)
            if distance <= 2:
                penalties.append(similarity * 1.35)
            else:
                penalties.append(similarity)
        if not penalties:
            return 0.0
        return max(penalties) + (sum(penalties) / len(penalties) * 0.2)

    def _recipe_similarity(self, left: Recipe, right: Recipe) -> float:
        if left.recipe_id == right.recipe_id:
            return 0.0
        similarity = 0.0
        if normalize_name(left.cuisine) == normalize_name(right.cuisine):
            similarity += 1.0
        shared_core_ingredients = len(self._core_ingredient_names(left) & self._core_ingredient_names(right))
        if shared_core_ingredients >= 3:
            similarity += 1.6
        elif shared_core_ingredients == 2:
            similarity += 1.1
        elif shared_core_ingredients == 1:
            similarity += 0.45
        if self._meal_style_markers(left) & self._meal_style_markers(right):
            similarity += 0.9
        return similarity

    def _core_ingredient_names(self, recipe: Recipe) -> frozenset[str]:
        cache_key = self._recipe_cache_key(recipe)
        cached = self._core_ingredient_names_cache.get(cache_key)
        if cached is not None:
            return cached
        canonical_names = {normalize_ingredient_name(item.name) for item in recipe.ingredients}
        core_names = canonical_names - LOW_SIGNAL_INGREDIENTS
        if core_names:
            result = frozenset(core_names)
        else:
            result = frozenset(canonical_names)
        self._core_ingredient_names_cache[cache_key] = result
        return result

    def _meal_style_markers(self, recipe: Recipe) -> frozenset[str]:
        cache_key = self._recipe_cache_key(recipe)
        cached = self._meal_style_markers_cache.get(cache_key)
        if cached is not None:
            return cached
        normalized_title = normalize_name(recipe.title)
        result = frozenset(keyword for keyword in MEAL_STYLE_KEYWORDS if keyword in normalized_title)
        self._meal_style_markers_cache[cache_key] = result
        return result

    def _weekly_variety_score(
        self,
        *,
        recipe: Recipe,
        candidate_role: str,
        anchor_recipe: Recipe | None,
        meals: list[PlannedMeal],
        variety_profile: VarietyProfile,
    ) -> WeeklyVarietyScore:
        if not self.week_balance_enabled:
            return WeeklyVarietyScore(total=0.0, reasons=())

        reasons: list[str] = []
        score = 0.0
        prior_same_role = [meal for meal in meals if meal.meal_role == candidate_role]
        if candidate_role == "main":
            prior_same_role = [meal for meal in prior_same_role if meal.meal_role == "main"]
            protein_key = self._primary_protein_key(recipe)
            if protein_key is not None:
                protein_repeats = sum(
                    1
                    for meal in prior_same_role
                    if self._primary_protein_key(meal.recipe) == protein_key
                )
                if protein_repeats == 0:
                    score += variety_profile.protein_variety_bonus
                    reasons.append("weekly:protein-variety")
                else:
                    score -= protein_repeats * variety_profile.protein_variety_bonus * 0.85
                    reasons.append("weekly:repeated-protein")

            prior_produce = {
                produce
                for meal in prior_same_role
                for produce in self._produce_keys(meal.recipe)
            }
            candidate_produce = self._produce_keys(recipe)
            new_produce = candidate_produce - prior_produce
            if new_produce:
                score += len(new_produce) * variety_profile.produce_variety_bonus
                reasons.append("weekly:produce-variety")
            elif candidate_produce and prior_same_role:
                score -= variety_profile.produce_variety_bonus * 0.55
                reasons.append("weekly:repeated-produce")

            starch_key = self._primary_starch_key(recipe)
            if starch_key is not None:
                starch_repeats = sum(
                    1
                    for meal in prior_same_role
                    if self._primary_starch_key(meal.recipe) == starch_key
                )
                if starch_repeats:
                    score -= starch_repeats * variety_profile.repeated_starch_penalty
                    reasons.append("weekly:repeated-starch")

            cuisine_repeats = sum(
                1
                for meal in prior_same_role
                if normalize_name(meal.recipe.cuisine) == normalize_name(recipe.cuisine)
            )
            if cuisine_repeats >= 2:
                score -= (cuisine_repeats - 1) * 0.45
                reasons.append("weekly:repeated-cuisine")

            structure_key = self._meal_structure_pattern_key(recipe)
            structure_repeats = sum(
                1
                for meal in prior_same_role
                if self._meal_structure_pattern_key(meal.recipe) == structure_key
            )
            if structure_repeats:
                score -= structure_repeats * variety_profile.repeated_meal_structure_penalty
                reasons.append("weekly:repeated-meal-structure")

            anchor_key = self._anchor_pattern_key(recipe)
            anchor_repeats = sum(
                1
                for meal in prior_same_role
                if self._anchor_pattern_key(meal.recipe) == anchor_key
            )
            if anchor_repeats:
                score -= anchor_repeats * variety_profile.repeated_anchor_pattern_penalty
                reasons.append("weekly:repeated-anchor-pattern")
        elif candidate_role == "side":
            prior_same_role = [meal for meal in prior_same_role if meal.meal_role == "side"]
            candidate_components = self._meal_component_tags(recipe)
            prior_components = {
                component
                for meal in prior_same_role
                for component in self._meal_component_tags(meal.recipe)
            }
            new_components = candidate_components - prior_components
            if new_components:
                score += len(new_components) * variety_profile.side_diversity_bonus
                reasons.append("weekly:side-diversity")
            prior_side_produce = {
                produce
                for meal in prior_same_role
                for produce in self._produce_keys(meal.recipe)
            }
            candidate_side_produce = self._produce_keys(recipe)
            if candidate_side_produce - prior_side_produce:
                score += variety_profile.side_diversity_bonus * 0.65
                reasons.append("weekly:side-produce-variety")
            elif candidate_side_produce and prior_same_role:
                score -= variety_profile.side_diversity_bonus * 0.45
                reasons.append("weekly:repeated-side-produce")
            side_structure_key = self._meal_structure_pattern_key(recipe)
            repeated_side_structures = sum(
                1
                for meal in prior_same_role
                if self._meal_structure_pattern_key(meal.recipe) == side_structure_key
            )
            if repeated_side_structures:
                score -= repeated_side_structures * variety_profile.repeated_meal_structure_penalty * 0.75
                reasons.append("weekly:repeated-side-structure")
            if anchor_recipe is not None:
                pairing_key = self._anchor_side_pairing_key(anchor_recipe, recipe)
                repeated_pairings = 0
                for meal in prior_same_role:
                    paired_main = self._main_for_day_slot(meals, meal.day, meal.slot)
                    if paired_main is None:
                        continue
                    if self._anchor_side_pairing_key(paired_main.recipe, meal.recipe) == pairing_key:
                        repeated_pairings += 1
                if repeated_pairings:
                    score -= repeated_pairings * variety_profile.repeated_side_pairing_penalty
                    reasons.append("weekly:repeated-side-pairing")
                if "vegetable" in candidate_components:
                    prior_vegetable_sides = sum(
                        1
                        for meal in prior_same_role
                        if "vegetable" in self._meal_component_tags(meal.recipe)
                    )
                    if prior_vegetable_sides < max(len(prior_same_role) // 2, 1):
                        score += variety_profile.side_diversity_bonus * 0.65
                        reasons.append("weekly:vegetable-side-balance")

        return WeeklyVarietyScore(total=round(score, 4), reasons=tuple(reasons))

    def _primary_protein_key(self, recipe: Recipe) -> str | None:
        cache_key = self._recipe_cache_key(recipe)
        if cache_key in self._primary_protein_key_cache:
            return self._primary_protein_key_cache[cache_key]
        for ingredient_name in sorted(self._core_ingredient_names(recipe)):
            if ingredient_name in PROTEIN_SUPPORT_INGREDIENTS:
                self._primary_protein_key_cache[cache_key] = ingredient_name
                return ingredient_name
        if "protein" in self._meal_component_tags(recipe):
            self._primary_protein_key_cache[cache_key] = "protein-supported"
            return "protein-supported"
        self._primary_protein_key_cache[cache_key] = None
        return None

    def _produce_keys(self, recipe: Recipe) -> frozenset[str]:
        cache_key = self._recipe_cache_key(recipe)
        cached = self._produce_keys_cache.get(cache_key)
        if cached is not None:
            return cached
        result = frozenset(
            ingredient_name
            for ingredient_name in self._core_ingredient_names(recipe)
            if ingredient_name in VEGETABLE_SUPPORT_INGREDIENTS
        )
        self._produce_keys_cache[cache_key] = result
        return result

    def _primary_starch_key(self, recipe: Recipe) -> str | None:
        cache_key = self._recipe_cache_key(recipe)
        if cache_key in self._primary_starch_key_cache:
            return self._primary_starch_key_cache[cache_key]
        for ingredient_name in sorted(self._core_ingredient_names(recipe)):
            if ingredient_name in STARCH_PATTERN_INGREDIENTS:
                self._primary_starch_key_cache[cache_key] = ingredient_name
                return ingredient_name
        if "carb" in self._meal_component_tags(recipe):
            self._primary_starch_key_cache[cache_key] = "carb-supported"
            return "carb-supported"
        self._primary_starch_key_cache[cache_key] = None
        return None

    def _meal_structure_pattern_key(self, recipe: Recipe) -> str:
        cache_key = self._recipe_cache_key(recipe)
        cached = self._meal_structure_pattern_key_cache.get(cache_key)
        if cached is not None:
            return cached
        styles = sorted(self._meal_style_markers(recipe))
        components = sorted(self._meal_component_tags(recipe))
        if styles:
            result = styles[0]
        elif components:
            result = "+".join(components)
        else:
            result = normalize_name(recipe.title).split(" ")[0]
        self._meal_structure_pattern_key_cache[cache_key] = result
        return result

    def _anchor_pattern_key(self, recipe: Recipe) -> str:
        cache_key = self._recipe_cache_key(recipe)
        cached = self._anchor_pattern_key_cache.get(cache_key)
        if cached is not None:
            return cached
        result = "|".join(
            (
                self._primary_protein_key(recipe) or "no-protein",
                self._primary_starch_key(recipe) or "no-starch",
                self._meal_structure_pattern_key(recipe),
            )
        )
        self._anchor_pattern_key_cache[cache_key] = result
        return result

    def _anchor_side_pairing_key(self, anchor_recipe: Recipe, side_recipe: Recipe) -> str:
        return f"{self._anchor_pattern_key(anchor_recipe)}->{self._meal_structure_pattern_key(side_recipe)}"

    def _main_for_day_slot(
        self,
        meals: list[PlannedMeal],
        day_number: int,
        slot_number: int,
    ) -> PlannedMeal | None:
        return next(
            (
                meal
                for meal in meals
                if meal.day == day_number and meal.slot == slot_number and meal.meal_role == "main"
            ),
            None,
        )

    def _main_meal_target_gap(
        self,
        meals: list[PlannedMeal],
        component: str,
        weekly_target_amount: float,
    ) -> float:
        current_amount = sum(
            1.0
            for meal in meals
            if meal.meal_role == "main" and component in self._meal_component_tags(meal.recipe)
        )
        return max(weekly_target_amount - current_amount, 0.0)

    def _side_meal_target_gap(
        self,
        meals: list[PlannedMeal],
        component: str,
        weekly_target_amount: float,
        current_side_count: int,
    ) -> float:
        if current_side_count == 0:
            return weekly_target_amount
        current_amount = sum(
            1.0
            for meal in meals
            if meal.meal_role == "side" and component in self._meal_component_tags(meal.recipe)
        )
        return max((weekly_target_amount * 0.6) - current_amount, 0.0)

    def _planning_goal(self, user_profile) -> str:
        if user_profile is None:
            return ""
        return normalize_name(user_profile.planning_goal)

    def _personal_target_score(
        self,
        *,
        recipe: Recipe,
        request: PlannerRequest,
        candidate_role: str,
        anchor_recipe: Recipe | None,
        meals: list[PlannedMeal],
        day_number: int,
        daily_state_before: DailyNutrientState,
        daily_state_after: DailyNutrientState,
        daily_deficits_before: DailyNutrientDeficits,
        daily_deficits_after: DailyNutrientDeficits,
    ) -> PersonalTargetScore:
        targets = self._effective_daily_targets(request)

        nutrition = recipe.estimated_nutrition_per_serving
        guidance = self._meal_guidance_profile(recipe)
        components = self._meal_component_tags(recipe)
        reasons: list[str] = []
        score = 0.0
        meals_per_day = max(request.meals_per_day, 1)
        current_side_count = sum(1 for meal in meals if meal.day == day_number and meal.meal_role == "side")
        if candidate_role == "main":
            protein_gap_closed = daily_deficits_before.protein_grams - daily_deficits_after.protein_grams
            produce_gap_closed = daily_deficits_before.produce_support - daily_deficits_after.produce_support
            grains_gap_closed = (
                daily_deficits_before.grains_starches_support - daily_deficits_after.grains_starches_support
            )
            calorie_improvement = (
                (daily_deficits_before.calories_below_min + daily_deficits_before.calories_above_max)
                - (daily_deficits_after.calories_below_min + daily_deficits_after.calories_above_max)
            )
            if "protein" in components:
                score += 0.35
                reasons.append("target:protein-support")
            if protein_gap_closed > 0:
                score += min(1.1, protein_gap_closed / 16.0)
                reasons.append("target:protein-range")
            elif nutrition is not None and nutrition.protein_grams < (targets.protein_target_min_grams / max(meals_per_day, 2)) * 0.45:
                score -= 0.45
                reasons.append("target:low-protein")
            if "vegetable" in components:
                score += 0.2
                reasons.append("target:produce-support")
            if produce_gap_closed > 0:
                score += min(0.8, produce_gap_closed * 0.22)
                reasons.append("target:produce-gap")
            if grains_gap_closed > 0 and "carb" in components:
                score += min(0.55, grains_gap_closed * 0.1)
                reasons.append("target:grains-support")
            if calorie_improvement > 0:
                score += min(0.35, calorie_improvement / 450.0)
                reasons.append("target:calorie-guidance")
            if self._planning_goal(request.user_profile) == "high protein preference":
                protein_ratio = 0.0 if nutrition is None else (nutrition.protein_grams / max(targets.protein_target_min_grams / max(meals_per_day, 2), 1.0))
                if protein_gap_closed > 0 and protein_ratio >= 0.9:
                    score += 1.35
                    reasons.append("target:goal-high-protein")
                elif protein_gap_closed > 0 and "protein" in components:
                    score += 0.85
                    reasons.append("target:goal-high-protein")
                else:
                    score -= 0.8
                    reasons.append("target:goal-low-protein")
        elif candidate_role == "side":
            protein_gap_closed = daily_deficits_before.protein_grams - daily_deficits_after.protein_grams
            produce_gap_closed = daily_deficits_before.produce_support - daily_deficits_after.produce_support
            grains_gap_closed = (
                daily_deficits_before.grains_starches_support - daily_deficits_after.grains_starches_support
            )
            dairy_gap_closed = daily_deficits_before.dairy_support - daily_deficits_after.dairy_support
            calorie_improvement = (
                (daily_deficits_before.calories_below_min + daily_deficits_before.calories_above_max)
                - (daily_deficits_after.calories_below_min + daily_deficits_after.calories_above_max)
            )
            if "vegetable" in components:
                score += 0.45
                reasons.append("target:produce-support")
            if produce_gap_closed > 0:
                score += min(0.65, produce_gap_closed * 0.24)
                reasons.append("target:produce-gap")
            if protein_gap_closed > 0 and "protein" in components:
                score += min(0.6, protein_gap_closed / 18.0)
                reasons.append("target:protein-gap")
                if daily_deficits_before.produce_support <= 1.5:
                    score += 0.45
                    reasons.append("target:protein-priority")
            if anchor_recipe is not None:
                main_components = self._meal_component_tags(anchor_recipe)
                if grains_gap_closed > 0 and "carb" in components and "carb" not in main_components:
                    score += min(0.35, grains_gap_closed * 0.12)
                    reasons.append("target:grains-support")
                anchor_guidance = self._meal_guidance_profile(anchor_recipe)
                if dairy_gap_closed > 0 and "dairy" in guidance.food_group_tags and "dairy" not in anchor_guidance.food_group_tags:
                    score += min(0.3, dairy_gap_closed * 0.25)
                    reasons.append("target:dairy-support")
            elif grains_gap_closed > 0 and "carb" in components:
                score += min(0.25, grains_gap_closed * 0.08)
                reasons.append("target:grains-support")
            if calorie_improvement > 0 and current_side_count == 0:
                score += min(0.2, calorie_improvement / 600.0)
                reasons.append("target:calorie-guidance")

        if nutrition is not None:
            midpoint = (targets.calorie_target_min + targets.calorie_target_max) / 2
            meal_target = midpoint / meals_per_day
            if abs(nutrition.calories - meal_target) <= max(140, meal_target * 0.18):
                score += 0.1
                if "target:calorie-guidance" not in reasons:
                    reasons.append("target:calorie-guidance")

        return PersonalTargetScore(total=round(score, 4), reasons=tuple(reasons))

    def _meal_balance_score(
        self,
        recipe: Recipe,
        desired_slot: str,
        candidate_role: str,
        anchor_recipe: Recipe | None,
    ) -> MealBalanceScore:
        if not self.balance_scoring_enabled:
            return MealBalanceScore(total=0.0, components=frozenset(), reasons=())

        normalized_title = normalize_name(recipe.title)
        recipe_role = self._recipe_role(recipe, desired_slot)
        components = self._meal_component_tags(recipe)
        guidance = self._meal_guidance_profile(recipe)
        reasons: list[str] = []
        score = 0.0

        if desired_slot not in {"lunch", "dinner"}:
            return MealBalanceScore(total=0.0, components=components, reasons=())

        if recipe_role in {"condiment", "dessert", "beverage", "snack"}:
            penalty = {
                "condiment": 3.6,
                "dessert": 3.3,
                "beverage": 3.3,
                "snack": 2.4,
            }[recipe_role]
            reasons.append(f"penalty:{recipe_role}")
            return MealBalanceScore(total=-penalty, components=components, reasons=tuple(reasons))

        if "protein_foods" in guidance.food_group_tags:
            score += 0.22 if candidate_role == "main" else 0.12
            reasons.append("guidance:protein_foods")
        if guidance.food_group_tags & {"vegetables", "vegetables_legumes", "vegetables_starchy"}:
            score += 0.18 if candidate_role == "main" else 0.18
            reasons.append("guidance:vegetables")
        if guidance.food_group_tags & {"grains", "grains_starches", "vegetables_starchy"}:
            score += 0.14 if candidate_role == "main" else 0.14
            reasons.append("guidance:grains_starches")
        if "dairy" in guidance.food_group_tags:
            score += 0.05 if candidate_role == "main" else 0.08
            reasons.append("guidance:dairy")

        if "protein" in components:
            score += 1.05 if candidate_role == "main" else 0.4
            reasons.append("protein-support")
        if "vegetable" in components:
            score += 0.8 if candidate_role == "main" else 1.0
            reasons.append("vegetable-support")
        if "carb" in components:
            score += 0.6 if candidate_role == "main" else 0.3
            reasons.append("carb-support")

        if candidate_role == "main":
            if recipe_role == "side":
                score -= 1.7
                reasons.append("penalty:side-like-main")
            if len(components) >= 2:
                score += 0.7
                reasons.append("anchor-composition")
            else:
                score -= 0.75
                reasons.append("penalty:weak-anchor")
            if "protein" not in components and "vegetable" not in components:
                score -= 0.65
                reasons.append("penalty:low-sustainability")
            if any(keyword in normalized_title for keyword in NON_MEAL_LUNCH_DINNER_KEYWORDS):
                score -= 0.8
                reasons.append("penalty:non-meal-title")
        elif candidate_role == "side":
            if recipe_role != "side":
                score -= 0.5
                reasons.append("penalty:main-like-side")
            if anchor_recipe is not None:
                main_components = self._meal_component_tags(anchor_recipe)
                main_profile = self._meal_composition_profile(anchor_recipe, anchor_recipe.base_servings)
                side_profile = self._meal_composition_profile(recipe, recipe.base_servings)
                missing_components = {"protein", "vegetable", "carb"} - set(main_components)
                complemented = components & missing_components
                overlap = components & main_components
                if complemented:
                    score += len(complemented) * 1.4
                    reasons.append("complements-main")
                if side_profile.vegetable_support >= 0.9 and main_profile.vegetable_support < 0.9:
                    score += 1.1
                    reasons.append("complements-main-produce-gap")
                if side_profile.protein_support >= 0.9 and main_profile.protein_support < 1.0:
                    score += 0.75
                    reasons.append("complements-main-protein-gap")
                if side_profile.starch_support >= 0.8 and main_profile.starch_support < 0.8:
                    score += 0.35
                    reasons.append("complements-main-starch-gap")
                if (
                    main_profile.dominant_component == "starch"
                    and side_profile.dominant_component == "starch"
                ):
                    score -= 1.45
                    reasons.append("penalty:starch-heavy-pairing")
                elif (
                    main_profile.dominant_component != "balanced"
                    and side_profile.dominant_component == main_profile.dominant_component
                ):
                    score -= 0.65
                    reasons.append("penalty:duplicate-dominant-component")
                if main_profile.vegetable_support < 0.9 and side_profile.vegetable_support < 0.75:
                    score -= 0.35
                    reasons.append("penalty:produce-poor-pairing")
                if main_profile.heaviness == "heavy" and side_profile.heaviness == "heavy":
                    score -= 0.85
                    reasons.append("penalty:heavy-redundant-side")
                if overlap:
                    score -= len(overlap) * 0.35
                    reasons.append("overlaps-main")
                if not complemented and components:
                    score -= 0.4
                    reasons.append("limited-complement")
                if not components:
                    score -= 0.8
                    reasons.append("penalty:empty-side-support")

        return MealBalanceScore(total=round(score, 3), components=components, reasons=tuple(reasons))

    def _meal_component_tags(self, recipe: Recipe) -> frozenset[str]:
        cache_key = self._recipe_cache_key(recipe)
        cached = self._meal_component_tags_cache.get(cache_key)
        if cached is not None:
            return cached
        components: set[str] = set()
        ingredient_names = self._core_ingredient_names(recipe)
        nutrition = recipe.estimated_nutrition_per_serving
        guidance = self._meal_guidance_profile(recipe)

        protein_hits = ingredient_names & PROTEIN_SUPPORT_INGREDIENTS
        vegetable_hits = ingredient_names & VEGETABLE_SUPPORT_INGREDIENTS
        carb_hits = ingredient_names & CARB_SUPPORT_INGREDIENTS

        if (
            "protein" in guidance.component_tags
            or protein_hits
            or (nutrition is not None and nutrition.protein_grams >= 12.0)
        ):
            components.add("protein")
        if "vegetable" in guidance.component_tags or vegetable_hits:
            components.add("vegetable")
        if (
            "carb" in guidance.component_tags
            or carb_hits
            or (nutrition is not None and nutrition.carbs_grams >= 18.0)
        ):
            components.add("carb")
        result = frozenset(components)
        self._meal_component_tags_cache[cache_key] = result
        return result

    def _meal_guidance_profile(self, recipe: Recipe) -> MealGuidanceProfile:
        if not self.meal_guidance_enabled:
            return MealGuidanceProfile(food_group_tags=frozenset(), component_tags=frozenset())
        cache_key = self._recipe_cache_key(recipe)
        cached = self._meal_guidance_profile_cache.get(cache_key)
        if cached is not None:
            return cached

        food_group_tags: set[str] = set()
        component_tags: set[str] = set()
        for ingredient_name in self._core_ingredient_names(recipe):
            guidance = lookup_ingredient_guidance(ingredient_name)
            if guidance is None:
                continue
            food_group_tags.update(guidance.food_group_tags)
            component_tags.update(guidance.component_tags)
        result = MealGuidanceProfile(
            food_group_tags=frozenset(food_group_tags),
            component_tags=frozenset(component_tags),
        )
        self._meal_guidance_profile_cache[cache_key] = result
        return result

    def _recipe_role(self, recipe: Recipe, desired_slot: str) -> str:
        cache_key = (self._recipe_cache_key(recipe), desired_slot)
        cached = self._recipe_role_cache.get(cache_key)
        if cached is not None:
            return cached
        normalized_title = normalize_name(recipe.title)
        core_ingredient_count = len(self._core_ingredient_names(recipe))
        if any(keyword in normalized_title for keyword in HARD_NON_MEAL_TITLE_KEYWORDS):
            result = "condiment"
            self._recipe_role_cache[cache_key] = result
            return result
        if any(keyword in normalized_title for keyword in ("drink", "drinks", "juice", "lemonade", "limeade", "smoothie", "punch", "cocktail", "water ice", "beverage")):
            result = "beverage"
            self._recipe_role_cache[cache_key] = result
            return result
        if any(keyword in normalized_title for keyword in ("dessert", "desserts", "cake", "cakes", "cookie", "cookies", "brownie", "brownies", "pie", "pies", "pudding", "sorbet", "sherbet", "ice cream", "jam", "jelly", "marmalade", "candy", "candied", "fudge")):
            result = "dessert"
            self._recipe_role_cache[cache_key] = result
            return result
        if "snack" in normalized_title:
            result = "snack"
            self._recipe_role_cache[cache_key] = result
            return result
        if desired_slot == "breakfast":
            if "breakfast" in recipe.meal_types or any(keyword in normalized_title for keyword in BREAKFAST_TITLE_KEYWORDS):
                result = "breakfast_main"
            else:
                result = "main"
            self._recipe_role_cache[cache_key] = result
            return result
        if any(keyword in normalized_title for keyword in SIDE_TITLE_KEYWORDS):
            if (
                recipe.estimated_calories_per_serving is not None
                and recipe.estimated_calories_per_serving <= 220
            ):
                result = "side"
                self._recipe_role_cache[cache_key] = result
                return result
            if core_ingredient_count <= 3 and not any(
                keyword in normalized_title
                for keyword in ("bowl", "burger", "burrito", "casserole", "curry", "chili", "pasta", "plate", "sandwich", "skillet", "stew", "stuffed", "taco", "wrap")
            ):
                result = "side"
                self._recipe_role_cache[cache_key] = result
                return result
        result = "main"
        self._recipe_role_cache[cache_key] = result
        return result

    def _is_reasonable_meal_for_slot(self, recipe: Recipe, desired_slot: str) -> bool:
        normalized_title = normalize_name(recipe.title)
        if desired_slot == "breakfast" and any(keyword in normalized_title for keyword in ("sauce", "dip", "dressing", "relish", "spread", "marinade", "condiment")):
            return False
        if desired_slot in {"lunch", "dinner"} and any(
            keyword in normalized_title for keyword in HARD_NON_MEAL_TITLE_KEYWORDS
        ):
            if not any(keyword in normalized_title for keyword in SUBSTANTIAL_MEAL_KEYWORDS):
                return False
        if desired_slot in {"lunch", "dinner"} and any(
            keyword in normalized_title for keyword in NON_MEAL_LUNCH_DINNER_KEYWORDS
        ):
            if not any(keyword in normalized_title for keyword in SUBSTANTIAL_MEAL_KEYWORDS):
                return False
        role = self._recipe_role(recipe, desired_slot)
        if desired_slot in {"lunch", "dinner"} and role in {"condiment", "dessert", "beverage", "snack"}:
            return False
        if not any(keyword in normalized_title for keyword in NON_MEAL_TITLE_KEYWORDS):
            return True
        if any(keyword in normalized_title for keyword in SUBSTANTIAL_MEAL_KEYWORDS):
            return True
        core_ingredient_count = len(self._core_ingredient_names(recipe))
        return core_ingredient_count >= 5

    def diagnose_request_support(self, request: PlannerRequest) -> PlanSelectionDiagnostics:
        candidates = self._filter_recipes(request)
        pantry_inventory = self._normalized_pantry_inventory(request)
        variety_profile = self._variety_profile(request)
        purchased_quantities: dict[str, AggregatedIngredient] = {}
        meals: list[PlannedMeal] = []
        forced_repeat_slots = 0
        slot_diagnostics: list[SlotSelectionDiagnostics] = []
        top_rejections: dict[str, int] = {}

        for slot_index in range(7 * request.meals_per_day):
            slot_number = (slot_index % request.meals_per_day) + 1
            day_number = (slot_index // request.meals_per_day) + 1
            slot_label_text = slot_label(request.meals_per_day, slot_number, request.meal_structure).lower()
            slot_matches = self.slot_match_recipes(candidates, request, slot_number)
            reasonable_candidates = self.slot_reasonable_recipes(candidates, request, slot_number)
            effective_candidates = self._slot_recipe_groups(candidates, request, slot_number).mains
            rejection_counts: dict[str, int] = {}
            calorie_supported = 0
            price_supported = 0
            under_budget = 0
            under_cap = 0

            for recipe in effective_candidates:
                if recipe.estimated_calories_per_serving is None:
                    rejection_counts["unknown_calories"] = rejection_counts.get("unknown_calories", 0) + 1
                    continue
                calorie_supported += 1
                projected_quantities = {
                    name: AggregatedIngredient(quantity=value.quantity, unit=value.unit)
                    for name, value in purchased_quantities.items()
                }
                self._apply_recipe(projected_quantities, recipe, request, pantry_inventory)
                projected_total = self._estimate_total_cost(projected_quantities)
                if projected_total.unknown_item_count:
                    rejection_counts["unusable_price"] = rejection_counts.get("unusable_price", 0) + 1
                    continue
                price_supported += 1
                if projected_total.total_cost > request.weekly_budget + 1e-9:
                    rejection_counts["exceeds_weekly_budget"] = rejection_counts.get("exceeds_weekly_budget", 0) + 1
                    continue
                under_budget += 1
                if self._recipe_count(meals, recipe.title) >= variety_profile.same_recipe_weekly_cap:
                    rejection_counts["repeat_cap"] = rejection_counts.get("repeat_cap", 0) + 1
                    continue
                under_cap += 1

            selected = self._select_recipe(
                all_candidates=candidates,
                candidate_groups=self._slot_recipe_groups(candidates, request, slot_number),
                request=request,
                pantry_inventory=pantry_inventory,
                variety_profile=variety_profile,
                purchased_quantities=purchased_quantities,
                meals=meals,
                day_number=day_number,
                slot_number=slot_number,
                request_cycle_offset=0,
            )
            chosen_title = None
            used_repeat_fallback = False
            if selected is not None:
                recipe, incremental_cost, used_repeat_fallback = selected
                chosen_title = recipe.title
                self._apply_recipe(purchased_quantities, recipe, request, pantry_inventory)
                if used_repeat_fallback:
                    forced_repeat_slots += 1
                meals.append(
                    PlannedMeal(
                        day=day_number,
                        slot=slot_number,
                        recipe=recipe,
                        scaled_servings=request.servings,
                        incremental_cost=round(incremental_cost, 2),
                        consumed_cost=self._estimate_recipe_consumed_cost(recipe, request, pantry_inventory),
                        meal_role=self._recipe_role(recipe, slot_label_text),
                    )
                )

            for reason, count in rejection_counts.items():
                top_rejections[reason] = top_rejections.get(reason, 0) + count
            slot_diagnostics.append(
                SlotSelectionDiagnostics(
                    day=day_number,
                    slot_number=slot_number,
                    slot_label=slot_label_text,
                    slot_match_count=len(slot_matches),
                    reasonable_count=len(reasonable_candidates),
                    calorie_supported_count=calorie_supported,
                    price_supported_count=price_supported,
                    under_budget_count=under_budget,
                    under_cap_count=under_cap,
                    rejection_counts=tuple(sorted(rejection_counts.items(), key=lambda item: (-item[1], item[0]))),
                    chosen_title=chosen_title,
                    used_repeat_fallback=used_repeat_fallback,
                )
            )

        return PlanSelectionDiagnostics(
            slot_diagnostics=tuple(slot_diagnostics),
            top_rejection_reasons=tuple(sorted(top_rejections.items(), key=lambda item: (-item[1], item[0]))),
            forced_repeat_slots=forced_repeat_slots,
            repeat_message_truthful=all(
                not slot_diag.used_repeat_fallback or slot_diag.under_cap_count == 0
                for slot_diag in slot_diagnostics
            ),
        )

    def _neighbor_recipe_count(
        self,
        meals: list[PlannedMeal],
        recipe_title: str,
        day_number: int,
        slot_number: int,
        window_size: int = 2,
    ) -> int:
        target_index = self._meal_sequence_index(day_number, slot_number)
        return sum(
            1
            for meal in meals
            if meal.recipe.title == recipe_title
            and abs(self._meal_sequence_index(meal.day, meal.slot) - target_index) <= window_size
        )

    def _cuisine_count(self, meals: list[PlannedMeal], cuisine: str) -> int:
        normalized_cuisine = normalize_name(cuisine)
        return sum(1 for meal in meals if normalize_name(meal.recipe.cuisine) == normalized_cuisine)

    def _recent_cuisine_count(self, meals: list[PlannedMeal], cuisine: str) -> int:
        normalized_cuisine = normalize_name(cuisine)
        return sum(1 for meal in meals[-4:] if normalize_name(meal.recipe.cuisine) == normalized_cuisine)

    def _neighbor_cuisine_count(
        self,
        meals: list[PlannedMeal],
        cuisine: str,
        day_number: int,
        slot_number: int,
        window_size: int = 2,
    ) -> int:
        target_index = self._meal_sequence_index(day_number, slot_number)
        normalized_cuisine = normalize_name(cuisine)
        return sum(
            1
            for meal in meals
            if normalize_name(meal.recipe.cuisine) == normalized_cuisine
            and abs(self._meal_sequence_index(meal.day, meal.slot) - target_index) <= window_size
        )

    def _meal_sequence_index(self, day_number: int, slot_number: int) -> int:
        return ((day_number - 1) * 10) + slot_number

    def _estimate_total_cost(self, quantities: dict[str, AggregatedIngredient]) -> CostEstimate:
        total = 0.0
        unknown_item_count = 0
        for name, requirement in quantities.items():
            product = self.grocery_provider.get_product(name)
            decision = self._package_purchase(name, product, requirement.quantity, requirement.unit)
            if decision.cost is None:
                unknown_item_count += 1
                continue
            total += decision.cost
        return CostEstimate(total_cost=round(total, 2), unknown_item_count=unknown_item_count)

    def _build_shopping_list(
        self,
        quantities: dict[str, AggregatedIngredient],
    ) -> tuple[tuple[ShoppingListItem, ...], float]:
        items: list[ShoppingListItem] = []
        total = 0.0
        for name in sorted(quantities):
            requirement = quantities[name]
            product = self.grocery_provider.get_product(name)
            decision = self._package_purchase(name, product, requirement.quantity, requirement.unit)
            total += 0.0 if decision.cost is None else decision.cost
            items.append(
                ShoppingListItem(
                    name=name,
                    quantity=round(requirement.quantity, 2),
                    unit=requirement.unit,
                    estimated_packages=decision.packages,
                    package_quantity=0.0 if product is None else round(product.package_quantity, 2),
                    package_unit="" if product is None else product.unit,
                    purchased_quantity=round(decision.purchased_quantity, 2),
                    carryover_used_quantity=round(decision.carryover_used_quantity, 2),
                    leftover_quantity_remaining=round(decision.leftover_quantity_remaining, 2),
                    estimated_cost=None if decision.cost is None else round(decision.cost, 2),
                    pricing_source=product.source if product is not None else "unpriced",
                )
            )
        return tuple(items), round(total, 2)

    def _validate_constraint_support(
        self,
        candidates: tuple[Recipe, ...],
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
    ) -> None:
        calorie_slot_gaps: list[str] = []
        budget_slot_gaps: list[str] = []
        for slot_number in range(1, request.meals_per_day + 1):
            slot_candidates = self._slot_recipe_groups(candidates, request, slot_number).mains
            label = slot_label(request.meals_per_day, slot_number, request.meal_structure).lower()
            if not any(recipe.estimated_calories_per_serving is not None for recipe in slot_candidates):
                calorie_slot_gaps.append(label)
            if not any(self._recipe_cost_is_known(recipe, request, pantry_inventory) for recipe in slot_candidates):
                budget_slot_gaps.append(label)

        if calorie_slot_gaps:
            labels = ", ".join(calorie_slot_gaps)
            raise PlannerError(
                f"No recipes with known calorie estimates are available for {labels}, so the calorie target cannot be satisfied."
            )
        if budget_slot_gaps:
            labels = ", ".join(budget_slot_gaps)
            raise PlannerError(
                f"No fully priced recipes are available for {labels}, so the weekly budget cannot be verified."
            )

    def _recipe_cost_is_known(
        self,
        recipe: Recipe,
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
    ) -> bool:
        quantities: dict[str, AggregatedIngredient] = {}
        self._apply_recipe(quantities, recipe, request, pantry_inventory)
        return self._estimate_total_cost(quantities).unknown_item_count == 0

    def _estimate_recipe_consumed_cost(
        self,
        recipe: Recipe,
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
    ) -> float | None:
        total = 0.0
        scale = request.servings / recipe.base_servings
        for ingredient in recipe.ingredients:
            ingredient_name = normalize_ingredient_name(ingredient.name)
            if ingredient_name in pantry_inventory:
                continue
            product = self.grocery_provider.get_product(ingredient_name)
            cost = self._consumed_requirement_cost(
                ingredient_name,
                product,
                ingredient.quantity * scale,
                ingredient.unit,
            )
            if cost is None:
                return None
            total += cost
        return round(total, 2)

    def _cost_for_requirement(self, ingredient_name: str, product, required_quantity: float, required_unit: str) -> float:
        decision = self._package_purchase(ingredient_name, product, required_quantity, required_unit)
        return 0.0 if decision.cost is None else decision.cost

    def _consumed_requirement_cost(
        self,
        ingredient_name: str,
        product,
        required_quantity: float,
        required_unit: str,
    ) -> float | None:
        if product is None or product.package_price is None or product.package_quantity <= 0:
            return None
        purchasable_quantity = self._convert_to_purchase_unit(
            ingredient_name,
            required_quantity,
            required_unit,
            product.unit,
        )
        if purchasable_quantity is None:
            return None
        return (purchasable_quantity / product.package_quantity) * product.package_price

    def _package_purchase(
        self,
        ingredient_name: str,
        product,
        required_quantity: float,
        required_unit: str,
    ) -> PurchaseDecision:
        if product is None or product.package_price is None or product.package_quantity <= 0:
            return PurchaseDecision(0, 0.0, 0.0, 0.0, 0.0, None)
        purchasable_quantity = self._convert_to_purchase_unit(
            ingredient_name,
            required_quantity,
            required_unit,
            product.unit,
        )
        if purchasable_quantity is None:
            return PurchaseDecision(0, 0.0, 0.0, 0.0, 0.0, None)
        available_carryover = self._available_carryover_quantity(ingredient_name, product.unit)
        carryover_used = min(available_carryover, purchasable_quantity)
        remaining_required = max(purchasable_quantity - carryover_used, 0.0)
        packages = math.ceil(remaining_required / product.package_quantity)
        purchased_quantity = packages * product.package_quantity
        leftover_quantity_remaining = max(available_carryover + purchased_quantity - purchasable_quantity, 0.0)
        return PurchaseDecision(
            packages=packages,
            purchased_quantity=purchased_quantity,
            carryover_used_quantity=carryover_used,
            consumed_purchase_quantity=purchasable_quantity,
            leftover_quantity_remaining=leftover_quantity_remaining,
            cost=packages * product.package_price,
        )

    def _available_carryover_quantity(self, ingredient_name: str, product_unit: str) -> float:
        cache_key = (normalize_ingredient_name(ingredient_name), normalize_unit(product_unit))
        cached = self._carryover_quantity_cache.get(cache_key)
        if cached is not None:
            return cached
        inventory_item = self.carryover_inventory.get(normalize_ingredient_name(ingredient_name))
        if inventory_item is None:
            self._carryover_quantity_cache[cache_key] = 0.0
            return 0.0
        if normalize_unit(inventory_item.unit) != normalize_unit(product_unit):
            self._carryover_quantity_cache[cache_key] = 0.0
            return 0.0
        self._carryover_quantity_cache[cache_key] = inventory_item.quantity
        return inventory_item.quantity

    def _convert_to_purchase_unit(
        self,
        ingredient_name: str,
        quantity: float,
        recipe_unit: str,
        product_unit: str,
    ) -> float | None:
        normalized_recipe_unit = normalize_unit(recipe_unit)
        normalized_product_unit = normalize_unit(product_unit)
        if normalized_recipe_unit == normalized_product_unit:
            return quantity
        factor_key = (
            normalize_ingredient_name(ingredient_name),
            normalized_recipe_unit,
            normalized_product_unit,
        )
        if factor_key not in self._unit_conversion_factor_cache:
            converted_one = convert_ingredient_unit_quantity(
                ingredient_name,
                1.0,
                normalized_recipe_unit,
                normalized_product_unit,
            )
            self._unit_conversion_factor_cache[factor_key] = converted_one
        factor = self._unit_conversion_factor_cache[factor_key]
        if factor is None:
            return None
        return quantity * factor


def day_name(day_number: int) -> str:
    return DAY_NAMES[day_number - 1]


def slot_label(meals_per_day: int, slot_number: int, meal_structure: tuple[str, ...] = ()) -> str:
    desired_types = meal_structure or SLOT_LABELS.get(meals_per_day, ("meal",))
    desired = desired_types[min(slot_number - 1, len(desired_types) - 1)]
    return desired.title()
