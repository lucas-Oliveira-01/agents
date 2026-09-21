"""OmniRoute Delegation — Universal MCP delegation skill.

Provides diagnostic utilities, schema validation, and MCP client helpers
for the OmniRoute gateway delegation protocol.
"""

__version__ = "1.0.0"

from omniroute_delegation.mcp_client import MCPClient
from omniroute_delegation.schema_validator import SchemaValidator
from omniroute_delegation.task_builder import TaskBuilder

__all__ = ["MCPClient", "SchemaValidator", "TaskBuilder", "__version__"]
