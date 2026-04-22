from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from pantry_pilot.models import MealPlan


DEFAULT_PANTRY_CARRYOVER_PATH = Path(__file__).resolve().parent.parent / "data" / "pantry_carryover.json"


@dataclass(frozen=True)
class PantryInventoryItem:
    name: str
    quantity: float
    unit: str


class PantryCarryoverStore:
    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or DEFAULT_PANTRY_CARRYOVER_PATH

    def load_inventory(self) -> tuple[PantryInventoryItem, ...]:
        if not self.storage_path.exists():
            return ()
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ()
        if not isinstance(payload, list):
            return ()
        items: list[PantryInventoryItem] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            try:
                quantity = float(row["quantity"])
            except (KeyError, TypeError, ValueError):
                continue
            if quantity <= 0:
                continue
            items.append(
                PantryInventoryItem(
                    name=str(row["name"]),
                    quantity=quantity,
                    unit=str(row["unit"]),
                )
            )
        return tuple(sorted(items, key=lambda item: item.name))

    def save_inventory(self, items: tuple[PantryInventoryItem, ...]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(item) for item in items if item.quantity > 0]
        self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def reset(self) -> None:
        if self.storage_path.exists():
            self.storage_path.unlink()

    def apply_plan(self, plan: MealPlan) -> tuple[PantryInventoryItem, ...]:
        inventory = {
            item.name: PantryInventoryItem(item.name, item.quantity, item.unit)
            for item in self.load_inventory()
        }
        for item in plan.shopping_list:
            if not item.package_unit:
                continue
            if item.leftover_quantity_remaining > 1e-9:
                inventory[item.name] = PantryInventoryItem(
                    name=item.name,
                    quantity=round(item.leftover_quantity_remaining, 4),
                    unit=item.package_unit,
                )
            else:
                inventory.pop(item.name, None)
        updated = tuple(sorted(inventory.values(), key=lambda entry: entry.name))
        self.save_inventory(updated)
        return updated
