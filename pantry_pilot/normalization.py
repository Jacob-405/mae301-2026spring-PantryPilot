from __future__ import annotations


def normalize_name(value: str) -> str:
    return " ".join((value or "").strip().lower().replace("_", " ").split())


def parse_csv_list(value: str) -> tuple[str, ...]:
    parts = [normalize_name(part) for part in (value or "").split(",")]
    return tuple(part for part in parts if part)
