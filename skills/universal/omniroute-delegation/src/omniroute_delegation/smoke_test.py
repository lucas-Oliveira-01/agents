#!/usr/bin/env python3
"""OmniRoute Delegation — Smoke Test Diagnostic.

A standalone diagnostic script that validates connectivity and contract
conformance of the OmniRoute MCP gateway.

Usage:
    # Using default endpoint (http://127.0.0.1:20130/mcp)
    python -m omniroute_delegation.smoke_test

    # Using custom endpoint
    OMNIROUTE_MCP_URL=http://myhost:8080/mcp python -m omniroute_delegation.smoke_test

    # Or via installed entry point
    omniroute-smoke
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from omniroute_delegation.mcp_client import (
    GatewayUnreachableError,
    MCPApplicationError,
    MCPClient,
    MCPTransportError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Known tools from the contract (for reference only)
EXPECTED_TOOLS = [
    "delegate_task",
    "query_delegation",
    "delegation_summary",
    "query_cache",
    "invalidate_cache",
]


class StepStatus(str, Enum):
    PASS = "PASS"  # nosec B105
    FAIL = "FAIL"
    WARN = "WARN"
    SKIP = "SKIP"


@dataclass
class StepResult:
    name: str
    status: StepStatus
    message: str
    duration_ms: float = 0.0
    details: Optional[Dict[str, Any]] = None


@dataclass
class SmokeTestReport:
    endpoint: str
    health_endpoint: str
    timestamp: str = ""
    steps: List[StepResult] = field(default_factory=list)
    overall_status: StepStatus = StepStatus.PASS

    def add(self, result: StepResult) -> None:
        self.steps.append(result)
        if result.status == StepStatus.FAIL:
            self.overall_status = StepStatus.FAIL
        elif result.status == StepStatus.WARN and self.overall_status != StepStatus.FAIL:
            self.overall_status = StepStatus.WARN


# ---------------------------------------------------------------------------
# Smoke Test Runner
# ---------------------------------------------------------------------------


class SmokeTestRunner:
    """Executes the OmniRoute MCP smoke test diagnostic.

    Validates:
    1. Health endpoint connectivity
    2. MCP initialize handshake and session ID
    3. tools/list discovery and schema validation
    4. Minimal delegation task (if tools are available)
    5. Error handling verification
    """

    def __init__(self, client: Optional[MCPClient] = None):
        self._client = client or MCPClient()
        self._report = SmokeTestReport(
            endpoint=self._client.mcp_url,
            health_endpoint=self._client.health_url,
        )

    @property
    def report(self) -> SmokeTestReport:
        return self._report

    def run(self) -> SmokeTestReport:
        """Execute all smoke test steps.

        Returns:
            SmokeTestReport with results of each step.
        """
        import datetime

        self._report.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        self._step_health_check()
        self._step_initialize()
        self._step_discover_tools()
        self._step_validate_expected_tools()
        self._step_validate_tool_schemas()
        self._step_minimal_delegation()

        return self._report

    def _timed(self, func: Any) -> tuple:
        """Execute a function and return (result, duration_ms)."""
        start = time.monotonic()
        try:
            result = func()
            duration = (time.monotonic() - start) * 1000
            return result, duration
        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            raise _TimedError(exc, duration) from exc

    # -- Steps -------------------------------------------------------------

    def _step_health_check(self) -> None:
        """Step 1: Health endpoint connectivity."""
        try:
            result, duration = self._timed(self._client.health_check)
            self._report.add(
                StepResult(
                    name="health_check",
                    status=StepStatus.PASS,
                    message=f"Health endpoint reachable at {self._client.health_url}",
                    duration_ms=duration,
                    details=result if isinstance(result, dict) else {"raw": str(result)},
                )
            )
        except _TimedError as exc:
            if isinstance(exc.original, GatewayUnreachableError):
                self._report.add(
                    StepResult(
                        name="health_check",
                        status=StepStatus.FAIL,
                        message=f"Gateway unreachable: {exc.original}",
                        duration_ms=exc.duration_ms,
                    )
                )
            elif isinstance(exc.original, MCPTransportError):
                self._report.add(
                    StepResult(
                        name="health_check",
                        status=StepStatus.WARN,
                        message=f"Health endpoint returned error: {exc.original}",
                        duration_ms=exc.duration_ms,
                    )
                )
            else:
                self._report.add(
                    StepResult(
                        name="health_check",
                        status=StepStatus.FAIL,
                        message=f"Unexpected error: {exc.original}",
                        duration_ms=exc.duration_ms,
                    )
                )

    def _step_initialize(self) -> None:
        """Step 2: MCP initialize handshake."""
        try:
            session, duration = self._timed(self._client.initialize)
            details: Dict[str, Any] = {
                "protocol_version": session.protocol_version,
                "session_id": session.session_id,
                "server_info": session.server_info,
            }

            if not session.session_id:
                self._report.add(
                    StepResult(
                        name="initialize",
                        status=StepStatus.WARN,
                        message="Initialize succeeded but no mcp-session-id returned.",
                        duration_ms=duration,
                        details=details,
                    )
                )
            else:
                self._report.add(
                    StepResult(
                        name="initialize",
                        status=StepStatus.PASS,
                        message=f"Session initialized. Protocol: {session.protocol_version}",
                        duration_ms=duration,
                        details=details,
                    )
                )
        except _TimedError as exc:
            self._report.add(
                StepResult(
                    name="initialize",
                    status=StepStatus.FAIL,
                    message=f"Initialize failed: {exc.original}",
                    duration_ms=exc.duration_ms,
                )
            )
        except Exception as exc:
            self._report.add(
                StepResult(
                    name="initialize",
                    status=StepStatus.FAIL,
                    message=f"Initialize failed: {exc}",
                )
            )

    def _step_discover_tools(self) -> None:
        """Step 3: Execute tools/list."""
        if not self._client.session.is_initialized:
            self._report.add(
                StepResult(
                    name="discover_tools",
                    status=StepStatus.SKIP,
                    message="Skipped: session not initialized.",
                )
            )
            return

        try:
            tools, duration = self._timed(self._client.discover_tools)
            tool_names = list(tools.keys())
            self._report.add(
                StepResult(
                    name="discover_tools",
                    status=StepStatus.PASS,
                    message=f"Discovered {len(tools)} tools: {tool_names}",
                    duration_ms=duration,
                    details={"tool_count": len(tools), "tool_names": tool_names},
                )
            )
        except _TimedError as exc:
            self._report.add(
                StepResult(
                    name="discover_tools",
                    status=StepStatus.FAIL,
                    message=f"tools/list failed: {exc.original}",
                    duration_ms=exc.duration_ms,
                )
            )
        except Exception as exc:
            self._report.add(
                StepResult(
                    name="discover_tools",
                    status=StepStatus.FAIL,
                    message=f"tools/list failed: {exc}",
                )
            )

    def _step_validate_expected_tools(self) -> None:
        """Step 4: Check for expected tools (informational)."""
        tools = self._client.session.tools
        if not tools:
            self._report.add(
                StepResult(
                    name="validate_expected_tools",
                    status=StepStatus.SKIP,
                    message="Skipped: no tools discovered.",
                )
            )
            return

        found = [t for t in EXPECTED_TOOLS if t in tools]
        missing = [t for t in EXPECTED_TOOLS if t not in tools]
        extra = [t for t in tools if t not in EXPECTED_TOOLS]

        if missing:
            self._report.add(
                StepResult(
                    name="validate_expected_tools",
                    status=StepStatus.WARN,
                    message=(
                        f"Some expected tools not found: {missing}. "
                        f"This is informational; the runtime contract prevails."
                    ),
                    details={"found": found, "missing": missing, "extra": extra},
                )
            )
        else:
            self._report.add(
                StepResult(
                    name="validate_expected_tools",
                    status=StepStatus.PASS,
                    message=f"All expected tools found: {found}",
                    details={"found": found, "extra": extra},
                )
            )

    def _step_validate_tool_schemas(self) -> None:
        """Step 5: Validate tool schemas have expected structure."""
        tools = self._client.session.tools
        if not tools:
            self._report.add(
                StepResult(
                    name="validate_tool_schemas",
                    status=StepStatus.SKIP,
                    message="Skipped: no tools discovered.",
                )
            )
            return

        issues: List[str] = []
        for name, tool in tools.items():
            if not tool.input_schema:
                issues.append(f"Tool '{name}' has no inputSchema.")
            if not tool.name:
                issues.append("Tool entry has empty name.")

        if issues:
            self._report.add(
                StepResult(
                    name="validate_tool_schemas",
                    status=StepStatus.WARN,
                    message=f"Schema issues: {issues}",
                    details={"issues": issues},
                )
            )
        else:
            self._report.add(
                StepResult(
                    name="validate_tool_schemas",
                    status=StepStatus.PASS,
                    message=f"All {len(tools)} tool schemas valid.",
                )
            )

    def _step_minimal_delegation(self) -> None:
        """Step 6: Execute a minimal delegation to prove the circuit."""
        if not self._client.session.has_tool("delegate_task"):
            self._report.add(
                StepResult(
                    name="minimal_delegation",
                    status=StepStatus.SKIP,
                    message="Skipped: 'delegate_task' tool not available.",
                )
            )
            return

        task_text = (
            "Objective: Confirmar conectividade e funcionamento básico.\n"
            "Constraints: Responda apenas com a frase exata solicitada.\n"
            "Context: Este é um smoke test de diagnóstico.\n"
            "Expected format: Texto puro, uma linha.\n"
            "Success criteria: Resposta contém a frase 'SMOKE_OK'."
        )

        # Build minimal arguments — only include params confirmed by schema
        tool = self._client.session.get_tool("delegate_task")
        args: Dict[str, Any] = {"task": task_text}

        # Only add perfil if the tool accepts it
        if tool and tool.accepts_param("profile"):
            args["profile"] = "cheap"

        # Only add cache_mode if accepted
        if tool and tool.accepts_param("cache_mode"):
            args["cache_mode"] = "bypass"

        try:
            result, duration = self._timed(lambda: self._client.call_tool("delegate_task", args))
            if not self._has_smoke_success(result):
                self._report.add(
                    StepResult(
                        name="minimal_delegation",
                        status=StepStatus.FAIL,
                        message="Delegation returned no valid SMOKE_OK result.",
                        duration_ms=duration,
                        details={"result_preview": str(result)[:500] if result else None},
                    )
                )
                return
            self._report.add(
                StepResult(
                    name="minimal_delegation",
                    status=StepStatus.PASS,
                    message="Minimal delegation completed successfully.",
                    duration_ms=duration,
                    details={"result_preview": str(result)[:500] if result else None},
                )
            )
        except MCPApplicationError as exc:
            self._report.add(
                StepResult(
                    name="minimal_delegation",
                    status=StepStatus.WARN,
                    message=f"Delegation returned application error: {exc}",
                    details={"error_code": exc.code, "error_data": exc.data},
                )
            )
        except _TimedError as exc:
            self._report.add(
                StepResult(
                    name="minimal_delegation",
                    status=StepStatus.FAIL,
                    message=f"Delegation failed: {exc.original}",
                    duration_ms=exc.duration_ms,
                )
            )
        except Exception as exc:
            self._report.add(
                StepResult(
                    name="minimal_delegation",
                    status=StepStatus.FAIL,
                    message=f"Delegation failed: {exc}",
                )
            )

    @staticmethod
    def _has_smoke_success(result: Any) -> bool:
        """Require the expected semantic marker in the tool result."""
        if not isinstance(result, dict):
            return False
        content = result.get("content")
        if not isinstance(content, list):
            return False
        return any(
            isinstance(item, dict)
            and item.get("type") == "text"
            and "SMOKE_OK" in item.get("text", "")
            for item in content
        )


class _TimedError(Exception):
    """Internal wrapper to carry timing info with exceptions."""

    def __init__(self, original: Exception, duration_ms: float):
        super().__init__(str(original))
        self.original = original
        self.duration_ms = duration_ms


# ---------------------------------------------------------------------------
# CLI / Main
# ---------------------------------------------------------------------------


def format_report(report: SmokeTestReport) -> str:
    """Format a smoke test report for terminal output."""
    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("OmniRoute Delegation — Smoke Test Report")
    lines.append("=" * 60)
    lines.append(f"  Endpoint:  {report.endpoint}")
    lines.append(f"  Health:    {report.health_endpoint}")
    lines.append(f"  Timestamp: {report.timestamp}")
    lines.append(f"  Overall:   {report.overall_status.value}")
    lines.append("-" * 60)

    for step in report.steps:
        status_icon = {
            StepStatus.PASS: "✅",
            StepStatus.FAIL: "❌",
            StepStatus.WARN: "⚠️",
            StepStatus.SKIP: "⏭️",
        }.get(step.status, "?")

        timing = f" ({step.duration_ms:.0f}ms)" if step.duration_ms > 0 else ""
        lines.append(f"  {status_icon} [{step.status.value}] {step.name}{timing}")
        lines.append(f"       {step.message}")
        if step.details:
            for key, value in step.details.items():
                val_str = str(value)
                if len(val_str) > 100:
                    val_str = val_str[:100] + "..."
                lines.append(f"         {key}: {val_str}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def main() -> None:
    """Entry point for the smoke test CLI."""
    print("OmniRoute Delegation — Smoke Test")
    print(f"  Endpoint: {os.environ.get('OMNIROUTE_MCP_URL', 'default')}")
    print()

    with MCPClient() as client:
        runner = SmokeTestRunner(client)
        report = runner.run()

    print(format_report(report))

    # Exit with appropriate code
    if report.overall_status == StepStatus.FAIL:
        sys.exit(1)
    elif report.overall_status == StepStatus.WARN:
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
