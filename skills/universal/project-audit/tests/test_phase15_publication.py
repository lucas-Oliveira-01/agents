from pathlib import Path
from uuid import uuid4

import pytest

from project_audit.models import (
    ApplicabilityDecision,
    ApplicabilityState,
    AuditPlan,
    AuditRun,
    AuditWorkItem,
    BudgetEnvelope,
    CredentialAccess,
    EgressDestination,
    EgressPolicy,
    Evidence,
    EvidenceValidity,
    ExecutionPolicy,
    ExecutionState,
    FilesystemAccess,
    NetworkAccess,
    Provenance,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    WorkItemAction,
    WorkItemFailureState,
)
from project_audit.orchestrator import Orchestrator, OrchestratorError, PublicationError
from project_audit.planner import build_target_snapshot
from project_audit.discovery import discover
from project_audit.state_store import StateStore


def _complete_graph(tmp_path: Path):
    target = tmp_path / "target"
    (target / "src").mkdir(parents=True)
    (target / "src/app.py").write_text("print('ok')\n", encoding="utf-8")

    discovery = discover(str(target))
    snapshot = build_target_snapshot(discovery)

    execution_policy = ExecutionPolicy(
        filesystem=FilesystemAccess.READ_ONLY,
        network=NetworkAccess.DISABLED,
        credentials=CredentialAccess.NONE,
    )
    egress_policy = EgressPolicy(
        destination=EgressDestination.LOCAL_ONLY,
        allow_sensitive=False,
    )
    plan_id = str(uuid4())
    plan = AuditPlan(
        plan_id=plan_id,
        target_snapshot_ref=snapshot.snapshot_fingerprint,
        requested_scope=["FULL"],
        applicability_decisions=[
            ApplicabilityDecision(
                domain="CODE_QUALITY/STATIC_REVIEW",
                applicable=ApplicabilityState.APPLICABLE,
                decision_basis="Phase 15 fixture",
                evidence_refs=[],
            )
        ],
        resolved_scope=["CODE_QUALITY"],
        work_items=[],
        execution_policy=execution_policy,
        egress_policy=egress_policy,
        budget_envelope=BudgetEnvelope(max_duration_seconds=300),
    )
    work_item = AuditWorkItem(
        work_item_id=str(uuid4()),
        plan_ref=plan_id,
        auditor="phase15-fixture",
        target_surface="CODE_QUALITY/STATIC_REVIEW",
        action=WorkItemAction.REAUDIT,
        decision_basis="Phase 15 fixture",
        effective_execution_policy=execution_policy,
        data_egress_policy=egress_policy,
    )
    plan.work_items = [work_item]

    orchestrator = Orchestrator(StateStore(target / ".audit" / "runs"))
    orchestrator.commit_snapshot(snapshot)
    orchestrator.freeze_and_commit_plan(plan)

    work_item.start_attempt()
    work_item.attempts[-1].finish(work_item.attempts[-1].started_at, exit_code=0)
    work_item.terminate(failure_state=WorkItemFailureState.NONE)
    orchestrator.commit_work_item(work_item)

    evidence = Evidence(
        evidence_id=str(uuid4()),
        target_snapshot_ref=snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
        source_refs=("src/app.py",),
        dependencies=(),
        validity=EvidenceValidity.VALID,
        provenance=Provenance(actor="phase15-fixture", generated_at=work_item.attempts[-1].finished_at),
        fingerprint="a" * 64,
    )
    orchestrator.commit_evidence(evidence, work_item)

    output = target / "audit-output"
    output.mkdir()
    artifact_refs = []
    for name in ("00_inventory.md", "01_coverage.md", "02_analytical.md", "03_audit_ledger.md"):
        p = output / name
        p.write_text(name + "\n", encoding="utf-8")
        artifact_refs.append(str(p))

    run = AuditRun(
        run_id=str(uuid4()),
        target_snapshot_ref=snapshot.snapshot_fingerprint,
        plan_ref=plan.plan_id,
        work_item_refs=[work_item.work_item_id],
        execution_completeness=RunExecutionCompleteness.COMPLETE,
        coverage_completeness=RunCoverageCompleteness.FULL,
        failure_state=RunFailureState.NONE,
        budget_state=RunBudgetState.HEALTHY,
        publication_state=RunPublicationState.NOT_PUBLISHED,
        artifact_refs=artifact_refs,
    )
    orchestrator.commit_run(run, plan, [work_item])
    return orchestrator, run, plan, [work_item], [evidence], snapshot


def test_publish_run_crosses_publication_barrier(tmp_path: Path) -> None:
    orchestrator, run, plan, work_items, evidence, snapshot = _complete_graph(tmp_path)

    published = orchestrator.publish_run(
        run,
        plan,
        work_items,
        evidence,
        snapshot.snapshot_fingerprint,
    )

    assert published.publication_state == RunPublicationState.PUBLISHED_COMPLETE
    persisted = orchestrator.store.load_run(run.run_id)
    assert persisted.publication_state == RunPublicationState.PUBLISHED_COMPLETE


def test_publish_run_is_idempotent(tmp_path: Path) -> None:
    orchestrator, run, plan, work_items, evidence, snapshot = _complete_graph(tmp_path)

    first = orchestrator.publish_run(
        run, plan, work_items, evidence, snapshot.snapshot_fingerprint
    )
    second = orchestrator.publish_run(
        run, plan, work_items, evidence, snapshot.snapshot_fingerprint
    )

    assert first.run_id == second.run_id
    assert second.publication_state == RunPublicationState.PUBLISHED_COMPLETE


def test_publish_run_rejects_incomplete_execution(tmp_path: Path) -> None:
    orchestrator, run, plan, work_items, evidence, snapshot = _complete_graph(tmp_path)
    run.execution_completeness = RunExecutionCompleteness.PARTIAL

    with pytest.raises(PublicationError, match="publication barrier"):
        orchestrator.publish_run(
            run, plan, work_items, evidence, snapshot.snapshot_fingerprint
        )

    assert run.publication_state == RunPublicationState.NOT_PUBLISHED


def test_publish_run_rejects_missing_physical_artifact(tmp_path: Path) -> None:
    orchestrator, run, plan, work_items, evidence, snapshot = _complete_graph(tmp_path)
    Path(run.artifact_refs[0]).unlink()

    with pytest.raises(PublicationError, match="artifacts"):
        orchestrator.publish_run(
            run, plan, work_items, evidence, snapshot.snapshot_fingerprint
        )

    assert run.publication_state == RunPublicationState.NOT_PUBLISHED


def test_direct_published_complete_write_is_rejected(tmp_path: Path) -> None:
    orchestrator, run, plan, work_items, evidence, snapshot = _complete_graph(tmp_path)
    run.publication_state = RunPublicationState.PUBLISHED_COMPLETE

    with pytest.raises(OrchestratorError, match="publish_run"):
        orchestrator.commit_run(run, plan, work_items)
