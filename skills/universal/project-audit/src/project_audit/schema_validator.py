"""
schema_validator.py — JSON Schema structural gate for project-audit

Validates entity dicts against the physical JSON Schemas located at:
  src/project_audit/schemas/

This is the STRUCTURAL gate. It complements (but does not replace) the
Semantic Validators in validators.py.

Schema validates FORM. Semantic Validators validate MEANING.
(semantic-validators.md preamble)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import jsonschema
    from jsonschema import validate as _validate, ValidationError as JVError
    from jsonschema.validators import validator_for

    try:
        from referencing import Registry, Resource
        from referencing.jsonschema import DRAFT202012

        _HAS_REFERENCING = True
    except ImportError:
        _HAS_REFERENCING = False

except ImportError as e:
    raise ImportError(f"jsonschema is required: {e}") from e


_SCHEMA_DIR: Optional[Path] = None


def _find_schema_dir() -> Path:
    """Locate schemas/ next to this file."""
    schemas = Path(__file__).resolve().parent / "schemas"
    if schemas.is_dir():
        return schemas
    raise FileNotFoundError(
        f"Cannot locate {schemas}. "
        "Ensure the package is properly installed."
    )


def _get_schema_dir() -> Path:
    global _SCHEMA_DIR
    if _SCHEMA_DIR is None or not _SCHEMA_DIR.is_dir():
        _SCHEMA_DIR = _find_schema_dir()
    return _SCHEMA_DIR


def _load_schema(name: str, schema_dir: Path) -> dict:
    path = schema_dir / name
    if not path.exists():
        raise FileNotFoundError(f"Schema not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _build_registry(schema_dir: Path) -> Any:
    """Build a jsonschema registry with shared.schema.json loaded."""
    if not _HAS_REFERENCING:
        return None
    shared = _load_schema("shared.schema.json", schema_dir)
    resource = Resource.from_contents(shared, default_specification=DRAFT202012)
    return Registry().with_resource(
        "shared.schema.json", resource
    ).with_resource(
        "https://antigravity.local/schemas/shared.schema.json", resource
    )


def validate_dict(entity_dict: dict, schema_name: str, schema_dir: Optional[Path] = None) -> List[str]:
    """
    Validate entity_dict against the named JSON schema.

    Returns a list of error messages (empty = valid).
    """
    sdir = schema_dir or _get_schema_dir()
    schema = _load_schema(schema_name, sdir)
    registry = _build_registry(sdir)

    errors: List[str] = []
    try:
        if registry is not None:
            validator_cls = validator_for(schema)
            validator = validator_cls(schema, registry=registry)
            for error in validator.iter_errors(entity_dict):
                errors.append(f"{error.json_path}: {error.message}")
        else:
            _validate(instance=entity_dict, schema=schema)
    except JVError as e:
        errors.append(str(e.message))
    return errors


# Convenience schema name constants
SCHEMA_TARGET_SNAPSHOT = "target-snapshot.schema.json"
SCHEMA_AUDIT_PLAN = "audit-plan.schema.json"
SCHEMA_AUDIT_WORK_ITEM = "audit-work-item.schema.json"
SCHEMA_EVIDENCE = "evidence.schema.json"
SCHEMA_AUDIT_RUN = "audit-run.schema.json"


def validate_target_snapshot(d: dict) -> List[str]:
    return validate_dict(d, SCHEMA_TARGET_SNAPSHOT)


def validate_audit_plan(d: dict) -> List[str]:
    return validate_dict(d, SCHEMA_AUDIT_PLAN)


def validate_audit_work_item(d: dict) -> List[str]:
    return validate_dict(d, SCHEMA_AUDIT_WORK_ITEM)


def validate_evidence(d: dict) -> List[str]:
    return validate_dict(d, SCHEMA_EVIDENCE)


def validate_audit_run(d: dict) -> List[str]:
    return validate_dict(d, SCHEMA_AUDIT_RUN)
