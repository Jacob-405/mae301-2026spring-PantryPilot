import csv
import re
import random
from pathlib import Path

import numpy as np
import tiktoken
from tqdm import tqdm

# --- PantryPilot heuristics (simple, consistent, MVP-friendly) ---

EXPENSIVE = {
    "shrimp", "salmon", "steak", "lamb", "scallop", "crab", "lobster", "saffron",
    "prosciutto", "truffle", "tuna", "tilapia"
}

TOOL_KEYWORDS = {
    "oven": ["bake", "roast", "preheat", "broil"],
    "skillet": ["skillet", "saute", "sauté", "fry", "pan-fry"],
    "pot": ["boil", "simmer", "stew", "soup"],
    "blender": ["blend", "puree", "purée", "smoothie"],
    "microwave": ["microwave"],
    "air fryer": ["air fryer", "airfryer"],
    "grill": ["grill"],
}

PREF_SAMPLES = [
    "vegetarian", "vegan", "spicy", "gluten-free", "high-protein", "dairy-free",
    "low-sodium", "kid-friendly", "quick", "comfort-food"
]

def normalize_text(s: str) -> str:
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s).strip()

    # Strip wrapping quotes/apostrophes repeatedly
    while len(s) > 0 and s[0] in "\"'":
        s = s[1:].lstrip()
    while len(s) > 0 and s[-1] in "\"'":
        s = s[:-1].rstrip()

    # Fix common artifact: starts with S / s after stripping quotes
    s = re.sub(r"^(s\s+)", "", s, flags=re.IGNORECASE)

    return s

def estimate_tools(text: str) -> list[str]:
    lower = text.lower()
    tools = []
    for tool, kws in TOOL_KEYWORDS.items():
        if any(kw in lower for kw in kws):
            tools.append(tool)
    return sorted(set(tools))[:5]  # keep short

def estimate_time_minutes(steps: list[str]) -> int:
    minutes = 6 * max(1, len(steps))
    joined = " ".join(steps).lower()

    if any(w in joined for w in ["bake", "roast"]):
        minutes += 20
    if any(w in joined for w in ["simmer", "stew"]):
        minutes += 15
    if "marinate" in joined:
        minutes += 30

    return int(max(10, min(minutes, 120)))

def estimate_budget_tier(ingredients: list[str]) -> str:
    lower_ings = " ".join(ingredients).lower()
    n = len(ingredients)

    if any(x in lower_ings for x in EXPENSIVE) or n >= 12:
        return "high"
    if n >= 8:
        return "medium"
    return "low"

def parse_ingredients(ingredients_raw: str) -> list[str]:
    s = (ingredients_raw or "").strip()
    if not s:
        return []

    # Some RecipeNLG variants store as a string list like "['salt', 'pepper']"
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]

    parts = [p.strip(" '\"\t") for p in s.split(",")]
    parts = [p for p in parts if p]
    return parts

def parse_steps(directions_raw: str) -> list[str]:
    s = (directions_raw or "").strip()
    if not s:
        return []

    s = s.replace("\r", " ").replace("\n", " ")
    s = re.sub(r"\s+", " ", s).strip()

    # Case: looks like a Python list string: ["Step one", "Step two", ...]
    if s.startswith("[") and s.endswith("]"):
        s2 = s[1:-1].strip()
        parts = re.split(r'"\s*,\s*"|\'\s*,\s*\'', s2)
        cleaned = []
        for p in parts:
            p = p.strip().strip("'").strip('"').strip()
            if p:
                cleaned.append(p)
        if len(cleaned) >= 2:
            return cleaned

    # Fallback: split into sentences
    parts = [p.strip() for p in s.split(".")]
    parts = [p for p in parts if p]
    return parts

def format_recipe(title: str, ingredients: list[str], steps: list[str]) -> str:
    title = normalize_text(title)
    ingredients = [normalize_text(x) for x in ingredients if x and x.strip()]
    steps = [normalize_text(x) for x in steps if x and x.strip()]

    # Basic sanity filters (helps quality)
    if len(title) < 4:
        return ""
    if len(ingredients) < 3 or len(ingredients) > 25:
        return ""
    if len(steps) < 2 or len(steps) > 30:
        return ""

    all_text = " ".join([title] + ingredients + steps)
    tools = estimate_tools(all_text)
    minutes = estimate_time_minutes(steps)
    budget = estimate_budget_tier(ingredients)

    prefs = ", ".join(random.sample(PREF_SAMPLES, k=2))

    out = []
    out.append("<REQUEST>")
    out.append(f"Budget: {budget}")
    out.append(f"Time: {minutes} minutes")
    out.append("Tools: " + (", ".join(tools) if tools else "none"))
    out.append(f"Preferences: {prefs}")
    out.append("</REQUEST>")
    out.append("<RECIPE>")
    out.append(f"Title: {title}")
    out.append("Ingredients:")
    for ing in ingredients[:20]:
        out.append(f"- {ing}")
    out.append("Steps:")
    for i, st in enumerate(steps[:25], 1):
        out.append(f"{i}) {st}")
    out.append("</RECIPE>")
    return "\n".join(out) + "\n"

def main():
    random.seed(1337)

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = repo_root / "nanogpt" / "data" / "processed"
    out_dir.mkdir(parents=True, exist_ok=True)

    csv_path = repo_root / "nanogpt" / "data" / "raw" / "recipenlg" / "full_dataset.csv"
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Missing {csv_path}\n"
            "Put full_dataset.csv at nanogpt/data/raw/recipenlg/full_dataset.csv"
        )

    # Read more rows, shuffle, keep a larger subset for training quality
    rows = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)
            if len(rows) >= 60000:
                break

    random.shuffle(rows)
    rows = rows[:50000]

    formatted = []
    for r in tqdm(rows, desc="Formatting"):
        title = (r.get("title", "") or "").strip()
        ingredients_raw = r.get("ingredients", "") or ""
        directions_raw = r.get("directions", "") or ""

        ingredients = parse_ingredients(ingredients_raw)
        steps = parse_steps(directions_raw)

        if not title or len(ingredients) < 3 or len(steps) < 2:
            continue

        block = format_recipe(title, ingredients, steps)
        if block:
            formatted.append(block)

    n = len(formatted)
    if n < 5000:
        print("WARNING: Very few usable recipes were parsed. The CSV format may differ from expectations.")
        print("Try opening full_dataset.csv and checking the column names/format for ingredients/directions.")

    n_val = max(1000, int(0.05 * n))
    val_text = "".join(formatted[:n_val])
    train_text = "".join(formatted[n_val:])

    (out_dir / "train.txt").write_text(train_text, encoding="utf-8")
    (out_dir / "val.txt").write_text(val_text, encoding="utf-8")

    enc = tiktoken.get_encoding("gpt2")

    def encode_to_bin(text: str, path: Path):
        ids = enc.encode(text)
        arr = np.array(ids, dtype=np.uint16)  # GPT-2 vocab fits in uint16
        arr.tofile(path)

    encode_to_bin(train_text, out_dir / "train.bin")
    encode_to_bin(val_text, out_dir / "val.bin")

    print(f"Done. Examples kept: {n}")
    print(f"Wrote: {out_dir/'train.bin'} and {out_dir/'val.bin'}")
    print("Next: run training with train.py")

if __name__ == "__main__":
    main()