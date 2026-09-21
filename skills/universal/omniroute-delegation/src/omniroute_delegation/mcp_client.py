"""MCP Streamable HTTP client for OmniRoute gateway.

Handles session management, contract discovery, and tool invocation
via the MCP JSON-RPC 2.0 protocol over HTTP.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

import httpx
import jsonschema

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MCP_URL = "http://127.0.0.1:20130/mcp"
DEFAULT_HEALTH_URL = "http://127.0.0.1:20130/health"
MCP_PROTOCOL_VERSION = "2024-11-05"

CLIENT_INFO = {
    "name": "omniroute-delegation",
    "version": "1.0.0",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ToolSchema:
    """Validated tool schema from tools/list."""

    name: str
    description: str
    input_schema: Dict[str, Any]
    required_params: List[str] = field(default_factory=list)
    optional_params: List[str] = field(default_factory=list)

    @classmethod
    def from_mcp(cls, tool_dict: Dict[str, Any]) -> "ToolSchema":
        """Parse a tool entry from MCP tools/list result."""
        name = tool_dict.get("name", "")
        description = tool_dict.get("description", "")
        input_schema = tool_dict.get("inputSchema", {})

        required_params = input_schema.get("required", [])
        properties = input_schema.get("properties", {})
        all_params = list(properties.keys())
        optional_params = [p for p in all_params if p not in required_params]

        return cls(
            name=name,
            description=description,
            input_schema=input_schema,
            required_params=list(required_params),
            optional_params=optional_params,
        )

    def accepts_param(self, param_name: str) -> bool:
        """Check if this tool accepts a given parameter."""
        return param_name in self.required_params or param_name in self.optional_params

    def get_param_type(self, param_name: str) -> Optional[str]:
        """Get the declared type for a parameter, if it exists."""
        props = self.input_schema.get("properties", {})
        param_def = props.get(param_name)
        if param_def is None:
            return None
        return param_def.get("type")

    def get_param_enum(self, param_name: str) -> Optional[List[str]]:
        """Get the enum constraint for a parameter, if any."""
        props = self.input_schema.get("properties", {})
        param_def = props.get(param_name)
        if param_def is None:
            return None
        return param_def.get("enum")


@dataclass
class MCPSession:
    """Represents an active MCP session."""

    session_id: Optional[str] = None
    server_info: Optional[Dict[str, Any]] = None
    protocol_version: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    tools: Dict[str, ToolSchema] = field(default_factory=dict)
    is_initialized: bool = False

    def has_tool(self, tool_name: str) -> bool:
        """Check if a tool was discovered in this session."""
        return tool_name in self.tools

    def get_tool(self, tool_name: str) -> Optional[ToolSchema]:
        """Get a tool schema by name."""
        return self.tools.get(tool_name)


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class MCPError(Exception):
    """Base exception for MCP protocol errors."""

    def __init__(self, message: str, code: Optional[int] = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


class MCPTransportError(MCPError):
    """HTTP transport-level error."""


class MCPProtocolError(MCPError):
    """JSON-RPC protocol-level error."""


class MCPApplicationError(MCPError):
    """Application-level error from the gateway."""


class GatewayUnreachableError(MCPTransportError):
    """Cannot connect to the MCP gateway."""


# Known application error codes
KNOWN_ERROR_CODES = frozenset(
    {
        "INVALID_INPUT",
        "INVALID_PROFILE",
        "INVALID_CACHE_MODE",
        "CACHE_KEY_REQUIRED",
        "CONFIG_MISSING",
        "GATEWAY_UNREACHABLE",
    }
)


# ---------------------------------------------------------------------------
# MCP Client
# ---------------------------------------------------------------------------


class MCPClient:
    """MCP Streamable HTTP client for the OmniRoute gateway.

    Manages session lifecycle, contract discovery, and tool invocation.

    Usage:
        client = MCPClient()
        session = client.initialize()
        tools = client.discover_tools()
        result = client.call_tool("delegar_tarefa", {"tarefa": "..."})
    """

    def __init__(
        self,
        mcp_url: Optional[str] = None,
        health_url: Optional[str] = None,
        timeout: float = 30.0,
        http_client: Optional[httpx.Client] = None,
    ):
        env_url = os.environ.get("OMNIROUTE_MCP_URL")
        self._mcp_url = env_url or mcp_url or DEFAULT_MCP_URL

        if health_url is not None:
            self._health_url = health_url
        elif self._mcp_url != DEFAULT_MCP_URL:
            base = self._mcp_url.rsplit("/", 1)[0]
            self._health_url = f"{base}/health"
        else:
            self._health_url = DEFAULT_HEALTH_URL

        self._timeout = timeout
        self._request_id = 0
        self._session = MCPSession()
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(timeout=timeout)

    @property
    def mcp_url(self) -> str:
        """The resolved MCP endpoint URL."""
        return self._mcp_url

    @property
    def health_url(self) -> str:
        """The resolved health endpoint URL."""
        return self._health_url

    @property
    def session(self) -> MCPSession:
        """The current MCP session."""
        return self._session

    def close(self) -> None:
        """Close the HTTP client if owned by this instance."""
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> "MCPClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # -- Internal helpers --------------------------------------------------

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _build_request(
        self,
        method: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        req: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
        }
        if params is not None:
            req["params"] = params
        return req

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session.session_id:
            headers["mcp-session-id"] = self._session.session_id
        return headers

    def _send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a JSON-RPC request and return the parsed response."""
        headers = self._build_headers()

        try:
            response = self._http.post(
                self._mcp_url,
                json=payload,
                headers=headers,
            )
        except httpx.ConnectError as exc:
            raise GatewayUnreachableError(
                f"Cannot connect to MCP gateway at {self._mcp_url}: {exc}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise MCPTransportError(
                f"Timeout connecting to MCP gateway at {self._mcp_url}: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise MCPTransportError(f"HTTP error communicating with MCP gateway: {exc}") from exc

        # Preserve session ID from response headers
        new_session_id = response.headers.get("mcp-session-id")
        if new_session_id:
            self._session.session_id = new_session_id

        # Parse response
        if response.status_code >= 400:
            raise MCPTransportError(
                f"HTTP {response.status_code}: {response.text}",
                code=response.status_code,
            )

        content_type = response.headers.get("content-type", "").lower()
        try:
            if "text/event-stream" in content_type:
                result = self._parse_sse_response(response.text)
            else:
                result = response.json()
        except MCPProtocolError:
            raise
        except Exception as exc:
            raise MCPProtocolError(f"Invalid JSON in response: {response.text[:200]}") from exc

        self._validate_jsonrpc_response(result, payload["id"])

        # Check for JSON-RPC error
        if "error" in result:
            error = result["error"]
            error_code = error.get("code", -1)
            error_message = error.get("message", "Unknown error")
            error_data = error.get("data")
            raise MCPApplicationError(
                f"JSON-RPC error {error_code}: {error_message}",
                code=error_code,
                data=error_data,
            )

        return result

    @staticmethod
    def _parse_sse_response(body: str) -> Dict[str, Any]:
        """Parse one JSON-RPC message from a server-sent event stream."""
        events: List[str] = []
        data_lines: List[str] = []

        def finish_event() -> None:
            if data_lines:
                events.append("\n".join(data_lines))
                data_lines.clear()

        for line in body.splitlines():
            if not line:
                finish_event()
            elif line.startswith(":") or line.startswith("event:") or line.startswith("id:"):
                continue
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
            else:
                raise MCPProtocolError(f"Invalid SSE line: {line[:120]}")
        finish_event()

        if len(events) != 1:
            raise MCPProtocolError("Expected exactly one JSON-RPC event in SSE response.")
        try:
            parsed = __import__("json").loads(events[0])
        except Exception as exc:
            raise MCPProtocolError("Invalid JSON in SSE data event.") from exc
        return parsed

    @staticmethod
    def _validate_jsonrpc_response(response: Any, request_id: Any) -> None:
        """Reject malformed or mis-correlated JSON-RPC responses."""
        if not isinstance(response, dict):
            raise MCPProtocolError("JSON-RPC response must be an object.")
        if response.get("jsonrpc") != "2.0":
            raise MCPProtocolError("JSON-RPC response must use version 2.0.")
        if "id" not in response or response["id"] != request_id:
            raise MCPProtocolError("JSON-RPC response ID does not match the request.")
        has_result = "result" in response
        has_error = "error" in response
        if has_result == has_error:
            raise MCPProtocolError(
                "JSON-RPC response must contain exactly one of result or error."
            )
        if has_error:
            error = response["error"]
            if not isinstance(error, dict) or not isinstance(error.get("code"), int):
                raise MCPProtocolError("JSON-RPC error must contain an integer code.")
            if not isinstance(error.get("message"), str):
                raise MCPProtocolError("JSON-RPC error must contain a string message.")

    # -- Public API --------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        """Perform a health check against the gateway.

        Returns:
            Dict with health status information.

        Raises:
            GatewayUnreachableError: If the gateway is unreachable.
            MCPTransportError: On HTTP errors.
        """
        try:
            response = self._http.get(self._health_url)
        except httpx.ConnectError as exc:
            raise GatewayUnreachableError(
                f"Cannot reach health endpoint at {self._health_url}: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise MCPTransportError(f"HTTP error on health check: {exc}") from exc

        if response.status_code >= 400:
            raise MCPTransportError(
                f"Health check returned HTTP {response.status_code}: {response.text}",
                code=response.status_code,
            )

        try:
            return response.json()
        except Exception:
            return {"status": "ok", "raw": response.text}

    def initialize(self) -> MCPSession:
        """Initialize an MCP session with the gateway.

        Sends the `initialize` request and preserves the `mcp-session-id`.

        Returns:
            The initialized MCPSession.

        Raises:
            GatewayUnreachableError: If gateway is unreachable.
            MCPProtocolError: On protocol-level errors.
            MCPApplicationError: On application-level errors.
        """
        payload = self._build_request(
            "initialize",
            {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        )

        result = self._send(payload)

        init_result = result.get("result", {})
        if not isinstance(init_result, dict):
            raise MCPProtocolError("initialize result must be an object.")
        if not isinstance(init_result.get("protocolVersion"), str):
            raise MCPProtocolError("initialize result lacks protocolVersion.")
        if not isinstance(init_result.get("capabilities"), dict):
            raise MCPProtocolError("initialize result lacks capabilities.")
        if not isinstance(init_result.get("serverInfo"), dict):
            raise MCPProtocolError("initialize result lacks serverInfo.")
        self._session.protocol_version = init_result.get("protocolVersion")
        self._session.server_info = init_result.get("serverInfo")
        self._session.capabilities = init_result.get("capabilities")
        self._session.is_initialized = True

        return self._session

    def discover_tools(self) -> Dict[str, ToolSchema]:
        """Execute tools/list and parse tool schemas.

        Must be called after initialize().

        Returns:
            Dict mapping tool names to their parsed ToolSchema.

        Raises:
            MCPProtocolError: If session is not initialized.
        """
        if not self._session.is_initialized:
            raise MCPProtocolError("Session not initialized. Call initialize() first.")

        payload = self._build_request("tools/list")
        result = self._send(payload)

        tools_result = result.get("result", {})
        tools_list = tools_result.get("tools", [])

        self._session.tools = {}
        for tool_dict in tools_list:
            schema = ToolSchema.from_mcp(tool_dict)
            self._session.tools[schema.name] = schema

        return self._session.tools

    def call_tool(
        self,
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Invoke a tool via tools/call.

        Args:
            tool_name: The name of the tool to call.
            arguments: The arguments to pass to the tool.

        Returns:
            The result from the tool invocation.

        Raises:
            MCPProtocolError: If session is not initialized or tool is unknown.
            MCPApplicationError: On application-level tool errors.
        """
        if not self._session.is_initialized:
            raise MCPProtocolError("Session not initialized. Call initialize() first.")
        if tool_name not in self._session.tools:
            raise MCPProtocolError(f"Tool '{tool_name}' was not discovered.")
        if arguments is not None:
            errors = self.validate_tool_params(tool_name, arguments)
            if errors:
                raise MCPProtocolError("Invalid tool parameters: " + "; ".join(errors))

        params: Dict[str, Any] = {"name": tool_name}
        if arguments:
            params["arguments"] = arguments

        payload = self._build_request("tools/call", params)
        result = self._send(payload)

        return result.get("result")

    def validate_tool_params(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> List[str]:
        """Pre-validate parameters against a discovered tool schema.

        Returns a list of validation error messages (empty if valid).
        """
        errors: List[str] = []

        tool = self._session.get_tool(tool_name)
        if tool is None:
            errors.append(f"Tool '{tool_name}' not found in discovered tools.")
            return errors

        # Check required params
        for req_param in tool.required_params:
            if req_param not in params:
                errors.append(f"Missing required parameter: '{req_param}'")

        # Check for unknown params
        known = set(tool.required_params) | set(tool.optional_params)
        for param_name in params:
            if param_name not in known:
                errors.append(f"Unknown parameter: '{param_name}'")

        # Check enum constraints
        for param_name, param_value in params.items():
            allowed = tool.get_param_enum(param_name)
            if allowed is not None and param_value not in allowed:
                errors.append(
                    f"Parameter '{param_name}' value '{param_value}' "
                    f"not in allowed values: {allowed}"
                )

        try:
            validator = jsonschema.Draft202012Validator(tool.input_schema)
            errors.extend(error.message for error in validator.iter_errors(params))
        except jsonschema.SchemaError as exc:
            errors.append(f"Invalid discovered tool schema: {exc.message}")

        return errors

    def should_rediscover(
        self,
        error: Optional[Exception] = None,
        schema_mismatch: bool = False,
        reconnected: bool = False,
        version_changed: bool = False,
    ) -> bool:
        """Determine if contract rediscovery is needed.

        Args:
            error: An exception from a failed tool call.
            schema_mismatch: If schema incompatibility was detected.
            reconnected: If the connection was re-established.
            version_changed: If version/configuration change is suspected.

        Returns:
            True if tools/list should be re-executed.
        """
        if schema_mismatch or reconnected or version_changed:
            return True

        if error is not None:
            if isinstance(error, MCPApplicationError):
                return True
            if isinstance(error, MCPTransportError):
                return True

        return False

    def filter_optional_params(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Filter params to only include those accepted by the tool.

        Removes any optional parameters not in the tool's schema.
        Required parameters are always preserved.
        """
        tool = self._session.get_tool(tool_name)
        if tool is None:
            return params

        known = set(tool.required_params) | set(tool.optional_params)
        return {k: v for k, v in params.items() if k in known}

    def list_discovered_tools(self) -> Sequence[str]:
        """Return names of all discovered tools."""
        return list(self._session.tools.keys())
