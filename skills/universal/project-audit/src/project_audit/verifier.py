"""
verifier.py — Independent Evidence Verifier (Phase 4).

The verifier is intentionally separate from SemanticAuditor. It never consumes
the model's raw output, provider, model name, description, recommendation, or
other narrative fields while deciding whether a candidate is safe to
consolidate.

Its authority is limited to deterministic evidence integrity:
- evidence exists and is VALID;
- evidence belongs to the exact WorkItem and TargetSnapshot;
- a stated source location is covered by the persisted Evidence source refs;
- P0/P1 candidates must already be CONFIRMED with HIGH confidence and a
  concrete source location before they may be consolidated.

The verifier never promotes a candidate. A failure yields REJECTED or
NOT_DETERMINABLE and the caller must not silently turn that into CONFIRMED.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import Iterable, List, Mapping, Optional, Tuple

from .models import AuditWorkItem, Evidence, EvidenceValidity, TargetSnapshot
from .semantic_auditor import SemanticFindingCandidate, SemanticReviewResult


class VerificationVerdict(str, Enum):
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    NOT_DETERMINABLE = "NOT_DETERMINABLE"


@dataclass(frozen=True)
class VerificationResult:
    candidate_id: str
    work_item_ref: str
    severity: str
    verdict: VerificationVerdict
    reasons: Tuple[str, ...]
    evidence_ref: Optional[str]
    verifier_version: str = "project-audit-verifier/1"


def candidate_identity(candidate: SemanticFindingCandidate) -> str:
    """Stable candidate identity independent of generated ordering."""
    payload = {
        "title": candidate.title,
        "category": candidate.category,
        "subcategory": candidate.subcategory,
        "type": candidate.finding_type,
        "status": candidate.status,
        "severity": candidate.severity,
        "confidence": candidate.confidence,
        "location": candidate.location,
        "evidence": candidate.evidence,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return "VC-" + digest[:16]


def _normalize_ref(value: str) -> str:
    text = str(value).strip().replace("\\", "/").lstrip("./")
    if not text:
        return ""
    if ":" in text and not (len(text) >= 2 and text[1] == ":"):
        head, suffix = text.rsplit(":", 1)
        pieces = suffix.split("-", 1)
        if suffix.isdigit() or (
            len(pieces) == 2 and all(part.isdigit() for part in pieces)
        ):
            text = head
    if "#L" in text:
        head, suffix = text.rsplit("#L", 1)
        pieces = suffix.split("-", 1)
        if suffix.isdigit() or (
            len(pieces) == 2 and all(part.isdigit() for part in pieces)
        ):
            text = head
    return text


def _location_ref(candidate: SemanticFindingCandidate) -> Optional[str]:
    location = candidate.location
    if not isinstance(location, dict):
        return None
    value = location.get("file")
    if isinstance(value, str) and value.strip():
        return _normalize_ref(value)
    return None


class IndependentVerifier:
    """Independent deterministic verification policy for semantic candidates."""

    def verify_candidate(
        self,
        candidate: SemanticFindingCandidate,
        review: SemanticReviewResult,
        work_item: AuditWorkItem,
        snapshot: TargetSnapshot,
    ) -> VerificationResult:
        candidate_id = candidate_identity(candidate)
        reasons: List[str] = []
        evidence = review.evidence

        if evidence is None:
            return VerificationResult(
                candidate_id,
                work_item.work_item_id,
                candidate.severity,
                VerificationVerdict.NOT_DETERMINABLE,
                ("no persisted Evidence is attached to the semantic review",),
                None,
            )

        if evidence.evidence_id is None or not evidence.evidence_id.strip():
            return VerificationResult(
                candidate_id,
                work_item.work_item_id,
                candidate.severity,
                VerificationVerdict.REJECTED,
                ("Evidence has no stable evidence_id",),
                None,
            )

        if evidence.work_item_ref != work_item.work_item_id:
            return VerificationResult(
                candidate_id,
                work_item.work_item_id,
                candidate.severity,
                VerificationVerdict.REJECTED,
                ("Evidence.work_item_ref does not match the reviewed WorkItem",),
                evidence.evidence_id,
            )

        if evidence.target_snapshot_ref != snapshot.snapshot_fingerprint:
            return VerificationResult(
                candidate_id,
                work_item.work_item_id,
                candidate.severity,
                VerificationVerdict.REJECTED,
                ("Evidence targets a different immutable TargetSnapshot",),
                evidence.evidence_id,
            )

        if evidence.validity != EvidenceValidity.VALID:
            return VerificationResult(
                candidate_id,
                work_item.work_item_id,
                candidate.severity,
                VerificationVerdict.NOT_DETERMINABLE,
                ("Evidence is not VALID for the current snapshot",),
                evidence.evidence_id,
            )

        location_ref = _location_ref(candidate)
        if location_ref is None:
            if candidate.severity in {"P0", "P1"}:
                return VerificationResult(
                    candidate_id,
                    work_item.work_item_id,
                    candidate.severity,
                    VerificationVerdict.NOT_DETERMINABLE,
                    ("P0/P1 candidate has no concrete source location",),
                    evidence.evidence_id,
                )
        else:
            source_refs = {
                _normalize_ref(ref)
                for ref in evidence.source_refs
                if _normalize_ref(ref)
            }
            if location_ref not in source_refs:
                return VerificationResult(
                    candidate_id,
                    work_item.work_item_id,
                    candidate.severity,
                    VerificationVerdict.REJECTED,
                    ("candidate location is not represented by persisted Evidence.source_refs",),
                    evidence.evidence_id,
                )
            reasons.append("candidate location is grounded in persisted source evidence")

        # Critical findings may only cross the verifier gate when the auditor
        # has already supplied the strongest epistemic state. The verifier does
        # not promote PROBABLE/NOT_DETERMINABLE to CONFIRMED.
        if candidate.severity in {"P0", "P1"}:
            if candidate.status != "CONFIRMED":
                return VerificationResult(
                    candidate_id,
                    work_item.work_item_id,
                    candidate.severity,
                    VerificationVerdict.NOT_DETERMINABLE,
                    ("P0/P1 candidate is not already CONFIRMED",),
                    evidence.evidence_id,
                )
            if candidate.confidence != "HIGH":
                return VerificationResult(
                    candidate_id,
                    work_item.work_item_id,
                    candidate.severity,
                    VerificationVerdict.NOT_DETERMINABLE,
                    ("P0/P1 candidate does not have HIGH confidence",),
                    evidence.evidence_id,
                )
            reasons.append("P0/P1 epistemic gate satisfied")

        reasons.append("Evidence validity and object references are consistent")
        return VerificationResult(
            candidate_id,
            work_item.work_item_id,
            candidate.severity,
            VerificationVerdict.VERIFIED,
            tuple(reasons),
            evidence.evidence_id,
        )

    def verify_review(
        self,
        review: SemanticReviewResult,
        work_item: AuditWorkItem,
        snapshot: TargetSnapshot,
    ) -> Tuple[VerificationResult, ...]:
        return tuple(
            self.verify_candidate(candidate, review, work_item, snapshot)
            for candidate in review.candidates
        )


def verify_semantic_reviews(
    reviews: Iterable[SemanticReviewResult],
    work_items: Mapping[str, AuditWorkItem],
    snapshot: TargetSnapshot,
    verifier: Optional[IndependentVerifier] = None,
) -> Tuple[VerificationResult, ...]:
    verifier = verifier or IndependentVerifier()
    results = []
    for review in reviews:
        work_item = work_items.get(review.work_item_ref)
        if work_item is None:
            for candidate in review.candidates:
                results.append(
                    VerificationResult(
                        candidate_id=candidate_identity(candidate),
                        work_item_ref=review.work_item_ref,
                        severity=candidate.severity,
                        verdict=VerificationVerdict.NOT_DETERMINABLE,
                        reasons=("semantic review references an unknown WorkItem",),
                        evidence_ref=None,
                    )
                )
            continue
        results.extend(verifier.verify_review(review, work_item, snapshot))
    return tuple(results)


def consolidated_reviews(
    reviews: Iterable[SemanticReviewResult],
    verification_results: Iterable[VerificationResult],
) -> Tuple[SemanticReviewResult, ...]:
    """Filter only verifier-blocked P0/P1 candidates before report consolidation."""
    decisions = {
        result.candidate_id: result
        for result in verification_results
    }
    output = []
    for review in reviews:
        kept = []
        for candidate in review.candidates:
            result = decisions.get(candidate_identity(candidate))
            if candidate.severity in {"P0", "P1"}:
                if result is not None and result.verdict == VerificationVerdict.VERIFIED:
                    kept.append(candidate)
            else:
                kept.append(candidate)
        output.append(__import__("dataclasses").replace(review, candidates=tuple(kept)))
    return tuple(output)
