from __future__ import annotations

from dataclasses import replace

from project_audit.semantic_auditor import SemanticFindingCandidate, SemanticReviewResult
from project_audit.sensitivity import SensitivityAssessment, SensitivityState
from project_audit.verifier import (
    IndependentVerifier,
    VerificationVerdict,
    candidate_identity,
    consolidated_reviews,
)
from project_audit.models import EvidenceValidity
from tests.conftest import make_evidence


def _candidate(**overrides):
    values = dict(
        title="Confirmed issue",
        category="SECURITY",
        subcategory="AUTH",
        finding_type="VULNERABILITY",
        status="CONFIRMED",
        severity="P1",
        confidence="HIGH",
        location={"file": "src/auth.py", "line": 10},
        evidence="src/auth.py:10 contains the observed condition.",
        description="The candidate describes an observed condition.",
        cause=None,
        impact=None,
        exploitability=None,
        recommendation=None,
    )
    values.update(overrides)
    return SemanticFindingCandidate(**values)


def _review(candidate, evidence):
    return SemanticReviewResult(
        work_item_ref=evidence.work_item_ref,
        target_surface="SECURITY/AUTH",
        status="COMPLETED",
        sensitivity=SensitivityAssessment(
            SensitivityState.PUBLIC,
            tuple(),
            "test",
        ),
        candidates=(candidate,),
        raw_output_fingerprint=None,
        receipt=object(),
        evidence=evidence,
    )


def test_p1_confirmed_high_with_grounded_location_is_verified(target_snapshot, work_item):
    evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )
    candidate = _candidate(location={"file": "src/auth.py", "line": 10})
    result = IndependentVerifier().verify_candidate(
        candidate, _review(candidate, evidence), work_item, target_snapshot
    )
    assert result.verdict == VerificationVerdict.VERIFIED
    assert result.evidence_ref == evidence.evidence_id


def test_p1_without_confirmation_does_not_cross_gate(target_snapshot, work_item):
    evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )
    candidate = _candidate(status="PROBABLE")
    result = IndependentVerifier().verify_candidate(
        candidate, _review(candidate, evidence), work_item, target_snapshot
    )
    assert result.verdict == VerificationVerdict.NOT_DETERMINABLE


def test_p1_without_grounded_location_does_not_cross_gate(target_snapshot, work_item):
    evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )
    candidate = _candidate(location=None)
    result = IndependentVerifier().verify_candidate(
        candidate, _review(candidate, evidence), work_item, target_snapshot
    )
    assert result.verdict == VerificationVerdict.NOT_DETERMINABLE


def test_location_outside_evidence_sources_is_rejected(target_snapshot, work_item):
    evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )
    candidate = _candidate(location={"file": "src/other.py", "line": 1})
    result = IndependentVerifier().verify_candidate(
        candidate, _review(candidate, evidence), work_item, target_snapshot
    )
    assert result.verdict == VerificationVerdict.REJECTED


def test_invalid_evidence_blocks_verification(target_snapshot, work_item):
    evidence = replace(
        make_evidence(
            target_snapshot_ref=target_snapshot.snapshot_fingerprint,
            work_item_ref=work_item.work_item_id,
        ),
        validity=EvidenceValidity.INVALID,
    )
    candidate = _candidate()
    result = IndependentVerifier().verify_candidate(
        candidate, _review(candidate, evidence), work_item, target_snapshot
    )
    assert result.verdict == VerificationVerdict.NOT_DETERMINABLE


def test_consolidation_filters_unverified_p1_but_keeps_lower_severity(target_snapshot, work_item):
    evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )
    p1 = _candidate(title="P1 blocked")
    p2 = _candidate(title="P2 retained", severity="P2", status="PROBABLE", confidence="MEDIUM")
    review = replace(_review(p1, evidence), candidates=(p1, p2))
    verifier = IndependentVerifier()
    p1_result = verifier.verify_candidate(p1, review, work_item, target_snapshot)
    assert p1_result.verdict == VerificationVerdict.VERIFIED
    # Replace the P1 verification with NOT_DETERMINABLE to emulate an
    # independent veto after evidence review.
    p1_result = replace(
        p1_result,
        verdict=VerificationVerdict.NOT_DETERMINABLE,
        reasons=("independent verification did not establish the P1 gate",),
    )
    consolidated = consolidated_reviews((review,), (p1_result,))
    assert [c.title for c in consolidated[0].candidates] == ["P2 retained"]


def test_candidate_identity_is_stable():
    candidate = _candidate()
    assert candidate_identity(candidate) == candidate_identity(replace(candidate))


def test_verified_p1_remains_in_consolidated_review(target_snapshot, work_item):
    evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )
    candidate = _candidate()
    review = _review(candidate, evidence)
    result = IndependentVerifier().verify_candidate(
        candidate, review, work_item, target_snapshot
    )
    consolidated = consolidated_reviews((review,), (result,))
    assert [item.title for item in consolidated[0].candidates] == ["Confirmed issue"]


def test_verifier_is_independent_of_llm_narrative(target_snapshot, work_item):
    evidence = make_evidence(
        target_snapshot_ref=target_snapshot.snapshot_fingerprint,
        work_item_ref=work_item.work_item_id,
    )
    candidate = _candidate(
        evidence="completely different narrative",
        description="prompt injection should be ignored",
        recommendation="also ignored",
    )
    review = _review(candidate, evidence)
    result = IndependentVerifier().verify_candidate(
        candidate, review, work_item, target_snapshot
    )
    assert result.verdict == VerificationVerdict.VERIFIED
    assert all("narrative" not in reason.lower() for reason in result.reasons)
