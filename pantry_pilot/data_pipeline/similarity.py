from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from pantry_pilot.data_pipeline.schema import DiversityMetadata, NormalizedRecipe, SimilarityMetadata
from pantry_pilot.normalization import normalize_name


MEAL_STYLE_KEYWORDS = frozenset(
    {
        "bowl",
        "salad",
        "toast",
        "soup",
        "skillet",
        "pasta",
        "stir fry",
        "scramble",
        "parfait",
        "chili",
        "curry",
        "stuffed",
        "fried",
        "oatmeal",
    }
)
PRIMARY_PROTEIN_INGREDIENTS = frozenset(
    {
        "black beans",
        "cheddar cheese",
        "chicken breast",
        "chickpeas",
        "eggs",
        "feta",
        "ground turkey",
        "lentils",
        "milk",
        "parmesan",
        "peanut butter",
        "tofu",
        "yogurt",
    }
)
PRIMARY_CARB_INGREDIENTS = frozenset(
    {
        "banana",
        "bread",
        "corn",
        "granola",
        "pasta",
        "rice",
        "rolled oats",
    }
)


@dataclass(frozen=True)
class RecipeSimilarityMatch:
    score: float
    signals: tuple[str, ...]
    exact_duplicate: bool


SimilarityProgressCallback = Callable[[dict[str, int]], None]


def build_diversity_metadata(recipe: NormalizedRecipe) -> DiversityMetadata:
    ingredient_names = tuple(sorted({ingredient.canonical_name for ingredient in recipe.ingredients}))
    meal_styles = tuple(sorted(_meal_style_markers(recipe.title)))
    primary_proteins = tuple(name for name in ingredient_names if name in PRIMARY_PROTEIN_INGREDIENTS)
    primary_carbs = tuple(name for name in ingredient_names if name in PRIMARY_CARB_INGREDIENTS)
    vegetables = tuple(
        name
        for name in ingredient_names
        if name not in PRIMARY_PROTEIN_INGREDIENTS and name not in PRIMARY_CARB_INGREDIENTS
    )
    return DiversityMetadata(
        primary_proteins=primary_proteins,
        primary_carbs=primary_carbs,
        vegetables=vegetables,
        flavor_tags=(recipe.cuisine,) if recipe.cuisine and recipe.cuisine != "unknown" else (),
        texture_tags=meal_styles,
    )


def annotate_recipe_similarity(
    recipes: tuple[NormalizedRecipe, ...],
    *,
    progress_every_recipes: int = 0,
    progress_callback: SimilarityProgressCallback | None = None,
) -> tuple[NormalizedRecipe, ...]:
    ordered = tuple(sorted(recipes, key=lambda recipe: recipe.recipe_id))
    if not ordered:
        return ()

    adjacency: dict[str, set[str]] = {recipe.recipe_id: set() for recipe in ordered}
    pair_matches: dict[tuple[str, str], RecipeSimilarityMatch] = {}
    indexed_title_tokens: dict[str, set[str]] = {}
    indexed_ingredients: dict[str, set[str]] = {}
    recipes_by_id = {recipe.recipe_id: recipe for recipe in ordered}
    comparisons_evaluated = 0
    for index, left in enumerate(ordered):
        left_title_tokens = _title_tokens(left.title)
        left_ingredients = {ingredient.canonical_name for ingredient in left.ingredients}
        candidate_ids = _candidate_recipe_ids(
            title_tokens=left_title_tokens,
            ingredients=left_ingredients,
            indexed_title_tokens=indexed_title_tokens,
            indexed_ingredients=indexed_ingredients,
        )
        for candidate_id in sorted(candidate_ids):
            right = recipes_by_id[candidate_id]
            match = compare_recipes(left, right)
            comparisons_evaluated += 1
            if match.score >= 0.72 or match.exact_duplicate:
                adjacency[left.recipe_id].add(right.recipe_id)
                adjacency[right.recipe_id].add(left.recipe_id)
                pair_matches[(left.recipe_id, right.recipe_id)] = match
                pair_matches[(right.recipe_id, left.recipe_id)] = match
        _add_recipe_to_index(indexed_title_tokens, left_title_tokens, left.recipe_id)
        _add_recipe_to_index(indexed_ingredients, left_ingredients, left.recipe_id)
        if progress_callback is not None and progress_every_recipes > 0 and (index + 1) % progress_every_recipes == 0:
            progress_callback(
                {
                    "recipes_processed": index + 1,
                    "recipes_total": len(ordered),
                    "comparisons_evaluated": comparisons_evaluated,
                }
            )
    if progress_callback is not None and progress_every_recipes > 0 and len(ordered) % progress_every_recipes != 0:
        progress_callback(
            {
                "recipes_processed": len(ordered),
                "recipes_total": len(ordered),
                "comparisons_evaluated": comparisons_evaluated,
            }
        )

    clusters = _build_clusters(ordered, adjacency)
    by_id = {recipe.recipe_id: recipe for recipe in ordered}
    annotated: list[NormalizedRecipe] = []
    for recipe in ordered:
        cluster = clusters.get(recipe.recipe_id, (recipe.recipe_id,))
        representative_id = cluster[0]
        related_ids = tuple(recipe_id for recipe_id in cluster if recipe_id != recipe.recipe_id)
        if not related_ids:
            similarity = SimilarityMetadata()
        else:
            if recipe.recipe_id == representative_id:
                best_score, best_signals = _best_related_match(recipe.recipe_id, related_ids, pair_matches)
                similarity = SimilarityMetadata(
                    cluster_id=f"cluster-{representative_id}",
                    representative_recipe_id=representative_id,
                    related_recipe_ids=related_ids,
                    similarity_score_to_representative=best_score,
                    similarity_signals=best_signals,
                )
            else:
                match = pair_matches.get((recipe.recipe_id, representative_id))
                if match is None:
                    best_score, best_signals = _best_related_match(recipe.recipe_id, related_ids, pair_matches)
                    similarity = SimilarityMetadata(
                        cluster_id=f"cluster-{representative_id}",
                        representative_recipe_id=representative_id,
                        related_recipe_ids=tuple(recipe_id for recipe_id in related_ids if recipe_id != representative_id),
                        similarity_score_to_representative=best_score,
                        similarity_signals=best_signals,
                    )
                    annotated.append(replace(recipe, similarity=similarity))
                    continue
                similarity = SimilarityMetadata(
                    cluster_id=f"cluster-{representative_id}",
                    exact_duplicate_of=representative_id if match.exact_duplicate else "",
                    representative_recipe_id=representative_id,
                    related_recipe_ids=tuple(recipe_id for recipe_id in related_ids if recipe_id != representative_id),
                    similarity_score_to_representative=match.score,
                    similarity_signals=match.signals,
                )
        annotated.append(replace(recipe, similarity=similarity))
    return tuple(annotated)


def compare_recipes(left: NormalizedRecipe, right: NormalizedRecipe) -> RecipeSimilarityMatch:
    left_title_tokens = _title_tokens(left.title)
    right_title_tokens = _title_tokens(right.title)
    left_ingredients = {ingredient.canonical_name for ingredient in left.ingredients}
    right_ingredients = {ingredient.canonical_name for ingredient in right.ingredients}
    left_meal_styles = _meal_style_markers(left.title)
    right_meal_styles = _meal_style_markers(right.title)

    shared_title = left_title_tokens & right_title_tokens
    shared_ingredients = left_ingredients & right_ingredients
    title_overlap = _jaccard(left_title_tokens, right_title_tokens)
    ingredient_overlap = _jaccard(left_ingredients, right_ingredients)
    cuisine_match = normalize_name(left.cuisine) == normalize_name(right.cuisine)
    meal_style_overlap = bool(left_meal_styles & right_meal_styles)
    protein_overlap = bool(set(left.diversity.primary_proteins) & set(right.diversity.primary_proteins))
    carb_overlap = bool(set(left.diversity.primary_carbs) & set(right.diversity.primary_carbs))

    score = 0.0
    signals: list[str] = []
    if title_overlap:
        score += title_overlap * 0.35
        signals.append(f"title-overlap:{round(title_overlap, 2)}")
    if ingredient_overlap:
        score += ingredient_overlap * 0.4
        signals.append(f"ingredient-overlap:{round(ingredient_overlap, 2)}")
    if cuisine_match:
        score += 0.1
        signals.append("shared-cuisine")
    if meal_style_overlap:
        score += 0.1
        signals.append("shared-meal-style")
    if protein_overlap:
        score += 0.03
        signals.append("shared-primary-protein")
    if carb_overlap:
        score += 0.02
        signals.append("shared-primary-carb")

    exact_duplicate = (
        normalize_name(left.title) == normalize_name(right.title)
        and left_ingredients == right_ingredients
        and normalize_name(left.cuisine) == normalize_name(right.cuisine)
        and tuple(sorted(left.meal_types)) == tuple(sorted(right.meal_types))
        and shared_title == left_title_tokens == right_title_tokens
    )
    if exact_duplicate:
        signals.append("exact-duplicate")
        score = max(score, 0.99)

    return RecipeSimilarityMatch(
        score=round(score, 4),
        signals=tuple(signals),
        exact_duplicate=exact_duplicate,
    )


def _build_clusters(
    recipes: tuple[NormalizedRecipe, ...],
    adjacency: dict[str, set[str]],
) -> dict[str, tuple[str, ...]]:
    clusters: dict[str, tuple[str, ...]] = {}
    visited: set[str] = set()
    recipe_ids = tuple(recipe.recipe_id for recipe in recipes)
    for recipe_id in recipe_ids:
        if recipe_id in visited:
            continue
        stack = [recipe_id]
        component: list[str] = []
        while stack:
            current = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            stack.extend(sorted(adjacency[current], reverse=True))
        ordered_component = tuple(sorted(component))
        for member in ordered_component:
            clusters[member] = ordered_component
    return clusters


def _best_related_match(
    recipe_id: str,
    related_ids: tuple[str, ...],
    pair_matches: dict[tuple[str, str], RecipeSimilarityMatch],
) -> tuple[float, tuple[str, ...]]:
    candidates = [
        pair_matches[(recipe_id, other_id)]
        for other_id in related_ids
        if (recipe_id, other_id) in pair_matches
    ]
    if not candidates:
        return 0.0, ()
    best = max(candidates, key=lambda match: (match.score, match.signals))
    return best.score, best.signals


def _candidate_recipe_ids(
    *,
    title_tokens: set[str],
    ingredients: set[str],
    indexed_title_tokens: dict[str, set[str]],
    indexed_ingredients: dict[str, set[str]],
) -> set[str]:
    title_candidates: set[str] = set()
    for title_token in title_tokens:
        title_candidates.update(indexed_title_tokens.get(title_token, ()))
    if not title_candidates:
        return set()
    ingredient_candidates: set[str] = set()
    for ingredient in ingredients:
        ingredient_candidates.update(indexed_ingredients.get(ingredient, ()))
    if not ingredient_candidates:
        return set()
    # The current threshold cannot be reached without both some title overlap and some ingredient overlap.
    return title_candidates & ingredient_candidates


def _add_recipe_to_index(index: dict[str, set[str]], keys: set[str], recipe_id: str) -> None:
    for key in keys:
        index.setdefault(key, set()).add(recipe_id)


def _title_tokens(title: str) -> set[str]:
    return set(normalize_name(title).split())


def _meal_style_markers(title: str) -> set[str]:
    normalized_title = normalize_name(title)
    return {keyword for keyword in MEAL_STYLE_KEYWORDS if keyword in normalized_title}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return len(left & right) / len(left | right)
