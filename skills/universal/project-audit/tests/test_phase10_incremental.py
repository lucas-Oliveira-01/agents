from __future__ import annotations

import dataclasses

from project_audit.incremental import (
    IncrementalDecision,
    derive_reused_evidence,
    match_previous_evidence,
    plan_incremental_actions_stable,
)
from project_audit.models import EvidenceValidity, TargetSnapshot, MethodologyState
from project_audit.runtime import run_full_audit
from tests.conftest import make_evidence, make_work_item


def _snapshot_with_inputs(base_snapshot, inputs):
    project_state = dataclasses.replace(
        base_snapshot.project_state,
        tracked_input_fingerprints=tuple(inputs),
    )
    return TargetSnapshot.create(
        base_snapshot.target_mode,
        project_state,
        MethodologyState(
            audit_contract_version=base_snapshot.methodology_state.audit_contract_version,
            auditor_versions=dict(base_snapshot.methodology_state.auditor_versions),
            policy_version=base_snapshot.methodology_state.policy_version,
        ),
    )


def test_stable_incremental_binding_survives_regenerated_work_item_ids(
    target_snapshot, work_item
):
    from project_audit.models import TrackedInputFingerprint

    previous_snapshot = _snapshot_with_inputs(
        target_snapshot,
        [TrackedInputFingerprint("src/app.py", "a" * 64)],
    )
    current_snapshot = _snapshot_with_inputs(
        previous_snapshot,
        [TrackedInputFingerprint("src/app.py", "a" * 64)],
    )

    previous = dataclasses.replace(
        work_item,
        work_item_id="00000000-0000-0000-0000-000000000001",
        target_surface="CODE_QUALITY/GENERAL",
    )
    current = dataclasses.replace(
        work_item,
        work_item_id="00000000-0000-0000-0000-000000000002",
        target_surface="CODE_QUALITY/GENERAL",
    )
    evidence = dataclasses.replace(
        make_evidence(
            target_snapshot_ref=previous_snapshot.snapshot_fingerprint,
            work_item_ref=previous.work_item_id,
        ),
        source_refs=("src/app.py:1",),
        dependencies=(),
    )

    matched = match_previous_evidence(
        [current],
        [previous],
        {previous.work_item_id: evidence},
    )
    assert matched[current.work_item_id].evidence_id == evidence.evidence_id

    bindings = plan_incremental_actions_stable(
        [current],
        [previous],
        {previous.work_item_id: evidence},
        previous_snapshot,
        current_snapshot,
    )
    assert bindings[0].decision == IncrementalDecision.REUSE
    assert current.action.value == "REUSE"


def test_ambiguous_previous_work_items_fail_closed_to_reaudit(
    target_snapshot, work_item
):
    previous_a = dataclasses.replace(work_item, work_item_id="00000000-0000-0000-0000-000000000001")
    previous_b = dataclasses.replace(work_item, work_item_id="00000000-0000-0000-0000-000000000002")
    current = dataclasses.replace(work_item, work_item_id="00000000-0000-0000-0000-000000000003")
    evidence_a = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=previous_a.work_item_id,
    )
    evidence_b = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=previous_b.work_item_id,
    )

    bindings = plan_incremental_actions_stable(
        [current],
        [previous_a, previous_b],
        {
            previous_a.work_item_id: evidence_a,
            previous_b.work_item_id: evidence_b,
        },
        target_snapshot,
        target_snapshot,
    )
    assert bindings[0].decision == IncrementalDecision.REAUDIT
    assert current.action.value == "REAUDIT"


def test_reused_evidence_is_fresh_and_keeps_historical_record(
    target_snapshot, work_item
):
    prior = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref="00000000-0000-0000-0000-000000000010",
    )
    current = dataclasses.replace(
        work_item,
        work_item_id="00000000-0000-0000-0000-000000000011",
    )

    from datetime import datetime, timezone

    reused = derive_reused_evidence(
        prior,
        target_snapshot,
        current,
        generated_at=datetime(2026, 9, 26, tzinfo=timezone.utc),
    )
    assert reused.evidence_id != prior.evidence_id
    assert reused.work_item_ref == current.work_item_id
    assert reused.target_snapshot_ref == target_snapshot.snapshot_fingerprint
    assert reused.fingerprint == prior.fingerprint
    assert reused.validity == EvidenceValidity.VALID
    assert reused.derived_from_evidence_ref == prior.evidence_id


def test_full_audit_can_reuse_safe_evidence_from_previous_run(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "src/app.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (project / "README.md").write_text("# baseline\n", encoding="utf-8")

    first = run_full_audit(str(project), overwrite_artifacts=True)

    (project / "README.md").write_text("# changed documentation only\n", encoding="utf-8")
    second = run_full_audit(
        str(project),
        overwrite_artifacts=True,
        previous_run_ref=first.engineering.run.run_id,
    )

    assert second.engineering.run.previous_run_ref == first.engineering.run.run_id
    reused = [
        evidence
        for evidence in second.engineering.evidence + second.security.evidence
        if evidence.derived_from_evidence_ref
    ]
    assert reused



def test_reused_finding_is_preserved_in_current_run(state_store, audit_plan, work_item, target_snapshot):
    from datetime import datetime, timezone
    from project_audit.finding_lifecycle import preserve_reused_findings
    from project_audit.models import (
        AuditRun,
        FindingFingerprint,
        FindingLifecycle,
        FindingRecord,
        FindingStatus,
        RunBudgetState,
        RunCoverageCompleteness,
        RunExecutionCompleteness,
        RunFailureState,
        RunPublicationState,
    )

    previous_run_ref = "00000000-0000-0000-0000-000000000099"
    current_run = AuditRun(
        run_id="00000000-0000-0000-0000-000000000100",
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        plan_ref=audit_plan.plan_id,
        work_item_refs=[work_item.work_item_id],
        execution_completeness=RunExecutionCompleteness.COMPLETE,
        coverage_completeness=RunCoverageCompleteness.FULL,
        failure_state=RunFailureState.NONE,
        budget_state=RunBudgetState.HEALTHY,
        publication_state=RunPublicationState.NOT_PUBLISHED,
    )
    fingerprint = FindingFingerprint(
        domain="SECURITY",
        control_surface="AUTHENTICATION",
        defect_type="VULNERABILITY",
    )
    from project_audit.finding_lifecycle import finding_key
    key = finding_key(fingerprint)
    now = datetime(2026, 9, 26, tzinfo=timezone.utc)
    record = FindingRecord(
        finding_key=key,
        fingerprint=fingerprint,
        status=FindingStatus.CONFIRMED,
        lifecycle=FindingLifecycle.PERSISTING,
        run_ref=previous_run_ref,
        evidence_ref=None,
        first_seen=now,
        last_seen=now,
        previous_lifecycle=FindingLifecycle.NEW,
        severity="P1",
        history=(FindingLifecycle.NEW, FindingLifecycle.PERSISTING),
    )
    state_store.save_finding_record(record)

    security_item = dataclasses.replace(
        work_item,
        target_surface="SECURITY/AUTHENTICATION",
        work_item_id="00000000-0000-0000-0000-000000000101",
    )
    prior_evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref="00000000-0000-0000-0000-000000000099",
    )
    current_evidence = derive_reused_evidence(
        prior_evidence,
        target_snapshot,
        security_item,
        generated_at=now,
    )

    preserved = preserve_reused_findings(
        state_store,
        current_run,
        previous_run_ref,
        [security_item],
        {security_item.work_item_id: current_evidence},
    )
    assert key in preserved
    current = state_store.load_finding_record(key)
    assert current.lifecycle == FindingLifecycle.PERSISTING
    assert current.run_ref == current_run.run_id
    assert current.evidence_ref == current_evidence.evidence_id
