"""Tests for schema validation — delegation tasks and MCP messages.

Tests cover:
- Delegation task schema validation (valid/invalid payloads)
- Semantic rule enforcement (cache constraints, task structure)
- MCP request/response validation
- tools/list result validation
- Known error code identification
- Schema loading and error handling
"""

from __future__ import annotations


import pytest

from omniroute_delegation.schema_validator import SchemaValidator
from tests.helpers import REFERENCES_DIR

# ===========================================================================
# Schema Loading
# ===========================================================================


class TestSchemaLoading:
    """Test schema loading from references directory."""

    def test_load_delegation_schema(self):
        validator = SchemaValidator(str(REFERENCES_DIR))
        schema = validator.delegation_schema
        assert schema["$id"] == "omniroute-delegation-task.schema.json"
        assert "task" in schema["properties"]

    def test_load_mcp_schema(self):
        validator = SchemaValidator(str(REFERENCES_DIR))
        schema = validator.mcp_messages_schema
        assert "definitions" in schema
        assert "jsonrpc_request" in schema["definitions"]

    def test_load_nonexistent_dir(self):
        validator = SchemaValidator("/nonexistent/path")
        with pytest.raises(FileNotFoundError):
            _ = validator.delegation_schema

    def test_lazy_loading(self):
        validator = SchemaValidator(str(REFERENCES_DIR))
        # Schema should not be loaded yet
        assert validator._delegation_schema is None
        # Access triggers loading
        _ = validator.delegation_schema
        assert validator._delegation_schema is not None
        # Second access uses cache
        schema2 = validator.delegation_schema
        assert schema2 is validator._delegation_schema


# ===========================================================================
# Delegation Task Validation — Valid Payloads
# ===========================================================================


class TestDelegationTaskValid:
    """Test validation of valid delegation task payloads."""

    @pytest.fixture
    def validator(self) -> SchemaValidator:
        return SchemaValidator(str(REFERENCES_DIR))

    def test_minimal_valid(self, validator: SchemaValidator):
        result = validator.validate_delegation_task({"task": "Test task"})
        assert result.is_valid

    def test_full_valid(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": (
                    "Objetivo: test\n"
                    "Restrições: none\n"
                    "Contexto: none\n"
                    "Formato esperado: text\n"
                    "Critérios de sucesso: correct"
                ),
                "profile": "coding",
                "context": "some context",
                "task_id": "task-001",
                "cache_mode": "native",
                "max_tokens": 500,
                "temperature": 0,
            }
        )
        assert result.is_valid

    def test_deterministic_with_cache_key(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": (
                    "Objetivo: test\n"
                    "Restrições: none\n"
                    "Contexto: none\n"
                    "Formato esperado: text\n"
                    "Critérios de sucesso: correct"
                ),
                "cache_mode": "deterministic",
                "cache_key": "abc123",
                "temperature": 0,
            }
        )
        assert result.is_valid

    def test_bypass_cache(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": "test",
                "cache_mode": "bypass",
            }
        )
        assert result.is_valid

    def test_bool_conversion_truthy(self, validator: SchemaValidator):
        result = validator.validate_delegation_task({"task": "valid"})
        assert bool(result) is True


# ===========================================================================
# Delegation Task Validation — Invalid Payloads
# ===========================================================================


class TestDelegationTaskInvalid:
    """Test validation of invalid delegation task payloads."""

    @pytest.fixture
    def validator(self) -> SchemaValidator:
        return SchemaValidator(str(REFERENCES_DIR))

    def test_missing_tarefa(self, validator: SchemaValidator):
        result = validator.validate_delegation_task({})
        assert not result.is_valid
        assert any("task" in e.lower() for e in result.errors)

    def test_empty_tarefa(self, validator: SchemaValidator):
        result = validator.validate_delegation_task({"task": ""})
        assert not result.is_valid

    @pytest.mark.parametrize("value", [None, True])
    def test_invalid_tarefa_type_returns_result(self, validator: SchemaValidator, value):
        result = validator.validate_delegation_task({"task": value})
        assert not result.is_valid
        assert result.errors

    def test_invalid_cache_mode(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": "test",
                "cache_mode": "invalid_mode",
            }
        )
        assert not result.is_valid

    def test_invalid_temperature_too_high(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": "test",
                "temperature": 5.0,
            }
        )
        assert not result.is_valid

    def test_negative_max_tokens(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": "test",
                "max_tokens": -1,
            }
        )
        assert not result.is_valid

    def test_additional_properties_rejected(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": "test",
                "unknown_field": "value",
            }
        )
        assert not result.is_valid

    def test_bool_conversion_falsy(self, validator: SchemaValidator):
        result = validator.validate_delegation_task({})
        assert bool(result) is False


# ===========================================================================
# Semantic Rule Enforcement
# ===========================================================================


class TestSemanticRules:
    """Test semantic validations beyond JSON Schema."""

    @pytest.fixture
    def validator(self) -> SchemaValidator:
        return SchemaValidator(str(REFERENCES_DIR))

    def test_deterministic_without_cache_key(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": "test",
                "cache_mode": "deterministic",
            }
        )
        assert not result.is_valid
        assert any("cache_key" in e for e in result.errors)

    def test_deterministic_with_session_id(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": "test",
                "cache_mode": "deterministic",
                "cache_key": "key123",
                "session_id": "sess-001",
            }
        )
        assert not result.is_valid
        assert any("session_id" in e for e in result.errors)

    def test_missing_task_sections_warning(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": "Just a plain task without sections",
            }
        )
        assert result.is_valid  # Not an error, just a warning
        assert len(result.warnings) > 0
        assert any("Objetivo" in w for w in result.warnings)

    def test_complete_task_no_warning(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": (
                    "Objetivo: do something\n"
                    "Restrições: none\n"
                    "Contexto: here\n"
                    "Formato esperado: text\n"
                    "Critérios de sucesso: done"
                ),
            }
        )
        assert result.is_valid
        assert not any("Objetivo" in w for w in result.warnings)

    def test_deterministic_nonzero_temperature_warning(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": "test",
                "cache_mode": "deterministic",
                "cache_key": "key123",
                "temperature": 0.5,
            }
        )
        assert result.is_valid  # Warning only
        assert any("temperature" in w for w in result.warnings)

    def test_very_low_max_tokens_warning(self, validator: SchemaValidator):
        result = validator.validate_delegation_task(
            {
                "task": "test",
                "max_tokens": 5,
            }
        )
        assert result.is_valid
        assert any("max_tokens" in w for w in result.warnings)


# ===========================================================================
# MCP Message Validation
# ===========================================================================


class TestMCPMessageValidation:
    """Test validation of MCP JSON-RPC messages."""

    @pytest.fixture
    def validator(self) -> SchemaValidator:
        return SchemaValidator(str(REFERENCES_DIR))

    def test_valid_request(self, validator: SchemaValidator):
        result = validator.validate_mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            }
        )
        assert result.is_valid

    def test_request_without_params(self, validator: SchemaValidator):
        result = validator.validate_mcp_request(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
            }
        )
        assert result.is_valid

    def test_invalid_jsonrpc_version(self, validator: SchemaValidator):
        result = validator.validate_mcp_request(
            {
                "jsonrpc": "1.0",
                "id": 1,
                "method": "test",
            }
        )
        assert not result.is_valid

    def test_valid_success_response(self, validator: SchemaValidator):
        result = validator.validate_mcp_response(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {"tools": []},
            }
        )
        assert result.is_valid

    def test_valid_error_response(self, validator: SchemaValidator):
        result = validator.validate_mcp_response(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {"code": -32600, "message": "Invalid Request"},
            }
        )
        assert result.is_valid

    def test_response_missing_both_result_and_error(self, validator: SchemaValidator):
        result = validator.validate_mcp_response(
            {
                "jsonrpc": "2.0",
                "id": 1,
            }
        )
        assert not result.is_valid

    def test_valid_tools_list_result(self, validator: SchemaValidator):
        result = validator.validate_tools_list_result(
            {
                "tools": [
                    {"name": "delegate_task", "inputSchema": {"type": "object"}},
                ],
            }
        )
        assert result.is_valid

    def test_tools_list_empty(self, validator: SchemaValidator):
        result = validator.validate_tools_list_result({"tools": []})
        assert result.is_valid

    def test_tools_list_missing_name(self, validator: SchemaValidator):
        result = validator.validate_tools_list_result(
            {
                "tools": [{"inputSchema": {"type": "object"}}],
            }
        )
        assert not result.is_valid


# ===========================================================================
# Known Error Codes
# ===========================================================================


class TestKnownErrorCodes:
    """Test identification of known OmniRoute error codes."""

    @pytest.fixture
    def validator(self) -> SchemaValidator:
        return SchemaValidator(str(REFERENCES_DIR))

    @pytest.mark.parametrize(
        "code",
        [
            "INVALID_INPUT",
            "INVALID_PROFILE",
            "INVALID_CACHE_MODE",
            "CACHE_KEY_REQUIRED",
            "CONFIG_MISSING",
            "GATEWAY_UNREACHABLE",
        ],
    )
    def test_known_error_codes(self, validator: SchemaValidator, code: str):
        assert validator.is_known_error_code(code)

    def test_unknown_error_code(self, validator: SchemaValidator):
        assert not validator.is_known_error_code("UNKNOWN_ERROR")

    def test_empty_error_code(self, validator: SchemaValidator):
        assert not validator.is_known_error_code("")
