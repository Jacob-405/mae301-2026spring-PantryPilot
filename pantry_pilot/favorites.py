from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from pantry_pilot.models import (
    MealPlan,
    NutritionEstimate,
    PersonalNutritionTargets,
    PlannedMeal,
    PlannerRequest,
    Recipe,
    RecipeIngredient,
    ShoppingListItem,
    UserNutritionProfile,
)


DEFAULT_FAVORITES_PATH = Path(__file__).resolve().parent.parent / "data" / "saved_plans.json"


@dataclass(frozen=True)
class SavedPlanRecord:
    plan_id: str
    name: str
    saved_at: str
    request: PlannerRequest
    plan: MealPlan


class FavoritePlanStore:
    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or DEFAULT_FAVORITES_PATH

    def list_saved_plans(self) -> tuple[tuple[SavedPlanRecord, ...], str | None]:
        payload, warning = self._read_payload()
        if not payload:
            return (), warning
        records: list[SavedPlanRecord] = []
        for row in payload:
            try:
                records.append(self._deserialize_record(row))
            except (KeyError, TypeError, ValueError):
                warning = "Some saved plans could not be read and were skipped."
        ordered = tuple(sorted(records, key=lambda item: item.saved_at, reverse=True))
        return ordered, warning

    def save_plan(
        self,
        *,
        name: str,
        saved_at: str,
        request: PlannerRequest,
        plan: MealPlan,
    ) -> SavedPlanRecord:
        existing_payload, _ = self._read_payload()
        record = SavedPlanRecord(
            plan_id=uuid4().hex,
            name=name.strip() or "Saved PantryPilot Plan",
            saved_at=saved_at,
            request=request,
            plan=plan,
        )
        existing_payload.append(self._serialize_record(record))
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(existing_payload, indent=2), encoding="utf-8")
        return record

    def load_plan(self, plan_id: str) -> tuple[SavedPlanRecord | None, str | None]:
        records, warning = self.list_saved_plans()
        for record in records:
            if record.plan_id == plan_id:
                return record, warning
        return None, warning

    def _read_payload(self) -> tuple[list[dict[str, Any]], str | None]:
        if not self.storage_path.exists():
            return [], None
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return [], f"Saved plans file at {self.storage_path} could not be read. PantryPilot is starting with an empty saved-plans list."
        if not isinstance(payload, list):
            return [], f"Saved plans file at {self.storage_path} has an unexpected format. PantryPilot is starting with an empty saved-plans list."
        rows = [row for row in payload if isinstance(row, dict)]
        return rows, None

    def _serialize_record(self, record: SavedPlanRecord) -> dict[str, Any]:
        return {
            "plan_id": record.plan_id,
            "name": record.name,
            "saved_at": record.saved_at,
            "request": asdict(record.request),
            "plan": {
                "meals": [self._serialize_planned_meal(meal) for meal in record.plan.meals],
                "shopping_list": [asdict(item) for item in record.plan.shopping_list],
                "estimated_total_cost": record.plan.estimated_total_cost,
                "notes": list(record.plan.notes),
                "pricing_source": record.plan.pricing_source,
                "selected_store": record.plan.selected_store,
            },
        }

    def _deserialize_record(self, row: dict[str, Any]) -> SavedPlanRecord:
        request_data = dict(row["request"])
        request_data["cuisine_preferences"] = tuple(request_data.get("cuisine_preferences", ()))
        request_data["allergies"] = tuple(request_data.get("allergies", ()))
        request_data["excluded_ingredients"] = tuple(request_data.get("excluded_ingredients", ()))
        request_data["diet_restrictions"] = tuple(request_data.get("diet_restrictions", ()))
        request_data["pantry_staples"] = tuple(request_data.get("pantry_staples", ()))
        request_data["meal_structure"] = tuple(request_data.get("meal_structure", ()))
        user_profile = request_data.get("user_profile")
        request_data["user_profile"] = None if user_profile is None else UserNutritionProfile(**user_profile)
        personal_targets = request_data.get("personal_targets")
        request_data["personal_targets"] = (
            None if personal_targets is None else PersonalNutritionTargets(**personal_targets)
        )
        plan_data = dict(row["plan"])
        meals = tuple(self._deserialize_planned_meal(item) for item in plan_data.get("meals", ()))
        shopping_list = tuple(
            ShoppingListItem(**item) for item in plan_data.get("shopping_list", ())
        )
        return SavedPlanRecord(
            plan_id=str(row["plan_id"]),
            name=str(row["name"]),
            saved_at=str(row["saved_at"]),
            request=PlannerRequest(**request_data),
            plan=MealPlan(
                meals=meals,
                shopping_list=shopping_list,
                estimated_total_cost=float(plan_data["estimated_total_cost"]),
                notes=tuple(plan_data.get("notes", ())),
                pricing_source=str(plan_data.get("pricing_source", "mock")),
                selected_store=str(plan_data.get("selected_store", "")),
            ),
        )

    def _serialize_planned_meal(self, meal: PlannedMeal) -> dict[str, Any]:
        return {
            "day": meal.day,
            "slot": meal.slot,
            "recipe": self._serialize_recipe(meal.recipe),
            "scaled_servings": meal.scaled_servings,
            "incremental_cost": meal.incremental_cost,
            "consumed_cost": meal.consumed_cost,
            "meal_role": meal.meal_role,
        }

    def _serialize_recipe(self, recipe: Recipe) -> dict[str, Any]:
        return {
            "recipe_id": recipe.recipe_id,
            "title": recipe.title,
            "cuisine": recipe.cuisine,
            "base_servings": recipe.base_servings,
            "estimated_calories_per_serving": recipe.estimated_calories_per_serving,
            "prep_time_minutes": recipe.prep_time_minutes,
            "meal_types": list(recipe.meal_types),
            "diet_tags": sorted(recipe.diet_tags),
            "allergens": None if recipe.allergens is None else sorted(recipe.allergens),
            "ingredients": [asdict(ingredient) for ingredient in recipe.ingredients],
            "steps": list(recipe.steps),
            "estimated_nutrition_per_serving": (
                None
                if recipe.estimated_nutrition_per_serving is None
                else asdict(recipe.estimated_nutrition_per_serving)
            ),
        }

    def _deserialize_planned_meal(self, row: dict[str, Any]) -> PlannedMeal:
        recipe_data = dict(row["recipe"])
        recipe_data["meal_types"] = tuple(recipe_data.get("meal_types", ()))
        recipe_data["diet_tags"] = frozenset(recipe_data.get("diet_tags", ()))
        allergens = recipe_data.get("allergens")
        recipe_data["allergens"] = None if allergens is None else frozenset(allergens)
        nutrition = recipe_data.get("estimated_nutrition_per_serving")
        recipe_data["estimated_nutrition_per_serving"] = (
            None if nutrition is None else NutritionEstimate(**nutrition)
        )
        recipe_data["ingredients"] = tuple(
            RecipeIngredient(**ingredient) for ingredient in recipe_data.get("ingredients", ())
        )
        recipe_data["steps"] = tuple(recipe_data.get("steps", ()))
        return PlannedMeal(
            day=int(row["day"]),
            slot=int(row["slot"]),
            recipe=Recipe(**recipe_data),
            scaled_servings=int(row["scaled_servings"]),
            incremental_cost=float(row["incremental_cost"]),
            consumed_cost=(
                None
                if row.get("consumed_cost") is None
                else float(row["consumed_cost"])
            ),
            meal_role=str(row.get("meal_role", "main")),
        )
