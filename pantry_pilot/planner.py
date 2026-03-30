from __future__ import annotations

import math
from dataclasses import dataclass

from pantry_pilot.models import MealPlan, PlannedMeal, PlannerRequest, Recipe, ShoppingListItem
from pantry_pilot.normalization import normalize_name
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
    ) -> None:
        self.recipe_provider = recipe_provider or LocalRecipeProvider()
        self.grocery_provider = grocery_provider or MockGroceryProvider()
        self.pricing_source = pricing_source
        self.selected_store = selected_store
        self.same_recipe_weekly_cap = same_recipe_weekly_cap
        self.repetition_penalty = repetition_penalty
        self.slot_repetition_penalty = slot_repetition_penalty
        self.recent_repeat_penalty = recent_repeat_penalty

    def create_plan(self, request: PlannerRequest) -> MealPlan:
        candidates = self._filter_recipes(request)
        if not candidates:
            raise PlannerError("No recipes match the current safety and planning filters.")

        total_slots = 7 * request.meals_per_day
        purchased_quantities: dict[str, AggregatedIngredient] = {}
        meals: list[PlannedMeal] = []
        notes: list[str] = []
        forced_repeat_slots = 0

        for slot_index in range(total_slots):
            slot_number = (slot_index % request.meals_per_day) + 1
            selected = self._select_recipe(candidates, request, purchased_quantities, meals, slot_number)
            if selected is None:
                raise PlannerError("The planner could not build a full 7-day plan within the weekly budget.")

            recipe, incremental_cost, exceeded_cap = selected
            self._apply_recipe(purchased_quantities, recipe, request)
            if exceeded_cap:
                forced_repeat_slots += 1
            meals.append(
                PlannedMeal(
                    day=(slot_index // request.meals_per_day) + 1,
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
        excluded = {normalize_name(value) for value in request.excluded_ingredients}
        required_tags = {normalize_name(value) for value in request.diet_restrictions}
        cuisines = {normalize_name(value) for value in request.cuisine_preferences}

        filtered: list[Recipe] = []
        for recipe in self.recipe_provider.list_recipes():
            if recipe.allergens is None:
                continue
            recipe_allergens = {normalize_name(value) for value in recipe.allergens}
            if allergies & recipe_allergens:
                continue
            ingredient_names = {normalize_name(item.name) for item in recipe.ingredients}
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
        purchased_quantities: dict[str, AggregatedIngredient],
        meals: list[PlannedMeal],
        slot_number: int,
    ) -> tuple[Recipe, float, bool] | None:
        current_total = self._estimate_total_cost(purchased_quantities)
        slot_candidates = self._recipes_for_slot(candidates, request.meals_per_day, slot_number)
        preferred_recipes = tuple(
            recipe
            for recipe in slot_candidates
            if self._recipe_count(meals, recipe.title) < self.same_recipe_weekly_cap
        )

        best_choice = self._best_choice(
            preferred_recipes,
            request,
            purchased_quantities,
            meals,
            slot_number,
            current_total,
        )
        if best_choice is not None:
            return best_choice[0], best_choice[1], False

        best_choice = self._best_choice(
            slot_candidates,
            request,
            purchased_quantities,
            meals,
            slot_number,
            current_total,
        )
        if best_choice is None:
            return None
        return best_choice[0], best_choice[1], True

    def _best_choice(
        self,
        candidates: tuple[Recipe, ...],
        request: PlannerRequest,
        purchased_quantities: dict[str, AggregatedIngredient],
        meals: list[PlannedMeal],
        slot_number: int,
        current_total: float,
    ) -> tuple[Recipe, float] | None:
        best_choice: tuple[tuple[float, int, int, int, str], Recipe, float] | None = None

        for recipe in candidates:
            projected_quantities = {
                name: AggregatedIngredient(quantity=value.quantity, unit=value.unit)
                for name, value in purchased_quantities.items()
            }
            self._apply_recipe(projected_quantities, recipe, request)
            projected_total = self._estimate_total_cost(projected_quantities)
            if projected_total > request.weekly_budget + 1e-9:
                continue

            incremental_cost = projected_total - current_total
            repeat_count = self._recipe_count(meals, recipe.title)
            slot_repeat_count = self._slot_recipe_count(meals, recipe.title, slot_number)
            recent_repeat_count = self._recent_repeat_count(meals, recipe.title)
            effective_cost = incremental_cost
            effective_cost += repeat_count * self.repetition_penalty
            effective_cost += slot_repeat_count * self.slot_repetition_penalty
            effective_cost += recent_repeat_count * self.recent_repeat_penalty
            sort_key = (
                round(effective_cost, 4),
                repeat_count,
                slot_repeat_count,
                recent_repeat_count,
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
    ) -> None:
        pantry = {normalize_name(value) for value in request.pantry_staples}
        scale = request.servings / recipe.base_servings
        for ingredient in recipe.ingredients:
            name = normalize_name(ingredient.name)
            if name in pantry:
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

    def _recipe_count(self, meals: list[PlannedMeal], recipe_title: str) -> int:
        return sum(1 for meal in meals if meal.recipe.title == recipe_title)

    def _slot_recipe_count(self, meals: list[PlannedMeal], recipe_title: str, slot_number: int) -> int:
        return sum(1 for meal in meals if meal.recipe.title == recipe_title and meal.slot == slot_number)

    def _recent_repeat_count(self, meals: list[PlannedMeal], recipe_title: str) -> int:
        return sum(1 for meal in meals[-3:] if meal.recipe.title == recipe_title)

    def _estimate_total_cost(self, quantities: dict[str, AggregatedIngredient]) -> float:
        total = 0.0
        for name, requirement in quantities.items():
            product = self.grocery_provider.get_product(name)
            total += self._cost_for_requirement(product, requirement.quantity)
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
            packages, cost = self._package_and_cost(product, requirement.quantity)
            total += cost
            items.append(
                ShoppingListItem(
                    name=name,
                    quantity=round(requirement.quantity, 2),
                    unit=product.unit if product is not None else requirement.unit,
                    estimated_packages=packages,
                    estimated_cost=round(cost, 2) if product is not None and product.package_price is not None else None,
                    pricing_source=product.source if product is not None else "unpriced",
                )
            )
        return tuple(items), round(total, 2)

    def _cost_for_requirement(self, product, required_quantity: float) -> float:
        _, cost = self._package_and_cost(product, required_quantity)
        return cost

    def _package_and_cost(self, product, required_quantity: float) -> tuple[int, float]:
        if product is None or product.package_price is None or product.package_quantity <= 0:
            return 0, 0.0
        packages = math.ceil(required_quantity / product.package_quantity)
        return packages, packages * product.package_price


def day_name(day_number: int) -> str:
    return DAY_NAMES[day_number - 1]


def slot_label(meals_per_day: int, slot_number: int) -> str:
    desired_types = SLOT_LABELS.get(meals_per_day, ("meal",))
    desired = desired_types[min(slot_number - 1, len(desired_types) - 1)]
    return desired.title()
