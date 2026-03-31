from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecipeIngredient:
    name: str
    quantity: float
    unit: str


@dataclass(frozen=True)
class Recipe:
    recipe_id: str
    title: str
    cuisine: str
    base_servings: int
    estimated_calories_per_serving: int
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
    meal_structure: tuple[str, ...] = ()
    zip_code: str = ""
    pricing_mode: str = "mock"
    store_location_id: str = ""
    daily_calorie_target_min: int = 1600
    daily_calorie_target_max: int = 2200
    variety_preference: str = "balanced"
    leftovers_mode: str = "off"


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
    package_quantity: float = 0.0
    package_unit: str = ""
    purchased_quantity: float = 0.0
    estimated_cost: float | None = None
    pricing_source: str = "mock"


@dataclass(frozen=True)
class MealPlan:
    meals: tuple[PlannedMeal, ...]
    shopping_list: tuple[ShoppingListItem, ...]
    estimated_total_cost: float
    notes: tuple[str, ...] = ()
    pricing_source: str = "mock"
    selected_store: str = ""
