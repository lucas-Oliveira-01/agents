"""
Phase 8 — operational acceptance and determinism tests.

The suite deliberately validates the existing deterministic-first runtime rather
than provider intelligence. The goal is to detect replay drift, volatile
fingerprints, and lifecycle regressions before adding new audit capabilities.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Tuple
from uuid import uuid4

import pytest

from project_audit.engineering_auditor import EngineeringAuditor
from project_audit.fake_auditor import FakeAuditor, FakeAuditorResult
from project_audit.finding_lifecycle import reconcile_finding_lifecycle
from project_audit.models import (
    ApplicabilityDecision,
    ApplicabilityState,
    AuditPlan,
    AuditRun,
    AuditWorkItem,
    Evidence,
    EvidenceValidity,
    ExecutionPolicy,
    CredentialAccess,
    EgressDestination,
    EgressPolicy,
    FilesystemAccess,
    FindingLifecycle,
    NetworkAccess,
    Provenance,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    WorkItemAction,
)
from project_audit.planner import build_target_snapshot
from project_audit.discovery import discover
from project_audit.runtime import run_full_audit
from project_audit.security_pass import DeterministicSecurityAuditor
from project_audit.semantic_auditor import SemanticFindingCandidate, SemanticReviewResult
from project_audit.sensitivity import SensitivityAssessment, SensitivityState
from project_audit.state_store import StateStore
from project_audit.verifier import VerificationResult, VerificationVerdict, candidate_identity


CORPUS_PATH = Path(__file__).with_name("phase8_corpus.json")
CORPUS = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))["projects"]


def _materialize(project: Dict[str, object], root: Path) -> None:
    files = project["files"]
    assert isinstance(files, dict)
    for relative, value in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(value), encoding="utf-8")


def _file_signature(discovery) -> Tuple[Tuple[str, str, int], ...]:
    return tuple(
        sorted(
            (item.path, item.sha256 or "", item.size)
            for item in discovery.files
        )
    )


def _inspection_signature(result) -> Tuple[object, ...]:
    observations = []
    for item in result.inspections:
        observations.append(
            (
                item.target_surface,
                item.fingerprint,
                tuple(item.source_refs),
                tuple(
                    (
                        observation.code,
                        observation.category,
                        observation.subcategory,
                        observation.state,
                        observation.summary,
                        tuple(observation.source_refs),
                    )
                    for observation in item.observations
                ),
            )
        )
    return tuple(sorted(observations))


def _runtime_signature(result) -> str:
    prepared = result.prepared
    payload = {
        "snapshot": prepared.snapshot.to_dict(),
        "files": [
            (
                item.path,
                item.kind.value,
                tuple(item.domains),
            )
            for item in prepared.file_classifications
        ],
        "work_items": [
            (
                item.target_surface,
                item.auditor,
                item.action.value,
                item.decision_basis,
            )
            for item in prepared.work_items
        ],
        "engineering": _inspection_signature(result.engineering),
        "security": _inspection_signature(result.security),
        "evidence": sorted(
            (
                evidence.fingerprint,
                tuple(evidence.source_refs),
                evidence.validity.value,
            )
            for evidence in result.engineering.evidence + result.security.evidence
        ),
        "run_states": (
            result.engineering.run.execution_completeness.value,
            result.engineering.run.coverage_completeness.value,
            result.engineering.run.failure_state.value,
            result.security.run.execution_completeness.value,
            result.security.run.coverage_completeness.value,
            result.security.run.failure_state.value,
        ),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("project", CORPUS, ids=[project["id"] for project in CORPUS])
def test_golden_corpus_has_stable_discovery(project, tmp_path) -> None:
    target = tmp_path / str(project["id"])
    _materialize(project, target)

    first = discover(str(target))
    second = discover(str(target))

    assert len(first.files) >= int(project["expected_min_files"])
    assert _file_signature(first) == _file_signature(second)

    must_contain = project.get("must_contain", [])
    discovered = {item.path for item in first.files}
    for relative in must_contain:
        assert relative in discovered


def test_security_golden_project_triggers_deterministic_secret_signal(tmp_path) -> None:
    project = next(item for item in CORPUS if item["id"] == "security-vulnerable")
    target = tmp_path / "security-vulnerable"
    _materialize(project, target)

    snapshot = discover(str(target))
    result = DeterministicSecurityAuditor().inspect(
        snapshot,
        "work-a",
        "SECURITY/SECRET_EXPOSURE",
    )

    observation = next(item for item in result.observations if item.code == "SEC-SECRET-001")
    assert observation.state == "OBSERVED"
    assert ".env" in observation.source_refs or "src/auth.py" in observation.source_refs


def test_deterministic_inspection_fingerprints_ignore_work_item_identity(tmp_path) -> None:
    project = next(item for item in CORPUS if item["id"] == "clean-project")
    target = tmp_path / "clean"
    _materialize(project, target)
    snapshot = discover(str(target))

    engineering = EngineeringAuditor()
    first_engineering = engineering.inspect(snapshot, "work-a", "CODE_QUALITY/GENERAL")
    second_engineering = engineering.inspect(snapshot, "work-b", "CODE_QUALITY/GENERAL")
    assert first_engineering.fingerprint == second_engineering.fingerprint

    security = DeterministicSecurityAuditor()
    first_security = security.inspect(snapshot, "work-a", "SECURITY/AUTHENTICATION")
    second_security = security.inspect(snapshot, "work-b", "SECURITY/AUTHENTICATION")
    assert first_security.fingerprint == second_security.fingerprint

    execution_policy = ExecutionPolicy(
        filesystem=FilesystemAccess.READ_ONLY,
        network=NetworkAccess.DISABLED,
        credentials=CredentialAccess.NONE,
    )
    egress_policy = EgressPolicy(
        destination=EgressDestination.LOCAL_ONLY,
        allow_sensitive=False,
    )
    wi_a = AuditWorkItem(
        work_item_id="work-a",
        plan_ref="plan",
        auditor="fake-auditor",
        target_surface="CODE_QUALITY/GENERAL",
        action=WorkItemAction.REAUDIT,
        decision_basis="deterministic",
        effective_execution_policy=execution_policy,
        data_egress_policy=egress_policy,
    )
    wi_b = AuditWorkItem(
        work_item_id="work-b",
        plan_ref="plan",
        auditor="fake-auditor",
        target_surface="CODE_QUALITY/GENERAL",
        action=WorkItemAction.REAUDIT,
        decision_basis="deterministic",
        effective_execution_policy=execution_policy,
        data_egress_policy=egress_policy,
    )
    fake = FakeAuditor(FakeAuditorResult.SUCCESS)
    _, evidence_a = fake.execute(wi_a)
    _, evidence_b = fake.execute(wi_b)
    assert evidence_a is not None and evidence_b is not None
    assert evidence_a.fingerprint == evidence_b.fingerprint


def test_full_audit_repeated_run_has_stable_canonical_signature(tmp_path) -> None:
    project = next(item for item in CORPUS if item["id"] == "clean-project")
    target = tmp_path / "repeatable"
    _materialize(project, target)

    first = run_full_audit(str(target), overwrite_artifacts=True)
    second = run_full_audit(str(target), overwrite_artifacts=True)

    assert first.prepared.snapshot.snapshot_fingerprint == second.prepared.snapshot.snapshot_fingerprint
    assert _runtime_signature(first) == _runtime_signature(second)


def _candidate(status: str = "CONFIRMED", severity: str = "P2") -> SemanticFindingCandidate:
    return SemanticFindingCandidate(
        title="Canonical auth defect",
        category="SECURITY",
        subcategory="AUTHENTICATION",
        finding_type="VULNERABILITY",
        status=status,
        severity=severity,
        confidence="HIGH",
        location={"file": "src/auth.py", "line": 1},
        evidence="The source contains the authenticated control path used by this finding.",
        description="Stable lifecycle fixture.",
        cause="Fixture cause",
        impact="Fixture impact",
        exploitability="Fixture exploitability",
        recommendation="Fixture remediation",
    )


def _lifecycle_run(snapshot_ref: str, run_id: str) -> AuditRun:
    return AuditRun(
        run_id=run_id,
        target_snapshot_ref=snapshot_ref,
        plan_ref="plan",
        work_item_refs=["work-item"],
        execution_completeness=RunExecutionCompleteness.COMPLETE,
        coverage_completeness=RunCoverageCompleteness.FULL,
        failure_state=RunFailureState.NONE,
        publication_state=RunPublicationState.NOT_PUBLISHED,
    )


def test_finding_lifecycle_exercises_new_persisting_modified_fixed_regressed(tmp_path) -> None:
    target = tmp_path / "lifecycle"
    target.mkdir()
    (target / "src").mkdir()
    (target / "src/auth.py").write_text("def authenticate(value):\\n    return value\\n", encoding="utf-8")
    snapshot = build_target_snapshot(discover(str(target)))
    plan = AuditPlan(
        plan_id="plan",
        target_snapshot_ref=snapshot.snapshot_fingerprint,
        requested_scope=["FULL"],
        applicability_decisions=[
            ApplicabilityDecision(
                domain="SECURITY/AUTHENTICATION",
                applicable=ApplicabilityState.APPLICABLE,
                decision_basis="Phase 8 lifecycle fixture",
                evidence_refs=[],
            )
        ],
        resolved_scope=["SECURITY"],
        work_items=[],
        execution_policy=ExecutionPolicy(
            filesystem=FilesystemAccess.READ_ONLY,
            network=NetworkAccess.DISABLED,
            credentials=CredentialAccess.NONE,
        ),
        egress_policy=EgressPolicy(
            destination=EgressDestination.LOCAL_ONLY,
            allow_sensitive=False,
        ),
    )
    store = StateStore(tmp_path / "state")

    def reconcile(run_id: str, status: str, severity: str) -> FindingLifecycle:
        wi = AuditWorkItem(
            work_item_id="work-item",
            plan_ref="plan",
            auditor="phase8-fixture",
            target_surface="SECURITY/AUTHENTICATION",
            action=WorkItemAction.REAUDIT,
            decision_basis="fixture",
            effective_execution_policy=plan.execution_policy,
            data_egress_policy=plan.egress_policy,
        )
        candidate = _candidate(status=status, severity=severity)
        evidence = Evidence(
            evidence_id=str(uuid4()),
            target_snapshot_ref=snapshot.snapshot_fingerprint,
            work_item_ref=wi.work_item_id,
            source_refs=("src/auth.py:1",),
            dependencies=(),
            validity=EvidenceValidity.VALID,
            provenance=Provenance(
                actor="phase8-fixture",
                generated_at=datetime(2026, 9, 26, tzinfo=timezone.utc),
            ),
            fingerprint=hashlib.sha256(b"fixture").hexdigest(),
        )
        review = SemanticReviewResult(
            work_item_ref=wi.work_item_id,
            target_surface=wi.target_surface,
            status="COMPLETED",
            sensitivity=SensitivityAssessment(
                SensitivityState.UNKNOWN,
                (),
                "Fixture",
            ),
            candidates=(candidate,),
            raw_output_fingerprint=None,
            receipt=object(),
            evidence=evidence,
        )
        verification = VerificationResult(
            candidate_identity(candidate),
            wi.work_item_id,
            candidate.severity,
            VerificationVerdict.VERIFIED,
            ("fixture",),
            evidence.evidence_id,
        )
        records = reconcile_finding_lifecycle(
            store,
            _lifecycle_run(snapshot.snapshot_fingerprint, run_id),
            plan,
            (review,),
            (verification,),
        )
        assert records
        return records[-1].lifecycle

    assert reconcile("run-1", "CONFIRMED", "P2") == FindingLifecycle.NEW
    assert reconcile("run-2", "CONFIRMED", "P2") == FindingLifecycle.PERSISTING
    assert reconcile("run-3", "PROBABLE", "P2") == FindingLifecycle.MODIFIED

    fixed_records = reconcile_finding_lifecycle(
        store,
        _lifecycle_run(snapshot.snapshot_fingerprint, "run-4"),
        plan,
        (),
        (),
    )
    assert fixed_records
    assert fixed_records[-1].lifecycle == FindingLifecycle.FIXED

    assert reconcile("run-5", "PROBABLE", "P2") == FindingLifecycle.REGRESSED
