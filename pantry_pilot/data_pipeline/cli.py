from __future__ import annotations

import argparse
import json
from pathlib import Path

from pantry_pilot.data_pipeline.importer import ImportConfig, import_recipes_from_file


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import local recipe files into PantryPilot's processed dataset format.")
    parser.add_argument("raw_path", help="Path to a raw local recipe file (.json or .csv).")
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
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = import_recipes_from_file(
        Path(args.raw_path),
        processed_path=None if args.processed_path is None else Path(args.processed_path),
        config=ImportConfig(max_unmapped_ingredient_fraction=args.max_unmapped_fraction),
    )
    print(json.dumps({"output_path": result.output_path, "stats_path": result.stats_path, "stats": result.stats}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
