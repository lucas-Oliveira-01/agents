from __future__ import annotations

from pathlib import Path

from project_audit.classifiers import classify_applicability, classify_files, classify_stack
from project_audit.context_builder import build_context
from project_audit.delegation import (
    DelegationBackend,
    DelegationResult,
    DelegationStatus,
    WorkerPort,
)
from project_audit.discovery import discover
from project_audit.models import (
    AuditRun,
    EgressDestination,
    EgressPolicy,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
)
from project_audit.planner import prepare_audit
from project_audit.semantic_auditor import SemanticAuditor
from project_audit.sensitivity import SensitivityState, assess_text


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class FakeBackend(DelegationBackend):
    def __init__(self, payload: dict):
        self.payload = payload
        self.called = False

    def delegate(self, request):
        self.called = True
        return DelegationResult(
            request_id=request.request_id,
            status=DelegationStatus.SUCCESS,
            output_payload=self.payload,
            error_message=None,
            provider_info="fake-semantic/v1",
            usage_tokens=10,
        )


def _run_for(prepared, work_item):
    return AuditRun(
        run_id="run-1",
        target_snapshot_ref=prepared.snapshot.snapshot_fingerprint,
        plan_ref=prepared.plan.plan_id,
        work_item_refs=[work_item.work_item_id],
        execution_completeness=RunExecutionCompleteness.PARTIAL,
        coverage_completeness=RunCoverageCompleteness.PARTIAL,
        failure_state=RunFailureState.NONE,
        budget_state=RunBudgetState.HEALTHY,
        publication_state=RunPublicationState.NOT_PUBLISHED,
    )


def test_context_builder_is_bounded_and_deterministic(tmp_path: Path) -> None:
    for idx in range(20):
        _write(tmp_path, "src/module{}/service.py".format(idx), "print('x')\n")

    discovery = discover(tmp_path)
    first = build_context(discovery, "ARCHITECTURE/STRUCTURE", max_files=5)
    second = build_context(discovery, "ARCHITECTURE/STRUCTURE", max_files=5)

    assert len(first.items) <= 5
    assert first.fingerprint == second.fingerprint
    assert [item.path for item in first.items] == [item.path for item in second.items]


def test_sensitivity_defaults_to_unknown_and_detects_secrets(tmp_path: Path) -> None:
    unknown = assess_text("class Service: pass", "src/service.py")
    secret = assess_text(
        "api_key='super-secret-value'",
        "config.py",
    )

    assert unknown.state == SensitivityState.UNKNOWN
    assert secret.state == SensitivityState.SECRET
    assert secret.is_sensitive


def test_semantic_auditor_blocks_unknown_context_under_default_egress(tmp_path: Path) -> None:
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

    backend = FakeBackend({"findings": []})
    auditor = SemanticAuditor(WorkerPort(backend, "test-semantic"))
    result = auditor.review(work_item, _run_for(prepared, work_item), build_context(discovery, work_item.target_surface))

    assert result.status == "BLOCKED"
    assert result.sensitivity.state == SensitivityState.UNKNOWN
    assert backend.called is False


def test_semantic_auditor_accepts_structured_output_when_policy_explicitly_allows_sensitive_data(
    tmp_path: Path,
) -> None:
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

    payload = {
        "findings": [
            {
                "title": "Example finding",
                "category": "CODE_QUALITY",
                "subcategory": "STATIC_REVIEW",
                "type": "TECHNICAL_DEFECT",
                "status": "PROBABLE",
                "severity": "P2",
                "confidence": "MEDIUM",
                "location": {"file": "src/app.py", "line": 1},
                "description": "The semantic worker identified a candidate requiring confirmation.",
                "cause": "Example cause",
                "impact": "Example impact",
                "exploitability": None,
                "recommendation": "Confirm against project requirements.",
            }
        ]
    }
    backend = FakeBackend(payload)
    auditor = SemanticAuditor(WorkerPort(backend, "test-semantic"))
    result = auditor.review(work_item, _run_for(prepared, work_item), build_context(discovery, work_item.target_surface))

    assert result.status == "COMPLETED"
    assert backend.called is True
    assert len(result.candidates) == 1
    assert result.evidence is not None


def test_semantic_auditor_rejects_invalid_worker_output(tmp_path: Path) -> None:
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

    backend = FakeBackend({"unexpected": []})
    auditor = SemanticAuditor(WorkerPort(backend, "test-semantic"))
    result = auditor.review(work_item, _run_for(prepared, work_item), build_context(discovery, work_item.target_surface))

    assert result.status == "INVALID_OUTPUT"
    assert result.evidence is None
