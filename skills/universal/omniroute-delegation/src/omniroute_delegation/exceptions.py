"""Typed exceptions for the OmniRoute delegation trust boundary."""

from __future__ import annotations

from typing import Any, Optional


class DelegationError(Exception):
    """Base exception for the delegation skill."""


class MCPError(DelegationError):
    """Base exception for MCP transport and protocol failures."""

    def __init__(
        self,
        message: str,
        code: Optional[int] = None,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.data = data


class MCPTransportError(MCPError):
    """HTTP transport-level failure."""


class MCPProtocolError(MCPError):
    """JSON-RPC protocol-level failure."""


class MCPApplicationError(MCPError):
    """Application-level failure returned by the gateway."""


class GatewayUnreachableError(MCPTransportError):
    """The MCP gateway cannot be reached."""


class SchemaViolationError(MCPProtocolError):
    """A tool or semantic payload violates its declared contract."""


class CredentialLeakPreventedError(DelegationError):
    """A delegation was blocked because sensitive material was detected."""

    def __init__(self, findings: list[str]) -> None:
        self.findings = findings
        super().__init__(
            "Delegation blocked because credential-like material was detected: "
            + ", ".join(findings)
        )


class SemanticCoverageFailedError(DelegationError):
    """Semantic coverage could not be completed after recovery attempts."""

    def __init__(self, result: Any) -> None:
        self.result = result
        state = getattr(result, "state", "UNKNOWN")
        super().__init__(
            f"Semantic coverage failed after recovery attempts; final state={state}."
        )


class SandboxError(DelegationError):
    """Workspace sandbox setup or policy failure."""


class SandboxUnavailableError(SandboxError):
    """A required OS-level sandbox is not available."""


class WorkerManagerError(DelegationError):
    """Base exception for worker lifecycle failures."""


class WorkerTimeoutError(WorkerManagerError):
    """A worker exceeded its configured timeout."""


class WorkerStartupError(WorkerManagerError):
    """A worker watchdog or harness failed to start."""


class MemoryScopeError(DelegationError):
    """Memory scope setup or finalization failure."""
