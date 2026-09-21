"""
omniroute_backend.py — OmniRoute Delegation Backend

Implements the DelegationBackend interface using the `delegar_tarefa` MCP tool
from the omnirouter server.
"""

import json
from typing import Any, Dict

from .delegation import DelegationBackend, DelegationRequest, DelegationResult, DelegationStatus


class MCPOmniRouteBackend(DelegationBackend):
    """
    Delegation backend that routes tasks through the OmniRoute MCP server.
    """

    def __init__(self, mcp_client_callable):
        """
        :param mcp_client_callable: A callable that invokes an MCP tool.
                                    Signature: fn(server_name, tool_name, arguments) -> dict
        """
        self.mcp_client_callable = mcp_client_callable

    def delegate(self, request: DelegationRequest) -> DelegationResult:
        # Convert context payload to the required text format for OmniRoute
        context_str = json.dumps(request.context_payload, indent=2)
        instruction = f"Execute Audit WorkItem: {request.work_item_ref} for auditor: {request.auditor_name}"

        # Setup the MCP tool arguments
        args = {
            "task_id": request.request_id,
            "instruction": instruction,
            "context": context_str,
            "target_surface": request.target_surface,
            "required_capabilities": [
                f"fs:{request.execution_policy.filesystem.value}",
                f"net:{request.execution_policy.network.value}",
            ]
        }

        try:
            # Call the OmniRoute MCP tool synchronously
            mcp_result = self.mcp_client_callable("omnirouter", "delegar_tarefa", args)
            
            # Note: MCP tools return a list of content blocks, usually with text.
            # We assume a well-formed response from OmniRoute.
            # Because this is a simplified integration, we parse the result.
            
            # If the tool returned an error or failure indicator
            if mcp_result.get("isError"):
                return DelegationResult(
                    request_id=request.request_id,
                    status=DelegationStatus.FAILED,
                    output_payload=None,
                    error_message=str(mcp_result),
                    provider_info="omniroute/error",
                    usage_tokens=0,
                )
            
            # Extract text payload (assuming standard MCP result format)
            content = mcp_result.get("content", [])
            text_result = ""
            for block in content:
                if block.get("type") == "text":
                    text_result += block.get("text", "")

            # Attempt to parse as JSON output payload if OmniRoute returns structured data
            try:
                output_payload = json.loads(text_result)
            except json.JSONDecodeError:
                output_payload = {"raw_text": text_result}

            # If OmniRoute delegates properly, it should pass back the route it used
            provider_info = "omniroute/dynamic"
            if isinstance(output_payload, dict) and "_omniroute_meta" in output_payload:
                provider_info = output_payload["_omniroute_meta"].get("route", provider_info)

            return DelegationResult(
                request_id=request.request_id,
                status=DelegationStatus.SUCCESS,
                output_payload=output_payload,
                error_message=None,
                provider_info=provider_info,
                usage_tokens=None,
            )

        except Exception as e:
            # Handle transport or unexpected errors without crashing the core
            return DelegationResult(
                request_id=request.request_id,
                status=DelegationStatus.FAILED,
                output_payload=None,
                error_message=str(e),
                provider_info="omniroute/exception",
                usage_tokens=0,
            )
