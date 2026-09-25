"""Task builder for constructing well-formed delegation payloads.

Provides a fluent API for building delegation tasks with proper
structure, context efficiency, and security guardrails.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Known observed profiles — only for reference, always confirm at runtime
OBSERVED_PROFILES = frozenset({"cheap", "fast", "coding", "coding:pro", "smart"})

VALID_CACHE_MODES = frozenset({"native", "bypass", "deterministic"})

# Patterns that suggest credentials in context
_CREDENTIAL_PATTERNS = [
    re.compile(r"(?:api[_-]?key|apikey)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"(?:password|passwd|pwd)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"(?:secret|token)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"(?:bearer|authorization)\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----", re.IGNORECASE),
    re.compile(r"ghp_[A-Za-z0-9]{36,}", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9]{20,}", re.IGNORECASE),
    re.compile(r"AIza[A-Za-z0-9_-]{35}", re.IGNORECASE),
]

# Task template
_TASK_TEMPLATE = """Objetivo: {objective}
Restrições: {constraints}
Contexto: {context}
Formato esperado: {format}
Critérios de sucesso: {criteria}"""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class SecurityScanResult:
    """Result of a security scan on delegation content."""

    is_clean: bool
    findings: List[str] = field(default_factory=list)


@dataclass
class DelegationDecision:
    """Result of the delegation decision gate."""

    should_delegate: bool
    reason: str


# ---------------------------------------------------------------------------
# Task Builder
# ---------------------------------------------------------------------------


class TaskBuilder:
    """Fluent builder for constructing delegation task payloads.

    Enforces the five-section task structure, context efficiency,
    and security guardrails (credential scanning, prompt injection).

    Usage:
        task = (TaskBuilder()
            .objetivo("Analyze the function for edge cases")
            .restricoes("Do not execute code")
            .contexto("def foo(x): return x + 1")
            .formato("Bullet list of edge cases")
            .criterios("All edge cases identified with severity")
            .perfil("coding")
            .temperature(0)
            .build())
    """

    def __init__(self) -> None:
        self._objective: str = ""
        self._constraints: str = ""
        self._context: str = ""
        self._format: str = ""
        self._criteria: str = ""
        self._profile: Optional[str] = None
        self._task_id: Optional[str] = None
        self._session_id: Optional[str] = None
        self._cache_mode: Optional[str] = None
        self._cache_key: Optional[str] = None
        self._max_tokens: Optional[int] = None
        self._temperature: Optional[float] = None

    # -- Fluent setters ----------------------------------------------------

    def objective(self, value: str) -> "TaskBuilder":
        """Set the task objective."""
        self._objective = value
        return self

    def constraints(self, value: str) -> "TaskBuilder":
        """Set the task constraints."""
        self._constraints = value
        return self

    def context(self, value: str) -> "TaskBuilder":
        """Set the task context (treated as untrusted data)."""
        self._context = value
        return self

    def format(self, value: str) -> "TaskBuilder":
        """Set the expected output format."""
        self._format = value
        return self

    def criteria(self, value: str) -> "TaskBuilder":
        """Set the success criteria."""
        self._criteria = value
        return self

    def profile(self, value: str) -> "TaskBuilder":
        """Set the profile/route hint. Must be confirmed against runtime schema."""
        self._profile = value
        return self

    def task_id(self, value: str) -> "TaskBuilder":
        """Set the tracking task ID."""
        self._task_id = value
        return self

    def session_id(self, value: str) -> "TaskBuilder":
        """Set the application-level session ID."""
        self._session_id = value
        return self

    def cache_mode(self, value: str) -> "TaskBuilder":
        """Set the cache mode: native, bypass, or deterministic."""
        if value not in VALID_CACHE_MODES:
            raise ValueError(
                f"Invalid cache_mode '{value}'. Must be one of: {sorted(VALID_CACHE_MODES)}"
            )
        self._cache_mode = value
        return self

    def cache_key(self, value: str) -> "TaskBuilder":
        """Set the deterministic cache key."""
        self._cache_key = value
        return self

    def max_tokens(self, value: int) -> "TaskBuilder":
        """Set the maximum tokens for the leaf response."""
        if value < 1:
            raise ValueError("max_tokens must be >= 1")
        self._max_tokens = value
        return self

    def temperature(self, value: float) -> "TaskBuilder":
        """Set the sampling temperature (0 for deterministic)."""
        if value < 0 or value > 2:
            raise ValueError("temperature must be between 0 and 2")
        self._temperature = value
        return self

    # -- Build -------------------------------------------------------------

    def build(self) -> Dict[str, Any]:
        """Build the delegation task payload.

        Returns:
            Dict ready to be passed as arguments to tools/call.

        Raises:
            ValueError: If required fields are missing or security violations detected.
        """
        # Validate required fields
        if not self._objective.strip():
            raise ValueError("'objetivo' is required for every delegation task.")
        if not self._constraints.strip():
            raise ValueError("'restricoes' is required for every delegation task.")

        # Build tarefa string
        task = _TASK_TEMPLATE.format(
            objective=self._objective,
            constraints=self._constraints,
            context=self._context or "Nenhum contexto adicional.",
            format=self._format or "Texto livre.",
            criteria=self._criteria or "Resposta correta e completa.",
        )

        # Build params
        params: Dict[str, Any] = {"task": task}

        if self._profile is not None:
            params["profile"] = self._profile
        if self._context:
            params["context"] = self._context
        if self._task_id is not None:
            params["task_id"] = self._task_id
        if self._session_id is not None:
            params["session_id"] = self._session_id
        if self._cache_mode is not None:
            params["cache_mode"] = self._cache_mode
        if self._cache_key is not None:
            params["cache_key"] = self._cache_key
        if self._max_tokens is not None:
            params["max_tokens"] = self._max_tokens
        if self._temperature is not None:
            params["temperature"] = self._temperature

        findings: List[str] = []
        for field_name, value in params.items():
            if isinstance(value, str):
                scan = self.scan_for_credentials(value)
                if not scan.is_clean and True:
                    findings.extend(f"{field_name}: {finding}" for finding in scan.findings)
        if findings:
            raise ValueError(
                "Security violation: potential credentials detected in delegation payload. "
                f"Findings: {findings}"
            )

        # Validate cache constraints
        if self._cache_mode == "deterministic":
            if not self._cache_key:
                raise ValueError("cache_mode='deterministic' requires a 'cache_key'.")
            if self._session_id:
                raise ValueError("cache_mode='deterministic' is incompatible with 'session_id'.")

        return params

    # -- Utility methods ---------------------------------------------------

    @staticmethod
    def scan_for_credentials(text: str) -> SecurityScanResult:
        """Scan text for potential credential patterns.

        Args:
            text: The text content to scan.

        Returns:
            SecurityScanResult indicating if the text is clean.
        """
        if not text:
            return SecurityScanResult(is_clean=True)

        findings: List[str] = []
        for pattern in _CREDENTIAL_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                # Don't include the actual credential in the finding
                findings.append(f"Potential credential pattern detected: {pattern.pattern}")

        return SecurityScanResult(
            is_clean=len(findings) == 0,
            findings=findings,
        )

    @staticmethod
    def compute_cache_key(*elements: str) -> str:
        """Compute a deterministic cache key from semantic elements.

        All elements that affect the output should be included:
        code content, profile, version, parameters, etc.

        Args:
            *elements: String elements to hash together.

        Returns:
            A SHA-256 hex digest string.
        """
        hasher = hashlib.sha256()
        canonical_elements = json.dumps(
            sorted(elements), ensure_ascii=False, separators=(",", ":")
        )
        hasher.update(canonical_elements.encode("utf-8"))
        return hasher.hexdigest()

    @staticmethod
    def evaluate_delegation(
        is_simple: bool = False,
        needs_only_local_state: bool = False,
        no_benefit_from_second_opinion: bool = False,
        requires_unavailable_tools: bool = False,
        context_cannot_be_sent_safely: bool = False,
        benefits_from_review: bool = False,
        complex_reasoning: bool = False,
        code_analysis: bool = False,
        tradeoff_analysis: bool = False,
    ) -> DelegationDecision:
        """Evaluate whether delegation should be used.

        Implements the delegation decision gate from the contract.

        Returns:
            DelegationDecision with should_delegate and reason.
        """
        # Anti-delegation conditions (resolve locally)
        if requires_unavailable_tools:
            return DelegationDecision(
                should_delegate=False,
                reason="Task requires tools the leaf does not possess.",
            )
        if context_cannot_be_sent_safely:
            return DelegationDecision(
                should_delegate=False,
                reason="Context cannot be sent safely to a leaf agent.",
            )
        if is_simple and needs_only_local_state and no_benefit_from_second_opinion:
            return DelegationDecision(
                should_delegate=False,
                reason="Simple task with local state and no benefit from delegation.",
            )

        # Pro-delegation conditions
        if benefits_from_review:
            return DelegationDecision(
                should_delegate=True,
                reason="Task benefits from independent review or second opinion.",
            )
        if complex_reasoning:
            return DelegationDecision(
                should_delegate=True,
                reason="Task involves complex reasoning or debugging.",
            )
        if code_analysis:
            return DelegationDecision(
                should_delegate=True,
                reason="Task involves code analysis or synthesis.",
            )
        if tradeoff_analysis:
            return DelegationDecision(
                should_delegate=True,
                reason="Task involves comparison of alternatives or trade-off analysis.",
            )

        # Default: resolve locally
        return DelegationDecision(
            should_delegate=False,
            reason="No clear benefit from delegation identified.",
        )
