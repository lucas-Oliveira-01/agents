from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterable, Tuple

from .classifiers import ApplicabilityDecision as ClassifiedApplicability
from .classifiers import ApplicabilityState, FileClassification, classify_task
from .discovery import DiscoverySnapshot
from .models import (
    ApplicabilityDecision as CanonicalApplicabilityDecision,
    AuditPlan,
    AuditWorkItem,
    CredentialAccess,
    EgressDestination,
    EgressPolicy,
    ExecutionPolicy,
    FilesystemAccess,
    MethodologyState,
    NetworkAccess,
    ProjectState,
    TargetMode,
    TargetSnapshot,
    TrackedInputFingerprint,
    WorkItemAction,
    WorkingTreeState,
)

AUDIT_CONTRACT_VERSION = "project-audit/1"
POLICY_VERSION = "deterministic-first/1"
IMPLEMENTER_VERSION = "project-audit-0.1.0"


@dataclass(frozen=True)
class PreparedAudit:
    snapshot: TargetSnapshot
    plan: AuditPlan
    work_items: Tuple[AuditWorkItem, ...]
    file_classifications: Tuple[FileClassification, ...]
    applicability: Tuple[ClassifiedApplicability, ...]


def _working_tree_state(snapshot: DiscoverySnapshot) -> WorkingTreeState:
    if not snapshot.git.is_repository:
        return WorkingTreeState.DIRTY
    if snapshot.git.working_tree_dirty:
        return WorkingTreeState.DIRTY
    return WorkingTreeState.CLEAN


def _input_fingerprints(snapshot: DiscoverySnapshot, target_mode: TargetMode) -> Tuple[TrackedInputFingerprint, ...]:
    tracked = set(snapshot.git.tracked_paths)
    rows = []
    for item in snapshot.files:
        if target_mode == TargetMode.COMMIT and snapshot.git.is_repository and item.path not in tracked:
            continue
        if item.binary or not item.sha256:
            continue
        rows.append(TrackedInputFingerprint(item.path, item.sha256))
    return tuple(sorted(rows, key=lambda item: item.path))


def _default_policies() -> Tuple[ExecutionPolicy, EgressPolicy]:
    execution = ExecutionPolicy(
        filesystem=FilesystemAccess.READ_ONLY,
        network=NetworkAccess.DISABLED,
        credentials=CredentialAccess.NONE,
        timeout_ms=60_000,
        max_retries=1,
    )
    egress = EgressPolicy(destination=EgressDestination.LOCAL_ONLY, allow_sensitive=False)
    return execution, egress


def build_target_snapshot(snapshot: DiscoverySnapshot, target_mode: TargetMode = TargetMode.WORKTREE) -> TargetSnapshot:
    project_state = ProjectState(
        repository_identity=snapshot.git.remote_url or str(snapshot.root),
        revision_identity=snapshot.git.revision or "NOT_AVAILABLE",
        working_tree_state=_working_tree_state(snapshot),
        submodules_state=(),
        tracked_input_fingerprints=_input_fingerprints(snapshot, target_mode),
    )
    methodology = MethodologyState(
        audit_contract_version=AUDIT_CONTRACT_VERSION,
        auditor_versions={"project-audit": IMPLEMENTER_VERSION},
        policy_version=POLICY_VERSION,
    )
    return TargetSnapshot.create(target_mode, project_state, methodology)


def build_plan(snapshot: TargetSnapshot, applicability: Iterable[ClassifiedApplicability]) -> Tuple[AuditPlan, Tuple[AuditWorkItem, ...]]:
    execution_policy, egress_policy = _default_policies()
    plan_id = str(uuid.uuid4())
    decisions = tuple(applicability)
    applicable = [d for d in decisions if d.state == ApplicabilityState.APPLICABLE]
    uncertain = [d for d in decisions if d.state == ApplicabilityState.NOT_DETERMINABLE]
    resolved = sorted({d.category for d in applicable} | {d.category for d in uncertain})
    requested_scope = ["FULL"]

    work_items = []
    for decision in sorted(decisions, key=lambda item: (item.category, item.subcategory)):
        if decision.state == ApplicabilityState.NOT_APPLICABLE:
            continue
        task = f"Audit {decision.category}/{decision.subcategory}"
        task_class = classify_task(task)
        evidence = ", ".join(decision.evidence_paths[:3]) or "no direct path evidence"
        work_items.append(
            AuditWorkItem(
                work_item_id=str(uuid.uuid4()),
                plan_ref=plan_id,
                auditor="project-audit/single-agent",
                target_surface=f"{decision.category}/{decision.subcategory}",
                action=WorkItemAction.REAUDIT,
                decision_basis=(
                    f"Applicability={decision.state.value}; {decision.reason}; "
                    f"task_kind={task_class.kind.value}; deterministic_first=true; evidence={evidence}"
                ),
                effective_execution_policy=execution_policy,
                data_egress_policy=egress_policy,
            )
        )

    canonical_decisions = [
        CanonicalApplicabilityDecision(
            domain=f"{decision.category}/{decision.subcategory}",
            applicable=decision.state != ApplicabilityState.NOT_APPLICABLE,
            decision_basis=(
                f"state={decision.state.value}; {decision.reason}; "
                f"evidence={', '.join(decision.evidence_paths[:3]) or 'none'}"
            ),
            evidence_refs=[],
        )
        for decision in decisions
    ]

    plan = AuditPlan(
        plan_id=plan_id,
        target_snapshot_ref=snapshot.snapshot_fingerprint,
        requested_scope=requested_scope,
        applicability_decisions=canonical_decisions,
        resolved_scope=resolved,
        work_items=work_items,
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    return plan, tuple(work_items)


def prepare_audit(discovery: DiscoverySnapshot, files: Tuple[FileClassification, ...], applicability: Tuple[ClassifiedApplicability, ...], target_mode: TargetMode = TargetMode.WORKTREE) -> PreparedAudit:
    snapshot = build_target_snapshot(discovery, target_mode=target_mode)
    plan, work_items = build_plan(snapshot, applicability)
    return PreparedAudit(snapshot, plan, work_items, files, applicability)
