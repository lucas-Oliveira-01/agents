"""Pydantic contracts for OmniRoute delegation trust boundaries."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExecutionState(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    PARTIAL_COVERAGE = "PARTIAL_COVERAGE"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    CANCELLED = "CANCELLED"
    SUCCESS = "SUCCESS"


class DelegateKind(str, Enum):
    L3T = "L3T"
    L3W = "L3W"


class TransportContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    jsonrpc: str = "2.0"
    request_id: Union[int, str]
    method: str
    params: Optional[Dict[str, Any]] = None


class ToolContract(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")
    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class DelegationTask(BaseModel):
    """Internal English contract mapped to the Portuguese MCP wire contract."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    task: str = Field(min_length=1)
    profile: Optional[str] = None
    context: Optional[str] = None
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    cache_mode: Optional[str] = None
    cache_key: Optional[str] = None
    max_tokens: Optional[int] = Field(default=None, ge=1)
    temperature: Optional[float] = Field(default=None, ge=0, le=2)

    @field_validator("cache_mode")
    @classmethod
    def validate_cache_mode(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and value not in {"native", "bypass", "deterministic"}:
            raise ValueError("Invalid cache_mode")
        return value

    def to_wire(self) -> Dict[str, Any]:
        return self.model_dump(exclude_none=True)


class LeafFinding(BaseModel):
    model_config = ConfigDict(extra="allow")

    title: str = Field(min_length=1)
    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    confidence: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    evidence: Optional[str] = None
    raw_severity: Optional[str] = None
    normalization_rule: Optional[str] = None


class LeafContract(BaseModel):
    """Semantic result produced by an L3 delegate."""

    model_config = ConfigDict(extra="allow")
    findings: List[LeafFinding] = Field(default_factory=list)
    raw_output: Optional[str] = None


class AuditContract(BaseModel):
    """Canonical result consumed by the orchestrator."""

    model_config = ConfigDict(extra="forbid")
    state: ExecutionState
    findings: List[LeafFinding] = Field(default_factory=list)
    raw_errors: List[Dict[str, Any]] = Field(default_factory=list)
    attempts: int = 0
    delegate_kind: DelegateKind = DelegateKind.L3T
    leaf: Optional[LeafContract] = None
    worker_id: Optional[str] = None
    workspace_dir: Optional[str] = None
    changed_files: List[str] = Field(default_factory=list)


class L3TDelegate:
    """Stateless delegate interface: request in, semantic payload out."""

    kind = DelegateKind.L3T

    def execute(self, task: DelegationTask) -> Any:
        raise NotImplementedError


class L3WDelegate:
    """Stateful worker interface with isolated workspace and harness."""

    kind = DelegateKind.L3W

    async def execute(
        self,
        task: DelegationTask,
        workspace_dir: str,
        harness: Any,
    ) -> AuditContract:
        raise NotImplementedError
