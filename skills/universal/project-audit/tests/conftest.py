"""
conftest.py — Shared fixtures for project-audit test suite

All fixtures are deterministic and isolated (tmp_path per test).
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from project_audit.models import (
    ApplicabilityDecision,
    AuditPlan,
    AuditWorkItem,
    BudgetEnvelope,
    CredentialAccess,
    EgressDestination,
    EgressPolicy,
    Evidence,
    EvidenceValidity,
    ExecutionPolicy,
    FilesystemAccess,
    MethodologyState,
    NetworkAccess,
    ProjectState,
    Provenance,
    SubmoduleState,
    TargetMode,
    TargetSnapshot,
    TrackedInputFingerprint,
    WorkItemAction,
    WorkingTreeState,
)
from project_audit.state_store import StateStore


FIXED_TS = datetime(2026, 9, 21, 12, 0, 0, tzinfo=timezone.utc)


def make_project_state(
    repo: str = "https://github.com/test/repo",
    revision: str = "abc123def456abc123def456abc123def456abc12",
    tree_state: WorkingTreeState = WorkingTreeState.CLEAN,
) -> ProjectState:
    return ProjectState(
        repository_identity=repo,
        revision_identity=revision,
        working_tree_state=tree_state,
        submodules_state=(),
        tracked_input_fingerprints=(
            TrackedInputFingerprint(
                path="pyproject.toml",
                fingerprint="a" * 64,
            ),
        ),
    )


def make_methodology_state() -> MethodologyState:
    return MethodologyState(
        audit_contract_version="1.0.0",
        auditor_versions={"security-audit": "0.1.0"},
        policy_version="1.0.0",
    )


@pytest.fixture
def project_state() -> ProjectState:
    return make_project_state()


@pytest.fixture
def methodology_state() -> MethodologyState:
    return make_methodology_state()


@pytest.fixture
def target_snapshot(project_state, methodology_state) -> TargetSnapshot:
    return TargetSnapshot.create(
        target_mode=TargetMode.COMMIT,
        project_state=project_state,
        methodology_state=methodology_state,
    )


@pytest.fixture
def execution_policy() -> ExecutionPolicy:
    return ExecutionPolicy(
        filesystem=FilesystemAccess.READ_ONLY,
        network=NetworkAccess.DISABLED,
        credentials=CredentialAccess.NONE,
    )


@pytest.fixture
def egress_policy() -> EgressPolicy:
    return EgressPolicy(
        destination=EgressDestination.LOCAL_ONLY,
        allow_sensitive=False,
    )


@pytest.fixture
def audit_plan(target_snapshot, execution_policy, egress_policy) -> AuditPlan:
    plan_id = str(uuid.uuid4())
    return AuditPlan(
        plan_id=plan_id,
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        requested_scope=["security", "code"],
        applicability_decisions=[
            ApplicabilityDecision(
                domain="security",
                applicable=True,
                decision_basis="Security audit applicable — auth module present",
                evidence_refs=[],
            ),
            ApplicabilityDecision(
                domain="code",
                applicable=True,
                decision_basis="Code audit applicable — Python sources detected",
                evidence_refs=[],
            ),
        ],
        resolved_scope=["security", "code"],
        work_items=[],
        execution_policy=execution_policy,
        egress_policy=egress_policy,
        budget_envelope=BudgetEnvelope(max_duration_seconds=300),
    )


def make_work_item(
    plan_id: str,
    auditor: str = "fake-auditor",
    target_surface: str = "src/",
    action: WorkItemAction = WorkItemAction.REAUDIT,
    execution_policy: ExecutionPolicy = None,
    egress_policy: EgressPolicy = None,
) -> AuditWorkItem:
    if execution_policy is None:
        execution_policy = ExecutionPolicy(
            filesystem=FilesystemAccess.READ_ONLY,
            network=NetworkAccess.DISABLED,
            credentials=CredentialAccess.NONE,
        )
    if egress_policy is None:
        egress_policy = EgressPolicy(
            destination=EgressDestination.LOCAL_ONLY,
            allow_sensitive=False,
        )
    return AuditWorkItem(
        work_item_id=str(uuid.uuid4()),
        plan_ref=plan_id,
        auditor=auditor,
        target_surface=target_surface,
        action=action,
        decision_basis="Test work item",
        effective_execution_policy=execution_policy,
        data_egress_policy=egress_policy,
    )


@pytest.fixture
def work_item(audit_plan, execution_policy, egress_policy) -> AuditWorkItem:
    return make_work_item(
        plan_id=audit_plan.plan_id,
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )


def make_evidence(
    evidence_id: str = None,
    target_snapshot_ref: str = "a" * 64,
    work_item_ref: str = None,
) -> Evidence:
    return Evidence(
        evidence_id=evidence_id or str(uuid.uuid4()),
        target_snapshot_ref=target_snapshot_ref,
        work_item_ref=work_item_ref or str(uuid.uuid4()),
        source_refs=("src/auth.py:10-20",),
        dependencies=("pyproject.toml",),
        validity=EvidenceValidity.VALID,
        provenance=Provenance(actor="test", generated_at=FIXED_TS),
        fingerprint="b" * 64,
    )


@pytest.fixture
def evidence(work_item, target_snapshot) -> Evidence:
    return make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )


@pytest.fixture
def state_store(tmp_path) -> StateStore:
    return StateStore(tmp_path / "audit_store")
