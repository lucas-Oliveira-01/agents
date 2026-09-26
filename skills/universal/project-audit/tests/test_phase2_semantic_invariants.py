from __future__ import annotations

import dataclasses
import uuid
from datetime import timedelta

from project_audit.models import (
    AuditRun,
    EvidenceValidity,
    ExecutionState,
    FindingLifecycle,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    WorkItemAction,
    WorkItemFailureState,
)
from project_audit.validators import (
    derive_coverage_completeness,
    validate_evidence_snapshot_consistency,
    validate_finding_lifecycle_sequence,
    validate_finding_lifecycle_transition,
    validate_plan_scope_resolution,
    validate_plan_work_item_references,
    validate_run_work_item_references,
    validate_state_graph,
)
from tests.conftest import FIXED_TS, make_evidence, make_work_item


def _complete(item):
    attempt = item.start_attempt(started_at=FIXED_TS)
    attempt.finish(finished_at=FIXED_TS + timedelta(seconds=1), exit_code=0)
    item.terminate(WorkItemFailureState.NONE)
    return item


def _run(plan, snapshot, items, coverage):
    return AuditRun(
        run_id=str(uuid.uuid4()),
        target_snapshot_ref=snapshot.snapshot_fingerprint,
        plan_ref=plan.plan_id,
        work_item_refs=[item.work_item_id for item in items],
        execution_completeness=RunExecutionCompleteness.COMPLETE,
        coverage_completeness=coverage,
        failure_state=RunFailureState.NONE,
        budget_state=RunBudgetState.HEALTHY,
        publication_state=RunPublicationState.NOT_PUBLISHED,
    )


def test_plan_scope_must_match_applicability(audit_plan):
    audit_plan.resolved_scope = ["security"]
    result = validate_plan_scope_resolution(audit_plan)
    assert result.is_error
    assert result.code == "PLAN_SCOPE_RESOLUTION_MISMATCH"


def test_plan_and_work_item_reference_sets_must_match(audit_plan, work_item):
    audit_plan.work_items = [work_item]
    assert validate_plan_work_item_references(audit_plan, [work_item]).is_pass

    other = make_work_item(plan_id=audit_plan.plan_id, target_surface="code/quality")
    mismatch = validate_plan_work_item_references(audit_plan, [other])
    assert mismatch.is_error
    assert mismatch.code == "PLAN_WORK_ITEM_SET_MISMATCH"


def test_run_and_work_item_reference_sets_must_match(audit_plan, target_snapshot, work_item):
    audit_plan.work_items = [work_item]
    run = _run(audit_plan, target_snapshot, [work_item], RunCoverageCompleteness.NONE)
    run.work_item_refs = []
    result = validate_run_work_item_references(run, audit_plan, [work_item])
    assert result.is_error
    assert result.code == "RUN_WORK_ITEM_SET_MISMATCH"


def test_coverage_uses_domain_union_not_item_count(audit_plan, target_snapshot):
    audit_plan.resolved_scope = ["security", "code"]
    security = _complete(make_work_item(audit_plan.plan_id, target_surface="security/authentication"))
    duplicate_security = _complete(make_work_item(audit_plan.plan_id, target_surface="security/authorization"))

    derived = derive_coverage_completeness(
        audit_plan,
        [security, duplicate_security],
    )
    assert derived == RunCoverageCompleteness.PARTIAL


def test_coverage_is_full_when_every_selected_domain_is_covered(audit_plan, target_snapshot):
    security = _complete(make_work_item(audit_plan.plan_id, target_surface="security/authentication"))
    code = _complete(make_work_item(audit_plan.plan_id, target_surface="code/static-review"))

    derived = derive_coverage_completeness(audit_plan, [security, code])
    assert derived == RunCoverageCompleteness.FULL

    security_evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=security.work_item_id,
    )
    code_evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=code.work_item_id,
    )
    audit_plan.work_items = [security, code]
    run = _run(audit_plan, target_snapshot, [security, code], derived)
    assert validate_state_graph(
        target_snapshot,
        audit_plan,
        [security, code],
        run,
        [security_evidence, code_evidence],
    ).has_errors is False


def test_reuse_only_counts_with_valid_evidence(audit_plan, target_snapshot):
    item = make_work_item(
        audit_plan.plan_id,
        target_surface="security/authentication",
        action=WorkItemAction.REUSE,
    )
    evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=item.work_item_id,
    )

    assert derive_coverage_completeness(audit_plan, [item], [evidence]) == RunCoverageCompleteness.PARTIAL

    invalid = dataclasses.replace(evidence, validity=EvidenceValidity.INVALID)
    assert derive_coverage_completeness(audit_plan, [item], [invalid]) == RunCoverageCompleteness.PARTIAL


def test_evidence_snapshot_mismatch_is_rejected(target_snapshot, work_item):
    evidence = make_evidence(
        target_snapshot_ref="d" * 64,
        work_item_ref=work_item.work_item_id,
    )
    result = validate_evidence_snapshot_consistency(evidence, work_item, target_snapshot)
    assert result.is_error
    assert result.code == "EVIDENCE_SNAPSHOT_MISMATCH"


def test_evidence_raw_output_hash_is_verified(target_snapshot, work_item):
    raw = "raw semantic response"
    evidence = dataclasses.replace(
        make_evidence(
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            work_item_ref=work_item.work_item_id,
        ),
        raw_output=raw,
        raw_output_sha256="0" * 64,
    )
    result = validate_evidence_snapshot_consistency(evidence, work_item, target_snapshot)
    assert result.is_error
    assert result.code == "EVIDENCE_RAW_OUTPUT_HASH_MISMATCH"


def test_lifecycle_requires_fixed_before_regressed():
    assert validate_finding_lifecycle_transition(
        FindingLifecycle.NEW, FindingLifecycle.REGRESSED
    ).is_error
    assert validate_finding_lifecycle_transition(
        FindingLifecycle.FIXED, FindingLifecycle.REGRESSED
    ).is_pass


def test_invalidated_is_not_fixed():
    result = validate_finding_lifecycle_transition(
        FindingLifecycle.INVALIDATED, FindingLifecycle.FIXED
    )
    assert result.is_error
    assert result.code == "FINDING_INVALIDATED_NOT_FIXED"


def test_lifecycle_sequence_is_validated():
    result = validate_finding_lifecycle_sequence([
        FindingLifecycle.NEW,
        FindingLifecycle.PERSISTING,
        FindingLifecycle.MODIFIED,
        FindingLifecycle.FIXED,
        FindingLifecycle.REGRESSED,
    ])
    assert not result.has_errors

    invalid = validate_finding_lifecycle_sequence([
        FindingLifecycle.NEW,
        FindingLifecycle.REGRESSED,
    ])
    assert invalid.has_errors
