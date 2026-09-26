"""Tests for the task builder — construction, security, and delegation decisions.

Tests cover:
- Fluent API task construction
- Five-section task template validation
- Credential scanning (API keys, tokens, passwords, SSH keys)
- Cache key computation
- Delegation decision gate logic
- Validation of cache constraints
- Input validation (empty fields, invalid values)
"""

from __future__ import annotations

import pytest

from omniroute_delegation.task_builder import (
    OBSERVED_PROFILES,
    VALID_CACHE_MODES,
    TaskBuilder,
)

# ===========================================================================
# Task Construction
# ===========================================================================


class TestTaskConstruction:
    """Test fluent API task building."""

    def test_minimal_task(self):
        task = TaskBuilder().objetivo("Analyze code").restricoes("Do not execute").build()
        assert "task" in task
        assert "Objective: Analyze code" in task["task"]
        assert "Constraints: Do not execute" in task["task"]

    def test_full_task(self):
        task = (
            TaskBuilder()
            .objetivo("Review function")
            .restricoes("Read-only analysis")
            .contexto("def foo(): pass")
            .formato("Bullet list")
            .criterios("All issues found")
            .perfil("coding")
            .task_id("task-001")
            .cache_mode("native")
            .max_tokens(500)
            .temperature(0)
            .build()
        )
        assert task["task"].startswith("Objective: Review function")
        assert task["profile"] == "coding"
        assert task["task_id"] == "task-001"
        assert task["cache_mode"] == "native"
        assert task["max_tokens"] == 500
        assert task["temperature"] == 0

    def test_five_sections_present(self):
        task = (
            TaskBuilder()
            .objetivo("Test")
            .restricoes("None")
            .contexto("Context here")
            .formato("JSON")
            .criterios("Correct")
            .build()
        )
        task = task["task"]
        assert "Objective:" in task
        assert "Constraints:" in task
        assert "Context:" in task
        assert "Expected format:" in task
        assert "Success criteria:" in task

    def test_default_contexto(self):
        task = TaskBuilder().objetivo("Test").restricoes("None").build()
        assert "Nenhum contexto adicional" in task["task"]

    def test_default_formato(self):
        task = TaskBuilder().objetivo("Test").restricoes("None").build()
        assert "Texto livre" in task["task"]

    def test_default_criterios(self):
        task = TaskBuilder().objetivo("Test").restricoes("None").build()
        assert "Resposta correta e completa" in task["task"]

    def test_contexto_only_added_when_nonempty(self):
        task = TaskBuilder().objetivo("Test").restricoes("None").build()
        # contexto key should not be in params since _contexto is empty
        assert "context" not in task

    def test_contexto_added_when_set(self):
        task = TaskBuilder().objetivo("Test").restricoes("None").contexto("Some code").build()
        assert task["context"] == "Some code"

    def test_optional_params_excluded_when_none(self):
        task = TaskBuilder().objetivo("Test").restricoes("None").build()
        assert "profile" not in task
        assert "task_id" not in task
        assert "session_id" not in task
        assert "cache_mode" not in task
        assert "cache_key" not in task
        assert "max_tokens" not in task
        assert "temperature" not in task


# ===========================================================================
# Input Validation
# ===========================================================================


class TestInputValidation:
    """Test input validation and error cases."""

    def test_missing_objetivo(self):
        with pytest.raises(ValueError, match="objetivo"):
            TaskBuilder().restricoes("None").build()

    def test_missing_restricoes(self):
        with pytest.raises(ValueError, match="restricoes"):
            TaskBuilder().objetivo("Test").build()

    def test_invalid_cache_mode(self):
        with pytest.raises(ValueError, match="cache_mode"):
            TaskBuilder().cache_mode("invalid")

    def test_negative_max_tokens(self):
        with pytest.raises(ValueError, match="max_tokens"):
            TaskBuilder().max_tokens(0)

    def test_temperature_too_high(self):
        with pytest.raises(ValueError, match="temperature"):
            TaskBuilder().temperature(3.0)

    def test_temperature_negative(self):
        with pytest.raises(ValueError, match="temperature"):
            TaskBuilder().temperature(-0.5)


# ===========================================================================
# Cache Constraints
# ===========================================================================


class TestCacheConstraints:
    """Test cache mode and key constraints."""

    def test_deterministic_requires_cache_key(self):
        with pytest.raises(ValueError, match="cache_key"):
            (TaskBuilder().objetivo("Test").restricoes("None").cache_mode("deterministic").build())

    def test_deterministic_with_cache_key(self):
        task = (
            TaskBuilder()
            .objetivo("Test")
            .restricoes("None")
            .cache_mode("deterministic")
            .cache_key("abc123")
            .build()
        )
        assert task["cache_mode"] == "deterministic"
        assert task["cache_key"] == "abc123"

    def test_deterministic_incompatible_with_session_id(self):
        with pytest.raises(ValueError, match="session_id"):
            (
                TaskBuilder()
                .objetivo("Test")
                .restricoes("None")
                .cache_mode("deterministic")
                .cache_key("key123")
                .session_id("sess-001")
                .build()
            )

    def test_native_cache_mode(self):
        task = TaskBuilder().objetivo("Test").restricoes("None").cache_mode("native").build()
        assert task["cache_mode"] == "native"

    def test_bypass_cache_mode(self):
        task = TaskBuilder().objetivo("Test").restricoes("None").cache_mode("bypass").build()
        assert task["cache_mode"] == "bypass"


# ===========================================================================
# Credential Scanning
# ===========================================================================


class TestCredentialScanning:
    """Test security scanning for credentials in context."""

    def test_clean_text(self):
        result = TaskBuilder.scan_for_credentials("def foo(): return 42")
        assert result.is_clean
        assert len(result.findings) == 0

    def test_empty_text(self):
        result = TaskBuilder.scan_for_credentials("")
        assert result.is_clean

    def test_detect_api_key(self):
        result = TaskBuilder.scan_for_credentials("api_key=sk-12345abcdef")
        assert not result.is_clean
        assert len(result.findings) > 0

    def test_detect_password(self):
        result = TaskBuilder.scan_for_credentials("password=mySecret123!")
        assert not result.is_clean

    def test_detect_bearer_token(self):
        result = TaskBuilder.scan_for_credentials("authorization=Bearer eyJhb...")
        assert not result.is_clean

    def test_detect_github_token(self):
        result = TaskBuilder.scan_for_credentials(
            "token: ghp_1234567890abcdefghijklmnopqrstuvwxyz12"
        )
        assert not result.is_clean

    def test_detect_openai_key(self):
        result = TaskBuilder.scan_for_credentials("OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwx")
        assert not result.is_clean

    def test_detect_private_key(self):
        result = TaskBuilder.scan_for_credentials("-----BEGIN RSA PRIVATE KEY-----\nMIIE...")
        assert not result.is_clean

    def test_detect_gcp_key(self):
        result = TaskBuilder.scan_for_credentials("key=AIzaSyA1234567890abcdefghijklmnopqrs123")
        assert not result.is_clean

    def test_build_rejects_credentials(self):
        with pytest.raises(ValueError, match="credential"):
            (
                TaskBuilder()
                .objetivo("Test")
                .restricoes("None")
                .contexto('api_key="q9M2vH7kX4pL8zN3sT6wR1yU5aB8cD2e"')
                .build()
            )

    def test_build_rejects_credentials_in_task_id(self):
        with pytest.raises(ValueError, match="credential"):
            (TaskBuilder().objetivo("Test").restricoes("None").task_id("token=secret123").build())


# ===========================================================================
# Cache Key Computation
# ===========================================================================


class TestCacheKeyComputation:
    """Test deterministic cache key generation."""

    def test_same_inputs_same_key(self):
        key1 = TaskBuilder.compute_cache_key("code", "coding", "v1")
        key2 = TaskBuilder.compute_cache_key("code", "coding", "v1")
        assert key1 == key2

    def test_different_inputs_different_key(self):
        key1 = TaskBuilder.compute_cache_key("code1", "coding", "v1")
        key2 = TaskBuilder.compute_cache_key("code2", "coding", "v1")
        assert key1 != key2

    def test_order_independent(self):
        key1 = TaskBuilder.compute_cache_key("a", "b", "c")
        key2 = TaskBuilder.compute_cache_key("c", "a", "b")
        assert key1 == key2

    def test_key_is_hex_digest(self):
        key = TaskBuilder.compute_cache_key("test")
        assert len(key) == 64  # SHA-256 hex digest
        assert all(c in "0123456789abcdef" for c in key)

    def test_key_has_unambiguous_element_boundaries(self):
        key1 = TaskBuilder.compute_cache_key("ab", "c")
        key2 = TaskBuilder.compute_cache_key("a", "bc")
        assert key1 != key2


# ===========================================================================
# Delegation Decision Gate
# ===========================================================================


class TestDelegationDecision:
    """Test delegation decision logic."""

    def test_simple_local_task(self):
        decision = TaskBuilder.evaluate_delegation(
            is_simple=True,
            needs_only_local_state=True,
            no_benefit_from_second_opinion=True,
        )
        assert not decision.should_delegate
        assert "simple" in decision.reason.lower()

    def test_requires_unavailable_tools(self):
        decision = TaskBuilder.evaluate_delegation(
            requires_unavailable_tools=True,
        )
        assert not decision.should_delegate
        assert "tools" in decision.reason.lower()

    def test_context_unsafe(self):
        decision = TaskBuilder.evaluate_delegation(
            context_cannot_be_sent_safely=True,
        )
        assert not decision.should_delegate

    def test_benefits_from_review(self):
        decision = TaskBuilder.evaluate_delegation(
            benefits_from_review=True,
        )
        assert decision.should_delegate
        assert "review" in decision.reason.lower()

    def test_complex_reasoning(self):
        decision = TaskBuilder.evaluate_delegation(
            complex_reasoning=True,
        )
        assert decision.should_delegate

    def test_code_analysis(self):
        decision = TaskBuilder.evaluate_delegation(
            code_analysis=True,
        )
        assert decision.should_delegate

    def test_tradeoff_analysis(self):
        decision = TaskBuilder.evaluate_delegation(
            tradeoff_analysis=True,
        )
        assert decision.should_delegate

    def test_no_signals(self):
        decision = TaskBuilder.evaluate_delegation()
        assert not decision.should_delegate

    def test_anti_delegation_overrides_pro(self):
        """Anti-delegation conditions like unavailable tools should win."""
        decision = TaskBuilder.evaluate_delegation(
            requires_unavailable_tools=True,
            benefits_from_review=True,
        )
        assert not decision.should_delegate

    def test_context_unsafe_overrides_pro(self):
        decision = TaskBuilder.evaluate_delegation(
            context_cannot_be_sent_safely=True,
            complex_reasoning=True,
        )
        assert not decision.should_delegate


# ===========================================================================
# Constants Verification
# ===========================================================================


class TestConstants:
    """Test that constants match the contract."""

    def test_observed_profiles(self):
        expected = {"cheap", "fast", "coding", "coding:pro", "smart"}
        assert OBSERVED_PROFILES == expected

    def test_valid_cache_modes(self):
        expected = {"native", "bypass", "deterministic"}
        assert VALID_CACHE_MODES == expected

    def test_profiles_preserve_colon(self):
        """Verify 'coding:pro' is not transformed to 'coding_pro'."""
        assert "coding:pro" in OBSERVED_PROFILES
        assert "coding_pro" not in OBSERVED_PROFILES
