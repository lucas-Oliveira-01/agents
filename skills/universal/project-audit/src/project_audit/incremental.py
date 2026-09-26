"""
incremental.py — Deterministic Evidence Dependency Graph and action matrix.

Phase 3 freezes the previously deferred dependency algorithm from ADR-04.

The graph is conservative:
- source_inputs are hard dependencies;
- semantic dependencies are soft dependencies;
- deleted/missing dependencies invalidate old evidence;
- source changes require REAUDIT;
- soft dependency changes require REVALIDATE;
- breaking methodology changes require REAUDIT;
- auditor implementation changes require REVALIDATE;
- indeterminate state fails safe to REAUDIT.

INVALIDATE is an evidence-level planning decision. The canonical
AuditWorkItem action remains executable (REUSE/REVALIDATE/REAUDIT); an
INVALIDATE decision is therefore bound to REAUDIT so stale evidence is
not reused and a fresh executable WorkItem is scheduled.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Optional, Tuple
import uuid

from .models import (
    AuditWorkItem,
    Evidence,
    EvidenceValidity,
    Provenance,
    MethodologyState,
    TargetSnapshot,
    WorkItemAction,
)


class DependencyKind(str, Enum):
    SOURCE = "SOURCE"
    SEMANTIC = "SEMANTIC"
    METHODOLOGY_CONTRACT = "METHODOLOGY_CONTRACT"
    METHODOLOGY_POLICY = "METHODOLOGY_POLICY"
    AUDITOR_VERSION = "AUDITOR_VERSION"


class IncrementalDecision(str, Enum):
    REUSE = "REUSE"
    REVALIDATE = "REVALIDATE"
    REAUDIT = "REAUDIT"
    INVALIDATE = "INVALIDATE"


@dataclass(frozen=True)
class DependencyNode:
    kind: DependencyKind
    key: str
    observed_fingerprint: Optional[str]


@dataclass(frozen=True)
class EvidenceDependencyGraph:
    evidence_id: str
    target_snapshot_ref: str
    auditor: str
    nodes: Tuple[DependencyNode, ...]

    @property
    def source_nodes(self) -> Tuple[DependencyNode, ...]:
        return tuple(node for node in self.nodes if node.kind == DependencyKind.SOURCE)

    @property
    def semantic_nodes(self) -> Tuple[DependencyNode, ...]:
        return tuple(node for node in self.nodes if node.kind == DependencyKind.SEMANTIC)


def normalize_input_ref(value: str) -> str:
    """Convert a source/dependency reference into a snapshot input path."""
    text = str(value).strip().replace("\\", "/").lstrip("./")
    if not text:
        return ""
    # Location annotations such as path:10, path:10-20 or path#L10 do not
    # change dependency identity. Preserve Windows drive-letter prefixes.
    if ":" in text and not (len(text) >= 2 and text[1] == ":"):
        head, suffix = text.rsplit(":", 1)
        pieces = suffix.split("-", 1)
        if suffix.isdigit() or (len(pieces) == 2 and all(part.isdigit() for part in pieces)):
            text = head
    if "#L" in text:
        head, suffix = text.rsplit("#L", 1)
        pieces = suffix.split("-", 1)
        if suffix.isdigit() or (len(pieces) == 2 and all(part.isdigit() for part in pieces)):
            text = head
    return text


def _snapshot_inputs(snapshot: TargetSnapshot) -> Mapping[str, str]:
    return {
        item.path.replace("\\", "/").lstrip("./"): item.fingerprint
        for item in snapshot.project_state.tracked_input_fingerprints
    }


def _auditor_version(methodology: MethodologyState, auditor: str) -> Optional[str]:
    versions = dict(methodology.auditor_versions)
    if auditor in versions:
        return versions[auditor]
    if auditor.endswith("-audit") and auditor[:-6] in versions:
        return versions[auditor[:-6]]
    if auditor == "project-audit/single-agent":
        return versions.get("project-audit")
    return None


def build_dependency_graph(
    evidence: Evidence,
    snapshot: TargetSnapshot,
    auditor: str,
) -> EvidenceDependencyGraph:
    """Freeze dependency edges against the snapshot that produced evidence."""
    inputs = _snapshot_inputs(snapshot)
    nodes = []

    for ref in sorted({normalize_input_ref(value) for value in evidence.source_refs} - {""}):
        nodes.append(
            DependencyNode(
                kind=DependencyKind.SOURCE,
                key=ref,
                observed_fingerprint=inputs.get(ref),
            )
        )

    for ref in sorted({normalize_input_ref(value) for value in evidence.dependencies} - {""}):
        nodes.append(
            DependencyNode(
                kind=DependencyKind.SEMANTIC,
                key=ref,
                observed_fingerprint=inputs.get(ref),
            )
        )

    nodes.extend(
        [
            DependencyNode(
                kind=DependencyKind.METHODOLOGY_CONTRACT,
                key="methodology:contract",
                observed_fingerprint=snapshot.methodology_state.audit_contract_version,
            ),
            DependencyNode(
                kind=DependencyKind.METHODOLOGY_POLICY,
                key="methodology:policy",
                observed_fingerprint=snapshot.methodology_state.policy_version,
            ),
            DependencyNode(
                kind=DependencyKind.AUDITOR_VERSION,
                key="methodology:auditor:" + auditor,
                observed_fingerprint=_auditor_version(snapshot.methodology_state, auditor),
            ),
        ]
    )

    return EvidenceDependencyGraph(
        evidence_id=evidence.evidence_id,
        target_snapshot_ref=evidence.target_snapshot_ref,
        auditor=auditor,
        nodes=tuple(nodes),
    )


def _current_value(
    node: DependencyNode,
    snapshot: TargetSnapshot,
    auditor: str,
) -> Optional[str]:
    inputs = _snapshot_inputs(snapshot)
    if node.kind in (DependencyKind.SOURCE, DependencyKind.SEMANTIC):
        return inputs.get(node.key)
    if node.kind == DependencyKind.METHODOLOGY_CONTRACT:
        return snapshot.methodology_state.audit_contract_version
    if node.kind == DependencyKind.METHODOLOGY_POLICY:
        return snapshot.methodology_state.policy_version
    if node.kind == DependencyKind.AUDITOR_VERSION:
        return _auditor_version(snapshot.methodology_state, auditor)
    return None


def decide_incremental_action(
    evidence: Evidence,
    previous_snapshot: TargetSnapshot,
    current_snapshot: TargetSnapshot,
    auditor: str,
) -> IncrementalDecision:
    """Apply the frozen ADR-04 precedence:
    INVALIDATE > REAUDIT > REVALIDATE > REUSE.
    """
    if evidence.validity == EvidenceValidity.INVALID:
        return IncrementalDecision.INVALIDATE
    if evidence.validity == EvidenceValidity.NOT_DETERMINABLE:
        return IncrementalDecision.REAUDIT

    if not evidence.source_refs and not evidence.dependencies:
        return IncrementalDecision.REAUDIT

    graph = build_dependency_graph(evidence, previous_snapshot, auditor)

    # Deleted/unresolvable dependencies invalidate factual evidence first.
    for node in graph.nodes:
        if node.kind in (DependencyKind.SOURCE, DependencyKind.SEMANTIC):
            if node.observed_fingerprint is None:
                return IncrementalDecision.REAUDIT
            if _current_value(node, current_snapshot, auditor) is None:
                return IncrementalDecision.INVALIDATE

    # Breaking methodology invalidates the old assessment's compatibility.
    for node in graph.nodes:
        if node.kind in (
            DependencyKind.METHODOLOGY_CONTRACT,
            DependencyKind.METHODOLOGY_POLICY,
        ) and node.observed_fingerprint != _current_value(node, current_snapshot, auditor):
            return IncrementalDecision.REAUDIT

    # Source changes invalidate reuse and require substantive re-analysis.
    for node in graph.source_nodes:
        if node.observed_fingerprint != _current_value(node, current_snapshot, auditor):
            return IncrementalDecision.REAUDIT

    # Loosely coupled semantic dependency changes require cheap revalidation.
    for node in graph.semantic_nodes:
        if node.observed_fingerprint != _current_value(node, current_snapshot, auditor):
            return IncrementalDecision.REVALIDATE

    # Auditor implementation drift affects the assessment, not the observed fact.
    for node in graph.nodes:
        if node.kind == DependencyKind.AUDITOR_VERSION:
            current = _current_value(node, current_snapshot, auditor)
            if node.observed_fingerprint is None or current is None:
                return IncrementalDecision.REAUDIT
            if node.observed_fingerprint != current:
                return IncrementalDecision.REVALIDATE

    if evidence.validity == EvidenceValidity.STALE:
        return IncrementalDecision.REVALIDATE

    return IncrementalDecision.REUSE


def bind_decision_to_work_item(
    work_item: AuditWorkItem,
    decision: IncrementalDecision,
) -> AuditWorkItem:
    """Bind a planning decision to the executable canonical WorkItem action."""
    action = {
        IncrementalDecision.REUSE: WorkItemAction.REUSE,
        IncrementalDecision.REVALIDATE: WorkItemAction.REVALIDATE,
        IncrementalDecision.REAUDIT: WorkItemAction.REAUDIT,
        # INVALIDATE is evidence-level. The old evidence is invalidated and a
        # fresh executable audit is scheduled.
        IncrementalDecision.INVALIDATE: WorkItemAction.REAUDIT,
    }[decision]
    work_item.action = action
    work_item.decision_basis = (
        "incremental_decision=" + decision.value
        + "; executable_action=" + action.value
        + "; evidence_reuse="
        + ("allowed" if decision == IncrementalDecision.REUSE else "denied")
    )
    return work_item


def plan_incremental_actions(
    work_items: Iterable[AuditWorkItem],
    evidence_by_work_item: Mapping[str, Evidence],
    previous_snapshot: TargetSnapshot,
    current_snapshot: TargetSnapshot,
) -> Tuple[IncrementalDecision, ...]:
    """Compute and bind deterministic actions for an existing WorkItem set."""
    decisions = []
    for work_item in work_items:
        evidence = evidence_by_work_item.get(work_item.work_item_id)
        if evidence is None:
            decision = IncrementalDecision.REAUDIT
            work_item.action = WorkItemAction.REAUDIT
            work_item.decision_basis = (
                "incremental_decision=REAUDIT; reason=missing_prior_evidence"
            )
        else:
            decision = decide_incremental_action(
                evidence=evidence,
                previous_snapshot=previous_snapshot,
                current_snapshot=current_snapshot,
                auditor=work_item.auditor,
            )
            bind_decision_to_work_item(work_item, decision)
        decisions.append(decision)
    return tuple(decisions)



@dataclass(frozen=True)
class IncrementalBinding:
    """Stable binding between a current WorkItem and prior logical evidence."""

    current_work_item_ref: str
    previous_work_item_ref: Optional[str]
    evidence_ref: Optional[str]
    decision: IncrementalDecision


def stable_work_item_key(work_item: AuditWorkItem) -> Tuple[str, str]:
    """Logical WorkItem identity independent of generated UUIDs."""
    return work_item.auditor, work_item.target_surface


def match_previous_evidence(
    current_work_items: Iterable[AuditWorkItem],
    previous_work_items: Iterable[AuditWorkItem],
    previous_evidence: Mapping[str, Evidence],
) -> Mapping[str, Evidence]:
    """Match evidence to current WorkItems by stable logical identity.

    Ambiguous prior matches are deliberately omitted so the caller fails safe
    to REAUDIT instead of guessing which historical evidence belongs to a task.
    """
    previous_index: dict[Tuple[str, str], list[Tuple[str, Evidence]]] = {}
    for previous in previous_work_items:
        evidence = previous_evidence.get(previous.work_item_id)
        if evidence is None:
            continue
        previous_index.setdefault(stable_work_item_key(previous), []).append(
            (previous.work_item_id, evidence)
        )

    bound: dict[str, Evidence] = {}
    for current in current_work_items:
        matches = previous_index.get(stable_work_item_key(current), [])
        if len(matches) == 1:
            bound[current.work_item_id] = matches[0][1]
    return bound


def plan_incremental_actions_stable(
    current_work_items: Iterable[AuditWorkItem],
    previous_work_items: Iterable[AuditWorkItem],
    previous_evidence: Mapping[str, Evidence],
    previous_snapshot: TargetSnapshot,
    current_snapshot: TargetSnapshot,
) -> Tuple[IncrementalBinding, ...]:
    """Apply the deterministic incremental matrix across regenerated WorkItems."""
    current = tuple(current_work_items)
    evidence_by_current = match_previous_evidence(
        current, previous_work_items, previous_evidence
    )
    previous_by_current = {
        current_item.work_item_id: previous
        for current_item in current
        for previous in previous_work_items
        if stable_work_item_key(current_item) == stable_work_item_key(previous)
    }

    bindings = []
    for item in current:
        evidence = evidence_by_current.get(item.work_item_id)
        previous = previous_by_current.get(item.work_item_id)
        if evidence is None:
            decision = IncrementalDecision.REAUDIT
            item.action = WorkItemAction.REAUDIT
            item.decision_basis = (
                "incremental_decision=REAUDIT; reason=missing_or_ambiguous_prior_evidence"
            )
            bindings.append(
                IncrementalBinding(
                    item.work_item_id,
                    previous.work_item_id if previous is not None else None,
                    None,
                    decision,
                )
            )
            continue

        decision = decide_incremental_action(
            evidence,
            previous_snapshot,
            current_snapshot,
            item.auditor,
        )
        bind_decision_to_work_item(item, decision)
        bindings.append(
            IncrementalBinding(
                item.work_item_id,
                previous.work_item_id if previous is not None else None,
                evidence.evidence_id,
                decision,
            )
        )
    return tuple(bindings)


def derive_reused_evidence(
    prior: Evidence,
    current_snapshot: TargetSnapshot,
    current_work_item: AuditWorkItem,
    *,
    generated_at,
    actor: str = "project-audit/incremental-reuse",
) -> Evidence:
    """Create a fresh immutable Evidence record for a safe REUSE decision."""
    return Evidence(
        evidence_id=str(uuid.uuid4()),
        target_snapshot_ref=current_snapshot.snapshot_fingerprint,
        work_item_ref=current_work_item.work_item_id,
        source_refs=tuple(prior.source_refs),
        dependencies=tuple(prior.dependencies),
        validity=EvidenceValidity.VALID,
        provenance=Provenance(
            actor=actor,
            generated_at=generated_at,
            policy_version=current_snapshot.methodology_state.policy_version,
        ),
        fingerprint=prior.fingerprint,
        provider=prior.provider,
        model=prior.model,
        raw_output=prior.raw_output,
        raw_output_sha256=prior.raw_output_sha256,
        derived_from_evidence_ref=prior.evidence_id,
    )
