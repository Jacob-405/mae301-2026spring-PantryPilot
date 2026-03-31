from __future__ import annotations


INGREDIENT_ALIASES = {
    "avocados": "avocado",
    "bell peppers": "bell pepper",
    "black bean": "black beans",
    "black beans canned": "black beans",
    "broccoli florets": "broccoli",
    "carrots": "carrot",
    "canned chickpeas": "chickpeas",
    "cherry tomatoes": "tomato",
    "cloves garlic": "garlic",
    "corn kernels": "corn",
    "egg": "eggs",
    "garlic clove": "garlic",
    "garlic cloves": "garlic",
    "lemons": "lemon",
    "limes": "lime",
    "old fashioned oats": "rolled oats",
    "penne pasta": "pasta",
    "red onion": "onion",
    "roma tomatoes": "tomato",
    "rolled oat": "rolled oats",
    "tomatoes": "tomato",
    "veggie broth": "vegetable broth",
    "yellow onion": "onion",
    "zucchinis": "zucchini",
}

UNIT_ALIASES = {
    "block": "block",
    "blocks": "block",
    "can": "can",
    "cans": "can",
    "clove": "clove",
    "cloves": "clove",
    "cup": "cup",
    "cups": "cup",
    "item": "item",
    "items": "item",
    "ounce": "oz",
    "ounces": "oz",
    "oz.": "oz",
    "oz": "oz",
    "lb": "lb",
    "pound": "lb",
    "pounds": "lb",
    "slice": "slice",
    "slices": "slice",
    "stalk": "stalk",
    "stalks": "stalk",
    "tbsp": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tsp": "tsp",
}

UNIT_CONVERSION_FACTORS = {
    ("tsp", "tbsp"): 1.0 / 3.0,
    ("tbsp", "tsp"): 3.0,
    ("tbsp", "cup"): 1.0 / 16.0,
    ("cup", "tbsp"): 16.0,
    ("tsp", "cup"): 1.0 / 48.0,
    ("cup", "tsp"): 48.0,
    ("oz", "lb"): 1.0 / 16.0,
    ("lb", "oz"): 16.0,
}


def normalize_name(value: str) -> str:
    cleaned = (value or "").strip().lower().replace("_", " ").replace("-", " ")
    for token in ",.;:()":
        cleaned = cleaned.replace(token, " ")
    return " ".join(cleaned.split())


def normalize_ingredient_name(value: str) -> str:
    normalized = normalize_name(value)
    return INGREDIENT_ALIASES.get(normalized, normalized)


def normalize_unit(value: str) -> str:
    normalized = normalize_name(value)
    return UNIT_ALIASES.get(normalized, normalized)


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
