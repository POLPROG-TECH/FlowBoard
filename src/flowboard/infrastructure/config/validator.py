"""JSON-Schema based validation for FlowBoard configuration."""

from __future__ import annotations

import importlib.resources
import json
import threading
from pathlib import Path
from typing import Any

import jsonschema

# Try to find the schema in multiple locations for robustness.
_STATIC_CANDIDATES = [
    Path(__file__).resolve().parents[4] / "config.schema.json",  # dev / editable install
    Path(__file__).resolve().parent / "config.schema.json",  # bundled alongside validator
]

_cached_schema: dict[str, Any] | None = None
_schema_lock = threading.Lock()


def _find_schema_path() -> Path:
    """Blocker #15: robust schema resolution including importlib.resources."""
    candidates = [*_STATIC_CANDIDATES, Path.cwd() / "config.schema.json"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    # Fallback: try importlib.resources for installed package
    try:
        ref = importlib.resources.files("flowboard") / ".." / ".." / ".." / "config.schema.json"
        p = Path(str(ref))
        if p.exists():
            return p
    except (TypeError, FileNotFoundError, ModuleNotFoundError):
        pass
    raise FileNotFoundError(
        "config.schema.json not found. Searched:\n"
        + "\n".join(f"  - {p}" for p in candidates)
        + "\nEnsure the schema is bundled with the package or present in CWD."
    )


def _load_schema() -> dict[str, Any]:
    global _cached_schema
    if _cached_schema is not None:
        return _cached_schema
    with _schema_lock:
        if _cached_schema is None:
            schema_path = _find_schema_path()
            with schema_path.open(encoding="utf-8") as fh:
                _cached_schema = json.load(fh)
    return _cached_schema


class ConfigValidationError(Exception):
    """Raised when configuration does not match the expected schema."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        msg = "Configuration validation failed:\n" + "\n".join(f"  • {e}" for e in errors)
        super().__init__(msg)


def validate_config_dict(data: dict[str, Any]) -> None:
    """Validate a raw config dict against the FlowBoard JSON Schema.

    Raises :class:`ConfigValidationError` with all found issues.
    """
    schema = _load_schema()
    validator = jsonschema.Draft7Validator(schema)
    errors: list[str] = []
    for err in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
        location = ".".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"{location}: {err.message}")
    if errors:
        raise ConfigValidationError(errors)
