"""
models.py — Domain Types for the project-audit Core Engine V1

All types are derived directly from the Canonical Data Model:
  docs/references/canonical-data-model.md

And physically validated against:
  docs/references/schemas/

Immutability contract:
  - TargetSnapshot: frozen dataclass — immutable after creation (ADR-06)
  - Evidence: frozen dataclass — immutable, append-only (canonical-data-model §4)
  - FindingFingerprint: frozen dataclass — stable identity descriptor
  - AuditPlan: mutable, but has a freeze() method; raises after frozen_at is set (canonical §2)
  - AuditWorkItem: mutable state machine (canonical §3)
  - AuditRun: mutable aggregate (canonical §5)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations — derived from JSON schemas (additionalProperties: false)
# ---------------------------------------------------------------------------


class TargetMode(str, Enum):
    COMMIT = "COMMIT"
    WORKTREE = "WORKTREE"
    EXPLICIT_SNAPSHOT = "EXPLICIT_SNAPSHOT"


class WorkingTreeState(str, Enum):
    CLEAN = "CLEAN"
    DIRTY = "DIRTY"
    UNTRACKED_ONLY = "UNTRACKED_ONLY"


class WorkItemAction(str, Enum):
    """Incremental decision for a WorkItem. INVALIDATE is a property of old
    evidence, not an action on the WorkItem (canonical-data-model §3, ADR-04)."""

    REUSE = "REUSE"
    REVALIDATE = "REVALIDATE"
    REAUDIT = "REAUDIT"


class ExecutionState(str, Enum):
    """Valid state machine transitions: PLANNED -> RUNNING -> TERMINATED."""

    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    TERMINATED = "TERMINATED"


class WorkItemFailureState(str, Enum):
    NONE = "NONE"
    INFRA_ERROR = "INFRA_ERROR"
    SAFETY_BLOCK = "SAFETY_BLOCK"
    SCHEMA_VIOLATION = "SCHEMA_VIOLATION"
    TIMEOUT = "TIMEOUT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class RunExecutionCompleteness(str, Enum):
    """Tracks whether all WorkItems reached a terminal state (ADR-07, canonical §5)."""

    PLANNED = "PLANNED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class RunCoverageCompleteness(str, Enum):
    """Tracks whether the requested_scope was fully covered (canonical §5).
    Separated from execution_completeness — one cannot be derived from the other."""

    PENDING = "PENDING"
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


class RunFailureState(str, Enum):
    NONE = "NONE"
    INFRA_ERROR = "INFRA_ERROR"
    SAFETY_BLOCK = "SAFETY_BLOCK"
    SNAPSHOT_DRIFT = "SNAPSHOT_DRIFT"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


class RunBudgetState(str, Enum):
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    EXHAUSTED = "EXHAUSTED"


class RunPublicationState(str, Enum):
    NOT_PUBLISHED = "NOT_PUBLISHED"
    PUBLISHED_COMPLETE = "PUBLISHED_COMPLETE"
    PUBLISHED_PARTIAL = "PUBLISHED_PARTIAL"


class EvidenceValidity(str, Enum):
    """Validity of evidence against the current TargetSnapshot (ADR-04).
    INVALID ≠ FIXED: invalidated evidence does NOT imply the finding is corrected."""

    VALID = "VALID"
    STALE = "STALE"
    INVALID = "INVALID"
    NOT_DETERMINABLE = "NOT_DETERMINABLE"


class FindingLifecycle(str, Enum):
    NEW = "NEW"
    PERSISTING = "PERSISTING"
    FIXED = "FIXED"
    REGRESSED = "REGRESSED"


class FilesystemAccess(str, Enum):
    READ_ONLY = "read-only"
    TEMPORARY_WRITE = "temporary-write"
    NONE = "none"


class NetworkAccess(str, Enum):
    DISABLED = "disabled"
    RESTRICTED = "restricted"
    FULL = "full"


class CredentialAccess(str, Enum):
    NONE = "none"
    EXPLICIT_ONLY = "explicit-only"


class EgressDestination(str, Enum):
    LOCAL_ONLY = "LOCAL_ONLY"
    APPROVED_EXTERNAL = "APPROVED_EXTERNAL"


# ---------------------------------------------------------------------------
# Value Objects (shared definitions, immutable)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionPolicy:
    """Capability-based execution constraints (ADR-05, shared.schema.json).
    Default is deny-all — callers must explicitly grant capabilities."""

    filesystem: FilesystemAccess = FilesystemAccess.NONE
    network: NetworkAccess = NetworkAccess.DISABLED
    credentials: CredentialAccess = CredentialAccess.NONE
    timeout_ms: Optional[int] = None

    def to_dict(self) -> dict:
        d: dict = {
            "filesystem": self.filesystem.value,
            "network": self.network.value,
            "credentials": self.credentials.value,
        }
        if self.timeout_ms is not None:
            d["timeout_ms"] = self.timeout_ms
        return d


@dataclass(frozen=True)
class EgressPolicy:
    """Data egress control (ADR-05). Default is deny external egress."""

    destination: EgressDestination = EgressDestination.LOCAL_ONLY
    allow_sensitive: bool = False

    def to_dict(self) -> dict:
        return {
            "destination": self.destination.value,
            "allow_sensitive": self.allow_sensitive,
        }


@dataclass(frozen=True)
class Provenance:
    """Attributable provenance of a generation action (shared.schema.json)."""

    actor: str
    generated_at: datetime
    policy_version: Optional[str] = None

    def to_dict(self) -> dict:
        d: dict = {
            "actor": self.actor,
            "generated_at": self.generated_at.isoformat(),
        }
        if self.policy_version is not None:
            d["policy_version"] = self.policy_version
        return d


@dataclass(frozen=True)
class FindingFingerprint:
    """Stable identity descriptor for a finding.
    Does NOT embed description, cause, impact, or recommendation (canonical §4)."""

    domain: str
    control_surface: str
    defect_type: str

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "control_surface": self.control_surface,
            "defect_type": self.defect_type,
        }


# ---------------------------------------------------------------------------
# TargetSnapshot — IMMUTABLE (frozen dataclass, ADR-06, canonical §1)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubmoduleState:
    path: str
    revision: str


@dataclass(frozen=True)
class TrackedInputFingerprint:
    path: str
    fingerprint: str  # sha256 hex, pattern ^[a-f0-9]{64}$


@dataclass(frozen=True)
class ProjectState:
    repository_identity: str
    revision_identity: str
    working_tree_state: WorkingTreeState
    submodules_state: tuple  # tuple[SubmoduleState, ...]
    tracked_input_fingerprints: tuple  # tuple[TrackedInputFingerprint, ...]


@dataclass(frozen=True)
class MethodologyState:
    audit_contract_version: str
    auditor_versions: dict  # frozen — convert from Dict[str, str]
    policy_version: str

    def __post_init__(self):
        import types
        if not isinstance(self.auditor_versions, types.MappingProxyType):
            object.__setattr__(self, "auditor_versions", types.MappingProxyType(dict(self.auditor_versions)))


@dataclass(frozen=True)
class TargetSnapshot:
    """
    Immutable representation of the exact target and methodology being audited.
    Answers: "What exactly is being audited, and under what rules?"

    canonical-data-model.md §1, ADR-06.
    Schema: docs/references/schemas/target-snapshot.schema.json
    """

    target_mode: TargetMode
    project_state: ProjectState
    methodology_state: MethodologyState
    snapshot_fingerprint: str  # sha256, derived deterministically

    @classmethod
    def create(
        cls,
        target_mode: TargetMode,
        project_state: ProjectState,
        methodology_state: MethodologyState,
    ) -> "TargetSnapshot":
        """Factory: computes deterministic snapshot_fingerprint from the state."""
        fp = cls._compute_fingerprint(target_mode, project_state, methodology_state)
        return cls(
            target_mode=target_mode,
            project_state=project_state,
            methodology_state=methodology_state,
            snapshot_fingerprint=fp,
        )

    @staticmethod
    def _compute_fingerprint(
        target_mode: TargetMode,
        project_state: ProjectState,
        methodology_state: MethodologyState,
    ) -> str:
        """Deterministic SHA-256 fingerprint of the snapshot state (canonical §1)."""
        canonical = json.dumps(
            {
                "target_mode": target_mode.value,
                "repository_identity": project_state.repository_identity,
                "revision_identity": project_state.revision_identity,
                "working_tree_state": project_state.working_tree_state.value,
                "submodules_state": sorted(
                    [{"path": s.path, "revision": s.revision} for s in project_state.submodules_state],
                    key=lambda x: x["path"],
                ),
                "tracked_input_fingerprints": sorted(
                    [{"path": t.path, "fingerprint": t.fingerprint} for t in project_state.tracked_input_fingerprints],
                    key=lambda x: x["path"],
                ),
                "audit_contract_version": methodology_state.audit_contract_version,
                "auditor_versions": dict(sorted(methodology_state.auditor_versions.items())),
                "policy_version": methodology_state.policy_version,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict:
        return {
            "snapshot_fingerprint": self.snapshot_fingerprint,
            "target_mode": self.target_mode.value,
            "project_state": {
                "repository_identity": self.project_state.repository_identity,
                "revision_identity": self.project_state.revision_identity,
                "working_tree_state": self.project_state.working_tree_state.value,
                "submodules_state": [
                    {"path": s.path, "revision": s.revision}
                    for s in self.project_state.submodules_state
                ],
                "tracked_input_fingerprints": [
                    {"path": t.path, "fingerprint": t.fingerprint}
                    for t in self.project_state.tracked_input_fingerprints
                ],
            },
            "methodology_state": {
                "audit_contract_version": self.methodology_state.audit_contract_version,
                "auditor_versions": dict(self.methodology_state.auditor_versions),
                "policy_version": self.methodology_state.policy_version,
            },
        }


# ---------------------------------------------------------------------------
# ExecutionReceipt — immutable execution trail (canonical §3 / §WorkItem)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExecutionReceipt:
    """
    Verifiable execution trail for a single worker invocation.
    ExecutionReceipt is evidence of execution, not the audit result.
    """

    receipt_id: str  # uuid
    work_item_ref: str  # uuid
    command: str
    arguments: List[str]
    policy_snapshot: ExecutionPolicy
    started_at: datetime
    finished_at: Optional[datetime]
    exit_code: Optional[int]
    artifact_refs: List[str]
    environment_summary: Optional[str] = None  # non-sensitive summary only

    def to_dict(self) -> dict:
        return {
            "receipt_id": self.receipt_id,
            "work_item_ref": self.work_item_ref,
            "command": self.command,
            "arguments": list(self.arguments),
            "policy_snapshot": self.policy_snapshot.to_dict(),
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "exit_code": self.exit_code,
            "artifact_refs": list(self.artifact_refs),
            "environment_summary": self.environment_summary,
        }


# ---------------------------------------------------------------------------
# Attempt — ordered execution history (canonical §3, ADR-07)
# ---------------------------------------------------------------------------


@dataclass
class Attempt:
    """
    One execution attempt for an AuditWorkItem.

    Attempts are ordered. Attempt #N cannot exist before Attempt #N-1.
    Timestamps must satisfy: attempt[i].started_at >= attempt[i-1].finished_at
    (semantic-validators.md §7)

    History is append-only — never delete or overwrite past attempts.
    """

    attempt_id: str  # uuid
    started_at: datetime
    finished_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    receipt_ref: Optional[str] = None  # uuid, points to ExecutionReceipt

    def finish(self, finished_at: datetime, exit_code: int, receipt_ref: Optional[str] = None) -> None:
        if self.finished_at is not None:
            raise ValueError(f"Attempt {self.attempt_id} is already finished.")
        self.finished_at = finished_at
        self.receipt_ref = receipt_ref

    def fail(self, finished_at: datetime, reason: str, receipt_ref: Optional[str] = None) -> None:
        if self.finished_at is not None:
            raise ValueError(f"Attempt {self.attempt_id} is already finished.")
        self.finished_at = finished_at
        self.failure_reason = reason
        self.receipt_ref = receipt_ref

    @property
    def is_finished(self) -> bool:
        return self.finished_at is not None

    @property
    def is_failed(self) -> bool:
        return self.failure_reason is not None

    def to_dict(self) -> dict:
        d: dict = {
            "attempt_id": self.attempt_id,
            "started_at": self.started_at.isoformat(),
        }
        if self.finished_at is not None:
            d["finished_at"] = self.finished_at.isoformat()
        if self.failure_reason is not None:
            d["failure_reason"] = self.failure_reason
        if self.receipt_ref is not None:
            d["receipt_ref"] = self.receipt_ref
        return d


# ---------------------------------------------------------------------------
# Evidence — IMMUTABLE observation (canonical §4, ADR-04)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Evidence:
    """
    Immutable factual observation. What was objectively observed.

    Evidence does NOT contain: opinion, narrative finding, recommendation,
    presumed cause, or arbitrary severity. (canonical-data-model.md §4)

    INVALID evidence ≠ FIXED finding. (ADR-04, semantic-validators.md §5)
    Schema: docs/references/schemas/evidence.schema.json
    """

    evidence_id: str  # uuid
    target_snapshot_ref: str  # fingerprint (sha256)
    work_item_ref: str  # uuid
    source_refs: tuple  # tuple[str, ...]  — file paths / line refs
    dependencies: tuple  # tuple[str, ...]  — semantic dependency refs
    validity: EvidenceValidity
    provenance: Provenance
    fingerprint: str  # sha256 of the observation content

    def to_dict(self) -> dict:
        return {
            "evidence_id": self.evidence_id,
            "target_snapshot_ref": self.target_snapshot_ref,
            "work_item_ref": self.work_item_ref,
            "source_refs": list(self.source_refs),
            "dependencies": list(self.dependencies),
            "validity": self.validity.value,
            "provenance": self.provenance.to_dict(),
            "fingerprint": self.fingerprint,
        }


# ---------------------------------------------------------------------------
# AuditWorkItem — mutable state machine (canonical §3)
# ---------------------------------------------------------------------------


class ImmutablePlanError(RuntimeError):
    """Raised when a mutating operation is attempted on a frozen AuditPlan."""


class IllegalStateTransitionError(RuntimeError):
    """Raised on invalid state machine transitions (semantic-validators.md §3)."""


class IllegalAttemptOrderError(RuntimeError):
    """Raised when temporal ordering of attempts is violated (semantic-validators.md §7)."""


@dataclass
class AuditWorkItem:
    """
    Atomic unit of execution. Separates immutable task declaration from
    mutable execution state.

    State machine: PLANNED -> RUNNING -> TERMINATED
    Back-transition to RUNNING after TERMINATED requires explicit retry/recovery.
    (semantic-validators.md §3)

    Schema: docs/references/schemas/audit-work-item.schema.json
    """

    work_item_id: str  # uuid
    plan_ref: str  # uuid — must point to an existing AuditPlan
    auditor: str
    target_surface: str
    action: WorkItemAction
    decision_basis: str
    effective_execution_policy: ExecutionPolicy
    data_egress_policy: EgressPolicy
    # Mutable execution state:
    execution_state: ExecutionState = ExecutionState.PLANNED
    failure_state: WorkItemFailureState = WorkItemFailureState.NONE
    attempts: List[Attempt] = field(default_factory=list)
    artifact_refs: List[str] = field(default_factory=list)

    # Valid transitions matrix
    _VALID_TRANSITIONS = {
        ExecutionState.PLANNED: {ExecutionState.RUNNING},
        ExecutionState.RUNNING: {ExecutionState.TERMINATED},
        ExecutionState.TERMINATED: set(),  # terminal; retry needs new attempt
    }

    def transition(self, new_state: ExecutionState) -> None:
        """Apply a validated state transition."""
        allowed = self._VALID_TRANSITIONS.get(self.execution_state, set())
        if new_state not in allowed:
            raise IllegalStateTransitionError(
                f"WorkItem {self.work_item_id}: cannot transition "
                f"{self.execution_state.value} -> {new_state.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        self.execution_state = new_state

    def start_attempt(self, started_at: Optional[datetime] = None) -> Attempt:
        """Create and register a new Attempt. Validates temporal ordering."""
        if self.execution_state == ExecutionState.TERMINATED:
            raise IllegalStateTransitionError(
                f"WorkItem {self.work_item_id} is TERMINATED. "
                "Create a new Attempt via retry_attempt() to re-run."
            )
        now = started_at or datetime.now(timezone.utc)
        if self.attempts:
            last = self.attempts[-1]
            if not last.is_finished:
                raise IllegalStateTransitionError(
                    f"Cannot start Attempt #{len(self.attempts) + 1}: "
                    f"Attempt #{len(self.attempts)} ({last.attempt_id}) is still running."
                )
            if last.finished_at and now < last.finished_at:
                raise IllegalAttemptOrderError(
                    f"Attempt #{len(self.attempts) + 1} start ({now.isoformat()}) "
                    f"is before Attempt #{len(self.attempts)} finish ({last.finished_at.isoformat()})."
                )
        attempt = Attempt(
            attempt_id=str(uuid.uuid4()),
            started_at=now,
        )
        self.attempts.append(attempt)
        if self.execution_state == ExecutionState.PLANNED:
            self.transition(ExecutionState.RUNNING)
        return attempt

    def retry_attempt(self, started_at: Optional[datetime] = None) -> Attempt:
        """Explicit retry: creates a new Attempt after TERMINATED state.
        RETRY ≠ RECOVERY (ADR-07). This is re-execution of the same logical work."""
        if self.execution_state != ExecutionState.TERMINATED:
            raise IllegalStateTransitionError(
                f"retry_attempt() requires TERMINATED state, "
                f"got {self.execution_state.value}"
            )
        # Transition back to RUNNING for retry
        self.execution_state = ExecutionState.RUNNING
        self.failure_state = WorkItemFailureState.NONE
        return self.start_attempt(started_at=started_at)

    def terminate(
        self,
        failure_state: WorkItemFailureState = WorkItemFailureState.NONE,
    ) -> None:
        """Terminate this WorkItem with the given failure state."""
        self.transition(ExecutionState.TERMINATED)
        self.failure_state = failure_state

    def to_dict(self) -> dict:
        return {
            "work_item_id": self.work_item_id,
            "plan_ref": self.plan_ref,
            "auditor": self.auditor,
            "target_surface": self.target_surface,
            "action": self.action.value,
            "decision_basis": self.decision_basis,
            "effective_execution_policy": self.effective_execution_policy.to_dict(),
            "data_egress_policy": self.data_egress_policy.to_dict(),
            "execution_state": self.execution_state.value,
            "failure_state": self.failure_state.value,
            "attempts": [a.to_dict() for a in self.attempts],
            "artifact_refs": list(self.artifact_refs),
        }


# ---------------------------------------------------------------------------
# AuditPlan — frozen-at-start (canonical §2)
# ---------------------------------------------------------------------------


@dataclass
class ApplicabilityDecision:
    domain: str
    applicable: bool
    decision_basis: str
    evidence_refs: List[str]  # uuid refs

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "applicable": self.applicable,
            "decision_basis": self.decision_basis,
            "evidence_refs": list(self.evidence_refs),
        }


@dataclass
class BudgetEnvelope:
    max_tokens: Optional[int] = None
    max_cost_usd: Optional[float] = None
    max_duration_seconds: Optional[int] = None

    def to_dict(self) -> dict:
        d: dict = {}
        if self.max_tokens is not None:
            d["max_tokens"] = self.max_tokens
        if self.max_cost_usd is not None:
            d["max_cost_usd"] = self.max_cost_usd
        if self.max_duration_seconds is not None:
            d["max_duration_seconds"] = self.max_duration_seconds
        return d


@dataclass
class AuditPlan:
    """
    Frozen-at-start execution plan.

    After freeze(), any mutation raises ImmutablePlanError.
    A new plan version must be created instead of mutating a frozen plan.
    (canonical-data-model.md §2, ADR-04)

    Schema: docs/references/schemas/audit-plan.schema.json
    """

    plan_id: str  # uuid
    target_snapshot_ref: str  # fingerprint
    requested_scope: List[str]
    applicability_decisions: List[ApplicabilityDecision]
    resolved_scope: List[str]
    work_items: List[AuditWorkItem]
    execution_policy: ExecutionPolicy
    egress_policy: EgressPolicy
    budget_envelope: Optional[BudgetEnvelope] = None
    frozen_at: Optional[datetime] = None  # None = not yet frozen

    @property
    def is_frozen(self) -> bool:
        return self.frozen_at is not None

    def freeze(self, at: Optional[datetime] = None) -> None:
        """Freeze the plan. Raises if already frozen."""
        if self.is_frozen:
            raise ImmutablePlanError(
                f"AuditPlan {self.plan_id} is already frozen at {self.frozen_at.isoformat()}."
            )
        self.frozen_at = at or datetime.now(timezone.utc)
        # Deep immutability: convert mutable collections to tuples
        if hasattr(self, "requested_scope"):
            self.requested_scope = tuple(self.requested_scope)  # type: ignore
        if hasattr(self, "applicability_decisions"):
            self.applicability_decisions = tuple(self.applicability_decisions)  # type: ignore
        if hasattr(self, "resolved_scope"):
            self.resolved_scope = tuple(self.resolved_scope)  # type: ignore
        if hasattr(self, "work_items"):
            self.work_items = tuple(self.work_items)  # type: ignore

    def _assert_mutable(self, operation: str) -> None:
        if self.is_frozen:
            raise ImmutablePlanError(
                f"Cannot {operation}: AuditPlan {self.plan_id} is frozen since {self.frozen_at.isoformat()}."
            )

    def add_work_item(self, item: AuditWorkItem) -> None:
        self._assert_mutable("add_work_item")
        self.work_items.append(item)

    def to_dict(self) -> dict:
        d: dict = {
            "plan_id": self.plan_id,
            "target_snapshot_ref": self.target_snapshot_ref,
            "requested_scope": list(self.requested_scope),
            "applicability_decisions": [a.to_dict() for a in self.applicability_decisions],
            "resolved_scope": list(self.resolved_scope),
            "work_items": [{"work_item_id": wi.work_item_id} for wi in self.work_items],
            "execution_policy": self.execution_policy.to_dict(),
            "egress_policy": self.egress_policy.to_dict(),
        }
        if self.frozen_at is not None:
            d["frozen_at"] = self.frozen_at.isoformat()
        if self.budget_envelope is not None:
            d["budget_envelope"] = self.budget_envelope.to_dict()
        return d


# ---------------------------------------------------------------------------
# AuditRun — mutable aggregate (canonical §5)
# ---------------------------------------------------------------------------


@dataclass
class AuditRun:
    """
    Mutable aggregate tracking what actually happened during execution.

    Uses references, not embedding. Separates:
      - previous_run_ref: standard incremental context
      - recovery_from_ref: reconciliation from an interrupted run
    These are NEVER equivalent (ADR-07, canonical §5).

    Separates:
      - execution_completeness: all WorkItems finalized?
      - coverage_completeness: full requested_scope covered?
    These CANNOT be derived from one another (canonical §5, semantic-validators §6).

    Schema: docs/references/schemas/audit-run.schema.json
    """

    run_id: str  # uuid
    target_snapshot_ref: str  # fingerprint
    plan_ref: str  # uuid
    work_item_refs: List[str]  # uuids
    # State vectors (all separated, never auto-derived from each other):
    execution_completeness: RunExecutionCompleteness = RunExecutionCompleteness.PLANNED
    coverage_completeness: RunCoverageCompleteness = RunCoverageCompleteness.PENDING
    failure_state: RunFailureState = RunFailureState.NONE
    budget_state: RunBudgetState = RunBudgetState.HEALTHY
    publication_state: RunPublicationState = RunPublicationState.NOT_PUBLISHED
    artifact_refs: List[str] = field(default_factory=list)
    # Lineage (optional but semantically distinct)
    previous_run_ref: Optional[str] = None   # incremental: reference to older run
    recovery_from_ref: Optional[str] = None  # recovery: reference to interrupted run

    def to_dict(self) -> dict:
        d: dict = {
            "run_id": self.run_id,
            "target_snapshot_ref": self.target_snapshot_ref,
            "plan_ref": self.plan_ref,
            "execution_completeness": self.execution_completeness.value,
            "coverage_completeness": self.coverage_completeness.value,
            "failure_state": self.failure_state.value,
            "budget_state": self.budget_state.value,
            "publication_state": self.publication_state.value,
            "work_item_refs": list(self.work_item_refs),
            "artifact_refs": list(self.artifact_refs),
        }
        if self.previous_run_ref is not None:
            d["previous_run_ref"] = self.previous_run_ref
        if self.recovery_from_ref is not None:
            d["recovery_from_ref"] = self.recovery_from_ref
        return d
