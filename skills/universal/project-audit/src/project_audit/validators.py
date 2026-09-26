"""
validators.py — Semantic Validators for project-audit Core Engine V1

Implements the deterministic, pure validation rules from:
  docs/references/semantic-validators.md

Core properties:
  1. Deterministic & Pure — no LLM, no network, no heuristics
  2. Monotonic Authority — only return PASS/WARNING/ERROR, never mutate
  3. Strict Epistemology — distinguish ERROR (definite) from UNDETERMINABLE

These validators complement JSON Schema (structural) validation. They enforce
meaning, cross-object invariants, and state machine semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from .models import (
    AuditPlan,
    AuditRun,
    AuditWorkItem,
    Evidence,
    EgressDestination,
    ApplicabilityState,
    EvidenceValidity,
    ExecutionState,
    FindingLifecycle,
    RunExecutionCompleteness,
    RunCoverageCompleteness,
    RunFailureState,
    TargetSnapshot,
    WorkItemAction,
    WorkItemFailureState,
)


# ---------------------------------------------------------------------------
# Validation result types
# ---------------------------------------------------------------------------


class ValidationLevel(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    UNDETERMINABLE = "UNDETERMINABLE"  # missing context, not a bug


@dataclass(frozen=True)
class ValidationResult:
    level: ValidationLevel
    code: str          # machine-readable code (e.g., "REUSE_INVALID_EVIDENCE")
    message: str       # human-readable explanation
    context: Optional[dict] = None  # optional structured context

    @property
    def is_pass(self) -> bool:
        return self.level == ValidationLevel.PASS

    @property
    def is_error(self) -> bool:
        return self.level == ValidationLevel.ERROR


@dataclass(frozen=True)
class ValidationReport:
    results: List[ValidationResult]

    @property
    def has_errors(self) -> bool:
        return any(r.is_error for r in self.results)

    @property
    def has_warnings(self) -> bool:
        return any(r.level == ValidationLevel.WARNING for r in self.results)

    @property
    def overall(self) -> ValidationLevel:
        if self.has_errors:
            return ValidationLevel.ERROR
        if self.has_warnings:
            return ValidationLevel.WARNING
        if any(r.level == ValidationLevel.UNDETERMINABLE for r in self.results):
            return ValidationLevel.UNDETERMINABLE
        return ValidationLevel.PASS

    def errors(self) -> List[ValidationResult]:
        return [r for r in self.results if r.is_error]

    def warnings(self) -> List[ValidationResult]:
        return [r for r in self.results if r.level == ValidationLevel.WARNING]


def _pass(code: str, message: str) -> ValidationResult:
    return ValidationResult(ValidationLevel.PASS, code, message)


def _warn(code: str, message: str, context: Optional[dict] = None) -> ValidationResult:
    return ValidationResult(ValidationLevel.WARNING, code, message, context)


def _error(code: str, message: str, context: Optional[dict] = None) -> ValidationResult:
    return ValidationResult(ValidationLevel.ERROR, code, message, context)


def _undeterminable(code: str, message: str) -> ValidationResult:
    return ValidationResult(ValidationLevel.UNDETERMINABLE, code, message)


# ---------------------------------------------------------------------------
# §1 — Identity & Canonical Consistency
# ---------------------------------------------------------------------------


def validate_target_snapshot_immutability(snapshot: TargetSnapshot) -> ValidationResult:
    """
    TargetSnapshot must have a stable, non-empty fingerprint.
    Immutability is enforced structurally (frozen dataclass), but we verify
    the fingerprint is present and well-formed.
    (semantic-validators.md §1)
    """
    if not snapshot.snapshot_fingerprint:
        return _error(
            "SNAPSHOT_MISSING_FINGERPRINT",
            "TargetSnapshot has no snapshot_fingerprint.",
        )
    if len(snapshot.snapshot_fingerprint) != 64:
        return _error(
            "SNAPSHOT_INVALID_FINGERPRINT",
            f"snapshot_fingerprint must be 64 hex chars, got {len(snapshot.snapshot_fingerprint)}.",
            {"fingerprint": snapshot.snapshot_fingerprint},
        )
    return _pass("SNAPSHOT_FINGERPRINT_VALID", "TargetSnapshot fingerprint is present and well-formed.")


def validate_target_snapshot_fingerprint_matches(snapshot: TargetSnapshot) -> ValidationResult:
    """
    Verifies that the stored fingerprint matches what would be re-derived.
    Detects silent tampering or reconstruction bugs.
    (semantic-validators.md §1)
    """
    from .models import TargetSnapshot as TS
    expected = TS._compute_fingerprint(
        snapshot.target_mode,
        snapshot.project_state,
        snapshot.methodology_state,
    )
    if snapshot.snapshot_fingerprint != expected:
        return _error(
            "SNAPSHOT_FINGERPRINT_MISMATCH",
            "Stored snapshot_fingerprint does not match re-derived value. Possible tampering or corruption.",
            {"stored": snapshot.snapshot_fingerprint, "expected": expected},
        )
    return _pass("SNAPSHOT_FINGERPRINT_CONSISTENT", "Fingerprint is consistent with snapshot state.")


# ---------------------------------------------------------------------------
# §2 — Referential Integrity
# ---------------------------------------------------------------------------


def validate_work_item_plan_ref(
    work_item: AuditWorkItem,
    known_plan_ids: List[str],
) -> ValidationResult:
    """
    AuditWorkItem.plan_ref must point to a known AuditPlan.
    (semantic-validators.md §2)
    """
    if work_item.plan_ref not in known_plan_ids:
        return _error(
            "WORK_ITEM_DANGLING_PLAN_REF",
            f"WorkItem {work_item.work_item_id} references unknown plan {work_item.plan_ref}.",
            {"plan_ref": work_item.plan_ref, "known_plans": known_plan_ids},
        )
    return _pass("WORK_ITEM_PLAN_REF_VALID", f"WorkItem plan_ref {work_item.plan_ref} resolves correctly.")


def validate_evidence_work_item_ref(
    evidence: Evidence,
    known_work_item_ids: List[str],
) -> ValidationResult:
    """
    Evidence.work_item_ref must point to a known AuditWorkItem.
    (semantic-validators.md §2)
    """
    if evidence.work_item_ref not in known_work_item_ids:
        return _error(
            "EVIDENCE_DANGLING_WORK_ITEM_REF",
            f"Evidence {evidence.evidence_id} references unknown WorkItem {evidence.work_item_ref}.",
            {"work_item_ref": evidence.work_item_ref},
        )
    return _pass("EVIDENCE_WORK_ITEM_REF_VALID", "Evidence work_item_ref resolves correctly.")


def validate_run_recovery_ref(
    run: AuditRun,
    known_run_ids: List[str],
    interrupted_run_ids: List[str],
) -> ValidationResult:
    """
    AuditRun.recovery_from_ref must point to an interrupted/failed run.
    It cannot point to a successful run. (semantic-validators.md §2)
    """
    if run.recovery_from_ref is None:
        return _pass("RUN_NO_RECOVERY_REF", "No recovery_from_ref — not a recovery run.")
    if run.recovery_from_ref not in known_run_ids:
        return _error(
            "RUN_DANGLING_RECOVERY_REF",
            f"Run {run.run_id} recovery_from_ref {run.recovery_from_ref} does not exist.",
        )
    if run.recovery_from_ref not in interrupted_run_ids:
        return _error(
            "RUN_RECOVERY_REF_NOT_INTERRUPTED",
            f"Run {run.run_id} recovery_from_ref {run.recovery_from_ref} must point to "
            "an interrupted/failed run, not a successful one.",
        )
    return _pass("RUN_RECOVERY_REF_VALID", "recovery_from_ref points to a valid interrupted run.")


def validate_run_previous_ref_distinct_from_recovery(run: AuditRun) -> ValidationResult:
    """
    previous_run_ref ≠ recovery_from_ref — these are semantically distinct.
    (ADR-07, canonical §5)
    """
    if (
        run.previous_run_ref is not None
        and run.recovery_from_ref is not None
        and run.previous_run_ref == run.recovery_from_ref
    ):
        return _error(
            "RUN_LINEAGE_REF_COLLISION",
            f"Run {run.run_id}: previous_run_ref and recovery_from_ref cannot point to the same run. "
            "These are semantically distinct concepts.",
        )
    return _pass("RUN_LINEAGE_REFS_DISTINCT", "previous_run_ref and recovery_from_ref are distinct.")


# ---------------------------------------------------------------------------
# Phase 2 — Cross-object semantic invariants
# ---------------------------------------------------------------------------


def _scope_domain(value: str) -> str:
    """Canonicalize a scope/surface to its top-level audit domain."""
    return str(value).strip().split("/", 1)[0].upper()


def _normalized_scope(values) -> set[str]:
    return {_scope_domain(v) for v in values if str(v).strip()}


def derive_selected_scope(plan: AuditPlan) -> set[str]:
    """Derive selected scope from applicability, never from an agent assertion."""
    if not plan.applicability_decisions:
        return _normalized_scope(plan.resolved_scope)
    return {
        _scope_domain(decision.domain)
        for decision in plan.applicability_decisions
        if decision.applicable in (
            ApplicabilityState.APPLICABLE,
            ApplicabilityState.UNKNOWN,
        )
    }


def validate_plan_snapshot_consistency(
    plan: AuditPlan,
    snapshot: TargetSnapshot,
) -> ValidationResult:
    if plan.target_snapshot_ref != snapshot.snapshot_fingerprint:
        return _error(
            "PLAN_SNAPSHOT_REF_MISMATCH",
            f"AuditPlan {plan.plan_id} references snapshot {plan.target_snapshot_ref[:16]}... "
            f"but supplied snapshot is {snapshot.snapshot_fingerprint[:16]}...",
        )
    return _pass("PLAN_SNAPSHOT_REF_VALID", "AuditPlan targets the supplied immutable snapshot.")


def validate_plan_scope_resolution(plan: AuditPlan) -> ValidationResult:
    """resolved_scope must equal applicability-derived selected scope."""
    resolved = _normalized_scope(plan.resolved_scope)
    selected = derive_selected_scope(plan)
    if selected != resolved:
        return _error(
            "PLAN_SCOPE_RESOLUTION_MISMATCH",
            f"AuditPlan {plan.plan_id} resolved_scope does not match applicability-derived scope.",
            {
                "selected_scope": sorted(selected),
                "resolved_scope": sorted(resolved),
            },
        )
    if not plan.applicability_decisions and resolved:
        return _undeterminable(
            "PLAN_SCOPE_APPLICABILITY_MISSING",
            f"AuditPlan {plan.plan_id} has resolved_scope but no applicability decisions; "
            "scope derivation cannot be independently established.",
        )
    return _pass("PLAN_SCOPE_RESOLUTION_VALID", "resolved_scope is derivable from applicability decisions.")


def validate_plan_work_item_references(
    plan: AuditPlan,
    work_items: List[AuditWorkItem],
) -> ValidationResult:
    """Plan and execution view must reference exactly the same WorkItems."""
    declared_ids = [wi.work_item_id for wi in plan.work_items]
    actual_ids = [wi.work_item_id for wi in work_items]
    if len(declared_ids) != len(set(declared_ids)):
        return _error(
            "PLAN_DUPLICATE_WORK_ITEM_REF",
            f"AuditPlan {plan.plan_id} contains duplicate WorkItem references.",
        )
    if len(actual_ids) != len(set(actual_ids)):
        return _error("WORK_ITEM_DUPLICATE_ID", "Execution supplied duplicate WorkItem IDs.")
    if set(declared_ids) != set(actual_ids):
        return _error(
            "PLAN_WORK_ITEM_SET_MISMATCH",
            f"AuditPlan {plan.plan_id} WorkItem refs do not match the supplied WorkItems.",
            {"declared": sorted(declared_ids), "actual": sorted(actual_ids)},
        )
    invalid_plan_refs = [
        wi.work_item_id for wi in work_items if wi.plan_ref != plan.plan_id
    ]
    if invalid_plan_refs:
        return _error(
            "WORK_ITEM_PLAN_REF_MISMATCH",
            "One or more WorkItems point to a different plan.",
            {"work_item_ids": invalid_plan_refs, "plan_id": plan.plan_id},
        )
    return _pass("PLAN_WORK_ITEM_REFERENCES_VALID", "Plan and WorkItem references are consistent.")


def validate_work_item_scope_membership(
    plan: AuditPlan,
    work_items: List[AuditWorkItem],
) -> ValidationResult:
    """Every informative WorkItem must target a selected/resolved domain."""
    selected = _normalized_scope(plan.resolved_scope)
    if not selected:
        return _undeterminable(
            "WORK_ITEM_SCOPE_NOT_DETERMINABLE",
            f"AuditPlan {plan.plan_id} has no resolved scope.",
        )

    unmatched = []
    for wi in work_items:
        domain = _scope_domain(wi.target_surface)
        if domain not in selected:
            unmatched.append((wi.work_item_id, domain, wi.target_surface))

    # Generic paths such as src/ do not encode an audit domain and remain
    # indeterminate rather than being misclassified as a scope violation.
    informative = [
        entry for entry in unmatched
        if entry[2].split("/", 1)[0].upper() not in {"SRC", "ROOT", "PROJECT"}
    ]
    if informative:
        return _error(
            "WORK_ITEM_OUTSIDE_RESOLVED_SCOPE",
            "One or more WorkItems target a domain outside the resolved scope.",
            {
                "work_items": [
                    {"work_item_id": wid, "domain": dom, "target_surface": surface}
                    for wid, dom, surface in informative
                ],
                "resolved_scope": sorted(selected),
            },
        )
    return _pass("WORK_ITEM_SCOPE_MEMBERSHIP_VALID", "WorkItems are contained by the resolved scope.")


def validate_completed_work_item_has_evidence(
    work_item: AuditWorkItem,
    evidence_for_item: List[Evidence],
) -> ValidationResult:
    """A successful terminal WorkItem must leave at least one Evidence edge."""
    if (
        work_item.execution_state == ExecutionState.TERMINATED
        and work_item.failure_state == WorkItemFailureState.NONE
        and not evidence_for_item
    ):
        return _error(
            "WORK_ITEM_COMPLETED_WITHOUT_EVIDENCE",
            f"WorkItem {work_item.work_item_id} terminated successfully but has no Evidence.",
        )
    return _pass("WORK_ITEM_EVIDENCE_LINK_VALID", "WorkItem execution has the required Evidence link.")


def validate_evidence_snapshot_consistency(
    evidence: Evidence,
    work_item: AuditWorkItem,
    snapshot: TargetSnapshot,
) -> ValidationResult:
    """Evidence must belong to the exact snapshot and WorkItem it claims."""
    if evidence.work_item_ref != work_item.work_item_id:
        return _error(
            "EVIDENCE_WORK_ITEM_MISMATCH",
            f"Evidence {evidence.evidence_id} references {evidence.work_item_ref}, "
            f"not WorkItem {work_item.work_item_id}.",
        )
    if evidence.target_snapshot_ref != snapshot.snapshot_fingerprint:
        return _error(
            "EVIDENCE_SNAPSHOT_MISMATCH",
            f"Evidence {evidence.evidence_id} references snapshot "
            f"{evidence.target_snapshot_ref[:16]}... but supplied snapshot is "
            f"{snapshot.snapshot_fingerprint[:16]}...",
        )
    if evidence.raw_output is not None:
        import hashlib
        expected = hashlib.sha256(evidence.raw_output.encode("utf-8")).hexdigest()
        if evidence.raw_output_sha256 != expected:
            return _error(
                "EVIDENCE_RAW_OUTPUT_HASH_MISMATCH",
                f"Evidence {evidence.evidence_id} raw_output_sha256 does not match raw_output.",
                {"expected": expected, "actual": evidence.raw_output_sha256},
            )
    return _pass("EVIDENCE_SNAPSHOT_CONSISTENT", "Evidence belongs to the supplied WorkItem and TargetSnapshot.")


def validate_run_work_item_references(
    run: AuditRun,
    plan: AuditPlan,
    work_items: List[AuditWorkItem],
) -> ValidationResult:
    """Run refs, plan refs and supplied WorkItems must form one closed set."""
    actual_ids = [wi.work_item_id for wi in work_items]
    refs = list(run.work_item_refs)
    if len(refs) != len(set(refs)):
        return _error(
            "RUN_DUPLICATE_WORK_ITEM_REF",
            f"AuditRun {run.run_id} contains duplicate WorkItem refs.",
        )
    if set(refs) != set(actual_ids):
        return _error(
            "RUN_WORK_ITEM_SET_MISMATCH",
            f"AuditRun {run.run_id} refs do not match supplied WorkItems.",
            {"run_refs": sorted(refs), "actual": sorted(actual_ids)},
        )
    if run.plan_ref != plan.plan_id:
        return _error(
            "RUN_PLAN_REF_MISMATCH",
            f"AuditRun {run.run_id} references plan {run.plan_ref}, not {plan.plan_id}.",
        )
    if run.target_snapshot_ref != plan.target_snapshot_ref:
        return _error(
            "RUN_SNAPSHOT_REF_MISMATCH",
            f"AuditRun {run.run_id} and AuditPlan {plan.plan_id} reference different snapshots.",
        )
    return _pass("RUN_WORK_ITEM_REFERENCES_VALID", "Run, plan, and WorkItems form a closed reference set.")


def _is_reusable_item(
    work_item: AuditWorkItem,
    evidence_for_item: List[Evidence],
) -> bool:
    return (
        work_item.action == WorkItemAction.REUSE
        and bool(evidence_for_item)
        and all(e.validity == EvidenceValidity.VALID for e in evidence_for_item)
    )


def derive_coverage_completeness(
    plan: AuditPlan,
    work_items: List[AuditWorkItem],
    evidence_list: Optional[List[Evidence]] = None,
) -> RunCoverageCompleteness:
    """Derive coverage from domain set inclusion, execution and prior evidence."""
    evidence_by_item: Dict[str, List[Evidence]] = {}
    for evidence in evidence_list or []:
        evidence_by_item.setdefault(evidence.work_item_ref, []).append(evidence)

    selected = _normalized_scope(plan.resolved_scope)
    covered: set[str] = set()
    blocked: set[str] = set()

    for wi in work_items:
        domain = _scope_domain(wi.target_surface)
        item_evidence = evidence_by_item.get(wi.work_item_id, [])
        reusable = _is_reusable_item(wi, item_evidence)
        completed = (
            wi.execution_state == ExecutionState.TERMINATED
            and wi.failure_state == WorkItemFailureState.NONE
        )
        if (reusable or completed) and domain in selected:
            covered.add(domain)
        if wi.failure_state == WorkItemFailureState.SAFETY_BLOCK and domain in selected:
            blocked.add(domain)

    if not selected or not work_items:
        return RunCoverageCompleteness.NONE
    if covered >= selected and not blocked:
        return RunCoverageCompleteness.FULL
    if not covered:
        return RunCoverageCompleteness.NONE
    return RunCoverageCompleteness.PARTIAL


def validate_evidence_set_for_run(
    run: AuditRun,
    work_items: List[AuditWorkItem],
    evidence_list: List[Evidence],
    snapshot: Optional[TargetSnapshot] = None,
) -> ValidationResult:
    """Validate every Evidence edge used by the run."""
    work_item_map = {wi.work_item_id: wi for wi in work_items}
    for evidence in evidence_list:
        wi = work_item_map.get(evidence.work_item_ref)
        if wi is None:
            return _error(
                "EVIDENCE_DANGLING_WORK_ITEM_REF",
                f"Evidence {evidence.evidence_id} references missing WorkItem {evidence.work_item_ref}.",
            )
        if snapshot is not None:
            result = validate_evidence_snapshot_consistency(evidence, wi, snapshot)
            if result.is_error:
                return result
        elif evidence.target_snapshot_ref != run.target_snapshot_ref:
            return _error(
                "EVIDENCE_SNAPSHOT_MISMATCH",
                f"Evidence {evidence.evidence_id} references a snapshot outside the run.",
            )
    return _pass("RUN_EVIDENCE_REFERENCES_VALID", "All run Evidence references resolve.")


# ---------------------------------------------------------------------------
# §3 — State Machine & Cross-Object Transitions
# ---------------------------------------------------------------------------


def validate_work_item_state_machine(work_item: AuditWorkItem) -> ValidationResult:
    """
    Validates that execution_state is consistent with attempt history.
    RUNNING requires at least one unfinished attempt.
    TERMINATED requires at least one attempt.
    (semantic-validators.md §3)
    """
    state = work_item.execution_state
    attempts = work_item.attempts

    if state == ExecutionState.RUNNING:
        if not attempts:
            return _error(
                "WORK_ITEM_RUNNING_NO_ATTEMPTS",
                f"WorkItem {work_item.work_item_id} is RUNNING but has no attempts.",
            )
        active = [a for a in attempts if not a.is_finished]
        if not active:
            return _error(
                "WORK_ITEM_RUNNING_ALL_ATTEMPTS_FINISHED",
                f"WorkItem {work_item.work_item_id} is RUNNING but all attempts are finished.",
            )
    if state == ExecutionState.TERMINATED:
        if not attempts:
            return _error(
                "WORK_ITEM_TERMINATED_NO_ATTEMPTS",
                f"WorkItem {work_item.work_item_id} is TERMINATED but has no attempts.",
            )
    return _pass("WORK_ITEM_STATE_MACHINE_VALID", f"WorkItem state machine is consistent.")


def validate_run_not_complete_with_running_items(
    run: AuditRun,
    work_items: List[AuditWorkItem],
) -> ValidationResult:
    """
    An AuditRun cannot be COMPLETE if any referenced WorkItem is still RUNNING.
    (semantic-validators.md §3)
    """
    if run.execution_completeness != RunExecutionCompleteness.COMPLETE:
        return _pass("RUN_COMPLETION_NOT_CLAIMED", "Run is not claiming COMPLETE status.")

    running = [wi for wi in work_items if wi.execution_state == ExecutionState.RUNNING]
    if running:
        return _error(
            "RUN_COMPLETE_WITH_RUNNING_ITEMS",
            f"AuditRun {run.run_id} claims COMPLETE but {len(running)} WorkItem(s) are still RUNNING.",
            {"running_item_ids": [wi.work_item_id for wi in running]},
        )
    return _pass("RUN_COMPLETION_CONSISTENT", "Run COMPLETE status is consistent with WorkItem states.")


# ---------------------------------------------------------------------------
# §4 — Incremental / Reuse Validity (ADR-04)
# ---------------------------------------------------------------------------


def validate_reuse_action_has_valid_evidence(
    work_item: AuditWorkItem,
    evidence_for_item: List[Evidence],
) -> ValidationResult:
    """
    REUSE is only legal if prior evidence exists and is VALID.
    INVALID evidence + REUSE action = ERROR. (semantic-validators.md §4, ADR-04)
    """
    if work_item.action != WorkItemAction.REUSE:
        return _pass("REUSE_CHECK_SKIPPED", f"WorkItem action is {work_item.action.value}, not REUSE.")

    if not evidence_for_item:
        return _error(
            "REUSE_NO_PRIOR_EVIDENCE",
            f"WorkItem {work_item.work_item_id} action=REUSE but no prior evidence found.",
        )

    invalid_evidence = [e for e in evidence_for_item if e.validity == EvidenceValidity.INVALID]
    if invalid_evidence:
        return _error(
            "REUSE_INVALID_EVIDENCE",
            f"WorkItem {work_item.work_item_id} action=REUSE but evidence is INVALID. "
            "INVALID evidence cannot be reused. (ADR-04)",
            {"invalid_evidence_ids": [e.evidence_id for e in invalid_evidence]},
        )

    not_determinable = [e for e in evidence_for_item if e.validity == EvidenceValidity.NOT_DETERMINABLE]
    if not_determinable:
        return _error(
            "REUSE_UNDETERMINABLE_EVIDENCE",
            f"WorkItem {work_item.work_item_id} action=REUSE but evidence validity is NOT_DETERMINABLE. "
            "Fail-safe: treat as REAUDIT required. (ADR-04)",
        )

    return _pass("REUSE_EVIDENCE_VALID", f"WorkItem REUSE action has valid prior evidence.")


# ---------------------------------------------------------------------------
# §5 — Evidence & Finding Lifecycle Integrity (ADR-04)
# ---------------------------------------------------------------------------


def validate_evidence_invalid_not_reused(
    work_item: AuditWorkItem,
    evidence_for_item: List[Evidence],
) -> ValidationResult:
    """
    Evidence=INVALID cannot coexist with WorkItem.action=REUSE for the same evidence.
    INVALIDATE ≠ FIXED: missing evidence does not authorize marking finding as FIXED.
    (semantic-validators.md §5)
    """
    if work_item.action != WorkItemAction.REUSE:
        return _pass("EVIDENCE_REUSE_CHECK_SKIPPED", "Not a REUSE action.")

    invalid = [e for e in evidence_for_item if e.validity == EvidenceValidity.INVALID]
    if invalid:
        return _error(
            "EVIDENCE_INVALID_WITH_REUSE",
            f"WorkItem {work_item.work_item_id}: INVALID evidence cannot be paired with action=REUSE. "
            "(INVALIDATE ≠ FIXED — semantic-validators §5)",
        )
    return _pass("EVIDENCE_VALIDITY_CONSISTENT_WITH_ACTION", "Evidence validity is consistent with action.")


def validate_finding_lifecycle_transition(
    previous_lifecycle: FindingLifecycle,
    new_lifecycle: FindingLifecycle,
) -> ValidationResult:
    """Validate the explicit FindingLifecycle state machine."""
    transitions = {
        FindingLifecycle.NEW: {
            FindingLifecycle.PERSISTING,
            FindingLifecycle.MODIFIED,
            FindingLifecycle.FIXED,
            FindingLifecycle.INVALIDATED,
        },
        FindingLifecycle.PERSISTING: {
            FindingLifecycle.PERSISTING,
            FindingLifecycle.MODIFIED,
            FindingLifecycle.FIXED,
            FindingLifecycle.INVALIDATED,
        },
        FindingLifecycle.MODIFIED: {
            FindingLifecycle.PERSISTING,
            FindingLifecycle.MODIFIED,
            FindingLifecycle.FIXED,
            FindingLifecycle.INVALIDATED,
        },
        FindingLifecycle.FIXED: {
            FindingLifecycle.FIXED,
            FindingLifecycle.REGRESSED,
        },
        FindingLifecycle.REGRESSED: {
            FindingLifecycle.PERSISTING,
            FindingLifecycle.MODIFIED,
            FindingLifecycle.FIXED,
            FindingLifecycle.INVALIDATED,
        },
        FindingLifecycle.INVALIDATED: {
            FindingLifecycle.NEW,
            FindingLifecycle.PERSISTING,
            FindingLifecycle.MODIFIED,
        },
    }
    allowed = transitions.get(previous_lifecycle, set())
    if new_lifecycle not in allowed:
        if new_lifecycle == FindingLifecycle.REGRESSED:
            return _error(
                "FINDING_LIFECYCLE_INVALID_REGRESSION",
                f"Finding cannot transition {previous_lifecycle.value} -> REGRESSED. "
                "REGRESSED requires a prior FIXED state.",
            )
        if new_lifecycle == FindingLifecycle.FIXED and previous_lifecycle == FindingLifecycle.INVALIDATED:
            return _error(
                "FINDING_INVALIDATED_NOT_FIXED",
                "INVALIDATED cannot transition directly to FIXED; invalid evidence is not remediation proof.",
            )
        return _error(
            "FINDING_LIFECYCLE_INVALID_TRANSITION",
            f"Lifecycle transition {previous_lifecycle.value} -> {new_lifecycle.value} is not permitted.",
        )
    return _pass(
        "FINDING_LIFECYCLE_TRANSITION_VALID",
        f"Lifecycle transition {previous_lifecycle.value} -> {new_lifecycle.value} is valid.",
    )


def validate_finding_lifecycle_sequence(
    history: List[FindingLifecycle],
) -> ValidationReport:
    """Validate a complete lifecycle history from earliest to latest state."""
    if not history:
        return ValidationReport([
            _undeterminable("FINDING_LIFECYCLE_EMPTY", "No lifecycle history supplied.")
        ])
    results: List[ValidationResult] = [
        validate_finding_lifecycle_transition(previous, current)
        for previous, current in zip(history, history[1:])
    ]
    if not results:
        results.append(_pass("FINDING_LIFECYCLE_SINGLE_STATE", "Single-state lifecycle history is valid."))
    return ValidationReport(results)


# ---------------------------------------------------------------------------
# §6 — Coverage Completeness (Derived, Not Declared)
# ---------------------------------------------------------------------------


def validate_coverage_not_full_with_blocked_items(
    run: AuditRun,
    work_items: List[AuditWorkItem],
) -> ValidationResult:
    """
    If any WorkItem was BLOCKED, coverage is strictly PARTIAL.
    Coverage cannot be FULL if safety gate blocked any domain.
    (semantic-validators.md §6)
    """
    blocked = [wi for wi in work_items if wi.failure_state == WorkItemFailureState.SAFETY_BLOCK]
    if not blocked:
        return _pass("COVERAGE_NO_BLOCKED_ITEMS", "No SAFETY_BLOCK items — coverage may be FULL.")

    all_blocked = len(blocked) == len(work_items)

    if all_blocked and run.coverage_completeness not in (RunCoverageCompleteness.NONE,):
        return _error(
            "COVERAGE_MUST_BE_NONE_ALL_BLOCKED",
            f"Run {run.run_id}: ALL {len(blocked)} WorkItem(s) were SAFETY_BLOCK. "
            "Coverage must be NONE — no audit was performed. (ADR-07 §2: BLOCKED ≠ PARTIAL)",
            {
                "blocked_item_ids": [wi.work_item_id for wi in blocked],
                "declared_coverage": run.coverage_completeness.value,
            },
        )
    if not all_blocked and run.coverage_completeness == RunCoverageCompleteness.FULL:
        return _error(
            "COVERAGE_FULL_WITH_BLOCKED_ITEMS",
            f"Run {run.run_id} claims FULL coverage but {len(blocked)} WorkItem(s) were SAFETY_BLOCK. "
            "Coverage must be PARTIAL when any item was blocked by the safety gate.",
            {"blocked_item_ids": [wi.work_item_id for wi in blocked]},
        )
    return _pass("COVERAGE_BLOCKED_CONSISTENT", "Coverage is consistent with BLOCKED items.")


def validate_coverage_completeness_derivable(
    run: AuditRun,
    plan: AuditPlan,
    work_items: List[AuditWorkItem],
    evidence_list: Optional[List[Evidence]] = None,
) -> ValidationResult:
    """Coverage is derived from domain set inclusion, not item counts."""
    selected = _normalized_scope(plan.resolved_scope)
    if plan.applicability_decisions:
        derived_selected = derive_selected_scope(plan)
        if derived_selected != selected:
            return _error(
                "PLAN_SCOPE_RESOLUTION_MISMATCH",
                f"AuditPlan {plan.plan_id} resolved_scope differs from applicability-derived scope.",
                {
                    "selected_scope": sorted(derived_selected),
                    "resolved_scope": sorted(selected),
                },
            )

    expected = derive_coverage_completeness(plan, work_items, evidence_list)
    evidence_by_item: Dict[str, List[Evidence]] = {}
    for evidence in evidence_list or []:
        evidence_by_item.setdefault(evidence.work_item_ref, []).append(evidence)

    covered = {
        _scope_domain(wi.target_surface)
        for wi in work_items
        if _scope_domain(wi.target_surface) in selected
        and (
            (
                wi.action == WorkItemAction.REUSE
                and bool(evidence_by_item.get(wi.work_item_id))
                and all(
                    e.validity == EvidenceValidity.VALID
                    for e in evidence_by_item[wi.work_item_id]
                )
            )
            or (
                wi.execution_state == ExecutionState.TERMINATED
                and wi.failure_state == WorkItemFailureState.NONE
            )
        )
    }

    if run.coverage_completeness != expected:
        return _error(
            "COVERAGE_COMPLETENESS_MISMATCH",
            f"Run {run.run_id}: declared coverage_completeness={run.coverage_completeness.value} "
            f"but derived value is {expected.value}.",
            {
                "selected_scope": sorted(selected),
                "covered_scope": sorted(covered),
                "missing_scope": sorted(selected - covered),
                "derived": expected.value,
                "declared": run.coverage_completeness.value,
            },
        )
    return _pass(
        "COVERAGE_COMPLETENESS_DERIVABLE",
        f"Coverage is derivable: covered={sorted(covered)}, selected={sorted(selected)}.",
    )


# ---------------------------------------------------------------------------
# §7 — Budget & Attempt Consistency (ADR-07)
# ---------------------------------------------------------------------------


def validate_attempt_ordering(work_item: AuditWorkItem) -> ValidationResult:
    """
    Attempt #N cannot exist without Attempt #N-1.
    Temporal ordering: attempt[i].started_at >= attempt[i-1].finished_at
    (semantic-validators.md §7)
    """
    attempts = work_item.attempts
    for i in range(1, len(attempts)):
        prev = attempts[i - 1]
        curr = attempts[i]
        if not prev.is_finished:
            return _error(
                "ATTEMPT_ORDERING_PREV_NOT_FINISHED",
                f"WorkItem {work_item.work_item_id}: Attempt #{i} started before "
                f"Attempt #{i - 1} ({prev.attempt_id}) was finished.",
            )
        if prev.finished_at and curr.started_at < prev.finished_at:
            return _error(
                "ATTEMPT_ORDERING_TEMPORAL_VIOLATION",
                f"WorkItem {work_item.work_item_id}: Attempt #{i + 1} started at "
                f"{curr.started_at.isoformat()} which is before Attempt #{i} "
                f"finished at {prev.finished_at.isoformat()}.",
            )
    return _pass("ATTEMPT_ORDERING_VALID", "Attempt ordering is temporally consistent.")


# ---------------------------------------------------------------------------
# §8 — Trust, Safety & Egress (ADR-05)
# ---------------------------------------------------------------------------


def validate_execution_gate(work_item: AuditWorkItem) -> ValidationResult:
    """
    Command execution without a validated capability set -> ERROR.
    Deny-by-default: unknown permissions must not authorize execution.
    (ADR-05, semantic-validators.md §8)
    """
    policy = work_item.effective_execution_policy
    # Credentials must never be implicitly inherited from host
    # Only NONE or EXPLICIT_ONLY are safe values
    from .models import CredentialAccess
    if policy.credentials not in (CredentialAccess.NONE, CredentialAccess.EXPLICIT_ONLY):
        return _error(
            "EXECUTION_GATE_UNKNOWN_CREDENTIAL_ACCESS",
            f"WorkItem {work_item.work_item_id}: execution policy credentials="
            f"{policy.credentials} is not a recognized safe value. Deny-by-default. (ADR-05)",
        )
    return _pass("EXECUTION_GATE_POLICY_VALID", "Execution policy is within safe parameters.")


def validate_egress_policy(
    work_item: AuditWorkItem,
    data_is_sensitive: Optional[bool] = None,
) -> ValidationResult:
    """
    EgressPolicy=DENY + sensitive data -> ERROR (cannot result in ALLOWED).
    If sensitivity is UNKNOWN (None), fail-closed (treat as sensitive).
    (ADR-05, semantic-validators.md §8)
    """
    policy = work_item.data_egress_policy
    # UNKNOWN (None) is treated as True (fail closed)
    is_sensitive = data_is_sensitive if data_is_sensitive is not None else True
    
    if (
        policy.destination == EgressDestination.LOCAL_ONLY
        and not policy.allow_sensitive
        and is_sensitive
    ):
        return _error(
            "EGRESS_SENSITIVE_DATA_DENIED",
            f"WorkItem {work_item.work_item_id}: data_egress_policy denies external egress "
            f"but sensitive data was detected (or sensitivity is UNKNOWN). DO NOT SEND. (ADR-05)",
        )
    return _pass("EGRESS_POLICY_CONSISTENT", "Egress policy is consistent with data classification.")


def validate_snapshot_drift(
    run: AuditRun,
    current_snapshot_fingerprint: str,
) -> ValidationResult:
    """
    If the project changed during execution (snapshot drift), the run must
    be stopped and affected evidence invalidated. (canonical §1, §5)
    """
    if run.target_snapshot_ref != current_snapshot_fingerprint:
        return _error(
            "SNAPSHOT_DRIFT_DETECTED",
            f"Run {run.run_id}: target_snapshot_ref ({run.target_snapshot_ref[:16]}...) "
            f"does not match current snapshot ({current_snapshot_fingerprint[:16]}...). "
            "Snapshot drift detected — execution must stop and affected evidence must be invalidated.",
            {
                "run_snapshot": run.target_snapshot_ref,
                "current_snapshot": current_snapshot_fingerprint,
            },
        )
    return _pass("SNAPSHOT_INTEGRITY_VALID", "Snapshot fingerprint is intact — no drift detected.")


# ---------------------------------------------------------------------------
# §9 — Publication Eligibility (The Final Gate)
# ---------------------------------------------------------------------------


def validate_publication_artifacts_registered(run: AuditRun) -> ValidationResult:
    """A complete audit must register the four required Markdown artifact outputs."""
    required = {
        "00_inventory.md",
        "01_coverage.md",
        "02_analytical.md",
        "03_audit_ledger.md",
    }
    registered = {ref.rsplit("/", 1)[-1] for ref in run.artifact_refs}
    missing = sorted(required - registered)
    if missing:
        return _error(
            "PUBLISH_ARTIFACTS_MISSING",
            f"Run {run.run_id}: required audit artifacts are not fully registered.",
            {"missing_artifacts": missing, "registered_artifacts": sorted(registered)},
        )
    return _pass(
        "PUBLISH_ARTIFACTS_REGISTERED",
        "All four required audit Markdown artifacts are registered.",
    )


def can_publish(
    run: AuditRun,
    work_items: List[AuditWorkItem],
    evidence_list: List[Evidence],
    current_snapshot_fingerprint: str,
    plan: AuditPlan,
) -> ValidationReport:
    """
    can_publish(run) -> ValidationReport

    Returns PASS only when ALL publication eligibility conditions are met.
    This is a DERIVED decision, not an arbitrary flag.
    (semantic-validators.md §9)

    Conditions that PREVENT publication:
      - Snapshot drift
      - Any FAILED or BLOCKED items without explicit risk acceptance
      - Invalid evidence referenced by REUSE items
      - Coverage is not FULL (unless PARTIAL publication is explicitly authorized)
      - Execution is not COMPLETE
    """
    results: List[ValidationResult] = []

    if len(work_items) == 0:
        results.append(_error("PUBLISH_EMPTY_AUDIT", "Cannot publish an audit with no work items."))
        # Early return because other checks don't make sense on empty
        return ValidationReport(results)
    
    if run.coverage_completeness == RunCoverageCompleteness.NONE:
        results.append(_error("PUBLISH_EMPTY_COVERAGE", "Cannot publish an audit with NONE coverage."))

    # 1. Snapshot integrity
    drift = validate_snapshot_drift(run, current_snapshot_fingerprint)
    results.append(drift)

    # 2. Execution completeness
    if run.execution_completeness not in (
        RunExecutionCompleteness.COMPLETE,
    ):
        results.append(
            _error(
                "PUBLISH_EXECUTION_INCOMPLETE",
                f"Run {run.run_id}: cannot publish. "
                f"execution_completeness={run.execution_completeness.value} (must be COMPLETE).",
            )
        )
    else:
        results.append(_pass("PUBLISH_EXECUTION_COMPLETE", "Execution is COMPLETE."))

    # 3. No FAILED items
    failed_items = [
        wi for wi in work_items
        if wi.failure_state not in (WorkItemFailureState.NONE,)
        and wi.execution_state == ExecutionState.TERMINATED
    ]
    if failed_items:
        results.append(
            _error(
                "PUBLISH_HAS_FAILED_ITEMS",
                f"Run {run.run_id}: {len(failed_items)} WorkItem(s) have failure states. "
                "Cannot publish without explicit risk acceptance.",
                {"failed_item_ids": [wi.work_item_id for wi in failed_items]},
            )
        )
    else:
        results.append(_pass("PUBLISH_NO_FAILED_ITEMS", "No WorkItems have failure states."))

    # 4. No INVALID evidence (REUSE items)
    reuse_items = {wi.work_item_id for wi in work_items if wi.action == WorkItemAction.REUSE}
    invalid_reuse_evidence = [
        e for e in evidence_list
        if e.work_item_ref in reuse_items and e.validity == EvidenceValidity.INVALID
    ]
    if invalid_reuse_evidence:
        results.append(
            _error(
                "PUBLISH_INVALID_REUSE_EVIDENCE",
                f"Run {run.run_id}: {len(invalid_reuse_evidence)} INVALID evidence item(s) "
                "referenced by REUSE WorkItems. (ADR-04)",
            )
        )
    else:
        results.append(_pass("PUBLISH_EVIDENCE_VALID", "No INVALID evidence in REUSE items."))

    # 5. Required audit artifacts
    results.append(validate_publication_artifacts_registered(run))

    # 6. Run failure state
    if run.failure_state != RunFailureState.NONE:
        results.append(
            _error(
                "PUBLISH_RUN_FAILURE_STATE",
                f"Run {run.run_id}: failure_state={run.failure_state.value}. Cannot publish.",
            )
        )
    else:
        results.append(_pass("PUBLISH_NO_FAILURE_STATE", "Run has no failure state."))

    return ValidationReport(results=results)


# ---------------------------------------------------------------------------
# Composite validators — run full validation suites
# ---------------------------------------------------------------------------

def validate_state_graph(
    snapshot: TargetSnapshot,
    plan: AuditPlan,
    work_items: List[AuditWorkItem],
    run: AuditRun,
    evidence_list: List[Evidence],
) -> ValidationReport:
    """Validate the complete Phase 2 state graph without mutation.

    This is the deterministic semantic gateway for the cross-object model:
    Snapshot -> Plan -> WorkItems -> Attempts -> Run -> Evidence.
    """
    results: List[ValidationResult] = [
        validate_target_snapshot_immutability(snapshot),
        validate_target_snapshot_fingerprint_matches(snapshot),
        validate_plan_snapshot_consistency(plan, snapshot),
        validate_plan_scope_resolution(plan),
        validate_plan_work_item_references(plan, work_items),
        validate_work_item_scope_membership(plan, work_items),
        validate_run_work_item_references(run, plan, work_items),
        validate_run_not_complete_with_running_items(run, work_items),
        validate_coverage_not_full_with_blocked_items(run, work_items),
        validate_coverage_completeness_derivable(run, plan, work_items, evidence_list),
        validate_evidence_set_for_run(run, work_items, evidence_list, snapshot),
    ]
    for work_item in work_items:
        item_evidence = [
            evidence for evidence in evidence_list
            if evidence.work_item_ref == work_item.work_item_id
        ]
        results.extend(
            validate_work_item(
                work_item,
                [plan.plan_id],
                item_evidence,
            ).results
        )
        results.append(
            validate_completed_work_item_has_evidence(work_item, item_evidence)
        )
    return ValidationReport(results)



def validate_work_item(
    work_item: AuditWorkItem,
    known_plan_ids: List[str],
    evidence_for_item: Optional[List[Evidence]] = None,
) -> ValidationReport:
    """Run all semantic validators applicable to a single AuditWorkItem."""
    evidence_for_item = evidence_for_item or []
    results = [
        validate_work_item_plan_ref(work_item, known_plan_ids),
        validate_work_item_state_machine(work_item),
        validate_attempt_ordering(work_item),
        validate_execution_gate(work_item),
        validate_reuse_action_has_valid_evidence(work_item, evidence_for_item),
        validate_evidence_invalid_not_reused(work_item, evidence_for_item),
    ]
    return ValidationReport(results=results)


def validate_run(
    run: AuditRun,
    plan: AuditPlan,
    work_items: List[AuditWorkItem],
    known_run_ids: Optional[List[str]] = None,
    interrupted_run_ids: Optional[List[str]] = None,
) -> ValidationReport:
    """Run all semantic validators applicable to an AuditRun."""
    known_run_ids = known_run_ids or []
    interrupted_run_ids = interrupted_run_ids or []
    # Run persistence can occur during intermediate execution states. The
    # terminal, full graph invariants (scope derivation and coverage derivation)
    # are enforced by validate_state_graph once all Evidence is available.
    results = [
        validate_run_not_complete_with_running_items(run, work_items),
        validate_run_work_item_references(run, plan, work_items),
        validate_coverage_not_full_with_blocked_items(run, work_items),
        validate_run_recovery_ref(run, known_run_ids, interrupted_run_ids),
        validate_run_previous_ref_distinct_from_recovery(run),
    ]
    return ValidationReport(results=results)


def validate_snapshot(snapshot: TargetSnapshot) -> ValidationReport:
    """Run all semantic validators applicable to a TargetSnapshot."""
    results = [
        validate_target_snapshot_immutability(snapshot),
        validate_target_snapshot_fingerprint_matches(snapshot),
    ]
    return ValidationReport(results=results)
