"""Security-enforcing facade for all OmniRoute MCP delegation."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .contracts import AuditContract, DelegationTask, ExecutionState, ToolContract
from .exceptions import CredentialLeakPreventedError, SchemaViolationError
from .mcp_client import MCPClient
from .task_builder import TaskBuilder


class DelegationGateway:
    """Single trust boundary for delegation.

    Callers never invoke the MCP tool directly. This facade owns task
    construction, credential scanning, schema validation, and dispatch.
    """

    TOOL_NAME = "delegar_tarefa"

    def __init__(
        self,
        client: MCPClient,
        task_builder: Optional[TaskBuilder] = None,
    ) -> None:
        self._client = client
        self._task_builder = task_builder or TaskBuilder()

    def _ensure_ready(self) -> None:
        if not self._client.session.is_initialized:
            self._client.initialize()
        if not self._client.session.tools:
            self._client.discover_tools()
        if not self._client.session.has_tool(self.TOOL_NAME):
            raise SchemaViolationError(
                f"Required MCP tool '{self.TOOL_NAME}' was not discovered."
            )

    def _scan(self, payload: Dict[str, Any]) -> None:
        findings = []
        for field_name, value in payload.items():
            if isinstance(value, str):
                result = self._task_builder.scan_for_credentials(value)
                findings.extend(
                    f"{field_name}: {finding}" for finding in result.findings
                )
        if findings:
            raise CredentialLeakPreventedError(findings)

    def build_task(self, task: DelegationTask) -> Dict[str, Any]:
        """Validate and convert an internal task to the MCP wire contract."""
        payload = task.to_wire()
        self._scan(payload)
        validation = self._client.validate_tool_params(self.TOOL_NAME, payload)
        if validation:
            raise SchemaViolationError("; ".join(validation))
        return payload

    def delegate(self, task: DelegationTask) -> Any:
        """Execute a stateless L3T delegation through every trust invariant."""
        self._ensure_ready()
        payload = self.build_task(task)
        return self._client.call_tool(self.TOOL_NAME, payload)

    def delegate_with_audit_state(self, task: DelegationTask) -> AuditContract:
        """Return an explicit execution state around one delegation attempt."""
        try:
            result = self.delegate(task)
            return AuditContract(
                state=ExecutionState.SUCCESS,
                findings=[],
                raw_errors=[],
                attempts=1,
            )
        except SchemaViolationError as exc:
            return AuditContract(
                state=ExecutionState.SCHEMA_VIOLATION,
                raw_errors=[{"type": type(exc).__name__, "message": str(exc)}],
                attempts=1,
            )
