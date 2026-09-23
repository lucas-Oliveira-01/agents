from __future__ import annotations

from typing import List, Optional

from .context_builder import build_context
from .discovery import DiscoverySnapshot
from .models import AuditRun, AuditWorkItem
from .orchestrator import Orchestrator
from .semantic_auditor import SemanticAuditor, SemanticReviewResult


def execute_semantic_review(
    orchestrator: Orchestrator,
    discovery: DiscoverySnapshot,
    run: AuditRun,
    work_item: AuditWorkItem,
    worker: SemanticAuditor,
) -> SemanticReviewResult:
    """Prepare minimal context and invoke semantic escalation behind policy gates."""
    context = build_context(discovery, work_item.target_surface)
    result = worker.review(work_item, run, context)

    if result.evidence is not None:
        orchestrator.commit_evidence(result.evidence, work_item)

    return result
