from __future__ import annotations

from pantry_pilot.models import Recipe, RecipeIngredient
from pantry_pilot.ingredient_catalog import lookup_ingredient_metadata
from pantry_pilot.normalization import normalize_ingredient_name, normalize_name, normalize_unit

REQUIRED_RECIPE_FIELDS = (
    "title",
    "cuisine",
    "base_servings",
    "estimated_calories_per_serving",
    "prep_time_minutes",
    "meal_types",
    "ingredients",
    "steps",
)
SAFE_DERIVED_DIET_TAGS = frozenset({"vegetarian", "vegan", "gluten-free", "dairy-free"})


def _ingredient(name: str, quantity: float, unit: str) -> dict[str, str | float]:
    return {"name": name, "quantity": quantity, "unit": unit}


RAW_RECIPES: tuple[dict, ...] = (
    {
        "title": "Avocado Toast",
        "cuisine": "american",
        "base_servings": 2,
        "estimated_calories_per_serving": 330,
        "prep_time_minutes": 10,
        "meal_types": ("breakfast", "lunch"),
        "ingredients": (
            _ingredient("bread", 4.0, "slices"),
            _ingredient("avocados", 2.0, "items"),
            _ingredient("tomatoes", 1.0, "item"),
            _ingredient("olive oil", 1.0, "tablespoon"),
        ),
        "steps": (
            "Toast bread and mash avocado.",
            "Top toast with avocado, tomato, and olive oil.",
        ),
    },
    {
        "title": "Banana Yogurt Oat Cup",
        "cuisine": "american",
        "base_servings": 2,
        "estimated_calories_per_serving": 310,
        "prep_time_minutes": 8,
        "meal_types": ("breakfast",),
        "ingredients": (
            _ingredient("yogurt", 1.5, "cups"),
            _ingredient("banana", 2.0, "items"),
            _ingredient("rolled oats", 1.0, "cup"),
            _ingredient("honey", 1.0, "tablespoon"),
            _ingredient("cinnamon", 1.0, "teaspoon"),
        ),
        "steps": (
            "Spoon yogurt into cups and stir in oats.",
            "Top with banana, honey, and cinnamon.",
        ),
    },
    {
        "title": "Berry Yogurt Parfait",
        "cuisine": "american",
        "base_servings": 2,
        "estimated_calories_per_serving": 360,
        "prep_time_minutes": 8,
        "meal_types": ("breakfast",),
        "ingredients": (
            _ingredient("yogurt", 2.0, "cups"),
            _ingredient("frozen berries", 2.0, "cups"),
            _ingredient("granola", 1.5, "cups"),
            _ingredient("honey", 2.0, "tablespoons"),
        ),
        "steps": (
            "Layer yogurt, berries, and granola into bowls.",
            "Drizzle with honey before serving.",
        ),
    },
    {
        "title": "Black Bean Corn Salad",
        "cuisine": "mexican",
        "base_servings": 4,
        "estimated_calories_per_serving": 280,
        "prep_time_minutes": 15,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("black beans", 2.0, "cans"),
            _ingredient("corn kernels", 2.0, "cups"),
            _ingredient("tomatoes", 2.0, "items"),
            _ingredient("lime", 1.0, "item"),
            _ingredient("olive oil", 1.0, "tablespoon"),
        ),
        "steps": (
            "Mix beans, corn, and tomato together.",
            "Dress with lime juice and olive oil.",
        ),
    },
    {
        "title": "Black Bean Taco Bowls",
        "cuisine": "mexican",
        "base_servings": 4,
        "estimated_calories_per_serving": 430,
        "prep_time_minutes": 25,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("rice", 2.0, "cups"),
            _ingredient("black beans canned", 2.0, "cans"),
            _ingredient("corn", 2.0, "cups"),
            _ingredient("salsa", 1.5, "cups"),
            _ingredient("avocado", 2.0, "items"),
            _ingredient("lime", 1.0, "item"),
        ),
        "steps": (
            "Cook rice and warm black beans with corn.",
            "Serve in bowls with salsa, avocado, and lime.",
        ),
    },
    {
        "title": "Broccoli Cheddar Rice Bowl",
        "cuisine": "american",
        "base_servings": 4,
        "estimated_calories_per_serving": 420,
        "prep_time_minutes": 25,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("rice", 2.0, "cups"),
            _ingredient("broccoli florets", 3.0, "cups"),
            _ingredient("cheddar cheese", 1.5, "cups"),
            _ingredient("carrots", 2.0, "items"),
            _ingredient("vegetable broth", 3.0, "cups"),
        ),
        "steps": (
            "Cook rice with broth while steaming broccoli and carrot.",
            "Stir in cheddar until melted and serve in bowls.",
        ),
    },
    {
        "title": "Broccoli Egg Breakfast Bowl",
        "cuisine": "american",
        "base_servings": 2,
        "estimated_calories_per_serving": 390,
        "prep_time_minutes": 15,
        "meal_types": ("breakfast", "lunch"),
        "ingredients": (
            _ingredient("rice", 1.0, "cup"),
            _ingredient("eggs", 4.0, "items"),
            _ingredient("broccoli", 2.0, "cups"),
            _ingredient("cheddar cheese", 0.5, "cup"),
            _ingredient("yellow onion", 0.5, "item"),
        ),
        "steps": (
            "Cook rice and saute broccoli with onion until tender.",
            "Scramble in eggs, top with cheddar, and serve warm in bowls.",
        ),
    },
    {
        "title": "Broccoli Garlic Rice",
        "cuisine": "american",
        "base_servings": 4,
        "estimated_calories_per_serving": 250,
        "prep_time_minutes": 20,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("rice", 2.0, "cups"),
            _ingredient("broccoli", 3.0, "cups"),
            _ingredient("garlic cloves", 4.0, "cloves"),
            _ingredient("olive oil", 2.0, "tablespoons"),
            _ingredient("lemon", 1.0, "item"),
        ),
        "steps": (
            "Cook rice and steam broccoli until tender.",
            "Toss with garlic, olive oil, and lemon.",
        ),
    },
    {
        "title": "Chicken Rice Skillet",
        "cuisine": "american",
        "base_servings": 4,
        "estimated_calories_per_serving": 480,
        "prep_time_minutes": 35,
        "meal_types": ("dinner",),
        "extra_diet_tags": ("high-protein",),
        "ingredients": (
            _ingredient("chicken breast", 1.5, "pounds"),
            _ingredient("rice", 2.0, "cups"),
            _ingredient("broccoli", 2.0, "cups"),
            _ingredient("carrots", 2.0, "items"),
            _ingredient("veggie broth", 4.0, "cups"),
        ),
        "steps": (
            "Brown chicken pieces in a skillet.",
            "Add rice, vegetables, and broth, then cover until cooked through.",
        ),
    },
    {
        "title": "Chicken Tomato Pasta",
        "cuisine": "italian",
        "base_servings": 4,
        "estimated_calories_per_serving": 520,
        "prep_time_minutes": 30,
        "meal_types": ("dinner",),
        "extra_diet_tags": ("high-protein",),
        "ingredients": (
            _ingredient("chicken breast", 1.0, "pound"),
            _ingredient("penne pasta", 12.0, "ounces"),
            _ingredient("canned tomatoes", 2.0, "cans"),
            _ingredient("spinach", 2.0, "cups"),
            _ingredient("garlic clove", 4.0, "cloves"),
        ),
        "steps": (
            "Cook pasta until tender while browning chicken.",
            "Simmer tomatoes, spinach, and garlic, then toss with pasta and chicken.",
        ),
    },
    {
        "title": "Chickpea Salsa Rice Skillet",
        "cuisine": "mexican",
        "base_servings": 4,
        "estimated_calories_per_serving": 390,
        "prep_time_minutes": 20,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("rice", 2.0, "cups"),
            _ingredient("canned chickpeas", 2.0, "cans"),
            _ingredient("corn", 2.0, "cups"),
            _ingredient("salsa", 1.5, "cups"),
            _ingredient("bell peppers", 1.0, "item"),
        ),
        "steps": (
            "Cook rice and saute bell pepper until tender.",
            "Fold in chickpeas, corn, and salsa until heated through.",
        ),
    },
    {
        "title": "Chickpea Tomato Skillet",
        "cuisine": "mediterranean",
        "base_servings": 4,
        "estimated_calories_per_serving": 260,
        "prep_time_minutes": 20,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("chickpeas", 2.0, "cans"),
            _ingredient("tomatoes", 3.0, "items"),
            _ingredient("garlic cloves", 3.0, "cloves"),
            _ingredient("olive oil", 2.0, "tablespoons"),
            _ingredient("spinach", 2.0, "cups"),
        ),
        "steps": (
            "Cook tomato and garlic in olive oil until saucy.",
            "Fold in chickpeas and spinach until warmed through.",
        ),
    },
    {
        "title": "Cinnamon Banana Oatmeal",
        "cuisine": "american",
        "base_servings": 2,
        "estimated_calories_per_serving": 280,
        "prep_time_minutes": 12,
        "meal_types": ("breakfast",),
        "ingredients": (
            _ingredient("old fashioned oats", 2.0, "cups"),
            _ingredient("banana", 2.0, "items"),
            _ingredient("cinnamon", 1.0, "teaspoon"),
            _ingredient("honey", 1.0, "tablespoon"),
        ),
        "steps": (
            "Cook oats with water until creamy.",
            "Top with sliced banana, cinnamon, and honey.",
        ),
    },
    {
        "title": "Cucumber Tomato Feta Toast",
        "cuisine": "mediterranean",
        "base_servings": 2,
        "estimated_calories_per_serving": 340,
        "prep_time_minutes": 10,
        "meal_types": ("breakfast", "lunch"),
        "ingredients": (
            _ingredient("bread", 4.0, "slices"),
            _ingredient("cucumber", 1.0, "item"),
            _ingredient("tomatoes", 2.0, "items"),
            _ingredient("feta", 0.5, "cup"),
            _ingredient("olive oil", 1.0, "tablespoon"),
        ),
        "steps": (
            "Toast bread and top with chopped cucumber and tomato.",
            "Finish with feta and olive oil.",
        ),
    },
    {
        "title": "Egg Fried Rice Bowl",
        "cuisine": "asian",
        "base_servings": 4,
        "estimated_calories_per_serving": 410,
        "prep_time_minutes": 20,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("rice", 2.0, "cups"),
            _ingredient("eggs", 4.0, "items"),
            _ingredient("carrot", 2.0, "items"),
            _ingredient("broccoli", 2.0, "cups"),
            _ingredient("soy sauce", 3.0, "tablespoons"),
        ),
        "steps": (
            "Cook rice and scramble eggs in a skillet.",
            "Stir in vegetables and soy sauce until everything is hot.",
        ),
    },
    {
        "title": "Feta Rice Stuffed Peppers",
        "cuisine": "mediterranean",
        "base_servings": 4,
        "estimated_calories_per_serving": 360,
        "prep_time_minutes": 35,
        "meal_types": ("dinner",),
        "ingredients": (
            _ingredient("bell peppers", 4.0, "items"),
            _ingredient("rice", 2.0, "cups"),
            _ingredient("feta", 1.0, "cup"),
            _ingredient("tomato", 2.0, "items"),
            _ingredient("olive oil", 1.0, "tablespoon"),
        ),
        "steps": (
            "Roast halved peppers until slightly tender.",
            "Fill with rice, tomato, and feta, then bake until hot.",
        ),
    },
    {
        "title": "Garlic Tomato Pasta",
        "cuisine": "italian",
        "base_servings": 4,
        "estimated_calories_per_serving": 390,
        "prep_time_minutes": 25,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("pasta", 16.0, "ounces"),
            _ingredient("canned tomatoes", 2.0, "cans"),
            _ingredient("spinach", 2.0, "cups"),
            _ingredient("garlic cloves", 4.0, "cloves"),
            _ingredient("olive oil", 2.0, "tablespoons"),
        ),
        "steps": (
            "Cook pasta until tender.",
            "Simmer tomatoes, garlic, and spinach, then toss with pasta.",
        ),
    },
    {
        "title": "Greek Chickpea Salad",
        "cuisine": "mediterranean",
        "base_servings": 4,
        "estimated_calories_per_serving": 370,
        "prep_time_minutes": 15,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("chickpeas", 2.0, "cans"),
            _ingredient("cucumber", 1.0, "item"),
            _ingredient("tomatoes", 2.0, "items"),
            _ingredient("feta", 1.0, "cup"),
            _ingredient("olive oil", 4.0, "tablespoons"),
            _ingredient("lemon", 1.0, "item"),
        ),
        "steps": (
            "Mix chickpeas with chopped vegetables and feta.",
            "Dress with olive oil and lemon juice.",
        ),
    },
    {
        "title": "Indian Lentil Spinach Curry",
        "cuisine": "indian",
        "base_servings": 4,
        "estimated_calories_per_serving": 410,
        "prep_time_minutes": 30,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("lentils", 2.0, "cups"),
            _ingredient("canned tomatoes", 2.0, "cans"),
            _ingredient("spinach", 3.0, "cups"),
            _ingredient("yellow onion", 1.0, "item"),
            _ingredient("curry powder", 2.0, "tablespoons"),
            _ingredient("rice", 2.0, "cups"),
        ),
        "steps": (
            "Cook onion with curry powder until fragrant, then add tomatoes and lentils.",
            "Fold in spinach and serve the curry over rice.",
        ),
    },
    {
        "title": "Lemon Chickpea Pasta",
        "cuisine": "mediterranean",
        "base_servings": 4,
        "estimated_calories_per_serving": 410,
        "prep_time_minutes": 25,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("pasta", 12.0, "oz"),
            _ingredient("chickpeas", 2.0, "cans"),
            _ingredient("spinach", 2.0, "cups"),
            _ingredient("lemon", 1.0, "item"),
            _ingredient("olive oil", 2.0, "tablespoons"),
        ),
        "steps": (
            "Cook pasta and warm chickpeas in olive oil.",
            "Toss with spinach and lemon before serving.",
        ),
    },
    {
        "title": "Lemon Lentil Rice Bowl",
        "cuisine": "mediterranean",
        "base_servings": 4,
        "estimated_calories_per_serving": 330,
        "prep_time_minutes": 30,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("lentils", 2.0, "cups"),
            _ingredient("rice", 2.0, "cups"),
            _ingredient("cucumber", 1.0, "item"),
            _ingredient("tomato", 2.0, "items"),
            _ingredient("lemon", 1.0, "item"),
        ),
        "steps": (
            "Cook lentils and rice until tender.",
            "Serve with cucumber, tomato, and lemon.",
        ),
    },
    {
        "title": "Lentil Salsa Rice Bowl",
        "cuisine": "mexican",
        "base_servings": 4,
        "estimated_calories_per_serving": 340,
        "prep_time_minutes": 30,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("lentils", 2.0, "cups"),
            _ingredient("rice", 2.0, "cups"),
            _ingredient("salsa", 1.5, "cups"),
            _ingredient("corn", 1.5, "cups"),
            _ingredient("lime", 1.0, "item"),
        ),
        "steps": (
            "Cook lentils and rice until tender.",
            "Top with salsa, corn, and lime.",
        ),
    },
    {
        "title": "Lentil Tomato Soup",
        "cuisine": "mediterranean",
        "base_servings": 4,
        "estimated_calories_per_serving": 290,
        "prep_time_minutes": 30,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("lentils", 2.0, "cups"),
            _ingredient("canned tomatoes", 2.0, "cans"),
            _ingredient("carrots", 2.0, "items"),
            _ingredient("celery", 2.0, "stalks"),
            _ingredient("yellow onion", 1.0, "item"),
            _ingredient("veggie broth", 6.0, "cups"),
            _ingredient("olive oil", 2.0, "tablespoons"),
        ),
        "steps": (
            "Cook onion, carrot, and celery in olive oil until softened.",
            "Add lentils, tomatoes, and broth, then simmer until tender.",
        ),
    },
    {
        "title": "Mediterranean Rice Bowl",
        "cuisine": "mediterranean",
        "base_servings": 4,
        "estimated_calories_per_serving": 360,
        "prep_time_minutes": 25,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("rice", 2.0, "cups"),
            _ingredient("chickpeas", 2.0, "cans"),
            _ingredient("cucumber", 1.0, "item"),
            _ingredient("tomato", 2.0, "items"),
            _ingredient("lemon", 1.0, "item"),
            _ingredient("olive oil", 2.0, "tablespoons"),
        ),
        "steps": (
            "Cook rice and warm chickpeas.",
            "Top bowls with cucumber, tomato, lemon, and olive oil.",
        ),
    },
    {
        "title": "Mexican Stuffed Peppers",
        "cuisine": "mexican",
        "base_servings": 4,
        "estimated_calories_per_serving": 400,
        "prep_time_minutes": 35,
        "meal_types": ("dinner",),
        "ingredients": (
            _ingredient("bell peppers", 4.0, "items"),
            _ingredient("rice", 2.0, "cups"),
            _ingredient("black beans", 2.0, "cans"),
            _ingredient("salsa", 1.5, "cups"),
            _ingredient("corn", 1.0, "cup"),
            _ingredient("cheddar cheese", 1.0, "cup"),
        ),
        "steps": (
            "Roast halved peppers until slightly tender.",
            "Fill with rice, beans, salsa, corn, and cheddar, then bake until hot.",
        ),
    },
    {
        "title": "Overnight Oats Bowl",
        "cuisine": "american",
        "base_servings": 2,
        "estimated_calories_per_serving": 430,
        "prep_time_minutes": 10,
        "meal_types": ("breakfast",),
        "ingredients": (
            _ingredient("rolled oats", 2.0, "cups"),
            _ingredient("milk", 2.0, "cups"),
            _ingredient("banana", 2.0, "items"),
            _ingredient("peanut butter", 4.0, "tablespoons"),
            _ingredient("cinnamon", 1.0, "teaspoon"),
        ),
        "steps": (
            "Stir oats, milk, peanut butter, and cinnamon together.",
            "Top with sliced banana and chill overnight.",
        ),
    },
    {
        "title": "Parmesan Broccoli Pasta",
        "cuisine": "italian",
        "base_servings": 4,
        "estimated_calories_per_serving": 440,
        "prep_time_minutes": 25,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("pasta", 12.0, "ounces"),
            _ingredient("broccoli", 3.0, "cups"),
            _ingredient("parmesan", 1.0, "cup"),
            _ingredient("olive oil", 2.0, "tablespoons"),
            _ingredient("garlic cloves", 2.0, "cloves"),
        ),
        "steps": (
            "Cook pasta and steam broccoli until tender.",
            "Toss with parmesan, olive oil, and garlic.",
        ),
    },
    {
        "title": "Pasta E Ceci Soup",
        "cuisine": "italian",
        "base_servings": 4,
        "estimated_calories_per_serving": 360,
        "prep_time_minutes": 30,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("pasta", 8.0, "ounces"),
            _ingredient("chickpeas", 2.0, "cans"),
            _ingredient("canned tomatoes", 2.0, "cans"),
            _ingredient("carrots", 2.0, "items"),
            _ingredient("vegetable broth", 5.0, "cups"),
        ),
        "steps": (
            "Simmer carrots, tomatoes, chickpeas, and broth until the flavors blend.",
            "Add pasta and cook until tender for a hearty soup.",
        ),
    },
    {
        "title": "Pasta Primavera",
        "cuisine": "italian",
        "base_servings": 4,
        "estimated_calories_per_serving": 430,
        "prep_time_minutes": 30,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("pasta", 16.0, "ounces"),
            _ingredient("zucchinis", 2.0, "items"),
            _ingredient("bell peppers", 1.0, "item"),
            _ingredient("spinach", 3.0, "cups"),
            _ingredient("parmesan", 1.0, "cup"),
            _ingredient("olive oil", 3.0, "tablespoons"),
        ),
        "steps": (
            "Cook pasta until tender.",
            "Saute vegetables and toss with pasta, olive oil, and parmesan.",
        ),
    },
    {
        "title": "Peanut Noodles",
        "cuisine": "asian",
        "base_servings": 4,
        "estimated_calories_per_serving": 500,
        "prep_time_minutes": 20,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("pasta", 12.0, "oz"),
            _ingredient("peanut butter", 6.0, "tablespoons"),
            _ingredient("soy sauce", 4.0, "tablespoons"),
            _ingredient("cucumber", 1.0, "item"),
            _ingredient("carrots", 2.0, "items"),
        ),
        "steps": (
            "Cook noodles and whisk together peanut butter and soy sauce.",
            "Toss noodles with sauce and vegetables.",
        ),
    },
    {
        "title": "Soy Tofu Cucumber Rice Bowl",
        "cuisine": "asian",
        "base_servings": 4,
        "estimated_calories_per_serving": 370,
        "prep_time_minutes": 25,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("tofu", 2.0, "blocks"),
            _ingredient("rice", 2.0, "cups"),
            _ingredient("cucumber", 1.0, "item"),
            _ingredient("carrots", 2.0, "items"),
            _ingredient("soy sauce", 3.0, "tablespoons"),
            _ingredient("lime", 1.0, "item"),
        ),
        "steps": (
            "Cook rice and brown tofu until lightly crisp.",
            "Serve with cucumber, carrot, soy sauce, and lime in bowls.",
        ),
    },
    {
        "title": "Savory Chickpea Toast",
        "cuisine": "mediterranean",
        "base_servings": 2,
        "estimated_calories_per_serving": 320,
        "prep_time_minutes": 12,
        "meal_types": ("breakfast", "lunch"),
        "ingredients": (
            _ingredient("bread", 4.0, "slices"),
            _ingredient("chickpeas", 1.0, "can"),
            _ingredient("lemon", 1.0, "item"),
            _ingredient("olive oil", 1.0, "tablespoon"),
            _ingredient("tomatoes", 1.0, "item"),
        ),
        "steps": (
            "Mash chickpeas with lemon and olive oil.",
            "Spread on toast and top with tomato.",
        ),
    },
    {
        "title": "Stuffed Zucchini Boats",
        "cuisine": "mediterranean",
        "base_servings": 4,
        "estimated_calories_per_serving": 330,
        "prep_time_minutes": 35,
        "meal_types": ("dinner",),
        "ingredients": (
            _ingredient("zucchini", 4.0, "items"),
            _ingredient("rice", 1.5, "cups"),
            _ingredient("chickpeas", 2.0, "cans"),
            _ingredient("tomatoes", 2.0, "items"),
            _ingredient("feta", 0.75, "cup"),
            _ingredient("olive oil", 1.0, "tablespoon"),
        ),
        "steps": (
            "Roast halved zucchini until just tender.",
            "Fill with rice, chickpeas, tomato, and feta, then bake until hot.",
        ),
    },
    {
        "title": "Spinach Tomato Egg Toast",
        "cuisine": "american",
        "base_servings": 2,
        "estimated_calories_per_serving": 360,
        "prep_time_minutes": 15,
        "meal_types": ("breakfast",),
        "ingredients": (
            _ingredient("bread", 4.0, "slices"),
            _ingredient("eggs", 4.0, "items"),
            _ingredient("spinach", 2.0, "cups"),
            _ingredient("tomatoes", 2.0, "items"),
            _ingredient("cheddar cheese", 0.5, "cup"),
        ),
        "steps": (
            "Cook eggs with spinach and tomato until set.",
            "Serve over toast with cheddar.",
        ),
    },
    {
        "title": "Tofu Stir-Fry",
        "cuisine": "asian",
        "base_servings": 4,
        "estimated_calories_per_serving": 350,
        "prep_time_minutes": 25,
        "meal_types": ("lunch", "dinner"),
        "ingredients": (
            _ingredient("tofu", 2.0, "blocks"),
            _ingredient("rice", 2.0, "cups"),
            _ingredient("broccoli", 2.0, "cups"),
            _ingredient("carrots", 2.0, "items"),
            _ingredient("soy sauce", 4.0, "tablespoons"),
            _ingredient("cloves garlic", 4.0, "cloves"),
        ),
        "steps": (
            "Cook rice while stir-frying tofu and vegetables.",
            "Add soy sauce and garlic, then cook until glossy.",
        ),
    },
    {
        "title": "Tomato Avocado Toast",
        "cuisine": "american",
        "base_servings": 2,
        "estimated_calories_per_serving": 350,
        "prep_time_minutes": 10,
        "meal_types": ("breakfast", "lunch"),
        "ingredients": (
            _ingredient("bread", 4.0, "slices"),
            _ingredient("avocado", 2.0, "items"),
            _ingredient("tomatoes", 2.0, "items"),
            _ingredient("lemon", 1.0, "item"),
        ),
        "steps": (
            "Toast bread and mash avocado with lemon.",
            "Top with sliced tomato and serve immediately.",
        ),
    },
    {
        "title": "Turkey Chili",
        "cuisine": "american",
        "base_servings": 4,
        "estimated_calories_per_serving": 390,
        "prep_time_minutes": 40,
        "meal_types": ("dinner",),
        "extra_diet_tags": ("high-protein",),
        "ingredients": (
            _ingredient("ground turkey", 1.0, "pound"),
            _ingredient("black beans", 2.0, "cans"),
            _ingredient("canned tomatoes", 2.0, "cans"),
            _ingredient("red onion", 1.0, "item"),
            _ingredient("bell peppers", 1.0, "item"),
            _ingredient("chili powder", 2.0, "tablespoons"),
        ),
        "steps": (
            "Brown turkey with onion and bell pepper.",
            "Add beans, tomatoes, and chili powder, then simmer until thick.",
        ),
    },
    {
        "title": "Turkey Taco Rice Skillet",
        "cuisine": "mexican",
        "base_servings": 4,
        "estimated_calories_per_serving": 450,
        "prep_time_minutes": 30,
        "meal_types": ("dinner",),
        "extra_diet_tags": ("high-protein",),
        "ingredients": (
            _ingredient("ground turkey", 1.0, "pound"),
            _ingredient("rice", 2.0, "cups"),
            _ingredient("salsa", 1.5, "cups"),
            _ingredient("corn", 1.5, "cups"),
            _ingredient("black beans", 1.0, "can"),
        ),
        "steps": (
            "Brown turkey and cook rice until tender.",
            "Fold in salsa, corn, and black beans until hot.",
        ),
    },
    {
        "title": "Veggie Egg Scramble",
        "cuisine": "american",
        "base_servings": 2,
        "estimated_calories_per_serving": 330,
        "prep_time_minutes": 15,
        "meal_types": ("breakfast",),
        "ingredients": (
            _ingredient("eggs", 6.0, "items"),
            _ingredient("spinach", 2.0, "cups"),
            _ingredient("bell peppers", 1.0, "item"),
            _ingredient("yellow onion", 0.5, "item"),
            _ingredient("cheddar cheese", 1.0, "cup"),
        ),
        "steps": (
            "Saute chopped vegetables until tender.",
            "Add beaten eggs and cook until set, then fold in cheese.",
        ),
    },
)


def sample_recipes() -> tuple[Recipe, ...]:
    _validate_raw_recipe_schema()
    return tuple(_build_recipe(record) for record in RAW_RECIPES)


def _build_recipe(record: dict) -> Recipe:
    ingredients = tuple(_build_ingredient(item) for item in record["ingredients"])
    canonical_names = tuple(ingredient.name for ingredient in ingredients)
    return Recipe(
        recipe_id=_recipe_id_from_title(record["title"]),
        title=record["title"],
        cuisine=normalize_name(record["cuisine"]),
        base_servings=int(record["base_servings"]),
        estimated_calories_per_serving=int(record["estimated_calories_per_serving"]),
        prep_time_minutes=int(record["prep_time_minutes"]),
        meal_types=tuple(normalize_name(value) for value in record["meal_types"]),
        diet_tags=_derive_diet_tags(canonical_names, record.get("extra_diet_tags", ())),
        allergens=_derive_allergens(canonical_names),
        ingredients=ingredients,
        steps=tuple(record["steps"]),
    )


def _build_ingredient(record: dict[str, str | float]) -> RecipeIngredient:
    return RecipeIngredient(
        name=normalize_ingredient_name(str(record["name"])),
        quantity=float(record["quantity"]),
        unit=normalize_unit(str(record["unit"])),
    )


def _derive_allergens(ingredient_names: tuple[str, ...]) -> frozenset[str] | None:
    allergens: set[str] = set()
    for ingredient_name in ingredient_names:
        profile = lookup_ingredient_metadata(ingredient_name)
        if profile is None or profile.allergens is None:
            return None
        allergens.update(profile.allergens)
    return frozenset(sorted(allergens))


def _derive_diet_tags(ingredient_names: tuple[str, ...], extra_tags: tuple[str, ...]) -> frozenset[str]:
    tags = {
        normalize_name(tag)
        for tag in extra_tags
        if normalize_name(tag) not in SAFE_DERIVED_DIET_TAGS
    }
    profiles = []
    for ingredient_name in ingredient_names:
        profile = lookup_ingredient_metadata(ingredient_name)
        if profile is None or profile.allergens is None:
            return frozenset(sorted(tags))
        profiles.append(profile)

    if all(not profile.diet_flags.meat for profile in profiles):
        tags.add("vegetarian")
    if all(not profile.diet_flags.meat and not profile.diet_flags.animal_product for profile in profiles):
        tags.add("vegan")
    if all("gluten" not in profile.allergens for profile in profiles):
        tags.add("gluten-free")
    if all("dairy" not in profile.allergens for profile in profiles):
        tags.add("dairy-free")
    return frozenset(sorted(tags))


def _recipe_id_from_title(title: str) -> str:
    return normalize_name(title).replace(" ", "-")


def _validate_raw_recipe_schema() -> None:
    seen_ids: set[str] = set()
    for record in RAW_RECIPES:
        missing_fields = [field for field in REQUIRED_RECIPE_FIELDS if field not in record]
        if missing_fields:
            raise ValueError(f"Recipe record is missing required fields: {missing_fields}")
        if not record["ingredients"]:
            raise ValueError(f"Recipe '{record['title']}' must include at least one ingredient.")
        if not record["steps"]:
            raise ValueError(f"Recipe '{record['title']}' must include at least one step.")
        recipe_id = _recipe_id_from_title(record["title"])
        if recipe_id in seen_ids:
            raise ValueError(f"Duplicate recipe id detected: {recipe_id}")
        seen_ids.add(recipe_id)
        for ingredient in record["ingredients"]:
            if set(ingredient) != {"name", "quantity", "unit"}:
                raise ValueError(
                    f"Recipe '{record['title']}' has an ingredient with an inconsistent schema: {ingredient}"
                )
