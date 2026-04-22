from __future__ import annotations

from dataclasses import dataclass
from collections import deque


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
    IngredientCatalogEntry("apple", aliases=("apples", "chopped apples", "sliced apples", "shredded tart apple"), supported_units=("item", "cup"), allergens=frozenset()),
    IngredientCatalogEntry("avocado", aliases=("avocados",), supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry("banana", supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry(
        "baking powder",
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "baking soda",
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "balsamic vinegar",
        supported_units=("tsp", "tbsp", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("blueberries", aliases=("fresh blueberries", "frozen blueberries"), supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry(
        "bell pepper",
        aliases=("bell peppers", "green bell pepper", "red bell pepper", "yellow bell pepper", "orange bell pepper"),
        supported_units=("item", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "black pepper",
        aliases=("ground black pepper", "black pepper to taste", "pepper"),
        supported_units=("tsp", "tbsp", "pinch"),
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
    IngredientCatalogEntry("carrot", aliases=("carrots", "sliced carrots", "diced carrot", "matchstick cut carrots"), supported_units=("item", "cup"), allergens=frozenset()),
    IngredientCatalogEntry("celery", aliases=("diced celery", "celery chopped", "chopped celery"), supported_units=("stalk", "cup"), allergens=frozenset()),
    IngredientCatalogEntry(
        "chicken broth",
        aliases=("chicken stock",),
        supported_units=("cup", "can"),
        allergens=frozenset(),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "cheddar cheese",
        aliases=("shredded cheddar cheese", "shredded cheddar"),
        supported_units=("cup", "oz", "package"),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry("cheese", supported_units=("cup", "oz", "item"), allergens=None, diet_flags=IngredientDietFlags(animal_product=True)),
    IngredientCatalogEntry(
        "chicken breast",
        aliases=("skinless boneless chicken breast halves", "boneless skinless chicken breasts", "chicken breast halves", "chicken breasts"),
        supported_units=("item", "lb"),
        allergens=frozenset(),
        diet_flags=IngredientDietFlags(meat=True),
    ),
    IngredientCatalogEntry(
        "chicken",
        aliases=("whole chicken",),
        supported_units=("item", "lb"),
        allergens=frozenset(),
        diet_flags=IngredientDietFlags(meat=True),
    ),
    IngredientCatalogEntry(
        "chicken gravy",
        supported_units=("item", "can", "cup"),
        allergens=frozenset({"gluten"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry("chickpeas", aliases=("canned chickpeas",), supported_units=("can", "cup"), allergens=frozenset()),
    IngredientCatalogEntry("chili powder", supported_units=("tsp", "tbsp", "pinch"), allergens=frozenset()),
    IngredientCatalogEntry("cinnamon", supported_units=("tsp", "tbsp", "pinch"), allergens=frozenset()),
    IngredientCatalogEntry("cilantro", aliases=("chopped fresh cilantro", "fresh cilantro leaves", "fresh cilantro"), supported_units=("tbsp", "cup"), allergens=frozenset()),
    IngredientCatalogEntry("corn", aliases=("corn kernels",), supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry("cornstarch", supported_units=("tsp", "tbsp", "cup"), allergens=frozenset()),
    IngredientCatalogEntry("cucumber", aliases=("thinly sliced cucumber", "diced cucumber"), supported_units=("item", "cup"), allergens=frozenset()),
    IngredientCatalogEntry(
        "cumin",
        aliases=("ground cumin",),
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("curry powder", supported_units=("tsp", "tbsp"), allergens=frozenset()),
    IngredientCatalogEntry(
        "cayenne pepper",
        supported_units=("tsp", "tbsp", "pinch"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("cherries", aliases=("fresh cherries", "sweet cherries", "frozen cherries"), supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry(
        "cocoa",
        aliases=("cocoa powder",),
        supported_units=("tbsp", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "coconut",
        aliases=("flaked coconut",),
        supported_units=("cup",),
        allergens=frozenset({"tree-nut"}),
    ),
    IngredientCatalogEntry(
        "cream cheese",
        supported_units=("item", "package", "oz", "cup"),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "cream of chicken soup",
        supported_units=("item", "can", "cup"),
        allergens=frozenset({"dairy", "gluten"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "cream of mushroom soup",
        supported_units=("item", "can", "cup"),
        allergens=frozenset({"dairy", "gluten"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "eggs",
        aliases=("egg", "large egg", "large eggs", "egg beaten", "eggs beaten"),
        supported_units=("item",),
        allergens=frozenset({"egg"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry("figs", aliases=("fresh figs",), supported_units=("item", "cup"), allergens=frozenset()),
    IngredientCatalogEntry(
        "flour",
        aliases=("all purpose flour", "all-purpose flour", "unbleached all-purpose flour", "self-rising flour"),
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
        "flour tortillas",
        supported_units=("item",),
        allergens=frozenset({"gluten"}),
    ),
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
        aliases=("fresh ginger root", "ground ginger", "minced fresh ginger root", "minced fresh ginger", "fresh ginger", "minced ginger"),
        supported_units=("tsp", "tbsp", "pinch"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("granola", supported_units=("cup",), allergens=frozenset({"gluten"})),
    IngredientCatalogEntry(
        "heavy cream",
        supported_units=("tbsp", "cup"),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "ground turkey",
        supported_units=("lb",),
        allergens=frozenset(),
        diet_flags=IngredientDietFlags(meat=True),
    ),
    IngredientCatalogEntry(
        "ground beef",
        aliases=("hamburger",),
        supported_units=("lb",),
        allergens=frozenset(),
        diet_flags=IngredientDietFlags(meat=True),
    ),
    IngredientCatalogEntry(
        "garam masala",
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "honey",
        supported_units=("tsp", "tbsp", "cup"),
        allergens=frozenset(),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "hot sauce",
        aliases=("hot pepper sauce",),
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("lemon", aliases=("lemons",), supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry("lemon juice", aliases=("fresh lemon juice",), supported_units=("tsp", "tbsp", "cup"), allergens=frozenset()),
    IngredientCatalogEntry("lentils", supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry("lime", aliases=("limes",), supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry("lime juice", aliases=("fresh lime juice",), supported_units=("tsp", "tbsp", "cup"), allergens=frozenset()),
    IngredientCatalogEntry(
        "milk",
        supported_units=("tsp", "tbsp", "cup"),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry("mayonnaise", supported_units=("tbsp", "cup"), allergens=frozenset({"egg"}), diet_flags=IngredientDietFlags(animal_product=True)),
    IngredientCatalogEntry(
        "mozzarella cheese",
        supported_units=("cup", "oz", "item"),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "mushroom",
        aliases=("sliced mushrooms", "mushrooms"),
        supported_units=("cup",),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("nutmeg", aliases=("ground nutmeg",), supported_units=("tsp", "tbsp", "pinch"), allergens=frozenset()),
    IngredientCatalogEntry("olive oil", supported_units=("tsp", "tbsp", "cup"), allergens=frozenset()),
    IngredientCatalogEntry(
        "onion",
        aliases=("red onion", "yellow onion", "chopped onion", "diced onion", "white onion", "sweet onion", "onion chopped", "onion finely diced", "onion minced"),
        supported_units=("item", "tbsp", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "oregano",
        aliases=("dried oregano",),
        supported_units=("tsp", "tbsp", "pinch"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("orange juice", supported_units=("tbsp", "cup"), allergens=frozenset()),
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
        aliases=("ground paprika",),
        supported_units=("tsp", "tbsp", "pinch"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("parsley", aliases=("dried parsley",), supported_units=("tsp", "tbsp"), allergens=frozenset()),
    IngredientCatalogEntry("peanut butter", supported_units=("tbsp",), allergens=frozenset({"peanut"})),
    IngredientCatalogEntry("pecans", aliases=("nuts pecans",), supported_units=("tbsp", "cup"), allergens=frozenset({"tree-nut"})),
    IngredientCatalogEntry("pineapple", supported_units=("item", "cup"), allergens=frozenset()),
    IngredientCatalogEntry("potato", aliases=("potatoes",), supported_units=("item", "cup"), allergens=frozenset()),
    IngredientCatalogEntry("raisins", supported_units=("tbsp", "cup"), allergens=frozenset()),
    IngredientCatalogEntry("red pepper flakes", aliases=("crushed red pepper flakes",), supported_units=("tsp", "tbsp", "pinch"), allergens=frozenset()),
    IngredientCatalogEntry(
        "rice",
        aliases=("white rice", "cooked white rice", "uncooked white rice"),
        supported_units=("cup",),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("rice vinegar", aliases=("distilled white vinegar", "white vinegar", "apple cider vinegar"), supported_units=("tsp", "tbsp", "cup"), allergens=frozenset()),
    IngredientCatalogEntry(
        "rolled oats",
        aliases=("old fashioned oats", "rolled oat", "quick cooking oats"),
        supported_units=("cup",),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "sour cream",
        supported_units=("tbsp", "cup", "item"),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "salt",
        aliases=("kosher salt", "sea salt", "salt and ground black pepper to taste"),
        supported_units=("tsp", "tbsp", "pinch"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("salsa", supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry(
        "sesame oil",
        aliases=("sesame oil divided",),
        supported_units=("tsp", "tbsp"),
        allergens=frozenset({"sesame"}),
    ),
    IngredientCatalogEntry("soy sauce", aliases=("reduced sodium soy sauce", "low sodium soy sauce"), supported_units=("tsp", "tbsp", "cup"), allergens=frozenset({"soy"})),
    IngredientCatalogEntry("spinach", supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry("strawberries", aliases=("fresh strawberries", "frozen strawberries"), supported_units=("cup",), allergens=frozenset()),
    IngredientCatalogEntry(
        "stuffing mix",
        aliases=("stove top stuffing", "stuffing"),
        supported_units=("item", "cup"),
        allergens=frozenset({"gluten"}),
    ),
    IngredientCatalogEntry(
        "sugar",
        aliases=("white sugar", "granulated sugar", "confectioners sugar", "powdered sugar", "brown sugar", "packed brown sugar", "light brown sugar", "dark brown sugar", "vanilla sugar"),
        supported_units=("tsp", "tbsp", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "thyme",
        aliases=("dried thyme",),
        supported_units=("tsp", "tbsp", "pinch"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry("tofu", supported_units=("block",), allergens=frozenset({"soy"})),
    IngredientCatalogEntry(
        "tomato",
        aliases=("cherry tomatoes", "roma tomatoes", "tomatoes", "diced roma tomatoes"),
        supported_units=("item", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "tomato sauce",
        supported_units=("can", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "turmeric",
        aliases=("ground turmeric",),
        supported_units=("tsp", "tbsp"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "vanilla extract",
        aliases=("vanilla",),
        supported_units=("tsp", "tbsp"),
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
        aliases=("canola oil", "oil"),
        supported_units=("tsp", "tbsp", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "walnuts",
        aliases=("chopped walnuts", "walnut"),
        supported_units=("tbsp", "cup"),
        allergens=frozenset({"tree-nut"}),
    ),
    IngredientCatalogEntry(
        "water",
        supported_units=("tbsp", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "yogurt",
        aliases=("plain yogurt", "vanilla yogurt"),
        supported_units=("cup",),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "evaporated milk",
        supported_units=("item", "cup"),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "bread crumbs",
        supported_units=("cup",),
        allergens=frozenset({"gluten"}),
    ),
    IngredientCatalogEntry(
        "buttermilk",
        supported_units=("cup",),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
    IngredientCatalogEntry(
        "green onion",
        aliases=("green onions",),
        supported_units=("item", "cup"),
        allergens=frozenset(),
    ),
    IngredientCatalogEntry(
        "mustard",
        supported_units=("tsp", "tbsp"),
        allergens=frozenset({"mustard"}),
    ),
    IngredientCatalogEntry(
        "worcestershire sauce",
        supported_units=("tsp", "tbsp"),
        allergens=frozenset({"fish"}),
    ),
    IngredientCatalogEntry(
        "bacon",
        supported_units=("slice", "item", "lb"),
        allergens=frozenset(),
        diet_flags=IngredientDietFlags(meat=True),
    ),
    IngredientCatalogEntry("zucchini", aliases=("zucchinis",), supported_units=("item",), allergens=frozenset()),
    IngredientCatalogEntry(
        "butter",
        aliases=("unsalted butter", "butter softened", "butter melted", "melted butter"),
        supported_units=("tbsp", "cup"),
        allergens=frozenset({"dairy"}),
        diet_flags=IngredientDietFlags(animal_product=True),
    ),
)

_UNIT_ENTRIES: tuple[UnitCatalogEntry, ...] = (
    UnitCatalogEntry("block", aliases=("blocks",)),
    UnitCatalogEntry("can", aliases=("cans",)),
    UnitCatalogEntry("clove", aliases=("cloves",)),
    UnitCatalogEntry("cup", aliases=("cups", "c")),
    UnitCatalogEntry("item", aliases=("items", "jar", "jars", "carton", "cartons", "box", "boxes", "bottle", "bottles", "bag", "bags", "envelope", "envelopes")),
    UnitCatalogEntry("package", aliases=("packages", "pkg", "pkgs")),
    UnitCatalogEntry("lb", aliases=("lbs", "pound", "pounds")),
    UnitCatalogEntry("oz", aliases=("ounce", "ounces", "oz.", "oz")),
    UnitCatalogEntry("pinch", aliases=("pinches",)),
    UnitCatalogEntry("slice", aliases=("slices",)),
    UnitCatalogEntry("stalk", aliases=("stalks",)),
    UnitCatalogEntry("tbsp", aliases=("tablespoon", "tablespoons", "tbsp", "tbs", "tbl")),
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

INGREDIENT_UNIT_CONVERSION_FACTORS = {
    ("apple", "item", "cup"): 1.5,
    ("bacon", "lb", "slice"): 16.0,
    ("baking powder", "tbsp", "tsp"): 3.0,
    ("baking soda", "tbsp", "tsp"): 3.0,
    ("bell pepper", "item", "cup"): 1.0,
    ("butter", "cup", "tbsp"): 16.0,
    ("carrot", "item", "cup"): 0.5,
    ("celery", "stalk", "cup"): 0.5,
    ("cheddar cheese", "cup", "oz"): 4.0,
    ("cheddar cheese", "package", "cup"): 2.0,
    ("chicken", "item", "lb"): 1.0,
    ("chicken breast", "item", "lb"): 0.5,
    ("cream of chicken soup", "item", "can"): 1.0,
    ("cream of chicken soup", "can", "cup"): 1.25,
    ("corn", "can", "cup"): 1.5,
    ("cream cheese", "item", "oz"): 8.0,
    ("cream cheese", "item", "cup"): 1.0,
    ("cream cheese", "package", "item"): 1.0,
    ("cream of mushroom soup", "item", "can"): 1.0,
    ("cream of mushroom soup", "can", "cup"): 1.25,
    ("garlic", "clove", "tsp"): 1.0,
    ("green onion", "item", "cup"): 0.25,
    ("milk", "can", "cup"): 1.5,
    ("mozzarella cheese", "item", "cup"): 1.0,
    ("mozzarella cheese", "cup", "oz"): 4.0,
    ("mozzarella cheese", "package", "cup"): 2.0,
    ("onion", "item", "cup"): 1.0,
    ("onion", "item", "tbsp"): 16.0,
    ("parmesan", "cup", "tbsp"): 16.0,
    ("pineapple", "item", "cup"): 4.0,
    ("potato", "item", "cup"): 1.5,
    ("rice", "item", "cup"): 1.0,
    ("sour cream", "item", "cup"): 2.0,
    ("stuffing mix", "item", "cup"): 3.0,
    ("sugar", "item", "cup"): 10.0,
    ("tomato", "item", "cup"): 1.0,
    ("tomato sauce", "can", "cup"): 1.75,
    ("evaporated milk", "item", "cup"): 1.5,
    ("vegetable oil", "item", "tbsp"): 32.0,
}

INGREDIENT_CALORIE_REFERENCES = {
    "apple": (95.0, "item"),
    "avocado": (240.0, "item"),
    "bacon": (43.0, "slice"),
    "baking powder": (2.0, "tsp"),
    "baking soda": (0.0, "tsp"),
    "balsamic vinegar": (14.0, "tbsp"),
    "bell pepper": (31.0, "item"),
    "black beans": (227.0, "can"),
    "black pepper": (5.0, "tsp"),
    "blueberries": (85.0, "cup"),
    "bread": (80.0, "slice"),
    "bread crumbs": (427.0, "cup"),
    "broccoli": (31.0, "cup"),
    "butter": (102.0, "tbsp"),
    "buttermilk": (152.0, "cup"),
    "canned tomatoes": (90.0, "can"),
    "carrot": (25.0, "item"),
    "celery": (6.0, "stalk"),
    "cheddar cheese": (455.0, "cup"),
    "chicken": (748.0, "lb"),
    "chicken breast": (748.0, "lb"),
    "chicken broth": (15.0, "cup"),
    "chicken gravy": (45.0, "cup"),
    "chickpeas": (210.0, "can"),
    "chili powder": (24.0, "tbsp"),
    "cilantro": (1.0, "tbsp"),
    "cinnamon": (6.0, "tsp"),
    "cocoa": (12.0, "tbsp"),
    "coconut": (466.0, "cup"),
    "corn": (143.0, "cup"),
    "cornstarch": (30.0, "tbsp"),
    "cream cheese": (99.0, "oz"),
    "cream of chicken soup": (180.0, "can"),
    "cream of mushroom soup": (180.0, "can"),
    "cucumber": (16.0, "item"),
    "cumin": (22.0, "tbsp"),
    "curry powder": (20.0, "tbsp"),
    "eggs": (72.0, "item"),
    "evaporated milk": (338.0, "item"),
    "feta": (396.0, "cup"),
    "figs": (37.0, "item"),
    "flour": (455.0, "cup"),
    "flour tortillas": (140.0, "item"),
    "frozen berries": (70.0, "cup"),
    "garam masala": (18.0, "tbsp"),
    "garlic": (4.0, "clove"),
    "garlic powder": (10.0, "tbsp"),
    "ginger": (5.0, "tbsp"),
    "granola": (597.0, "cup"),
    "green onion": (8.0, "item"),
    "ground beef": (1152.0, "lb"),
    "ground turkey": (770.0, "lb"),
    "heavy cream": (51.0, "tbsp"),
    "honey": (64.0, "tbsp"),
    "hot sauce": (0.0, "tbsp"),
    "lemon": (17.0, "item"),
    "lemon juice": (4.0, "tbsp"),
    "lentils": (230.0, "cup"),
    "lime": (20.0, "item"),
    "lime juice": (4.0, "tbsp"),
    "mayonnaise": (94.0, "tbsp"),
    "milk": (149.0, "cup"),
    "mozzarella cheese": (336.0, "cup"),
    "mushroom": (15.0, "cup"),
    "mustard": (9.0, "tbsp"),
    "nutmeg": (12.0, "tsp"),
    "olive oil": (119.0, "tbsp"),
    "onion": (44.0, "item"),
    "orange juice": (112.0, "cup"),
    "oregano": (3.0, "tsp"),
    "paprika": (20.0, "tbsp"),
    "parmesan": (22.0, "tbsp"),
    "parsley": (1.0, "tbsp"),
    "pasta": (100.0, "oz"),
    "peanut butter": (94.0, "tbsp"),
    "pecans": (196.0, "tbsp"),
    "pineapple": (82.0, "cup"),
    "potato": (163.0, "item"),
    "raisins": (434.0, "cup"),
    "red pepper flakes": (17.0, "tbsp"),
    "rice": (206.0, "cup"),
    "rice vinegar": (3.0, "tbsp"),
    "rolled oats": (307.0, "cup"),
    "salt": (0.0, "tsp"),
    "salsa": (36.0, "cup"),
    "sesame oil": (120.0, "tbsp"),
    "sour cream": (31.0, "tbsp"),
    "soy sauce": (9.0, "tbsp"),
    "spinach": (7.0, "cup"),
    "strawberries": (49.0, "cup"),
    "stuffing mix": (110.0, "cup"),
    "sugar": (774.0, "cup"),
    "thyme": (3.0, "tsp"),
    "tofu": (360.0, "block"),
    "tomato": (22.0, "item"),
    "tomato sauce": (80.0, "cup"),
    "turmeric": (21.0, "tbsp"),
    "vanilla extract": (12.0, "tsp"),
    "vegetable broth": (15.0, "cup"),
    "vegetable oil": (120.0, "tbsp"),
    "walnuts": (185.0, "tbsp"),
    "water": (0.0, "cup"),
    "worcestershire sauce": (13.0, "tbsp"),
    "yogurt": (150.0, "cup"),
    "zucchini": (33.0, "item"),
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


def ingredient_calorie_reference(value: str) -> tuple[float, str] | None:
    canonical_name = canonical_ingredient_name(value)
    return INGREDIENT_CALORIE_REFERENCES.get(canonical_name)


def convert_ingredient_unit_quantity(
    ingredient_name: str,
    quantity: float,
    from_unit: str,
    to_unit: str,
) -> float | None:
    normalized_from = canonical_unit_name(from_unit)
    normalized_to = canonical_unit_name(to_unit)
    if normalized_from == normalized_to:
        return quantity

    conversion_graph = _build_conversion_graph(canonical_ingredient_name(ingredient_name))
    if normalized_from not in conversion_graph:
        return None

    queue: deque[tuple[str, float]] = deque([(normalized_from, 1.0)])
    visited = {normalized_from}
    while queue:
        unit, factor = queue.popleft()
        for neighbor, edge_factor in conversion_graph.get(unit, {}).items():
            if neighbor in visited:
                continue
            next_factor = factor * edge_factor
            if neighbor == normalized_to:
                return quantity * next_factor
            visited.add(neighbor)
            queue.append((neighbor, next_factor))
    return None


def _build_conversion_graph(canonical_name: str) -> dict[str, dict[str, float]]:
    graph: dict[str, dict[str, float]] = {}

    def add_edge(source: str, target: str, factor: float) -> None:
        if factor <= 0:
            return
        graph.setdefault(source, {})[target] = factor
        graph.setdefault(target, {})[source] = 1.0 / factor

    for (source, target), factor in UNIT_CONVERSION_FACTORS.items():
        add_edge(source, target, factor)
    for (ingredient, source, target), factor in INGREDIENT_UNIT_CONVERSION_FACTORS.items():
        if ingredient == canonical_name:
            add_edge(source, target, factor)
    return graph
