"""Factories for constructing independent MCP test messages."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

REFERENCES_DIR = Path(__file__).parent.parent / "references"


def make_tool_dict(
    name: str = "delegate_task",
    description: str = "Delegate a task",
    properties: Optional[Dict[str, Any]] = None,
    required: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a mock tool dictionary as returned by tools/list."""
    if properties is None:
        properties = {
            "task": {"type": "string", "description": "Task text"},
            "profile": {
                "type": "string",
                "description": "Profile hint",
                "enum": ["cheap", "fast", "coding", "coding:pro", "smart"],
            },
            "context": {"type": "string", "description": "Context"},
            "task_id": {"type": "string", "description": "Tracking ID"},
            "session_id": {"type": "string", "description": "Session ID"},
            "cache_mode": {
                "type": "string",
                "description": "Cache mode",
                "enum": ["native", "bypass", "deterministic"],
            },
            "cache_key": {"type": "string", "description": "Cache key"},
            "max_tokens": {"type": "integer", "description": "Max tokens"},
            "temperature": {"type": "number", "description": "Temperature"},
        }
    if required is None:
        required = ["task"]

    return {
        "name": name,
        "description": description,
        "inputSchema": {
            "type": "object",
            "properties": properties,
            "required": required,
        },
    }


def make_tools_list_response(
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create a mock tools/list JSON-RPC response."""
    if tools is None:
        tools = [
            make_tool_dict("delegate_task"),
            make_tool_dict(
                "query_delegation",
                "Query delegation status",
                {"task_id": {"type": "string"}},
                ["task_id"],
            ),
            make_tool_dict(
                "delegation_summary",
                "Summary of delegations",
                {},
                [],
            ),
            make_tool_dict(
                "query_cache",
                "Query cache",
                {"cache_key": {"type": "string"}},
                ["cache_key"],
            ),
            make_tool_dict(
                "invalidate_cache",
                "Invalidate cache",
                {"cache_key": {"type": "string"}},
                ["cache_key"],
            ),
        ]
    return {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "tools": tools,
        },
    }


def make_initialize_response(
    session_id: str = "test-session-123",
    protocol_version: str = "2024-11-05",
    server_name: str = "omniroute-gateway",
    server_version: str = "1.0.0",
) -> Dict[str, Any]:
    """Create a mock initialize JSON-RPC response."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "protocolVersion": protocol_version,
            "capabilities": {},
            "serverInfo": {
                "name": server_name,
                "version": server_version,
            },
        },
    }


def make_tool_call_response(
    result: Any = None,
    request_id: int = 3,
) -> Dict[str, Any]:
    """Create a mock tools/call JSON-RPC response."""
    if result is None:
        result = {
            "content": [{"type": "text", "text": "SMOKE_OK — test response"}],
        }
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result,
    }


def make_jsonrpc_error(
    code: int = -32600,
    message: str = "Invalid Request",
    data: Any = None,
    request_id: Any = 1,
) -> Dict[str, Any]:
    """Create a mock JSON-RPC error response."""
    error: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": error,
    }
