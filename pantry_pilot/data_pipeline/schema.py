from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AllergenCompleteness(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SourceMetadata:
    source_id: str
    source_name: str
    source_type: str
    citation: str = ""
    source_url: str = ""
    license_name: str = ""
    file_path: str = ""
    checksum: str = ""
    ingested_at: str = ""


@dataclass(frozen=True)
class IngredientRecord:
    ingredient_id: str
    display_name: str
    canonical_name: str
    quantity: float
    unit: str
    preparation: str = ""
    notes: str = ""
    optional: bool = False
    category: str = ""


@dataclass(frozen=True)
class AllergenAssessment:
    allergens: frozenset[str] | None
    completeness: AllergenCompleteness
    unsafe_if_unknown: bool = True

    @property
    def is_known_safe(self) -> bool:
        return self.completeness is AllergenCompleteness.COMPLETE and self.allergens is not None


@dataclass(frozen=True)
class CalorieEstimate:
    calories_per_serving: int | None
    source: str = ""
    confidence: float | None = None
    notes: str = ""


@dataclass(frozen=True)
class DiversityMetadata:
    primary_proteins: tuple[str, ...] = ()
    primary_carbs: tuple[str, ...] = ()
    vegetables: tuple[str, ...] = ()
    cooking_methods: tuple[str, ...] = ()
    flavor_tags: tuple[str, ...] = ()
    texture_tags: tuple[str, ...] = ()
    seasonal_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class SimilarityMetadata:
    cluster_id: str = ""
    exact_duplicate_of: str = ""
    related_recipe_ids: tuple[str, ...] = ()
    representative_recipe_id: str = ""
    similarity_score_to_representative: float = 0.0
    similarity_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class NormalizedRecipe:
    recipe_id: str
    title: str
    source: SourceMetadata
    source_recipe_id: str
    cuisine: str
    meal_types: tuple[str, ...]
    diet_tags: frozenset[str]
    allergens: AllergenAssessment
    ingredients: tuple[IngredientRecord, ...]
    steps: tuple[str, ...]
    servings: int
    prep_time_minutes: int
    cook_time_minutes: int = 0
    total_time_minutes: int = 0
    calories: CalorieEstimate = field(default_factory=lambda: CalorieEstimate(calories_per_serving=None))
    diversity: DiversityMetadata = field(default_factory=DiversityMetadata)
    similarity: SimilarityMetadata = field(default_factory=SimilarityMetadata)
    normalized_search_text: str = ""
