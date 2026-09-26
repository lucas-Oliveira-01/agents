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

from .models import (
    AuditWorkItem,
    Evidence,
    EvidenceValidity,
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
