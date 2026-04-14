from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IngredientDietFlags:
    animal_product: bool = False
    meat: bool = False


@dataclass(frozen=True)
class IngredientCatalogEntry:
    canonical_name: str
    aliases: tuple[str, ...] = ()
    supported_units: tuple[str, ...] = ()
    allergens: frozenset[str] | None = None
    diet_flags: IngredientDietFlags = IngredientDietFlags()
    calories_per_unit: float | None = None
    calorie_unit: str = ""


@dataclass(frozen=True)
class UnitCatalogEntry:
    canonical_unit: str
    aliases: tuple[str, ...] = ()


_INGREDIENT_ENTRIES: tuple[IngredientCatalogEntry, ...] = (
    IngredientCatalogEntry("avocado", aliases=("avocados",), supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry("banana", supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry(
        "bell pepper",
        aliases=("bell peppers", "green bell pepper", "red bell pepper"),
        supported_units=("item",),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "black pepper",
        aliases=("ground black pepper", "black pepper to taste"),
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "black beans",
        aliases=("black bean", "black beans canned"),
        supported_units=("can", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("bread", supported_units=("slice",), allergens=frozenset({"gluten"})),
    IngredientCatalogEntry(
        "broccoli",
        aliases=("broccoli florets",),
        supported_units=("cup",),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("canned tomatoes", supported_units=("can",), allergens=frozenset()),
    IngredientCatalogEntry("carrot", aliases=("carrots",), supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry("celery", supported_units=("stalk",), allergens=frozenset()),
    IngredientCatalogEntry(
        "cheddar cheese",
        supported_units=("cup",),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "chicken breast",
        aliases=("skinless boneless chicken breast halves", "boneless skinless chicken breasts", "chicken breast halves"),
        supported_units=("lb",),
        allergens=frozenset(),
        diet_flags=IngredientDietFlags(meat=True),
    ),
    IngredientCatalogEntry("chickpeas", aliases=("canned chickpeas",), supported_units=("can", "cup"), allergens=frozenset()),
    IngredientCatalogEntry("chili powder", supported_units=("tbsp",), allergens=frozenset()),
    IngredientCatalogEntry("cinnamon", supported_units=("tsp",), allergens=frozenset()),
    IngredientCatalogEntry("corn", aliases=("corn kernels",), supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry("cucumber", supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry(
        "cumin",
        aliases=("ground cumin",),
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("curry powder", supported_units=("tbsp",), allergens=frozenset()),
    IngredientCatalogEntry(
        "eggs",
        aliases=("egg",),
        supported_units=("item",),
        allergens=frozenset({"egg"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "flour",
        aliases=("all purpose flour", "all-purpose flour"),
        supported_units=("cup", "tbsp"),
        allergens=frozenset({"gluten"}),
    ),
    IngredientCatalogEntry(
        "feta",
        supported_units=("cup",),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry("frozen berries", supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry(
        "garlic",
        aliases=("cloves garlic", "garlic clove", "garlic cloves", "minced garlic", "garlic minced"),
        supported_units=("clove", "tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "garlic powder",
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "ginger",
        aliases=("fresh ginger root", "ground ginger", "minced fresh ginger root"),
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("granola", supported_units=("cup",), allergens=frozenset({"gluten"})),
    IngredientCatalogEntry(
        "ground turkey",
        supported_units=("lb",),
        allergens=frozenset(),
        diet_flags=IngredientDietFlags(meat=True),
    ),
    IngredientCatalogEntry(
        "honey",
        supported_units=("tbsp",),
        allergens=frozenset(),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry("lemon", aliases=("lemons",), supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry("lentils", supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry("lime", aliases=("limes",), supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry(
        "milk",
        supported_units=("cup",),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry("olive oil", supported_units=("tbsp",), allergens=frozenset()),
    IngredientCatalogEntry(
        "onion",
        aliases=("red onion", "yellow onion", "chopped onion", "diced onion", "white onion", "sweet onion"),
        supported_units=("item", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "oregano",
        aliases=("dried oregano",),
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "parmesan",
        aliases=("grated parmesan cheese",),
        supported_units=("cup", "tbsp"),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry("pasta", aliases=("penne pasta",), supported_units=("oz",), allergens=frozenset({"gluten"})),
    IngredientCatalogEntry(
        "paprika",
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("peanut butter", supported_units=("tbsp",), allergens=frozenset({"peanut"})),
    IngredientCatalogEntry(
        "rice",
        aliases=("white rice", "cooked white rice", "uncooked white rice"),
        supported_units=("cup",),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "rolled oats",
        aliases=("old fashioned oats", "rolled oat"),
        supported_units=("cup",),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "salt",
        aliases=("kosher salt", "sea salt", "salt and ground black pepper to taste"),
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("salsa", supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry("soy sauce", supported_units=("tbsp",), allergens=frozenset({"soy"})),
    IngredientCatalogEntry("spinach", supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry("tofu", supported_units=("block",), allergens=frozenset({"soy"})),
    IngredientCatalogEntry(
        "tomato",
        aliases=("cherry tomatoes", "roma tomatoes", "tomatoes"),
        supported_units=("item",),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "tomato sauce",
        supported_units=("can", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "vegetable broth",
        aliases=("veggie broth",),
        supported_units=("cup",),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "vegetable oil",
        aliases=("canola oil",),
        supported_units=("tbsp", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "water",
        supported_units=("cup",),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "yogurt",
        supported_units=("cup",),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry("zucchini", aliases=("zucchinis",), supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry(
        "butter",
        supported_units=("tbsp", "cup"),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
)

_UNIT_ENTRIES: tuple[UnitCatalogEntry, ...] = (
    UnitCatalogEntry("block", aliases=("blocks",)),
    UnitCatalogEntry("can", aliases=("cans",)),
    UnitCatalogEntry("clove", aliases=("cloves",)),
    UnitCatalogEntry("cup", aliases=("cups",)),
    UnitCatalogEntry("item", aliases=("items",)),
    UnitCatalogEntry("package", aliases=("packages",)),
    UnitCatalogEntry("lb", aliases=("lbs", "pound", "pounds")),
    UnitCatalogEntry("oz", aliases=("ounce", "ounces", "oz.", "oz")),
    UnitCatalogEntry("pinch", aliases=("pinches",)),
    UnitCatalogEntry("slice", aliases=("slices",)),
    UnitCatalogEntry("stalk", aliases=("stalks",)),
    UnitCatalogEntry("tbsp", aliases=("tablespoon", "tablespoons", "tbsp")),
    UnitCatalogEntry("tsp", aliases=("teaspoon", "teaspoons", "tsp")),
)

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


def _normalize_key(value: str) -> str:
    cleaned = (value or "").strip().lower().replace("_", " ").replace("-", " ")
    for token in ",.;:()":
        cleaned = cleaned.replace(token, " ")
    return " ".join(cleaned.split())


def _build_ingredient_index() -> dict[str, IngredientCatalogEntry]:
    index: dict[str, IngredientCatalogEntry] = {}
    for entry in _INGREDIENT_ENTRIES:
        names = (entry.canonical_name, *entry.aliases)
        for name in names:
            index[_normalize_key(name)] = entry
    return index


def _build_unit_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for entry in _UNIT_ENTRIES:
        names = (entry.canonical_unit, *entry.aliases)
        for name in names:
            index[_normalize_key(name)] = entry.canonical_unit
    return index


INGREDIENT_CATALOG = {entry.canonical_name: entry for entry in _INGREDIENT_ENTRIES}
INGREDIENT_ALIAS_INDEX = _build_ingredient_index()
UNIT_ALIAS_INDEX = _build_unit_index()


def ingredient_catalog_entries() -> tuple[IngredientCatalogEntry, ...]:
    return _INGREDIENT_ENTRIES


def unit_catalog_entries() -> tuple[UnitCatalogEntry, ...]:
    return _UNIT_ENTRIES


def normalize_catalog_key(value: str) -> str:
    return _normalize_key(value)


def lookup_ingredient(value: str) -> IngredientCatalogEntry | None:
    return INGREDIENT_ALIAS_INDEX.get(_normalize_key(value))


def canonical_ingredient_name(value: str) -> str:
    entry = lookup_ingredient(value)
    if entry is None:
        return _normalize_key(value)
    return entry.canonical_name


def lookup_ingredient_metadata(value: str) -> IngredientCatalogEntry | None:
    return lookup_ingredient(value)


def canonical_unit_name(value: str) -> str:
    normalized = _normalize_key(value)
    return UNIT_ALIAS_INDEX.get(normalized, normalized)
