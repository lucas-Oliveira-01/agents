"""Durable finding lifecycle reconciliation for Phase 7."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Iterable, Tuple

from .models import (
    AuditPlan,
    AuditRun,
    FindingFingerprint,
    FindingLifecycle,
    FindingRecord,
    FindingStatus,
)
from .state_store import StateStore
from .semantic_auditor import SemanticFindingCandidate, SemanticReviewResult
from .verifier import VerificationResult, VerificationVerdict, candidate_identity


def canonical_finding_fingerprint(
    candidate: SemanticFindingCandidate,
    target_surface: str,
) -> FindingFingerprint:
    """Build identity from stable semantics, not generated narrative or a file path."""
    return FindingFingerprint(
        domain=candidate.category,
        control_surface=candidate.subcategory or str(target_surface).split("/", 1)[0].upper(),
        defect_type=candidate.finding_type,
    )


def finding_key(fingerprint: FindingFingerprint) -> str:
    payload = json.dumps(fingerprint.to_dict(), sort_keys=True, separators=(",", ":"))
    return "F-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _status(candidate: SemanticFindingCandidate) -> FindingStatus:
    return FindingStatus(candidate.status)


def reconcile_finding_lifecycle(
    store: StateStore,
    run: AuditRun,
    plan: AuditPlan,
    reviews: Iterable[SemanticReviewResult],
    verification_results: Iterable[VerificationResult],
) -> Tuple[FindingRecord, ...]:
    """Persist lifecycle transitions and only infer FIXED from a complete/full run."""
    verification = {result.candidate_id: result for result in verification_results}
    now = datetime.now(timezone.utc)
    seen = set()
    updated = []

    for review in reviews:
        for candidate in review.candidates:
            result = verification.get(candidate_identity(candidate))
            if result is not None and result.verdict != VerificationVerdict.VERIFIED:
                continue

            fingerprint = canonical_finding_fingerprint(candidate, review.target_surface)
            key = finding_key(fingerprint)
            seen.add(key)
            previous = store.load_finding_record(key) if store.finding_exists(key) else None
            status = _status(candidate)
            if previous is None:
                lifecycle = FindingLifecycle.NEW
            elif previous.lifecycle == FindingLifecycle.FIXED:
                lifecycle = FindingLifecycle.REGRESSED
            elif previous.status != status or previous.severity != candidate.severity:
                lifecycle = FindingLifecycle.MODIFIED
            else:
                lifecycle = FindingLifecycle.PERSISTING

            history = ((previous.history if previous else ()) + (lifecycle,))[-32:]
            record = FindingRecord(
                finding_key=key,
                fingerprint=fingerprint,
                status=status,
                lifecycle=lifecycle,
                run_ref=run.run_id,
                evidence_ref=result.evidence_ref if result is not None else None,
                first_seen=previous.first_seen if previous else now,
                last_seen=now,
                previous_lifecycle=previous.lifecycle if previous else None,
                severity=candidate.severity,
                history=history,
            )
            store.save_finding_record(record)
            updated.append(record)

    if run.execution_completeness.value == "COMPLETE" and run.coverage_completeness.value == "FULL":
        selected = {str(value).strip().split("/", 1)[0].upper() for value in plan.resolved_scope}
        for key in store.list_finding_keys():
            if key in seen:
                continue
            previous = store.load_finding_record(key)
            if previous.fingerprint.domain not in selected or previous.lifecycle == FindingLifecycle.FIXED:
                continue
            record = FindingRecord(
                finding_key=previous.finding_key,
                fingerprint=previous.fingerprint,
                status=previous.status,
                lifecycle=FindingLifecycle.FIXED,
                run_ref=run.run_id,
                evidence_ref=None,
                first_seen=previous.first_seen,
                last_seen=now,
                previous_lifecycle=previous.lifecycle,
                severity=previous.severity,
                history=(previous.history + (FindingLifecycle.FIXED,))[-32:],
            )
            store.save_finding_record(record)
            updated.append(record)

    return tuple(updated)
