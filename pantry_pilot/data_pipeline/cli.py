from __future__ import annotations

import argparse
import json
from pathlib import Path

from pantry_pilot.data_pipeline.importer import (
    ImportConfig,
    import_kaggle_recipe_directory,
    import_recipenlg_dataset,
    import_recipes_from_files,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import local recipe files into PantryPilot's processed dataset format.")
    parser.add_argument("raw_path", nargs="+", help="Path to one or more raw local recipe files (.json or .csv), or a Kaggle recipe directory.")
    parser.add_argument(
        "--processed-path",
        dest="processed_path",
        default=None,
        help="Optional output path for the processed recipes JSON file.",
    )
    parser.add_argument(
        "--max-unmapped-fraction",
        dest="max_unmapped_fraction",
        type=float,
        default=0.25,
        help="Reject rows when the unmapped ingredient fraction is above this threshold.",
    )
    parser.add_argument(
        "--kaggle-dir",
        dest="kaggle_dir",
        action="store_true",
        help="Treat the input path as a Kaggle recipe directory containing recipes.csv and test_recipes.csv.",
    )
    parser.add_argument(
        "--recipenlg",
        dest="recipenlg",
        action="store_true",
        help="Treat the input path as the RecipeNLG CSV file and run the streaming importer.",
    )
    parser.add_argument(
        "--row-limit",
        dest="row_limit",
        type=int,
        default=None,
        help="Optional RecipeNLG row limit for sample validation runs.",
    )
    parser.add_argument(
        "--max-output-recipes",
        dest="max_output_recipes",
        type=int,
        default=None,
        help="Optional cap on how many accepted recipes to serialize to the processed output.",
    )
    parser.add_argument(
        "--progress-every",
        dest="progress_every_rows",
        type=int,
        default=100000,
        help="Emit RecipeNLG progress after this many scanned rows. Use 0 to disable.",
    )
    parser.add_argument(
        "--checkpoint-every",
        dest="checkpoint_every_rows",
        type=int,
        default=100000,
        help="Write RecipeNLG checkpoint stats after this many scanned rows. Use 0 to disable.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = ImportConfig(
        max_unmapped_ingredient_fraction=args.max_unmapped_fraction,
        max_output_recipes=args.max_output_recipes,
        row_limit=args.row_limit,
        progress_every_rows=args.progress_every_rows,
        checkpoint_every_rows=args.checkpoint_every_rows,
    )
    if args.kaggle_dir:
        result = import_kaggle_recipe_directory(
            Path(args.raw_path[0]),
            processed_path=None if args.processed_path is None else Path(args.processed_path),
            config=config,
        )
    elif args.recipenlg:
        result = import_recipenlg_dataset(
            Path(args.raw_path[0]),
            processed_path=None if args.processed_path is None else Path(args.processed_path),
            config=config,
        )
    else:
        result = import_recipes_from_files(
            tuple(Path(path) for path in args.raw_path),
            processed_path=None if args.processed_path is None else Path(args.processed_path),
            config=config,
        )
    print(json.dumps({"output_path": result.output_path, "stats_path": result.stats_path, "stats": result.stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
