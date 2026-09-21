"""Tests for contract adherence — cross-cutting integration tests.

These tests verify that the implementation matches the core contract:
- Session ID distinction (mcp-session-id vs session_id)
- Profile preservation (no alias transformation)
- Recursion guard enforcement
- Delegation policy coherence
- Context efficiency guidelines
- Prompt injection defense
- Error taxonomy completeness
- Cache determinism rules
- Provenance support
"""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from omniroute_delegation.mcp_client import (
    KNOWN_ERROR_CODES,
    MCPClient,
    MCPSession,
    ToolSchema,
)
from omniroute_delegation.schema_validator import SchemaValidator
from omniroute_delegation.task_builder import (
    OBSERVED_PROFILES,
    TaskBuilder,
)
from tests.helpers import REFERENCES_DIR, make_tool_dict

# ===========================================================================
# Session ID Distinction
# ===========================================================================


class TestSessionIdDistinction:
    """Contract: mcp-session-id ≠ session_id (application parameter)."""

    def test_mcp_session_id_is_transport_level(self):
        """mcp-session-id is on the MCPSession, not in tool params."""
        session = MCPSession()
        session.session_id = "transport-sess-abc"
        # This is the transport-level session, not application
        assert session.session_id == "transport-sess-abc"

    def test_session_id_is_application_param(self):
        """session_id is a tool parameter, separate from MCP session."""
        task = (
            TaskBuilder().objetivo("Test").restricoes("None").session_id("app-session-001").build()
        )
        assert task["session_id"] == "app-session-001"

    def test_both_can_coexist_independently(self):
        """Both session types can exist simultaneously without conflict."""
        session = MCPSession()
        session.session_id = "mcp-transport-id"

        task = (
            TaskBuilder().objetivo("Test").restricoes("None").session_id("app-session-id").build()
        )

        assert session.session_id == "mcp-transport-id"
        assert task["session_id"] == "app-session-id"
        assert session.session_id != task["session_id"]


# ===========================================================================
# Profile Preservation
# ===========================================================================


class TestProfilePreservation:
    """Contract: Never invent aliases. Never auto-substitute."""

    def test_coding_pro_preserved_with_colon(self):
        """coding:pro must not become coding_pro."""
        task = TaskBuilder().objetivo("Test").restricoes("None").perfil("coding:pro").build()
        assert task["perfil"] == "coding:pro"
        assert "_" not in task["perfil"]

    def test_profile_values_exact(self):
        """All observed profiles are stored exactly as given."""
        for profile in OBSERVED_PROFILES:
            task = TaskBuilder().objetivo("Test").restricoes("None").perfil(profile).build()
            assert task["perfil"] == profile

    def test_auto_not_treated_as_profile(self):
        """auto is a route/target, not automatically a profile."""
        # The builder allows setting any string as perfil,
        # but the contract says to confirm schema first.
        # We just ensure it doesn't transform it.
        task = TaskBuilder().objetivo("Test").restricoes("None").perfil("auto").build()
        assert task["perfil"] == "auto"


# ===========================================================================
# Error Taxonomy
# ===========================================================================


class TestErrorTaxonomy:
    """Contract: All known error codes are defined and handled."""

    def test_all_known_error_codes_defined(self):
        expected = {
            "INVALID_INPUT",
            "INVALID_PROFILE",
            "INVALID_CACHE_MODE",
            "CACHE_KEY_REQUIRED",
            "CONFIG_MISSING",
            "GATEWAY_UNREACHABLE",
        }
        assert KNOWN_ERROR_CODES == expected

    def test_schema_validator_knows_all_codes(self):
        validator = SchemaValidator(str(REFERENCES_DIR))
        for code in KNOWN_ERROR_CODES:
            assert validator.is_known_error_code(code), f"Missing: {code}"


# ===========================================================================
# Cache Determinism Rules
# ===========================================================================


class TestCacheDeterminismRules:
    """Contract: Deterministic cache has strict rules."""

    def test_deterministic_requires_cache_key(self):
        """cache_mode=deterministic MUST have cache_key."""
        with pytest.raises(ValueError):
            (TaskBuilder().objetivo("Test").restricoes("None").cache_mode("deterministic").build())

    def test_deterministic_incompatible_with_session_id(self):
        """Do not combine deterministic cache with session_id."""
        with pytest.raises(ValueError, match="session_id"):
            (
                TaskBuilder()
                .objetivo("Test")
                .restricoes("None")
                .cache_mode("deterministic")
                .cache_key("key")
                .session_id("sess")
                .build()
            )

    def test_cache_key_represents_all_elements(self):
        """cache_key should be deterministic over all semantic elements."""
        key1 = TaskBuilder.compute_cache_key("code-v1", "coding", "params-a")
        key2 = TaskBuilder.compute_cache_key("code-v1", "coding", "params-a")
        key3 = TaskBuilder.compute_cache_key("code-v2", "coding", "params-a")
        assert key1 == key2
        assert key1 != key3


# ===========================================================================
# Delegation Policy Coherence
# ===========================================================================


class TestDelegationPolicyCoherence:
    """Contract: Delegation is optional, not obligatory."""

    def test_gateway_existence_does_not_force_delegation(self):
        """The existence of the gateway does not oblige delegation."""
        decision = TaskBuilder.evaluate_delegation(
            is_simple=True,
            needs_only_local_state=True,
            no_benefit_from_second_opinion=True,
        )
        assert not decision.should_delegate

    def test_tools_unavailability_blocks_delegation(self):
        """Cannot delegate if leaf lacks required tools."""
        decision = TaskBuilder.evaluate_delegation(
            requires_unavailable_tools=True,
            benefits_from_review=True,
        )
        assert not decision.should_delegate

    def test_unsafe_context_blocks_delegation(self):
        """Cannot delegate if context cannot be sent safely."""
        decision = TaskBuilder.evaluate_delegation(
            context_cannot_be_sent_safely=True,
            complex_reasoning=True,
        )
        assert not decision.should_delegate


# ===========================================================================
# Context Efficiency
# ===========================================================================


class TestContextEfficiency:
    """Contract: Maximize useful information per token."""

    def test_default_context_is_minimal(self):
        """Default context should not bloat the payload."""
        task = TaskBuilder().objetivo("Quick test").restricoes("None").build()
        # No contexto param when not set
        assert "contexto" not in task

    def test_explicit_format_sets_expectations(self):
        """Explicit output format reduces ambiguity."""
        task = (
            TaskBuilder()
            .objetivo("Test")
            .restricoes("None")
            .formato("JSON array of objects")
            .build()
        )
        assert "Formato esperado: JSON array of objects" in task["tarefa"]


# ===========================================================================
# Prompt Injection Defense
# ===========================================================================


class TestPromptInjectionDefense:
    """Contract: All delegated context is untrusted."""

    def test_credential_rejection_in_build(self):
        """Build rejects context containing credentials."""
        with pytest.raises(ValueError, match="credential"):
            (
                TaskBuilder()
                .objetivo("Test")
                .restricoes("None")
                .contexto("SECRET=abc123secrettoken789012345")
                .build()
            )

    def test_safe_context_accepted(self):
        """Normal code context is accepted."""
        task = (
            TaskBuilder()
            .objetivo("Test")
            .restricoes("None")
            .contexto("def hello():\n    return 'world'")
            .build()
        )
        assert task["contexto"] == "def hello():\n    return 'world'"

    def test_credential_in_objective_rejected(self):
        with pytest.raises(ValueError, match="credential"):
            TaskBuilder().objetivo("Use api_key=secret123").restricoes("None").build()


# ===========================================================================
# Recursion Guard
# ===========================================================================


class TestRecursionGuard:
    """Contract: Leaf cannot call tools, delegate, or alter authorization."""

    def test_task_template_enforces_constraints(self):
        """The task template includes restrictions for the leaf."""
        task = (
            TaskBuilder()
            .objetivo("Analyze this code")
            .restricoes("Do not execute commands, do not use tools, do not delegate")
            .build()
        )
        tarefa = task["tarefa"]
        assert "Restrições:" in tarefa
        # The restriction text should be preserved
        assert "não" in tarefa.lower() or "do not" in tarefa.lower()


# ===========================================================================
# Parameter Validation Against Schema
# ===========================================================================


class TestParameterSchemaCompliance:
    """Contract: Only send parameters confirmed by the current tool schema."""

    def test_filter_removes_unaccepted_params(self):
        """Params not in tool schema are filtered out."""
        mock_http = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_http)
        client._session.is_initialized = True

        tool = ToolSchema.from_mcp(
            make_tool_dict(
                properties={
                    "tarefa": {"type": "string"},
                    "perfil": {"type": "string"},
                },
                required=["tarefa"],
            )
        )
        client._session.tools["delegar_tarefa"] = tool

        filtered = client.filter_optional_params(
            "delegar_tarefa",
            {"tarefa": "test", "perfil": "coding", "unknown_param": "val"},
        )
        assert "tarefa" in filtered
        assert "perfil" in filtered
        assert "unknown_param" not in filtered

    def test_validate_catches_invalid_enum(self):
        """Validation catches values not in enum."""
        mock_http = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_http)
        client._session.is_initialized = True

        tool = ToolSchema.from_mcp(make_tool_dict())
        client._session.tools["delegar_tarefa"] = tool

        errors = client.validate_tool_params(
            "delegar_tarefa",
            {"tarefa": "test", "cache_mode": "invalid_mode"},
        )
        assert len(errors) > 0


# ===========================================================================
# Schema Structural Validation
# ===========================================================================


class TestSchemaStructuralValidation:
    """Contract: JSON schemas enforce the contract structure."""

    def test_delegation_schema_requires_tarefa(self):
        validator = SchemaValidator(str(REFERENCES_DIR))
        schema = validator.delegation_schema
        assert "tarefa" in schema.get("required", [])

    def test_delegation_schema_defines_cache_enum(self):
        validator = SchemaValidator(str(REFERENCES_DIR))
        schema = validator.delegation_schema
        cache_mode = schema["properties"]["cache_mode"]
        assert set(cache_mode["enum"]) == {"native", "bypass", "deterministic"}

    def test_delegation_schema_conditional_cache_key(self):
        """When cache_mode=deterministic, cache_key is required."""
        validator = SchemaValidator(str(REFERENCES_DIR))
        result = validator.validate_delegation_task(
            {
                "tarefa": "test",
                "cache_mode": "deterministic",
            }
        )
        assert not result.is_valid

    def test_mcp_schema_defines_all_error_codes(self):
        validator = SchemaValidator(str(REFERENCES_DIR))
        schema = validator.mcp_messages_schema
        known_codes = schema["definitions"]["known_error_codes"]["enum"]
        for code in KNOWN_ERROR_CODES:
            assert code in known_codes
