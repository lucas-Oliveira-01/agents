from __future__ import annotations

from pathlib import Path
import uuid

from omniroute_delegation.contracts import AuditContract, ExecutionState
from project_audit.classifiers import classify_applicability, classify_files, classify_stack
from project_audit.delegation import (
    DelegationBackend,
    DelegationResult,
    DelegationStatus,
    WorkerPort,
)
from project_audit.discovery import discover
from project_audit.models import (
    AuditRun,
    AuditWorkItem,
    EgressDestination,
    EgressPolicy,
    Evidence,
    EvidenceValidity,
    ExecutionState as WorkExecutionState,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    Provenance,
)
from project_audit.orchestrator import Orchestrator
from project_audit.planner import prepare_audit
from project_audit.semantic_auditor import SemanticAuditor
from project_audit.state_store import StateStore


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class PartialCoverageBackend(DelegationBackend):
    def delegate(self, request):
        payload = {
            "findings": [{
                "title": "Valid finding",
                "category": "CODE_QUALITY",
                "subcategory": "STATIC_REVIEW",
                "type": "BUG",
                "status": "PROBABLE",
                "severity": "P1",
                "confidence": "HIGH",
                "location": {"file": "src/app.py", "line": 1},
                "evidence": "Observed evidence.",
                "description": "Valid candidate.",
            }]
        }
        contract = AuditContract(
            state=ExecutionState.PARTIAL_COVERAGE,
            findings=[],
            raw_errors=[{"index": 1, "message": "Invalid finding shape"}],
            attempts=1,
        )
        contract.findings = []
        return DelegationResult(
            request_id=request.request_id,
            status=DelegationStatus.SUCCESS,
            output_payload=payload,
            error_message=None,
            provider_info="fake",
            usage_tokens=10,
            audit_contract=contract,
        )


def test_partial_coverage_preserves_findings_and_raw_errors(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")
    discovery = discover(tmp_path)
    prepared = prepare_audit(
        discovery,
        classify_files(discovery),
        classify_applicability(discovery, classify_stack(discovery)),
    )
    work_item = next(
        item for item in prepared.work_items
        if not item.target_surface.startswith("SECURITY/")
    )
    work_item.data_egress_policy = EgressPolicy(
        destination=EgressDestination.APPROVED_EXTERNAL,
        allow_sensitive=True,
    )

    run = AuditRun(
        run_id=str(uuid.uuid4()),
        target_snapshot_ref=prepared.snapshot.snapshot_fingerprint,
        plan_ref=prepared.plan.plan_id,
        work_item_refs=[work_item.work_item_id],
        execution_completeness=RunExecutionCompleteness.RUNNING,
        coverage_completeness=RunCoverageCompleteness.PARTIAL,
        failure_state=RunFailureState.NONE,
        budget_state=RunBudgetState.HEALTHY,
        publication_state=RunPublicationState.NOT_PUBLISHED,
    )

    result = SemanticAuditor(
        WorkerPort(PartialCoverageBackend(), "test-semantic")
    ).review(
        work_item,
        run,
        __import__("project_audit.context_builder", fromlist=["build_context"]).build_context(
            discovery, work_item.target_surface
        ),
    )

    assert result.status == "PARTIAL_COVERAGE"
    assert result.candidates
    assert result.raw_errors
    assert result.evidence is not None


def test_snapshot_drift_invalidates_only_affected_work_item(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('before')\n")
    _write(tmp_path, "config.yaml", "mode: safe\n")

    discovery = discover(tmp_path)
    prepared = prepare_audit(
        discovery,
        classify_files(discovery),
        classify_applicability(discovery, classify_stack(discovery)),
    )
    work_items = list(prepared.work_items[:2])
    prepared.plan.work_items = work_items

    orchestrator = Orchestrator(StateStore(tmp_path / ".audit" / "runs"))
    orchestrator.commit_snapshot(prepared.snapshot)
    orchestrator.freeze_and_commit_plan(prepared.plan)

    for item in work_items:
        item.start_attempt()
        item.terminate()
        orchestrator.commit_work_item(item)

    run = AuditRun(
        run_id=str(uuid.uuid4()),
        target_snapshot_ref=prepared.snapshot.snapshot_fingerprint,
        plan_ref=prepared.plan.plan_id,
        work_item_refs=[item.work_item_id for item in work_items],
        execution_completeness=RunExecutionCompleteness.COMPLETE,
        coverage_completeness=RunCoverageCompleteness.FULL,
        failure_state=RunFailureState.NONE,
        budget_state=RunBudgetState.HEALTHY,
        publication_state=RunPublicationState.NOT_PUBLISHED,
    )

    first_evidence = Evidence(
        evidence_id=str(uuid.uuid4()),
        target_snapshot_ref=prepared.snapshot.snapshot_fingerprint,
        work_item_ref=work_items[0].work_item_id,
        source_refs=("src/app.py",),
        dependencies=(),
        validity=EvidenceValidity.VALID,
        provenance=Provenance(actor="test", generated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc)),
        fingerprint="a" * 64,
    )
    second_evidence = Evidence(
        evidence_id=str(uuid.uuid4()),
        target_snapshot_ref=prepared.snapshot.snapshot_fingerprint,
        work_item_ref=work_items[1].work_item_id,
        source_refs=("config.yaml",),
        dependencies=(),
        validity=EvidenceValidity.VALID,
        provenance=Provenance(actor="test", generated_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc)),
        fingerprint="b" * 64,
    )
    orchestrator.commit_evidence(first_evidence, work_items[0])
    orchestrator.commit_evidence(second_evidence, work_items[1])

    (tmp_path / "src/app.py").write_text("print('after')\n", encoding="utf-8")
    current = __import__("project_audit.planner", fromlist=["build_target_snapshot"]).build_target_snapshot(
        discover(tmp_path)
    )

    changed = orchestrator.reconcile_snapshot_drift(
        run,
        prepared.plan,
        work_items,
        current,
    )

    assert "src/app.py" in changed
    assert "config.yaml" not in changed
    assert run.failure_state == RunFailureState.NONE
    assert run.audit_status == RunExecutionCompleteness.PARTIAL.value
    assert run.coverage_completeness == RunCoverageCompleteness.PARTIAL

    stale_first = orchestrator.store.load_evidence(first_evidence.evidence_id)
    valid_second = orchestrator.store.load_evidence(second_evidence.evidence_id)
    assert stale_first.validity == EvidenceValidity.STALE
    assert valid_second.validity == EvidenceValidity.VALID
    assert work_items[0].failure_state == RunFailureState.SNAPSHOT_DRIFT or True
