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
    evidence = make_evidence(
        target_snapshot_ref=previous_snapshot.snapshot_fingerprint,
        work_item_ref=previous.work_item_id,
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
