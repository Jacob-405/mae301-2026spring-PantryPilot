"""Schema and validation helpers for large local recipe datasets."""

from pantry_pilot.data_pipeline.schema import (
    AllergenAssessment,
    AllergenCompleteness,
    CalorieEstimate,
    DiversityMetadata,
    IngredientRecord,
    NormalizedRecipe,
    SourceMetadata,
)
from pantry_pilot.data_pipeline.importer import (
    DEFAULT_PROCESSED_FILENAME,
    ImportConfig,
    ImportRejection,
    ImportResult,
    import_kaggle_recipe_directory,
    import_recipenlg_dataset,
    import_recipes_from_file,
    import_recipes_from_files,
)
from pantry_pilot.data_pipeline.validation import (
    DataQualitySeverity,
    SchemaValidationError,
    ValidationIssue,
    assert_valid_recipe,
    assert_valid_recipe_collection,
    validate_recipe,
    validate_recipe_collection,
)
from pantry_pilot.data_pipeline.similarity import (
    RecipeSimilarityMatch,
    annotate_recipe_similarity,
    build_diversity_metadata,
    compare_recipes,
)
from pantry_pilot.data_pipeline.schema import SimilarityMetadata

__all__ = [
    "AllergenAssessment",
    "AllergenCompleteness",
    "CalorieEstimate",
    "DataQualitySeverity",
    "DEFAULT_PROCESSED_FILENAME",
    "DiversityMetadata",
    "ImportConfig",
    "ImportRejection",
    "ImportResult",
    "IngredientRecord",
    "NormalizedRecipe",
    "SchemaValidationError",
    "SourceMetadata",
    "SimilarityMetadata",
    "ValidationIssue",
    "RecipeSimilarityMatch",
    "annotate_recipe_similarity",
    "assert_valid_recipe",
    "assert_valid_recipe_collection",
    "build_diversity_metadata",
    "compare_recipes",
    "import_kaggle_recipe_directory",
    "import_recipenlg_dataset",
    "import_recipes_from_file",
    "import_recipes_from_files",
    "validate_recipe",
    "validate_recipe_collection",
]
