"""
test_omniroute_backend.py — Tests for OmniRoute Integration

Ensures the translation of MCP tool results into DelegationResult works correctly.
"""

import json

from project_audit.delegation import DelegationRequest, DelegationStatus
from project_audit.omniroute_backend import MCPOmniRouteBackend
from project_audit.models import ExecutionPolicy, FilesystemAccess, NetworkAccess, CredentialAccess


def test_omniroute_backend_success_with_json_output():
    """Validates successful MCP call parsing and metadata extraction."""
    def mock_mcp_client(server, tool, args):
        assert server == "omnirouter"
        assert tool == "delegar_tarefa"
        assert "fs:read-only" in args["required_capabilities"]

        # Simulate MCP JSON output embedded in a text block
        output = {
            "findings": ["XSS in login"],
            "_omniroute_meta": {"route": "claude-sonnet-3.5"}
        }
        return {
            "content": [{"type": "text", "text": json.dumps(output)}]
        }

    backend = MCPOmniRouteBackend(mcp_client_callable=mock_mcp_client)
    
    req = DelegationRequest(
        request_id="test-req",
        work_item_ref="wi-1",
        target_surface="login.py",
        auditor_name="security-auditor",
        context_payload={"source": "print('hello')"},
        execution_policy=ExecutionPolicy(
            filesystem=FilesystemAccess.READ_ONLY,
            network=NetworkAccess.DISABLED,
            credentials=CredentialAccess.NONE,
        )
    )

    result = backend.delegate(req)
    
    assert result.status == DelegationStatus.SUCCESS
    assert result.provider_info == "claude-sonnet-3.5"
    assert "findings" in result.output_payload
    assert result.output_payload["findings"] == ["XSS in login"]


def test_omniroute_backend_handles_mcp_error():
    """Validates that MCP level errors are translated to FAILED status."""
    def mock_mcp_error(server, tool, args):
        return {"isError": True, "error": "Gateway timeout"}

    backend = MCPOmniRouteBackend(mcp_client_callable=mock_mcp_error)
    req = DelegationRequest(
        request_id="test-req",
        work_item_ref="wi-1",
        target_surface="x",
        auditor_name="auditor",
        context_payload={},
        execution_policy=ExecutionPolicy(FilesystemAccess.NONE, NetworkAccess.DISABLED, CredentialAccess.NONE)
    )

    result = backend.delegate(req)
    
    assert result.status == DelegationStatus.FAILED
    assert "error" in result.error_message
    assert result.provider_info == "omniroute/error"


def test_omniroute_backend_handles_exceptions_gracefully():
    """Validates that runtime exceptions don't crash the orchestrator."""
    def mock_mcp_crash(server, tool, args):
        raise ConnectionError("Connection refused")

    backend = MCPOmniRouteBackend(mcp_client_callable=mock_mcp_crash)
    req = DelegationRequest(
        request_id="test-req",
        work_item_ref="wi-1",
        target_surface="x",
        auditor_name="auditor",
        context_payload={},
        execution_policy=ExecutionPolicy(FilesystemAccess.NONE, NetworkAccess.DISABLED, CredentialAccess.NONE)
    )

    result = backend.delegate(req)
    
    assert result.status == DelegationStatus.FAILED
    assert "Connection refused" in result.error_message
    assert result.provider_info == "omniroute/exception"
