"""Regression tests for the DelegationGateway trust boundary."""

from unittest.mock import MagicMock

import pytest

from omniroute_delegation.contracts import DelegationTask
from omniroute_delegation.delegation_gateway import DelegationGateway
from omniroute_delegation.exceptions import CredentialLeakPreventedError, SchemaViolationError
from omniroute_delegation.mcp_client import MCPClient, ToolSchema


def ready_client(arguments):
    client = MagicMock(spec=MCPClient)
    client.session.is_initialized = True
    client.session.tools = {
        "delegate_task": ToolSchema.from_mcp(
            {
                "name": "delegate_task",
                "description": "Delegate",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string"},
                        "profile": {"type": "string"},
                    },
                    "required": ["task", "context"],
                    "additionalProperties": False,
                },
            }
        )
    }
    client.session.has_tool.return_value = True
    client.session.get_tool.return_value = client.session.tools["delegate_task"]
    client.validate_tool_params.return_value = []
    client.call_tool.return_value = {"content": [{"type": "text", "text": "ok"}]}
    return client


def test_gateway_scans_before_mcp_call():
    client = ready_client({})
    gateway = DelegationGateway(client)
    task = DelegationTask(
        task="Review code",
        context="api_key=sk-secretkey123456789012345",
    )

    with pytest.raises(CredentialLeakPreventedError):
        gateway.delegate(task)

    client.call_tool.assert_not_called()


def test_gateway_validates_before_dispatch():
    client = ready_client({})
    client.validate_tool_params.return_value = ["invalid schema"]
    gateway = DelegationGateway(client)

    with pytest.raises(SchemaViolationError):
        gateway.delegate(DelegationTask(task="Review code"))

    client.call_tool.assert_not_called()


def test_gateway_maps_english_contract_to_runtime_schema():
    client = ready_client({})
    gateway = DelegationGateway(client)

    result = gateway.delegate(DelegationTask(task="Review code", profile="coding"))

    assert result["content"]
    client.call_tool.assert_called_once()
    args = client.call_tool.call_args.args[1]
    assert args == {"task": "Review code", "profile": "coding"}


def test_gateway_supports_legacy_wire_aliases():
    client = MagicMock(spec=MCPClient)
    client.session.is_initialized = True
    tool = ToolSchema.from_mcp(
        {
            "name": "delegate_task",
            "description": "Delegate",
            "inputSchema": {
                "type": "object",
                "properties": {"task": {"type": "string"}, "context": {"type": "string"}},
                "required": ["task", "context"],
            },
        }
    )
    client.session.has_tool.return_value = True
    client.session.get_tool.return_value = tool
    client.session.tools = {"delegate_task": tool}
    client.validate_tool_params.return_value = []
    client.call_tool.return_value = {"ok": True}

    result = DelegationGateway(client).delegate(DelegationTask(task="Review code"))

    assert result == {"ok": True}
    assert client.call_tool.call_args.args[1] == {"task": "Review code"}


def test_gateway_requires_discovered_tool():
    client = MagicMock(spec=MCPClient)
    client.session.is_initialized = True
    client.session.tools = {}
    client.session.has_tool.return_value = False

    with pytest.raises(SchemaViolationError):
        DelegationGateway(client).delegate(DelegationTask(task="Review code"))
