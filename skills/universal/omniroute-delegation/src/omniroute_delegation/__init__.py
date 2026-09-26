"""OmniRoute Delegation — Universal MCP delegation skill.

Provides diagnostic utilities, schema validation, and MCP client helpers
for the OmniRoute gateway delegation protocol.
"""

__version__ = "1.2.0"

from omniroute_delegation.contracts import (
    AuditContract,
    DelegateKind,
    DelegationTask,
    ExecutionState,
    L3TDelegate,
    L3WDelegate,
    LeafContract,
    LeafFinding,
    ToolContract,
    TransportContract,
)
from omniroute_delegation.delegation_gateway import DelegationGateway
from omniroute_delegation.exceptions import (
    CredentialLeakPreventedError,
    SchemaViolationError,
    SemanticCoverageFailedError,
)
from omniroute_delegation.mcp_client import MCPClient
from omniroute_delegation.schema_validator import SchemaValidator
from omniroute_delegation.semantic_parser import SemanticRecoveryLoop, extract_json, parse_leaf_output
from omniroute_delegation.l3w_delegate import L3WConfig, L3WDelegate, L3WSession
from omniroute_delegation.task_builder import TaskBuilder
from omniroute_delegation.worker_manager import (
    MemoryMode,
    MemoryScope,
    MemoryScopeConfig,
    SandboxPolicy,
    WorkerManager,
    WorkspaceSandbox,
)

__all__ = [
    "AuditContract", "CredentialLeakPreventedError", "DelegateKind", "DelegationGateway",
    "DelegationTask", "ExecutionState", "L3TDelegate", "L3WDelegate", "LeafContract",
    "LeafFinding", "MCPClient", "SchemaValidator", "SchemaViolationError",
    "SemanticCoverageFailedError", "SemanticRecoveryLoop", "TaskBuilder", "ToolContract",
    "TransportContract", "WorkerManager", "WorkspaceSandbox", "extract_json",
    "parse_leaf_output", "__version__",
]
