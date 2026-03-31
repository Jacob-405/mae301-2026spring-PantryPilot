from __future__ import annotations

import math
from dataclasses import dataclass

from pantry_pilot.models import MealPlan, PlannedMeal, PlannerRequest, Recipe, ShoppingListItem
from pantry_pilot.normalization import convert_unit_quantity, normalize_ingredient_name, normalize_name, normalize_unit
from pantry_pilot.providers import GroceryProvider, LocalRecipeProvider, MockGroceryProvider


DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SLOT_LABELS = {
    1: ("meal",),
    2: ("breakfast", "dinner"),
    3: ("breakfast", "lunch", "dinner"),
}


@dataclass
class AggregatedIngredient:
    quantity: float
    unit: str


@dataclass(frozen=True)
class VarietyProfile:
    same_recipe_weekly_cap: int
    repetition_penalty: float
    slot_repetition_penalty: float
    recent_repeat_penalty: float
    cuisine_repetition_penalty: float
    recent_cuisine_penalty: float
    calorie_target_weight: float


class PlannerError(Exception):
    pass


class WeeklyMealPlanner:
    def __init__(
        self,
        recipe_provider: LocalRecipeProvider | None = None,
        grocery_provider: GroceryProvider | None = None,
        pricing_source: str = "mock",
        selected_store: str = "",
        same_recipe_weekly_cap: int = 2,
        repetition_penalty: float = 4.0,
        slot_repetition_penalty: float = 2.5,
        recent_repeat_penalty: float = 1.5,
        pantry_preference_bonus: float = 0.35,
    ) -> None:
        self.recipe_provider = recipe_provider or LocalRecipeProvider()
        self.grocery_provider = grocery_provider or MockGroceryProvider()
        self.pricing_source = pricing_source
        self.selected_store = selected_store
        self.same_recipe_weekly_cap = same_recipe_weekly_cap
        self.repetition_penalty = repetition_penalty
        self.slot_repetition_penalty = slot_repetition_penalty
        self.recent_repeat_penalty = recent_repeat_penalty
        self.pantry_preference_bonus = pantry_preference_bonus

    def create_plan(self, request: PlannerRequest) -> MealPlan:
        candidates = self._filter_recipes(request)
        if not candidates:
            raise PlannerError("No recipes match the current safety and planning filters.")

        total_slots = 7 * request.meals_per_day
        pantry_inventory = self._normalized_pantry_inventory(request)
        variety_profile = self._variety_profile(request)
        purchased_quantities: dict[str, AggregatedIngredient] = {}
        meals: list[PlannedMeal] = []
        notes: list[str] = []
        forced_repeat_slots = 0

        for slot_index in range(total_slots):
            slot_number = (slot_index % request.meals_per_day) + 1
            day_number = (slot_index // request.meals_per_day) + 1
            selected = self._select_recipe(
                candidates,
                request,
                pantry_inventory,
                variety_profile,
                purchased_quantities,
                meals,
                day_number,
                slot_number,
            )
            if selected is None:
                raise PlannerError("The planner could not build a full 7-day plan within the weekly budget.")

            recipe, incremental_cost, exceeded_cap = selected
            self._apply_recipe(purchased_quantities, recipe, request, pantry_inventory)
            if exceeded_cap:
                forced_repeat_slots += 1
            meals.append(
                PlannedMeal(
                    day=day_number,
                    slot=slot_number,
                    recipe=recipe,
                    scaled_servings=request.servings,
                    incremental_cost=round(incremental_cost, 2),
                )
            )

        shopping_list, total_cost = self._build_shopping_list(purchased_quantities)
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

    def _filter_recipes(self, request: PlannerRequest) -> tuple[Recipe, ...]:
        allergies = {normalize_name(value) for value in request.allergies}
        excluded = {normalize_ingredient_name(value) for value in request.excluded_ingredients}
        required_tags = {normalize_name(value) for value in request.diet_restrictions}
        cuisines = {normalize_name(value) for value in request.cuisine_preferences}

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
            if recipe.prep_time_minutes > request.max_prep_time_minutes:
                continue
            if cuisines and normalize_name(recipe.cuisine) not in cuisines:
                continue
            filtered.append(recipe)

        return tuple(sorted(filtered, key=lambda recipe: recipe.title))

    def _select_recipe(
        self,
        candidates: tuple[Recipe, ...],
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
        variety_profile: VarietyProfile,
        purchased_quantities: dict[str, AggregatedIngredient],
        meals: list[PlannedMeal],
        day_number: int,
        slot_number: int,
    ) -> tuple[Recipe, float, bool] | None:
        current_total = self._estimate_total_cost(purchased_quantities)
        slot_candidates = self._recipes_for_slot(candidates, request.meals_per_day, slot_number)
        preferred_recipes = tuple(
            recipe
            for recipe in slot_candidates
            if self._recipe_count(meals, recipe.title) < variety_profile.same_recipe_weekly_cap
        )

        best_choice = self._best_choice(
            candidates,
            preferred_recipes,
            request,
            pantry_inventory,
            variety_profile,
            purchased_quantities,
            meals,
            day_number,
            slot_number,
            current_total,
        )
        if best_choice is not None:
            return best_choice[0], best_choice[1], False

        best_choice = self._best_choice(
            candidates,
            slot_candidates,
            request,
            pantry_inventory,
            variety_profile,
            purchased_quantities,
            meals,
            day_number,
            slot_number,
            current_total,
        )
        if best_choice is None:
            return None
        return best_choice[0], best_choice[1], True

    def _best_choice(
        self,
        all_candidates: tuple[Recipe, ...],
        candidates: tuple[Recipe, ...],
        request: PlannerRequest,
        pantry_inventory: frozenset[str],
        variety_profile: VarietyProfile,
        purchased_quantities: dict[str, AggregatedIngredient],
        meals: list[PlannedMeal],
        day_number: int,
        slot_number: int,
        current_total: float,
    ) -> tuple[Recipe, float] | None:
        best_choice: tuple[tuple[float, float, int, int, int, int, int, str], Recipe, float] | None = None

        for recipe in candidates:
            projected_quantities = {
                name: AggregatedIngredient(quantity=value.quantity, unit=value.unit)
                for name, value in purchased_quantities.items()
            }
            self._apply_recipe(projected_quantities, recipe, request, pantry_inventory)
            projected_total = self._estimate_total_cost(projected_quantities)
            if projected_total > request.weekly_budget + 1e-9:
                continue

            incremental_cost = projected_total - current_total
            pantry_match_count = self._pantry_match_count(recipe, pantry_inventory)
            repeat_count = self._recipe_count(meals, recipe.title)
            slot_repeat_count = self._slot_recipe_count(meals, recipe.title, slot_number)
            recent_repeat_count = self._recent_repeat_count(meals, recipe.title)
            cuisine_repeat_count = self._cuisine_count(meals, recipe.cuisine)
            recent_cuisine_count = self._recent_cuisine_count(meals, recipe.cuisine)
            projected_day_calories = self._projected_day_calories(
                all_candidates,
                meals,
                recipe,
                request,
                day_number,
                slot_number,
            )
            calorie_penalty = self._calorie_target_penalty(
                projected_day_calories,
                request.daily_calorie_target_min,
                request.daily_calorie_target_max,
            )
            effective_cost = incremental_cost
            effective_cost -= pantry_match_count * self.pantry_preference_bonus
            effective_cost += repeat_count * variety_profile.repetition_penalty
            effective_cost += slot_repeat_count * variety_profile.slot_repetition_penalty
            effective_cost += recent_repeat_count * variety_profile.recent_repeat_penalty
            effective_cost += cuisine_repeat_count * variety_profile.cuisine_repetition_penalty
            effective_cost += recent_cuisine_count * variety_profile.recent_cuisine_penalty
            effective_cost += calorie_penalty * variety_profile.calorie_target_weight
            sort_key = (
                round(effective_cost, 4),
                round(calorie_penalty, 4),
                -pantry_match_count,
                repeat_count,
                slot_repeat_count,
                recent_repeat_count,
                cuisine_repeat_count,
                recent_cuisine_count,
                recipe.title,
            )
            if best_choice is None or sort_key < best_choice[0]:
                best_choice = (sort_key, recipe, incremental_cost)

        if best_choice is None:
            return None
        return best_choice[1], round(best_choice[2], 2)

    def _recipes_for_slot(
        self,
        candidates: tuple[Recipe, ...],
        meals_per_day: int,
        slot_number: int,
    ) -> tuple[Recipe, ...]:
        desired_types = SLOT_LABELS.get(meals_per_day, ("meal",))
        desired = desired_types[min(slot_number - 1, len(desired_types) - 1)]
        matching = tuple(
            recipe for recipe in candidates if desired == "meal" or desired in recipe.meal_types
        )
        return matching or candidates

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
            return VarietyProfile(
                same_recipe_weekly_cap=self.same_recipe_weekly_cap + 1,
                repetition_penalty=self.repetition_penalty * 0.55,
                slot_repetition_penalty=self.slot_repetition_penalty * 0.55,
                recent_repeat_penalty=self.recent_repeat_penalty * 0.55,
                cuisine_repetition_penalty=0.45,
                recent_cuisine_penalty=0.2,
                calorie_target_weight=0.85,
            )
        if preference == "high":
            return VarietyProfile(
                same_recipe_weekly_cap=max(1, self.same_recipe_weekly_cap - 1),
                repetition_penalty=self.repetition_penalty * 1.8,
                slot_repetition_penalty=self.slot_repetition_penalty * 1.8,
                recent_repeat_penalty=self.recent_repeat_penalty * 1.8,
                cuisine_repetition_penalty=1.2,
                recent_cuisine_penalty=0.8,
                calorie_target_weight=1.15,
            )
        return VarietyProfile(
            same_recipe_weekly_cap=self.same_recipe_weekly_cap,
            repetition_penalty=self.repetition_penalty * 1.2,
            slot_repetition_penalty=self.slot_repetition_penalty * 1.2,
            recent_repeat_penalty=self.recent_repeat_penalty * 1.2,
            cuisine_repetition_penalty=0.8,
            recent_cuisine_penalty=0.45,
            calorie_target_weight=1.0,
        )

    def _pantry_match_count(self, recipe: Recipe, pantry_inventory: frozenset[str]) -> int:
        return sum(
            1
            for ingredient in recipe.ingredients
            if normalize_ingredient_name(ingredient.name) in pantry_inventory
        )

    def _meal_calories(self, recipe: Recipe, servings: int) -> int:
        return recipe.estimated_calories_per_serving * servings

    def _current_day_calories(self, meals: list[PlannedMeal], day_number: int) -> int:
        return sum(self._meal_calories(meal.recipe, meal.scaled_servings) for meal in meals if meal.day == day_number)

    def _projected_day_calories(
        self,
        candidates: tuple[Recipe, ...],
        meals: list[PlannedMeal],
        recipe: Recipe,
        request: PlannerRequest,
        day_number: int,
        slot_number: int,
    ) -> float:
        projected_total = self._current_day_calories(meals, day_number) + self._meal_calories(recipe, request.servings)
        for future_slot_number in range(slot_number + 1, request.meals_per_day + 1):
            projected_total += self._average_slot_calories(
                candidates,
                request.meals_per_day,
                future_slot_number,
                request.servings,
            )
        return projected_total

    def _average_slot_calories(
        self,
        candidates: tuple[Recipe, ...],
        meals_per_day: int,
        slot_number: int,
        servings: int,
    ) -> float:
        slot_candidates = self._recipes_for_slot(candidates, meals_per_day, slot_number)
        if not slot_candidates:
            return 0.0
        total = sum(self._meal_calories(recipe, servings) for recipe in slot_candidates)
        return total / len(slot_candidates)

    def _calorie_target_penalty(self, projected_day_calories: float, minimum: int, maximum: int) -> float:
        lower_bound = min(minimum, maximum)
        upper_bound = max(minimum, maximum)
        midpoint = (lower_bound + upper_bound) / 2
        if lower_bound <= projected_day_calories <= upper_bound:
            return abs(projected_day_calories - midpoint) / 600
        if projected_day_calories < lower_bound:
            return (lower_bound - projected_day_calories) / 220
        return (projected_day_calories - upper_bound) / 220

    def _recipe_count(self, meals: list[PlannedMeal], recipe_title: str) -> int:
        return sum(1 for meal in meals if meal.recipe.title == recipe_title)

    def _slot_recipe_count(self, meals: list[PlannedMeal], recipe_title: str, slot_number: int) -> int:
        return sum(1 for meal in meals if meal.recipe.title == recipe_title and meal.slot == slot_number)

    def _recent_repeat_count(self, meals: list[PlannedMeal], recipe_title: str) -> int:
        return sum(1 for meal in meals[-3:] if meal.recipe.title == recipe_title)

    def _cuisine_count(self, meals: list[PlannedMeal], cuisine: str) -> int:
        normalized_cuisine = normalize_name(cuisine)
        return sum(1 for meal in meals if normalize_name(meal.recipe.cuisine) == normalized_cuisine)

    def _recent_cuisine_count(self, meals: list[PlannedMeal], cuisine: str) -> int:
        normalized_cuisine = normalize_name(cuisine)
        return sum(1 for meal in meals[-4:] if normalize_name(meal.recipe.cuisine) == normalized_cuisine)

    def _estimate_total_cost(self, quantities: dict[str, AggregatedIngredient]) -> float:
        total = 0.0
        for name, requirement in quantities.items():
            product = self.grocery_provider.get_product(name)
            total += self._cost_for_requirement(product, requirement.quantity, requirement.unit)
        return round(total, 2)

    def _build_shopping_list(
        self,
        quantities: dict[str, AggregatedIngredient],
    ) -> tuple[tuple[ShoppingListItem, ...], float]:
        items: list[ShoppingListItem] = []
        total = 0.0
        for name in sorted(quantities):
            requirement = quantities[name]
            product = self.grocery_provider.get_product(name)
            packages, purchased_quantity, cost = self._package_purchase(product, requirement.quantity, requirement.unit)
            total += cost
            items.append(
                ShoppingListItem(
                    name=name,
                    quantity=round(requirement.quantity, 2),
                    unit=requirement.unit,
                    estimated_packages=packages,
                    package_quantity=0.0 if product is None else round(product.package_quantity, 2),
                    package_unit="" if product is None else product.unit,
                    purchased_quantity=round(purchased_quantity, 2),
                    estimated_cost=round(cost, 2) if product is not None and product.package_price is not None else None,
                    pricing_source=product.source if product is not None else "unpriced",
                )
            )
        return tuple(items), round(total, 2)

    def _cost_for_requirement(self, product, required_quantity: float, required_unit: str) -> float:
        _, _, cost = self._package_purchase(product, required_quantity, required_unit)
        return cost

    def _package_purchase(
        self,
        product,
        required_quantity: float,
        required_unit: str,
    ) -> tuple[int, float, float]:
        if product is None or product.package_price is None or product.package_quantity <= 0:
            return 0, 0.0, 0.0
        purchasable_quantity = self._convert_to_purchase_unit(required_quantity, required_unit, product.unit)
        if purchasable_quantity is None:
            return 0, 0.0, 0.0
        packages = math.ceil(purchasable_quantity / product.package_quantity)
        purchased_quantity = packages * product.package_quantity
        return packages, purchased_quantity, packages * product.package_price

    def _convert_to_purchase_unit(
        self,
        quantity: float,
        recipe_unit: str,
        product_unit: str,
    ) -> float | None:
        normalized_recipe_unit = normalize_unit(recipe_unit)
        normalized_product_unit = normalize_unit(product_unit)
        if normalized_recipe_unit == normalized_product_unit:
            return quantity
        return convert_unit_quantity(quantity, normalized_recipe_unit, normalized_product_unit)


def day_name(day_number: int) -> str:
    return DAY_NAMES[day_number - 1]


def slot_label(meals_per_day: int, slot_number: int) -> str:
    desired_types = SLOT_LABELS.get(meals_per_day, ("meal",))
    desired = desired_types[min(slot_number - 1, len(desired_types) - 1)]
    return desired.title()
