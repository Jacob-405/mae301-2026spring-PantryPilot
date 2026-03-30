from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecipeIngredient:
    name: str
    quantity: float
    unit: str


@dataclass(frozen=True)
class Recipe:
    title: str
    cuisine: str
    base_servings: int
    prep_time_minutes: int
    meal_types: tuple[str, ...]
    diet_tags: frozenset[str]
    allergens: frozenset[str] | None
    ingredients: tuple[RecipeIngredient, ...]
    steps: tuple[str, ...]


@dataclass(frozen=True)
class GroceryProduct:
    name: str
    package_quantity: float
    unit: str
    package_price: float | None
    source: str = "mock"


@dataclass(frozen=True)
class GroceryLocation:
    location_id: str
    name: str
    address_line: str
    city: str
    state: str
    postal_code: str
    chain: str = ""


@dataclass(frozen=True)
class PlannerRequest:
    weekly_budget: float
    servings: int
    cuisine_preferences: tuple[str, ...]
    allergies: tuple[str, ...]
    excluded_ingredients: tuple[str, ...]
    diet_restrictions: tuple[str, ...]
    pantry_staples: tuple[str, ...]
    max_prep_time_minutes: int
    meals_per_day: int
    zip_code: str = ""
    pricing_mode: str = "mock"
    store_location_id: str = ""


@dataclass(frozen=True)
class PlannedMeal:
    day: int
    slot: int
    recipe: Recipe
    scaled_servings: int
    incremental_cost: float


@dataclass(frozen=True)
class ShoppingListItem:
    name: str
    quantity: float
    unit: str
    estimated_packages: int
    estimated_cost: float | None
    pricing_source: str = "mock"


@dataclass(frozen=True)
class MealPlan:
    meals: tuple[PlannedMeal, ...]
    shopping_list: tuple[ShoppingListItem, ...]
    estimated_total_cost: float
    notes: tuple[str, ...] = ()
    pricing_source: str = "mock"
    selected_store: str = ""
