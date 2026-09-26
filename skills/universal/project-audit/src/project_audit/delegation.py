"""
delegation.py — Delegation Boundary & Worker Port

Provides the abstraction over execution workers (LLMs, deterministic scripts).
This ensures the Core Engine remains unaware of specific LLM providers,
OmniRoute routing, or concrete HTTP/MCP transports.

Architectural boundaries:
  Core Engine (AuditWorkItem) → WorkerPort → DelegationRequest → Gateway (OmniRoute/Fake)
"""

from __future__ import annotations

import abc
import dataclasses
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .models import AuditWorkItem, Evidence, ExecutionReceipt, ExecutionPolicy, Provenance, EvidenceValidity
if TYPE_CHECKING:
    from omniroute_delegation.contracts import AuditContract
from .validators import validate_egress_policy


class DelegationStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"  # Intercepted by policy/sandbox


@dataclasses.dataclass(frozen=True)
class DelegationRequest:
    """The normalized request payload sent across the boundary."""
    request_id: str
    work_item_ref: str
    target_surface: str
    auditor_name: str
    context_payload: Dict[str, Any]
    execution_policy: ExecutionPolicy

    @classmethod
    def from_work_item(cls, work_item: AuditWorkItem, context_payload: Dict[str, Any]) -> DelegationRequest:
        return cls(
            request_id=str(uuid.uuid4()),
            work_item_ref=work_item.work_item_id,
            target_surface=work_item.target_surface,
            auditor_name=work_item.auditor,
            context_payload=context_payload,
            execution_policy=work_item.effective_execution_policy,
        )


@dataclasses.dataclass(frozen=True)
class DelegationResult:
    """The normalized response payload received across the boundary."""
    request_id: str
    status: DelegationStatus
    output_payload: Optional[Dict[str, Any]]
    error_message: Optional[str]
    provider_info: Optional[str]
    usage_tokens: Optional[int]
    audit_contract: Optional["AuditContract"] = None


@dataclasses.dataclass(frozen=True)
class WorkerExecution:
    """Execution envelope preserving backward-compatible tuple unpacking."""

    receipt: ExecutionReceipt
    evidence: Optional[Evidence]
    result: Optional[DelegationResult]

    def __iter__(self):
        yield self.receipt
        yield self.evidence


class DelegationBackend(abc.ABC):
    """
    Abstract gateway to the execution layer.
    Can be backed by OmniRoute MCP, a mock, or a direct model call.
    """

    @abc.abstractmethod
    def delegate(self, request: DelegationRequest) -> DelegationResult:
        """Synchronously dispatch the request and await the result."""
        pass


class WorkerPort:
    """
    The port used by the Orchestrator/Auditor to send work across the boundary.
    It bridges the domain (AuditWorkItem) to the infrastructure (DelegationBackend).
    """

    def __init__(self, backend: DelegationBackend, actor_identity: str):
        self.backend = backend
        self.actor_identity = actor_identity

    def execute_delegation(
        self,
        work_item: AuditWorkItem,
        context_payload: Dict[str, Any],
        started_at: datetime,
        data_is_sensitive: Optional[bool] = None,
        target_snapshot_ref: Optional[str] = None,
    ) -> WorkerExecution:
        """
        Translates a WorkItem into a DelegationRequest, executes it via the backend,
        and translates the DelegationResult back into an ExecutionReceipt and Evidence.
        """
        request = DelegationRequest.from_work_item(work_item, context_payload)
        
        # Security Egress Check
        # Unknown sensitivity fails closed before any delegation.
        egress_check = validate_egress_policy(work_item, data_is_sensitive=data_is_sensitive)
        if egress_check.is_error:
            finished_at = datetime.now(timezone.utc)
            receipt = ExecutionReceipt(
                receipt_id=str(uuid.uuid4()),
                work_item_ref=work_item.work_item_id,
                command="omniroute-delegation",
                arguments=[request.request_id],
                policy_snapshot=work_item.effective_execution_policy,
                started_at=started_at,
                finished_at=finished_at,
                exit_code=126,
                artifact_refs=[],
                environment_summary=f"WorkerPort: {self.actor_identity} | error: {egress_check.message}",
            )
            return WorkerExecution(receipt, None, None)

        result = self.backend.delegate(request)
        finished_at = datetime.now(timezone.utc)

        # 1. Translate Status to Exit Code
        if result.status == DelegationStatus.BLOCKED:
            exit_code = 126
        elif result.status == DelegationStatus.SUCCESS:
            exit_code = 0
        else:
            exit_code = 1  # FAILED, TIMEOUT, etc.

        receipt = ExecutionReceipt(
            receipt_id=str(uuid.uuid4()),
            work_item_ref=work_item.work_item_id,
            command="omniroute-delegation",
            arguments=[request.request_id],
            policy_snapshot=work_item.effective_execution_policy,
            started_at=started_at,
            finished_at=finished_at,
            exit_code=exit_code,
            artifact_refs=[],
            environment_summary=f"WorkerPort: {self.actor_identity} | error: {result.error_message}" if result.error_message else None,
        )

        # 2. Build Evidence on success
        evidence = None
        if result.status == DelegationStatus.SUCCESS and result.output_payload and target_snapshot_ref:
            import hashlib
            
            # Deterministic serialization for fingerprint
            raw = json.dumps(result.output_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
            fp = hashlib.sha256(raw).hexdigest()

            evidence = Evidence(
                evidence_id=str(uuid.uuid4()),
                target_snapshot_ref=target_snapshot_ref,
                work_item_ref=work_item.work_item_id,
                source_refs=(),
                dependencies=(),
                validity=EvidenceValidity.NOT_DETERMINABLE,
                provenance=Provenance(
                    actor=f"{self.actor_identity} via {result.provider_info or 'unknown'}",
                    generated_at=finished_at,
                ),
                fingerprint=fp,
            )

        return WorkerExecution(receipt, evidence, result)
