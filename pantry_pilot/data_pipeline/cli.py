from __future__ import annotations

import argparse
import json
from pathlib import Path

from pantry_pilot.data_pipeline.importer import ImportConfig, import_kaggle_recipe_directory, import_recipes_from_files


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
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    config = ImportConfig(max_unmapped_ingredient_fraction=args.max_unmapped_fraction)
    if args.kaggle_dir:
        result = import_kaggle_recipe_directory(
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
