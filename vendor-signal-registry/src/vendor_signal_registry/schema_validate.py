"""Validate registry documents against schema.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_SCHEMA_CACHE: dict[str, Any] | None = None


def find_schema_path() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3] / "schema.json",  # Conduit/schema.json from src/...
        here.parents[2] / "schema.json",
        Path.cwd() / "schema.json",
        Path.cwd().parent / "schema.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "schema.json not found. Expected at repo root (Conduit/schema.json)."
    )


def load_schema() -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = json.loads(find_schema_path().read_text(encoding="utf-8"))
    return _SCHEMA_CACHE


def validate_registry(document: dict[str, Any]) -> list[str]:
    """Return a list of validation error messages (empty if valid)."""
    validator = Draft202012Validator(load_schema())
    return sorted(
        f"{'.'.join(str(p) for p in err.path) or '<root>'}: {err.message}"
        for err in validator.iter_errors(document)
    )


def assert_valid(document: dict[str, Any]) -> None:
    errors = validate_registry(document)
    if errors:
        joined = "\n".join(f"  - {e}" for e in errors)
        raise ValueError(f"registry.json failed schema validation:\n{joined}")
