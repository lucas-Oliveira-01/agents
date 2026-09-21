"""Tests for the MCP HTTP client — session management and transport.

Tests cover:
- Endpoint resolution (env var, parameter, default)
- Initialize handshake and session ID preservation
- tools/list parsing and ToolSchema construction
- tools/call invocation
- HTTP error handling (connect, timeout, status codes)
- JSON-RPC error handling
- Session state management
- Contract rediscovery logic
- Parameter validation and filtering
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from omniroute_delegation.mcp_client import (
    DEFAULT_HEALTH_URL,
    DEFAULT_MCP_URL,
    GatewayUnreachableError,
    MCPApplicationError,
    MCPClient,
    MCPProtocolError,
    MCPTransportError,
    MCPSession,
    ToolSchema,
)
from tests.helpers import (
    make_initialize_response,
    make_jsonrpc_error,
    make_tool_dict,
    make_tools_list_response,
    make_tool_call_response,
)

# ===========================================================================
# Endpoint Resolution
# ===========================================================================


class TestEndpointResolution:
    """Test MCP URL and health URL resolution logic."""

    def test_default_urls(self):
        client = MCPClient()
        assert client.mcp_url == DEFAULT_MCP_URL
        assert client.health_url == DEFAULT_HEALTH_URL
        client.close()

    def test_explicit_url_parameter(self):
        client = MCPClient(mcp_url="http://custom:9999/mcp")
        assert client.mcp_url == "http://custom:9999/mcp"
        client.close()

    def test_explicit_health_url(self):
        client = MCPClient(
            mcp_url="http://custom:9999/mcp",
            health_url="http://custom:9999/health",
        )
        assert client.health_url == "http://custom:9999/health"
        client.close()

    def test_env_var_takes_precedence(self):
        with patch.dict("os.environ", {"OMNIROUTE_MCP_URL": "http://env:8080/mcp"}):
            client = MCPClient()
            assert client.mcp_url == "http://env:8080/mcp"
            assert client.health_url == "http://env:8080/health"
            client.close()

    def test_explicit_param_overrides_env(self):
        with patch.dict("os.environ", {"OMNIROUTE_MCP_URL": "http://env:8080/mcp"}):
            client = MCPClient(mcp_url="http://explicit:7777/mcp")
            assert client.mcp_url == "http://env:8080/mcp"
            assert client.health_url == "http://env:8080/health"
            client.close()

    def test_env_var_derives_health_url(self):
        with patch.dict("os.environ", {"OMNIROUTE_MCP_URL": "http://env:8080/mcp"}):
            client = MCPClient()
            assert client.health_url == "http://env:8080/health"
            client.close()

    def test_explicit_url_derives_health_url_without_environment(self):
        with patch.dict("os.environ", {}, clear=True):
            client = MCPClient(mcp_url="http://custom:9999/mcp")
            assert client.health_url == "http://custom:9999/health"
            client.close()


# ===========================================================================
# ToolSchema Parsing
# ===========================================================================


class TestToolSchema:
    """Test ToolSchema parsing from MCP tool dictionaries."""

    def test_parse_full_tool(self):
        tool_dict = make_tool_dict()
        schema = ToolSchema.from_mcp(tool_dict)
        assert schema.name == "delegar_tarefa"
        assert "tarefa" in schema.required_params
        assert "perfil" in schema.optional_params
        assert "contexto" in schema.optional_params

    def test_accepts_param(self):
        tool_dict = make_tool_dict()
        schema = ToolSchema.from_mcp(tool_dict)
        assert schema.accepts_param("tarefa") is True
        assert schema.accepts_param("perfil") is True
        assert schema.accepts_param("nonexistent") is False

    def test_get_param_type(self):
        tool_dict = make_tool_dict()
        schema = ToolSchema.from_mcp(tool_dict)
        assert schema.get_param_type("tarefa") == "string"
        assert schema.get_param_type("max_tokens") == "integer"
        assert schema.get_param_type("temperature") == "number"
        assert schema.get_param_type("nonexistent") is None

    def test_get_param_enum(self):
        tool_dict = make_tool_dict()
        schema = ToolSchema.from_mcp(tool_dict)
        enum = schema.get_param_enum("perfil")
        assert enum is not None
        assert "coding" in enum
        assert "coding:pro" in enum
        assert schema.get_param_enum("tarefa") is None

    def test_empty_schema(self):
        schema = ToolSchema.from_mcp({"name": "empty", "inputSchema": {}})
        assert schema.name == "empty"
        assert schema.required_params == []
        assert schema.optional_params == []

    def test_missing_input_schema(self):
        schema = ToolSchema.from_mcp({"name": "bare"})
        assert schema.name == "bare"
        assert schema.input_schema == {}


# ===========================================================================
# Session Management
# ===========================================================================


class TestSessionManagement:
    """Test MCPSession state management."""

    def test_fresh_session(self):
        session = MCPSession()
        assert not session.is_initialized
        assert session.session_id is None
        assert not session.has_tool("delegar_tarefa")
        assert session.get_tool("delegar_tarefa") is None

    def test_session_with_tools(self):
        session = MCPSession()
        tool = ToolSchema.from_mcp(make_tool_dict())
        session.tools["delegar_tarefa"] = tool
        assert session.has_tool("delegar_tarefa")
        assert session.get_tool("delegar_tarefa") is tool
        assert not session.has_tool("nonexistent")


# ===========================================================================
# MCP Client — Initialize
# ===========================================================================


class TestMCPClientInitialize:
    """Test MCP initialize handshake."""

    def test_successful_initialize(self):
        mock_response = httpx.Response(
            200,
            json=make_initialize_response(),
            headers={"mcp-session-id": "sess-abc"},
        )
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_response

        client = MCPClient(http_client=mock_client)
        session = client.initialize()

        assert session.is_initialized
        assert session.session_id == "sess-abc"
        assert session.protocol_version == "2024-11-05"
        assert session.server_info["name"] == "omniroute-gateway"

    def test_initialize_without_session_id(self):
        mock_response = httpx.Response(
            200,
            json=make_initialize_response(),
            headers={},
        )
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_response

        client = MCPClient(http_client=mock_client)
        session = client.initialize()

        assert session.is_initialized
        assert session.session_id is None

    def test_initialize_gateway_unreachable(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.side_effect = httpx.ConnectError("Connection refused")

        client = MCPClient(http_client=mock_client)
        with pytest.raises(GatewayUnreachableError) as exc_info:
            client.initialize()
        assert "Connection refused" in str(exc_info.value)

    def test_initialize_timeout(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.side_effect = httpx.TimeoutException("Timeout")

        client = MCPClient(http_client=mock_client)
        with pytest.raises(MCPTransportError) as exc_info:
            client.initialize()
        assert "Timeout" in str(exc_info.value)

    def test_initialize_http_error(self):
        mock_response = httpx.Response(500, text="Internal Server Error")
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_response

        client = MCPClient(http_client=mock_client)
        with pytest.raises(MCPTransportError) as exc_info:
            client.initialize()
        assert "500" in str(exc_info.value)

    def test_initialize_invalid_json(self):
        mock_response = httpx.Response(
            200,
            text="not json at all",
            headers={"content-type": "text/plain"},
        )
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_response

        client = MCPClient(http_client=mock_client)
        with pytest.raises(MCPProtocolError) as exc_info:
            client.initialize()
        assert "Invalid JSON" in str(exc_info.value)

    def test_initialize_jsonrpc_error(self):
        mock_response = httpx.Response(
            200,
            json=make_jsonrpc_error(-32600, "Invalid Request"),
        )
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_response

        client = MCPClient(http_client=mock_client)
        with pytest.raises(MCPApplicationError) as exc_info:
            client.initialize()
        assert "-32600" in str(exc_info.value)

    @pytest.mark.parametrize(
        "message",
        [
            {"jsonrpc": "1.0", "id": 1, "result": {}},
            {"jsonrpc": "2.0", "id": 99, "result": {}},
            {"jsonrpc": "2.0", "id": 1, "result": {}, "error": {}},
        ],
    )
    def test_initialize_rejects_malformed_jsonrpc_response(self, message):
        mock_response = httpx.Response(200, json=message)
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_response
        client = MCPClient(http_client=mock_client)
        with pytest.raises(MCPProtocolError):
            client.initialize()

    def test_initialize_parses_single_sse_event(self):
        body = (
            "event: message\n"
            'data: {"jsonrpc":"2.0","id":1,'
            '"result":{"protocolVersion":"2024-11-05",'
            '"capabilities":{},"serverInfo":{"name":"gateway"}}}\n\n'
        )
        mock_response = httpx.Response(
            200,
            text=body,
            headers={"content-type": "text/event-stream", "mcp-session-id": "sess-sse"},
        )
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = mock_response
        session = MCPClient(http_client=mock_client).initialize()
        assert session.is_initialized
        assert session.session_id == "sess-sse"

    def test_initialize_rejects_empty_result(self):
        response = httpx.Response(
            200,
            json={"jsonrpc": "2.0", "id": 1, "result": {}},
        )
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.return_value = response
        with pytest.raises(MCPProtocolError, match="protocolVersion"):
            MCPClient(http_client=mock_client).initialize()


# ===========================================================================
# MCP Client — Tool Discovery
# ===========================================================================


class TestMCPClientDiscoverTools:
    """Test tools/list discovery and parsing."""

    def _make_initialized_client(self):
        """Helper to create a client with initialized session."""
        init_response = httpx.Response(
            200,
            json=make_initialize_response(),
            headers={"mcp-session-id": "sess-123"},
        )
        tools_response = httpx.Response(
            200,
            json=make_tools_list_response(),
            headers={"mcp-session-id": "sess-123"},
        )

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.side_effect = [init_response, tools_response]

        client = MCPClient(http_client=mock_client)
        client.initialize()
        return client

    def test_discover_tools_success(self):
        client = self._make_initialized_client()
        tools = client.discover_tools()

        assert "delegar_tarefa" in tools
        assert "consultar_delegacao" in tools
        assert "resumo_delegacoes" in tools
        assert "consultar_cache" in tools
        assert "invalidar_cache" in tools
        assert len(tools) == 5

    def test_discover_tools_not_initialized(self):
        mock_client = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_client)

        with pytest.raises(MCPProtocolError) as exc_info:
            client.discover_tools()
        assert "not initialized" in str(exc_info.value)

    def test_session_id_preserved_in_headers(self):
        init_response = httpx.Response(
            200,
            json=make_initialize_response(),
            headers={"mcp-session-id": "sess-xyz"},
        )
        tools_response = httpx.Response(
            200,
            json=make_tools_list_response(),
            headers={"mcp-session-id": "sess-xyz"},
        )

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.side_effect = [init_response, tools_response]

        client = MCPClient(http_client=mock_client)
        client.initialize()
        client.discover_tools()

        # Verify the second call (tools/list) included the session ID
        second_call = mock_client.post.call_args_list[1]
        headers = second_call[1].get("headers", {})
        assert headers.get("mcp-session-id") == "sess-xyz"


# ===========================================================================
# MCP Client — Tool Invocation
# ===========================================================================


class TestMCPClientCallTool:
    """Test tools/call invocation."""

    def _make_ready_client(self):
        """Helper to create a fully initialized client with discovered tools."""
        init_response = httpx.Response(
            200,
            json=make_initialize_response(),
            headers={"mcp-session-id": "sess-123"},
        )
        tools_response = httpx.Response(
            200,
            json=make_tools_list_response(),
            headers={"mcp-session-id": "sess-123"},
        )
        call_response = httpx.Response(
            200,
            json=make_tool_call_response(),
            headers={"mcp-session-id": "sess-123"},
        )

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.side_effect = [init_response, tools_response, call_response]

        client = MCPClient(http_client=mock_client)
        client.initialize()
        client.discover_tools()
        return client

    def test_call_tool_success(self):
        client = self._make_ready_client()
        result = client.call_tool("delegar_tarefa", {"tarefa": "test task"})
        assert result is not None

    def test_call_tool_not_initialized(self):
        mock_client = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_client)

        with pytest.raises(MCPProtocolError):
            client.call_tool("delegar_tarefa", {"tarefa": "test"})

    def test_call_tool_rejects_unknown_tool_before_http(self):
        mock_client = MagicMock(spec=httpx.Client)
        client = MCPClient(http_client=mock_client)
        client._session.is_initialized = True
        with pytest.raises(MCPProtocolError, match="not discovered"):
            client.call_tool("not_discovered", {})
        mock_client.post.assert_not_called()

    def test_call_tool_rejects_invalid_parameters_before_http(self):
        client = self._make_ready_client()
        mock_http = client._http
        with pytest.raises(MCPProtocolError, match="Invalid tool parameters"):
            client.call_tool("delegar_tarefa", {"tarefa": 123})
        assert mock_http.post.call_count == 2

    def test_call_tool_application_error(self):
        init_response = httpx.Response(
            200,
            json=make_initialize_response(),
            headers={"mcp-session-id": "sess-123"},
        )
        error_response = httpx.Response(
            200,
            json=make_jsonrpc_error(-32000, "INVALID_PROFILE", {"profile": "bad"}, request_id=3),
        )
        tools_response = httpx.Response(
            200,
            json=make_tools_list_response(),
            headers={"mcp-session-id": "sess-123"},
        )

        mock_client = MagicMock(spec=httpx.Client)
        mock_client.post.side_effect = [init_response, tools_response, error_response]

        client = MCPClient(http_client=mock_client)
        client.initialize()
        client.discover_tools()
        with pytest.raises(MCPApplicationError) as exc_info:
            client.call_tool("delegar_tarefa", {"tarefa": "test"})
        assert exc_info.value.code == -32000


# ===========================================================================
# Parameter Validation
# ===========================================================================


class TestParameterValidation:
    """Test parameter pre-validation against discovered schemas."""

    def _make_client_with_tools(self):
        """Client with discovered tools."""
        client = MCPClient(http_client=MagicMock(spec=httpx.Client))
        client._session.is_initialized = True
        tool = ToolSchema.from_mcp(make_tool_dict())
        client._session.tools["delegar_tarefa"] = tool
        return client

    def test_valid_params(self):
        client = self._make_client_with_tools()
        errors = client.validate_tool_params(
            "delegar_tarefa",
            {"tarefa": "test", "perfil": "coding"},
        )
        assert errors == []

    def test_missing_required_param(self):
        client = self._make_client_with_tools()
        errors = client.validate_tool_params(
            "delegar_tarefa",
            {"perfil": "coding"},
        )
        assert any("tarefa" in e for e in errors)

    def test_unknown_param(self):
        client = self._make_client_with_tools()
        errors = client.validate_tool_params(
            "delegar_tarefa",
            {"tarefa": "test", "unknown_param": "value"},
        )
        assert any("unknown_param" in e for e in errors)

    def test_invalid_enum_value(self):
        client = self._make_client_with_tools()
        errors = client.validate_tool_params(
            "delegar_tarefa",
            {"tarefa": "test", "perfil": "nonexistent_profile"},
        )
        assert any("nonexistent_profile" in e for e in errors)

    def test_tool_not_found(self):
        client = self._make_client_with_tools()
        errors = client.validate_tool_params(
            "nonexistent_tool",
            {"tarefa": "test"},
        )
        assert any("not found" in e for e in errors)


# ===========================================================================
# Parameter Filtering
# ===========================================================================


class TestParameterFiltering:
    """Test filtering of params to those accepted by tools."""

    def _make_client_with_tools(self):
        client = MCPClient(http_client=MagicMock(spec=httpx.Client))
        client._session.is_initialized = True
        tool = ToolSchema.from_mcp(make_tool_dict())
        client._session.tools["delegar_tarefa"] = tool
        return client

    def test_filter_removes_unknown(self):
        client = self._make_client_with_tools()
        filtered = client.filter_optional_params(
            "delegar_tarefa",
            {"tarefa": "test", "perfil": "coding", "unknown": "value"},
        )
        assert "tarefa" in filtered
        assert "perfil" in filtered
        assert "unknown" not in filtered

    def test_filter_preserves_all_known(self):
        client = self._make_client_with_tools()
        filtered = client.filter_optional_params(
            "delegar_tarefa",
            {"tarefa": "test", "perfil": "coding", "cache_mode": "native"},
        )
        assert len(filtered) == 3

    def test_filter_unknown_tool(self):
        client = self._make_client_with_tools()
        params = {"tarefa": "test", "extra": "val"}
        filtered = client.filter_optional_params("unknown_tool", params)
        assert filtered == params  # No filtering when tool unknown


# ===========================================================================
# Contract Rediscovery
# ===========================================================================


class TestContractRediscovery:
    """Test should_rediscover logic."""

    def test_rediscover_on_schema_mismatch(self):
        client = MCPClient(http_client=MagicMock(spec=httpx.Client))
        assert client.should_rediscover(schema_mismatch=True) is True

    def test_rediscover_on_reconnect(self):
        client = MCPClient(http_client=MagicMock(spec=httpx.Client))
        assert client.should_rediscover(reconnected=True) is True

    def test_rediscover_on_version_change(self):
        client = MCPClient(http_client=MagicMock(spec=httpx.Client))
        assert client.should_rediscover(version_changed=True) is True

    def test_rediscover_on_transport_error(self):
        client = MCPClient(http_client=MagicMock(spec=httpx.Client))
        error = MCPTransportError("Connection reset")
        assert client.should_rediscover(error=error) is True

    def test_rediscover_on_application_error(self):
        client = MCPClient(http_client=MagicMock(spec=httpx.Client))
        error = MCPApplicationError("INVALID_INPUT")
        assert client.should_rediscover(error=error) is True

    def test_no_rediscover_without_trigger(self):
        client = MCPClient(http_client=MagicMock(spec=httpx.Client))
        assert client.should_rediscover() is False


# ===========================================================================
# Context Manager
# ===========================================================================


class TestContextManager:
    """Test MCPClient context manager protocol."""

    def test_context_manager(self):
        mock_http = MagicMock(spec=httpx.Client)
        with MCPClient(http_client=mock_http) as client:
            assert client.mcp_url == DEFAULT_MCP_URL
        # Should NOT close an externally-provided client
        mock_http.close.assert_not_called()

    def test_context_manager_owns_client(self):
        # When no http_client is passed, MCPClient creates its own
        with patch("omniroute_delegation.mcp_client.httpx.Client") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            with MCPClient():
                pass
            mock_instance.close.assert_called_once()


# ===========================================================================
# Health Check
# ===========================================================================


class TestHealthCheck:
    """Test health check endpoint."""

    def test_health_check_success(self):
        mock_response = httpx.Response(200, json={"status": "ok"})
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        client = MCPClient(http_client=mock_client)
        result = client.health_check()
        assert result["status"] == "ok"

    def test_health_check_unreachable(self):
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")

        client = MCPClient(http_client=mock_client)
        with pytest.raises(GatewayUnreachableError):
            client.health_check()

    def test_health_check_http_error(self):
        mock_response = httpx.Response(503, text="Service Unavailable")
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        client = MCPClient(http_client=mock_client)
        with pytest.raises(MCPTransportError):
            client.health_check()

    def test_health_check_non_json(self):
        mock_response = httpx.Response(
            200,
            text="OK",
            headers={"content-type": "text/plain"},
        )
        mock_client = MagicMock(spec=httpx.Client)
        mock_client.get.return_value = mock_response

        client = MCPClient(http_client=mock_client)
        result = client.health_check()
        assert result["status"] == "ok"
        assert result["raw"] == "OK"
