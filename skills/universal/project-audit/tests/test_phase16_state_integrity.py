from __future__ import annotations

import dataclasses
import uuid

import pytest

from project_audit.fake_auditor import FakeAuditorResult, FakeAuditorWithSnapshot
from project_audit.models import (
    AuditRun,
    ExecutionState,
    ImmutablePlanError,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    WorkItemFailureState,
)
from project_audit.orchestrator import Orchestrator, OrchestratorError
from project_audit.validators import validate_run_work_item_references
from tests.conftest import make_work_item


def test_commit_work_item_requires_existing_plan(
    orchestrator, execution_policy, egress_policy
):
    work_item = make_work_item(
        plan_id=str(uuid.uuid4()),
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )

    with pytest.raises(OrchestratorError, match="does not resolve to a persisted AuditPlan"):
        orchestrator.commit_work_item(work_item)

    with pytest.raises(Exception):
        orchestrator.store.load_work_item(work_item.work_item_id)


def test_commit_work_item_enforces_semantic_state_gate(
    orchestrator, audit_plan, target_snapshot, execution_policy, egress_policy
):
    work_item = make_work_item(
        plan_id=audit_plan.plan_id,
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    audit_plan.work_items = [work_item]

    orchestrator.commit_snapshot(target_snapshot)
    orchestrator.freeze_and_commit_plan(audit_plan)

    work_item.execution_state = ExecutionState.RUNNING
    # RUNNING without an unfinished Attempt violates the WorkItem state machine.
    with pytest.raises(OrchestratorError, match="WORK_ITEM_RUNNING_NO_ATTEMPTS"):
        orchestrator.commit_work_item(work_item)

    with pytest.raises(Exception):
        orchestrator.store.load_work_item(work_item.work_item_id)


def test_frozen_plan_rejects_top_level_and_nested_mutation(audit_plan):
    audit_plan.freeze()

    with pytest.raises(ImmutablePlanError):
        audit_plan.resolved_scope = ("hacked",)

    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        audit_plan.applicability_decisions[0].applicable = audit_plan.applicability_decisions[0].applicable

    with pytest.raises(AttributeError):
        audit_plan.applicability_decisions[0].evidence_refs.append("hacked")

    with pytest.raises(dataclasses.FrozenInstanceError):
        audit_plan.execution_policy = dataclasses.replace(
            audit_plan.execution_policy,
            max_retries=99,
        )


def test_reloaded_frozen_plan_preserves_immutable_collections(
    orchestrator, audit_plan, target_snapshot
):
    orchestrator.commit_snapshot(target_snapshot)
    audit_plan.freeze()
    orchestrator.store.save_plan(audit_plan)

    loaded = orchestrator.store.load_plan(audit_plan.plan_id, work_items=[])

    assert isinstance(loaded.requested_scope, tuple)
    assert isinstance(loaded.applicability_decisions, tuple)
    assert isinstance(loaded.resolved_scope, tuple)
    assert isinstance(loaded.work_items, tuple)

    with pytest.raises(ImmutablePlanError):
        loaded.requested_scope = ("hacked",)


def test_run_plan_work_item_graph_cannot_use_a_subset(
    audit_plan, target_snapshot, execution_policy, egress_policy
):
    first = make_work_item(
        plan_id=audit_plan.plan_id,
        target_surface="security/authentication",
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    second = make_work_item(
        plan_id=audit_plan.plan_id,
        target_surface="security/authorization",
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    audit_plan.work_items = [first, second]

    run = AuditRun(
        run_id=str(uuid.uuid4()),
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        plan_ref=audit_plan.plan_id,
        work_item_refs=[first.work_item_id],
        execution_completeness=RunExecutionCompleteness.COMPLETE,
        coverage_completeness=RunCoverageCompleteness.FULL,
        failure_state=RunFailureState.NONE,
        budget_state=RunBudgetState.HEALTHY,
        publication_state=RunPublicationState.NOT_PUBLISHED,
    )

    result = validate_run_work_item_references(run, audit_plan, [first])

    assert result.is_error
    assert result.code == "RUN_PLAN_WORK_ITEM_SET_MISMATCH"


def test_vertical_slice_materializes_plan_work_item_closure(
    orchestrator, target_snapshot, execution_policy, egress_policy
):
    from project_audit.models import ApplicabilityDecision, ApplicabilityState, AuditPlan

    plan = AuditPlan(
        plan_id=str(uuid.uuid4()),
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        requested_scope=["security"],
        applicability_decisions=[
            ApplicabilityDecision(
                domain="security",
                applicable=ApplicabilityState.APPLICABLE,
                decision_basis="Phase 16 fixture",
                evidence_refs=[],
            )
        ],
        resolved_scope=["security"],
        work_items=[],
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    work_item = make_work_item(
        plan_id=plan.plan_id,
        target_surface="security/authentication",
        execution_policy=execution_policy,
        egress_policy=egress_policy,
    )
    auditor = FakeAuditorWithSnapshot(
        snapshot_fingerprint=target_snapshot.snapshot_fingerprint,
        result=FakeAuditorResult.SUCCESS,
    )

    orchestrator.execute_vertical_slice(
        snapshot=target_snapshot,
        plan=plan,
        work_items=[work_item],
        auditor=auditor,
    )

    assert [item.work_item_id for item in plan.work_items] == [work_item.work_item_id]
    assert isinstance(plan.work_items, tuple)
