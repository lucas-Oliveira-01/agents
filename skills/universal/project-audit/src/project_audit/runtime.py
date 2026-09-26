from __future__ import annotations

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
from .models import EgressPolicy, TargetMode
from .normalization_runner import NormalizationResult, run_audit_normalize
from .orchestrator import Orchestrator
from .planner import PreparedAudit, prepare_audit
from .report_writer import write_audit_artifacts
from .security_runner import SecurityPassResult, execute_security_pass
from .semantic_auditor import SemanticAuditor, SemanticReviewResult
from .state_store import StateStore


@dataclass(frozen=True)
class FullAuditResult:
    discovery: DiscoverySnapshot
    prepared: PreparedAudit
    engineering: EngineeringPassResult
    security: SecurityPassResult
    artifacts: Tuple[str, ...]
    normalization: Optional[NormalizationResult]
    semantic_reviews: Tuple[SemanticReviewResult, ...] = ()


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
    if not any(line.strip() in {".audit/", "/.audit/"} for line in content.splitlines()):
        ignore.write_text(content + ("\n" if content and not content.endswith("\n") else "") + "/.audit/\n", encoding="utf-8")
    vault.mkdir(parents=True, exist_ok=True)
    if not (vault / ".git").exists():
        subprocess.run(["git", "init", "-q", str(vault)], check=True, capture_output=True, timeout=10)
    toplevel = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=vault, text=True, timeout=10,
    ).strip()
    if Path(toplevel).resolve() != vault:
        raise ValueError(".audit must own its isolated Git repository")


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

    semantic_reviews = tuple(engineering.semantic_reviews) + tuple(security.semantic_reviews)
    run = engineering.run
    work_items = list(prepared.work_items)
    normalization = None
    # Render away from final paths. Drift during rendering cannot expose a report.
    with tempfile.TemporaryDirectory(prefix=".pending-", dir=vault) as temporary:
        staging = Path(temporary)
        orchestrator.check_target_unchanged(root, run, prepared.plan, work_items)
        staged = write_audit_artifacts(
            str(staging), prepared, discovery, engineering, security,
            semantic_reviews=semantic_reviews,
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
    )
