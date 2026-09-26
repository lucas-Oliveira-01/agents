"""Schema validation utilities for OmniRoute delegation payloads.

Validates delegation task parameters against the canonical JSON Schema
and provides runtime schema introspection for tool parameters.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REFERENCES_DIR = Path(__file__).parent / "references"
_DELEGATION_SCHEMA_FILE = "delegation_task.schema.json"
_MCP_MESSAGES_SCHEMA_FILE = "mcp_messages.schema.json"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of a schema validation."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.is_valid


# ---------------------------------------------------------------------------
# Schema Validator
# ---------------------------------------------------------------------------


class SchemaValidator:
    """Validates delegation payloads and MCP messages against JSON schemas.

    Loads schemas from the references/ directory and provides validation
    methods for delegation tasks and MCP protocol messages.

    Usage:
        validator = SchemaValidator()
        result = validator.validate_delegation_task({"task": "..."})
        if not result:
            print(result.errors)
    """

    def __init__(self, references_dir: Optional[str] = None):
        if references_dir is not None:
            self._refs_dir = Path(references_dir)
        else:
            self._refs_dir = _REFERENCES_DIR

        self._delegation_schema: Optional[Dict[str, Any]] = None
        self._mcp_schema: Optional[Dict[str, Any]] = None

    def _load_schema(self, filename: str) -> Dict[str, Any]:
        """Load a JSON schema from the references directory."""
        schema_path = self._refs_dir / filename
        if not schema_path.exists():
            raise FileNotFoundError(
                f"Schema file not found: {schema_path}. " f"References directory: {self._refs_dir}"
            )
        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @property
    def delegation_schema(self) -> Dict[str, Any]:
        """Lazily load and return the delegation task schema."""
        if self._delegation_schema is None:
            self._delegation_schema = self._load_schema(_DELEGATION_SCHEMA_FILE)
        return self._delegation_schema

    @property
    def mcp_messages_schema(self) -> Dict[str, Any]:
        """Lazily load and return the MCP messages schema."""
        if self._mcp_schema is None:
            self._mcp_schema = self._load_schema(_MCP_MESSAGES_SCHEMA_FILE)
        return self._mcp_schema

    def validate_delegation_task(
        self,
        task_params: Dict[str, Any],
    ) -> ValidationResult:
        """Validate a delegation task payload against the canonical schema.

        Args:
            task_params: The parameters dict to validate.

        Returns:
            ValidationResult with is_valid=True if valid, else errors populated.
        """
        errors: List[str] = []
        warnings: List[str] = []

        try:
            jsonschema.validate(instance=task_params, schema=self.delegation_schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"Schema validation error: {exc.message}")
            for context_error in exc.context or []:
                errors.append(f"  - {context_error.message}")
        except jsonschema.SchemaError as exc:
            errors.append(f"Schema definition error: {exc.message}")

        # Additional semantic validations beyond JSON Schema
        self._validate_semantic_rules(task_params, errors, warnings)

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def _validate_semantic_rules(
        self,
        params: Dict[str, Any],
        errors: List[str],
        warnings: List[str],
    ) -> None:
        """Apply semantic validations not expressible in JSON Schema alone."""
        # Rule: cache_mode=deterministic requires cache_key
        cache_mode = params.get("cache_mode")
        if cache_mode == "deterministic":
            if not params.get("cache_key"):
                errors.append("cache_mode='deterministic' requires a non-empty 'cache_key'.")
            # Rule: deterministic cache is incompatible with session_id
            if params.get("session_id"):
                errors.append(
                    "cache_mode='deterministic' is incompatible with 'session_id'. "
                    "Do not combine deterministic caching with session continuity."
                )

        # Rule: task should contain structured sections
        task = params.get("task", "")
        if isinstance(task, str) and task:
            expected_sections = [
                "Objective:",
                "Constraints:",
                "Context:",
                "Expected format:",
                "Success criteria:",
            ]
            missing = [s for s in expected_sections if s not in task]
            if missing:
                warnings.append(
                    f"Task description is missing recommended sections: {missing}. "
                    "A well-formed delegation should include all five sections."
                )

        # Rule: temperature=0 recommended for deterministic results
        if cache_mode == "deterministic" and params.get("temperature") is not None:
            if params["temperature"] != 0:
                warnings.append(
                    "cache_mode='deterministic' with temperature != 0 may produce "
                    "non-repeatable results, undermining cache determinism."
                )

        # Rule: max_tokens should be proportional
        max_tokens = params.get("max_tokens")
        if max_tokens is not None and max_tokens < 10:
            warnings.append(f"max_tokens={max_tokens} is very low and may truncate responses.")

    def validate_mcp_request(
        self,
        request: Dict[str, Any],
    ) -> ValidationResult:
        """Validate a JSON-RPC request message structure.

        Args:
            request: The JSON-RPC request dict.

        Returns:
            ValidationResult.
        """
        errors: List[str] = []
        schema = self.mcp_messages_schema
        request_schema = schema.get("definitions", {}).get("jsonrpc_request", {})

        try:
            jsonschema.validate(instance=request, schema=request_schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"Request validation error: {exc.message}")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def validate_mcp_response(
        self,
        response: Dict[str, Any],
    ) -> ValidationResult:
        """Validate a JSON-RPC response message structure.

        Args:
            response: The JSON-RPC response dict.

        Returns:
            ValidationResult.
        """
        errors: List[str] = []

        if "error" in response:
            schema_def = "jsonrpc_error_response"
        elif "result" in response:
            schema_def = "jsonrpc_success_response"
        else:
            errors.append("Response must contain either 'result' or 'error' field.")
            return ValidationResult(is_valid=False, errors=errors)

        schema = self.mcp_messages_schema
        response_schema = schema.get("definitions", {}).get(schema_def, {})

        try:
            jsonschema.validate(instance=response, schema=response_schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"Response validation error: {exc.message}")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def validate_tools_list_result(
        self,
        result: Dict[str, Any],
    ) -> ValidationResult:
        """Validate the result payload from tools/list.

        Args:
            result: The 'result' field from a tools/list response.

        Returns:
            ValidationResult.
        """
        errors: List[str] = []
        schema = self.mcp_messages_schema
        tools_schema = schema.get("definitions", {}).get("tools_list_result", {})

        try:
            jsonschema.validate(instance=result, schema=tools_schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"tools/list result validation error: {exc.message}")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    def is_known_error_code(self, code: str) -> bool:
        """Check if an error code is a known OmniRoute application error."""
        schema = self.mcp_messages_schema
        known_codes_def = schema.get("definitions", {}).get("known_error_codes", {})
        known_enum = known_codes_def.get("enum", [])
        return code in known_enum
