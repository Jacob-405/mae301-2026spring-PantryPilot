from __future__ import annotations

from pantry_pilot.ingredient_catalog import UNIT_CONVERSION_FACTORS, canonical_ingredient_name, canonical_unit_name


def normalize_name(value: str) -> str:
    cleaned = (value or "").strip().lower().replace("_", " ").replace("-", " ")
    for token in ",.;:()":
        cleaned = cleaned.replace(token, " ")
    return " ".join(cleaned.split())


def normalize_ingredient_name(value: str) -> str:
    return canonical_ingredient_name(value)


def normalize_unit(value: str) -> str:
    return canonical_unit_name(value)


def convert_unit_quantity(quantity: float, from_unit: str, to_unit: str) -> float | None:
    normalized_from = normalize_unit(from_unit)
    normalized_to = normalize_unit(to_unit)
    if normalized_from == normalized_to:
        return quantity
    factor = UNIT_CONVERSION_FACTORS.get((normalized_from, normalized_to))
    if factor is None:
        return None
    return quantity * factor


def parse_csv_list(value: str) -> tuple[str, ...]:
    parts = [normalize_name(part) for part in (value or "").split(",")]
    return tuple(part for part in parts if part)
