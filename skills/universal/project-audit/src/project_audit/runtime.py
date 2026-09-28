from __future__ import annotations

import dataclasses
import json
import shutil
import subprocess
import tempfile

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .classifiers import classify_applicability, classify_files, classify_stack
from .discovery import DiscoverySnapshot, discover
from .engineering_runner import EngineeringPassResult, execute_engineering_pass
from .models import EgressPolicy, RunCoverageCompleteness, RunExecutionCompleteness, RunFailureState, TargetMode
from .normalization_runner import NormalizationResult, run_audit_normalize
from .orchestrator import Orchestrator
from .planner import PreparedAudit, prepare_audit
from .report_writer import write_audit_artifacts
from .security_runner import SecurityPassResult, execute_security_pass
from .semantic_auditor import SemanticAuditor, SemanticReviewResult
from .verifier import VerificationResult, candidate_identity, consolidated_reviews, verify_semantic_reviews
from .state_store import AuditWriterLock, StateStore
from .finding_lifecycle import preserve_reused_findings, reconcile_finding_lifecycle
from .incremental import match_previous_evidence, plan_incremental_actions_stable
from .change_impact import ChangeImpact, build_change_impact
from .classification_lineage import (
    build_classification_lineage,
    build_reclassification_impact,
    missing_reclassification_impact,
)


@dataclass(frozen=True)
class FullAuditResult:
    discovery: DiscoverySnapshot
    prepared: PreparedAudit
    engineering: EngineeringPassResult
    security: SecurityPassResult
    artifacts: Tuple[str, ...]
    normalization: Optional[NormalizationResult]
    semantic_reviews: Tuple[SemanticReviewResult, ...] = ()
    verification_results: Tuple[VerificationResult, ...] = ()


def audit_paths(
    target: str, state_dir: Optional[str] = None, output_dir: Optional[str] = None,
) -> Tuple[Path, Path, Path, Path]:
    """Resolve the runtime's writable paths inside the target's audit vault."""
    root = Path(target).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Target is not a directory: {root}")
    vault = root / ".audit"
    if vault.is_symlink():
        raise ValueError(".audit must be an isolated directory, not a symlink")
    state = (Path(state_dir) if state_dir else vault / "runs").resolve()
    output = (Path(output_dir) if output_dir else vault).resolve()
    for path in (state, output):
        if path != vault and vault not in path.parents:
            raise ValueError("State and reports must remain inside <target>/.audit/")
    return root, vault, state, output


def initialize_audit_repository(root: Path, vault: Path) -> None:
    """Install the isolation boundary before discovery fingerprints the target."""
    ignore = root / ".gitignore"
    if ignore.is_symlink():
        raise ValueError("Cannot update a symlinked .gitignore")
    content = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
    # Honor an existing Git exclusion (including a caller-owned excludesFile).
    # This permits a genuinely clean COMMIT audit without changing target files.
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", ".audit/acceptance-probe"],
        cwd=root, capture_output=True, timeout=5,
    ).returncode == 0
    if not ignored and not any(line.strip() in {".audit/", "/.audit/"} for line in content.splitlines()):
        ignore.write_text(content + ("\n" if content and not content.endswith("\n") else "") + "/.audit/\n", encoding="utf-8")
    vault.mkdir(parents=True, exist_ok=True)
    if not (vault / ".git").exists():
        subprocess.run(["git", "init", "-q", str(vault)], check=True, capture_output=True, timeout=10)
    toplevel = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=vault, text=True, timeout=10,
    ).strip()
    if Path(toplevel).resolve() != vault:
        raise ValueError(".audit must own its isolated Git repository")


def _run_full_audit_unlocked(
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
    previous_run_ref: Optional[str] = None,
) -> FullAuditResult:
    """Execute the complete currently implemented single-agent two-pass runtime."""
    root, vault, resolved_state_dir, resolved_output_dir = audit_paths(target, state_dir, output_dir)
    initialize_audit_repository(root, vault)
    discovery = discover(str(root))
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

    orchestrator = Orchestrator(StateStore(resolved_state_dir))

    reusable_evidence_by_work_item = None
    incremental_impact = None
    classification_impact = None
    current_classification_lineage = build_classification_lineage(
        prepared.snapshot.snapshot_fingerprint,
        prepared.classification_results,
    )
    preserved_finding_keys = ()
    if previous_run_ref is not None:
        previous_run = orchestrator.store.load_run(previous_run_ref)
        previous_plan = orchestrator.store.load_plan(previous_run.plan_ref)
        previous_snapshot = orchestrator.store.load_snapshot(previous_run.target_snapshot_ref)
        if previous_snapshot.project_state.repository_identity != prepared.snapshot.project_state.repository_identity:
            raise ValueError(
                "previous_run_ref belongs to a different repository identity."
            )
        if previous_snapshot.target_mode != prepared.snapshot.target_mode:
            raise ValueError(
                "previous_run_ref uses a different TargetMode than the current audit."
            )
        previous_work_items = list(previous_plan.work_items)
        incremental_impact = build_change_impact(previous_snapshot, prepared.snapshot)
        if orchestrator.store.classification_lineage_exists(
            previous_snapshot.snapshot_fingerprint
        ):
            previous_classification_lineage = orchestrator.store.load_classification_lineage(
                previous_snapshot.snapshot_fingerprint
            )
            classification_impact = build_reclassification_impact(
                previous_classification_lineage,
                current_classification_lineage,
                prepared.work_items,
            )
        else:
            classification_impact = missing_reclassification_impact(
                prepared.snapshot.snapshot_fingerprint,
                prepared.work_items,
            )
        previous_evidence_candidates = {}
        for evidence_id in orchestrator.store.list_evidence_ids():
            evidence = orchestrator.store.load_evidence(evidence_id)
            if evidence.work_item_ref in previous_run.work_item_refs:
                previous_evidence_candidates.setdefault(
                    evidence.work_item_ref, []
                ).append(evidence)

        # Multiple historical Evidence records for one WorkItem are ambiguous
        # for automatic reuse. Preserve only one-to-one bindings; ambiguity
        # fails closed to REAUDIT.
        previous_evidence = {
            work_item_ref: candidates[0]
            for work_item_ref, candidates in previous_evidence_candidates.items()
            if len(candidates) == 1
        }

        plan_incremental_actions_stable(
            list(prepared.work_items),
            previous_work_items,
            previous_evidence,
            previous_snapshot,
            prepared.snapshot,
            change_impact=incremental_impact,
            classification_impact=classification_impact,
        )
        reusable_evidence_by_work_item = dict(
            match_previous_evidence(
                prepared.work_items,
                previous_work_items,
                previous_evidence,
            )
        )

    orchestrator.store.save_classification_lineage(current_classification_lineage)

    engineering = execute_engineering_pass(
        orchestrator,
        discovery,
        prepared.plan,
        list(prepared.work_items),
        target_snapshot=prepared.snapshot,
        semantic_worker=semantic_worker,
        previous_run_ref=previous_run_ref,
        reusable_evidence_by_work_item=reusable_evidence_by_work_item,
        reuse_path_aliases=dict(incremental_impact.rename_map) if incremental_impact else None,
    )
    security = execute_security_pass(
        orchestrator,
        discovery,
        prepared.plan,
        list(prepared.work_items),
        engineering.run,
        semantic_worker=semantic_worker,
        reusable_evidence_by_work_item=reusable_evidence_by_work_item,
        reuse_path_aliases=dict(incremental_impact.rename_map) if incremental_impact else None,
    )

    semantic_reviews = tuple(engineering.semantic_reviews) + tuple(security.semantic_reviews)
    run = engineering.run
    work_items = list(prepared.work_items)

    if previous_run_ref is not None and reusable_evidence_by_work_item:
        preserved_finding_keys = preserve_reused_findings(
            orchestrator.store,
            run,
            previous_run_ref,
            work_items,
            reusable_evidence_by_work_item,
        )
        orchestrator.commit_run(
            run,
            prepared.plan,
            work_items,
            known_run_ids=orchestrator.store.list_run_ids(),
        )

    # Phase 4: independent verification happens after semantic review and before
    # any report/normalizer consolidation. The verifier receives only persisted
    # Evidence context and the immutable TargetSnapshot, not the model narrative.
    work_item_map = {item.work_item_id: item for item in work_items}
    # Reload the canonical Evidence from disk so the verifier cannot depend on
    # an unpersisted in-memory semantic response.
    persisted_reviews = []
    for review in semantic_reviews:
        evidence = review.evidence
        if evidence is not None:
            evidence = orchestrator.store.load_evidence(evidence.evidence_id)
        persisted_reviews.append(
            dataclasses.replace(review, evidence=evidence)
        )
    verification_results = verify_semantic_reviews(
        tuple(persisted_reviews),
        work_item_map,
        prepared.snapshot,
    )
    consolidated = consolidated_reviews(semantic_reviews, verification_results)
    # Phase 7: persist lifecycle only from deterministic verifier results.
    reconcile_finding_lifecycle(
        orchestrator.store,
        run,
        prepared.plan,
        consolidated,
        verification_results,
        preserved_finding_keys=preserved_finding_keys,
    )
    normalization = None
    # Render away from final paths. Drift during rendering cannot expose a report.
    with tempfile.TemporaryDirectory(prefix=".pending-", dir=vault) as temporary:
        staging = Path(temporary)
        orchestrator.check_target_unchanged(root, run, prepared.plan, work_items)
        staged = write_audit_artifacts(
            str(staging), prepared, discovery, engineering, security,
            semantic_reviews=consolidated,
            verification_results=verification_results,
        )
        execution_state_path = staging / "audit_execution_state.json"
        execution_state_path.write_text(
            json.dumps(
                {
                    "run_id": run.run_id,
                    "target_snapshot_ref": run.target_snapshot_ref,
                    "execution_completeness": run.execution_completeness.value,
                    "coverage_completeness": run.coverage_completeness.value,
                    "failure_state": run.failure_state.value,
                    "semantic_required": semantic_worker is not None,
                    "semantic_reviews": [
                        {
                            "work_item_ref": review.work_item_ref,
                            "target_surface": review.target_surface,
                            "status": review.status,
                            "provider": review.provider,
                            "model": review.model,
                            "raw_output_sha256": review.raw_output_fingerprint,
                            "candidates": [
                                {
                                    "candidate_id": candidate_identity(candidate),
                                    "title": candidate.title,
                                    "category": candidate.category,
                                    "subcategory": candidate.subcategory,
                                    "finding_type": candidate.finding_type,
                                    "raw_type": candidate.raw_type,
                                    "type_normalization_rule": candidate.type_normalization_rule,
                                    "status": candidate.status,
                                    "raw_status": candidate.raw_status,
                                    "status_normalization_rule": candidate.status_normalization_rule,
                                    "severity": candidate.severity,
                                    "raw_severity": candidate.raw_severity,
                                    "severity_normalization_rule": candidate.normalization_rule,
                                    "confidence": candidate.confidence,
                                    "location": candidate.location,
                                    "evidence": candidate.evidence,
                                    "description": candidate.description,
                                    "recommendation": candidate.recommendation,
                                    "verification": next(
                                        (
                                            {
                                                "verdict": result.verdict.value,
                                                "evidence_ref": result.evidence_ref,
                                                "reasons": list(result.reasons),
                                            }
                                            for result in verification_results
                                            if result.candidate_id == candidate_identity(candidate)
                                        ),
                                        {
                                            "verdict": "NOT_DETERMINABLE",
                                            "evidence_ref": None,
                                            "reasons": ["No independent verification result was produced."],
                                        },
                                    ),
                                }
                                for candidate in review.candidates
                            ],
                        }
                        for review in semantic_reviews
                    ],
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        orchestrator.check_target_unchanged(root, run, prepared.plan, work_items)
        artifact_map = {key: str(resolved_output_dir / Path(path).name) for key, path in staged.items()}
        state_destination = resolved_output_dir / "audit_execution_state.json"
        final_paths = [Path(path) for path in artifact_map.values()] + [state_destination]
        normalized_dir = resolved_output_dir / "normalized"
        if normalized_dir.exists() and normalized_dir.is_symlink():
            if not normalized_dir.resolve().is_relative_to(resolved_output_dir.resolve()):
                raise ValueError(f"Security violation: normalized directory {normalized_dir} escapes audit vault.")

        if normalize:
            final_paths += [normalized_dir / name for name in (
                "report_data.json", "validation_report.json", "source_manifest.json", "report_data.schema.json",
            )]
        existing = [path for path in final_paths if path.exists()]
        if existing and not overwrite_artifacts:
            raise FileExistsError(f"Audit artifacts already exist: {existing}")
        backups = {}
        for index, path in enumerate(existing):
            backup = staging / f"backup-{index}"
            shutil.copyfile(path, backup)
            backups[path] = backup
        resolved_output_dir.mkdir(parents=True, exist_ok=True)
        try:
            orchestrator.check_target_unchanged(root, run, prepared.plan, work_items)
            for key, source in staged.items():
                Path(source).replace(artifact_map[key])
            execution_state_path_final = state_destination
            execution_state_path.replace(execution_state_path_final)
            if normalize:
                normalization = run_audit_normalize(
                    list(artifact_map.values()), str(normalized_dir),
                    base_dir=str(root),
                    command=normalize_command,
                    execution_state_path=str(execution_state_path_final),
                )
            orchestrator.check_target_unchanged(root, run, prepared.plan, work_items)
            run.artifact_refs = list(artifact_map.values()) + [str(state_destination)]
            if normalization is not None and normalization.status.startswith("COMPLETED"):
                run.artifact_refs.extend(str(path) for path in final_paths[4:])
            orchestrator.commit_run(
                run, prepared.plan, work_items, known_run_ids=orchestrator.store.list_run_ids(),
            )
            orchestrator.check_target_unchanged(root, run, prepared.plan, work_items)
            if (
                run.execution_completeness == RunExecutionCompleteness.COMPLETE
                and run.coverage_completeness == RunCoverageCompleteness.FULL
                and run.failure_state == RunFailureState.NONE
            ):
                evidence_by_item = {
                    item.work_item_id for item in work_items
                }
                persisted_evidence = []
                for evidence_id in orchestrator.store.list_evidence_ids():
                    evidence = orchestrator.store.load_evidence(evidence_id)
                    if evidence.work_item_ref in evidence_by_item:
                        persisted_evidence.append(evidence)
                orchestrator.publish_run(
                    run,
                    prepared.plan,
                    work_items,
                    persisted_evidence,
                    prepared.snapshot.snapshot_fingerprint,
                )
        except Exception:
            # Wipe only this attempt's outputs. Earlier successful runs remain intact.
            for path in final_paths:
                if path in backups:
                    shutil.copyfile(backups[path], path)
                else:
                    path.unlink(missing_ok=True)
            raise

    return FullAuditResult(
        discovery=discovery,
        prepared=prepared,
        engineering=engineering,
        security=security,
        artifacts=tuple(list(artifact_map.values()) + [str(state_destination)]),
        normalization=normalization,
        semantic_reviews=semantic_reviews,
        verification_results=verification_results,
    )

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
    previous_run_ref: Optional[str] = None,
) -> FullAuditResult:
    """Execute one complete audit while holding the physical audit writer lock."""

    root, vault, _, _ = audit_paths(target, state_dir, output_dir)
    with AuditWriterLock(vault / "audit-writer.lock"):
        return _run_full_audit_unlocked(
            target,
            state_dir=state_dir,
            output_dir=output_dir,
            target_mode=target_mode,
            overwrite_artifacts=overwrite_artifacts,
            normalize=normalize,
            normalize_command=normalize_command,
            semantic_worker=semantic_worker,
            semantic_egress_policy=semantic_egress_policy,
            previous_run_ref=previous_run_ref,
        )

