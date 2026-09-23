from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .classifiers import classify_applicability, classify_files, classify_stack
from .discovery import DiscoverySnapshot, discover
from .engineering_runner import EngineeringPassResult, execute_engineering_pass
from .models import EgressPolicy, TargetMode
from .normalization_runner import NormalizationResult, run_audit_normalize
from .orchestrator import Orchestrator
from .planner import PreparedAudit, prepare_audit
from .report_writer import write_audit_artifacts
from .security_runner import SecurityPassResult, execute_security_pass
from .semantic_auditor import SemanticAuditor
from .state_store import StateStore


@dataclass(frozen=True)
class FullAuditResult:
    discovery: DiscoverySnapshot
    prepared: PreparedAudit
    engineering: EngineeringPassResult
    security: SecurityPassResult
    artifacts: Tuple[str, ...]
    normalization: Optional[NormalizationResult]


def run_full_audit(
    target: str,
    *,
    state_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    target_mode: TargetMode = TargetMode.WORKTREE,
    overwrite_artifacts: bool = False,
    normalize: bool = False,
    normalize_command: str = "audit-normalize",
    semantic_worker: Optional[SemanticAuditor] = None,
    semantic_egress_policy: Optional[EgressPolicy] = None,
) -> FullAuditResult:
    """Execute the complete currently implemented single-agent two-pass runtime."""
    discovery = discover(target)
    files = classify_files(discovery)
    stack = classify_stack(discovery)
    applicability = classify_applicability(discovery, stack)
    prepared = prepare_audit(
        discovery,
        files,
        applicability,
        target_mode=target_mode,
    )

    if semantic_worker is not None:
        if semantic_egress_policy is None:
            raise ValueError(
                "semantic_worker requires an explicit semantic_egress_policy."
            )
        prepared.plan.egress_policy = semantic_egress_policy
        for item in prepared.work_items:
            item.data_egress_policy = semantic_egress_policy

    resolved_state_dir = Path(state_dir) if state_dir else discovery.root / ".audit" / "runs"
    orchestrator = Orchestrator(StateStore(resolved_state_dir))

    engineering = execute_engineering_pass(
        orchestrator,
        discovery,
        prepared.plan,
        list(prepared.work_items),
        target_snapshot=prepared.snapshot,
        semantic_worker=semantic_worker,
    )
    security = execute_security_pass(
        orchestrator,
        discovery,
        prepared.plan,
        list(prepared.work_items),
        engineering.run,
        semantic_worker=semantic_worker,
    )

    resolved_output_dir = output_dir or str(discovery.root / "docs" / "audit")
    artifact_map = write_audit_artifacts(
        resolved_output_dir,
        prepared,
        discovery,
        engineering,
        security,
        overwrite=overwrite_artifacts,
    )
    engineering.run.artifact_refs = list(artifact_map.values())
    orchestrator.commit_run(
        engineering.run,
        prepared.plan,
        list(prepared.work_items),
        known_run_ids=orchestrator.store.list_run_ids(),
    )

    normalization = None
    if normalize:
        normalized_dir = str(Path(resolved_output_dir) / "normalized")
        normalization = run_audit_normalize(
            list(artifact_map.values()),
            normalized_dir,
            base_dir=str(discovery.root),
            command=normalize_command,
        )
        if normalization.status.startswith("COMPLETED"):
            engineering.run.artifact_refs.extend([
                str(Path(normalized_dir) / "report_data.json"),
                str(Path(normalized_dir) / "validation_report.json"),
                str(Path(normalized_dir) / "source_manifest.json"),
                str(Path(normalized_dir) / "report_data.schema.json"),
            ])
            orchestrator.commit_run(
                engineering.run,
                prepared.plan,
                list(prepared.work_items),
                known_run_ids=orchestrator.store.list_run_ids(),
            )

    return FullAuditResult(
        discovery=discovery,
        prepared=prepared,
        engineering=engineering,
        security=security,
        artifacts=tuple(artifact_map.values()),
        normalization=normalization,
    )
