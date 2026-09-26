"""
autofix.py — Immutable Auto-Fix transaction protocol (Phase 5).

A fix is a new transaction over an immutable audit baseline:
  Snapshot A -> verified finding -> isolated worker patch -> apply -> Snapshot B
  -> delta re-audit -> Before/After Ledger -> lifecycle decision.

No existing Snapshot, Evidence, Run, or Finding record is mutated. A finding is
marked FIXED only in the new transaction ledger when the post-fix audit no
longer emits the same logical finding identity.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Tuple

from .discovery import discover
from .models import TargetMode, TargetSnapshot
from .planner import build_target_snapshot


class AutoFixError(RuntimeError):
    pass


@dataclass(frozen=True)
class FixCandidate:
    candidate_id: str
    source_run_id: str
    title: str
    category: str
    subcategory: Optional[str]
    finding_type: str
    status: str
    severity: str
    confidence: str
    location_file: str
    recommendation: str
    verifier_verdict: str


@dataclass(frozen=True)
class FixLedger:
    fix_id: str
    source_run_id: str
    candidate_id: str
    target_snapshot_a: str
    target_snapshot_b: Optional[str]
    patch_sha256: Optional[str]
    changed_files: Tuple[str, ...]
    before_present: bool
    after_present: Optional[bool]
    lifecycle: str
    outcome: str
    created_at: str
    worker_receipt: Optional[dict[str, Any]]
    reason: str

    def to_dict(self) -> dict:
        return {
            "fix_id": self.fix_id,
            "source_run_id": self.source_run_id,
            "candidate_id": self.candidate_id,
            "snapshot_a": self.target_snapshot_a,
            "snapshot_b": self.target_snapshot_b,
            "patch_sha256": self.patch_sha256,
            "changed_files": list(self.changed_files),
            "before_present": self.before_present,
            "after_present": self.after_present,
            "finding_lifecycle": self.lifecycle,
            "outcome": self.outcome,
            "created_at": self.created_at,
            "worker_receipt": self.worker_receipt,
            "reason": self.reason,
        }


def current_snapshot(
    root: Path,
    *,
    target_mode: TargetMode = TargetMode.WORKTREE,
) -> TargetSnapshot:
    discovery = discover(str(root))
    return build_target_snapshot(discovery, target_mode=target_mode)


def logical_finding_key(
    *,
    category: str,
    subcategory: Optional[str],
    finding_type: str,
    location_file: str,
) -> str:
    payload = {
        "category": str(category).strip().upper(),
        "subcategory": str(subcategory or "").strip().upper(),
        "finding_type": str(finding_type).strip().upper(),
        "location_file": str(location_file).strip().replace("\\", "/").lstrip("./"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def logical_finding_key_from_report(finding: Mapping[str, Any]) -> str:
    def _value(field: Any) -> Any:
        if isinstance(field, dict):
            return field.get("value")
        return field

    location = _value(finding.get("location"))
    location_file = ""
    if isinstance(location, dict):
        location_file = str(location.get("file") or "")

    return logical_finding_key(
        category=str(finding.get("category") or ""),
        subcategory=finding.get("subcategory"),
        finding_type=str(_value(finding.get("type")) or ""),
        location_file=location_file,
    )


def extract_fix_candidates(
    execution_state: Mapping[str, Any],
    *,
    run_id: str,
    candidate_id: Optional[str] = None,
) -> Tuple[FixCandidate, ...]:
    candidates = []
    for review in execution_state.get("semantic_reviews", []):
        for item in review.get("candidates", []):
            result = item.get("verification") or {}
            if result.get("verdict") != "VERIFIED":
                continue
            if item.get("severity") not in {"P0", "P1"}:
                continue
            if item.get("status") != "CONFIRMED" or item.get("confidence") != "HIGH":
                continue
            location = item.get("location") or {}
            location_file = location.get("file") if isinstance(location, dict) else None
            cid = item.get("candidate_id")
            if not cid or not location_file:
                continue
            if candidate_id and cid != candidate_id:
                continue
            candidates.append(
                FixCandidate(
                    candidate_id=cid,
                    source_run_id=run_id,
                    title=str(item.get("title") or ""),
                    category=str(item.get("category") or ""),
                    subcategory=item.get("subcategory"),
                    finding_type=str(item.get("finding_type") or item.get("type") or ""),
                    status=str(item.get("status") or ""),
                    severity=str(item.get("severity") or ""),
                    confidence=str(item.get("confidence") or ""),
                    location_file=str(location_file),
                    recommendation=str(item.get("recommendation") or ""),
                    verifier_verdict=str(result.get("verdict")),
                )
            )
    return tuple(candidates)


def validate_fix_preconditions(
    root: Path,
    source_snapshot: TargetSnapshot,
    observed_snapshot: TargetSnapshot,
) -> None:
    if source_snapshot.target_mode != TargetMode.COMMIT:
        raise AutoFixError(
            "Immutable auto-fix requires the source audit to use target_mode=COMMIT."
        )
    if source_snapshot.project_state.working_tree_state.value != "CLEAN":
        raise AutoFixError(
            "Immutable auto-fix requires Snapshot A to represent a clean working tree."
        )
    if observed_snapshot.snapshot_fingerprint != source_snapshot.snapshot_fingerprint:
        raise AutoFixError(
            "Target drifted after the source audit; refusing to apply a fix."
        )
    if not (root / ".git").exists():
        raise AutoFixError("Target must be a Git repository.")
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    if status.returncode != 0:
        raise AutoFixError("Unable to inspect Git working-tree state.")
    if status.stdout.strip():
        raise AutoFixError("Working tree is not clean; Snapshot A can no longer be applied safely.")


def validate_worker_patch(
    patch: str,
    *,
    expected_file: str,
) -> Tuple[str, ...]:
    if not patch.strip():
        raise AutoFixError("L3W produced an empty patch.")
    changed = []
    seen = set()
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:].strip()
            if path != "/dev/null":
                seen.add(path)
    if not seen:
        raise AutoFixError("L3W patch contains no file headers.")
    changed = tuple(sorted(seen))
    expected = expected_file.replace("\\", "/").lstrip("./")
    unexpected = [path for path in changed if path != expected]
    if unexpected:
        raise AutoFixError(
            "Auto-fix patch touches files outside the verified finding location: "
            + ", ".join(unexpected)
        )
    return changed


def apply_patch(root: Path, patch: str) -> str:
    digest = hashlib.sha256(patch.encode("utf-8")).hexdigest()
    check = subprocess.run(
        ["git", "apply", "--check", "--whitespace=nowarn", "-"],
        cwd=root,
        input=patch,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if check.returncode != 0:
        raise AutoFixError(
            "Generated patch failed git apply --check: "
            + (check.stderr.strip() or check.stdout.strip())
        )
    applied = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=root,
        input=patch,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    if applied.returncode != 0:
        raise AutoFixError(
            "Generated patch could not be applied: "
            + (applied.stderr.strip() or applied.stdout.strip())
        )
    return digest


def finding_present_in_report(
    report: Mapping[str, Any],
    key: str,
) -> bool:
    return any(
        logical_finding_key_from_report(finding) == key
        for finding in report.get("findings", [])
        if isinstance(finding, dict)
    )


def write_fix_ledger(root: Path, ledger: FixLedger) -> Path:
    destination = root / ".audit" / "fixes" / f"{ledger.fix_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name("." + destination.name + ".tmp")
    tmp.write_text(
        json.dumps(ledger.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(destination)
    return destination


def begin_ledger(candidate: FixCandidate, snapshot_a: TargetSnapshot) -> FixLedger:
    return FixLedger(
        fix_id=uuid.uuid4().hex,
        source_run_id=candidate.source_run_id,
        candidate_id=candidate.candidate_id,
        target_snapshot_a=snapshot_a.snapshot_fingerprint,
        target_snapshot_b=None,
        patch_sha256=None,
        changed_files=(),
        before_present=True,
        after_present=None,
        lifecycle="PERSISTING",
        outcome="STARTED",
        created_at=datetime.now(timezone.utc).isoformat(),
        worker_receipt=None,
        reason="Verified P0/P1 candidate selected for one immutable auto-fix transaction.",
    )


def complete_ledger(
    ledger: FixLedger,
    *,
    snapshot_b: TargetSnapshot,
    patch_sha256: str,
    changed_files: Iterable[str],
    after_present: bool,
    worker_receipt: Optional[dict[str, Any]],
) -> FixLedger:
    if after_present:
        return FixLedger(
            **{
                **ledger.__dict__,
                "target_snapshot_b": snapshot_b.snapshot_fingerprint,
                "patch_sha256": patch_sha256,
                "changed_files": tuple(changed_files),
                "after_present": True,
                "lifecycle": "PERSISTING",
                "outcome": "NOT_FIXED",
                "worker_receipt": worker_receipt,
                "reason": "Post-fix re-audit still emits the same logical finding.",
            }
        )
    return FixLedger(
        **{
            **ledger.__dict__,
            "target_snapshot_b": snapshot_b.snapshot_fingerprint,
            "patch_sha256": patch_sha256,
            "changed_files": tuple(changed_files),
            "after_present": False,
            "lifecycle": "FIXED",
            "outcome": "FIXED",
            "worker_receipt": worker_receipt,
            "reason": "Post-fix re-audit no longer emits the same logical finding identity.",
        }
    )


def run_immutable_fix(
    root: Path,
    *,
    state_dir: Path,
    source_run_id: str,
    candidate_id: str,
    semantic_worker: Any,
    semantic_egress_policy: Any,
    normalize_command: str,
    execution_state_path: Optional[Path] = None,
) -> FixLedger:
    """Execute exactly one verified P0/P1 fix transaction and re-audit it."""
    from .state_store import AuditWriterLock
    with AuditWriterLock(root / ".audit" / "audit-writer.lock"):
        return _run_immutable_fix_locked(
            root,
            state_dir=state_dir,
            source_run_id=source_run_id,
            candidate_id=candidate_id,
            semantic_worker=semantic_worker,
            semantic_egress_policy=semantic_egress_policy,
            normalize_command=normalize_command,
            execution_state_path=execution_state_path,
        )


def _run_immutable_fix_locked(
    root: Path,
    *,
    state_dir: Path,
    source_run_id: str,
    candidate_id: str,
    semantic_worker: Any,
    semantic_egress_policy: Any,
    normalize_command: str,
    execution_state_path: Optional[Path] = None,
) -> FixLedger:
    from .runtime import _run_full_audit_unlocked
    from .state_store import StateStore
    store = StateStore(state_dir)
    if not store.run_exists(source_run_id):
        raise AutoFixError(f"Source audit run {source_run_id} does not exist.")

    source_run = store.load_run(source_run_id)
    source_snapshot = store.load_snapshot(source_run.target_snapshot_ref)
    observed = current_snapshot(root, target_mode=source_snapshot.target_mode)
    validate_fix_preconditions(root, source_snapshot, observed)

    state_path = execution_state_path or (root / ".audit" / "audit_execution_state.json")
    if not state_path.is_file():
        raise AutoFixError(
            "Immutable auto-fix requires the source run execution state with verifier results."
        )
    try:
        execution_state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AutoFixError(f"Unable to read canonical execution state: {exc}") from exc

    candidates = extract_fix_candidates(
        execution_state,
        run_id=source_run_id,
        candidate_id=candidate_id,
    )
    if len(candidates) != 1:
        raise AutoFixError(
            f"Expected exactly one VERIFIED P0/P1 candidate {candidate_id}; found {len(candidates)}."
        )
    candidate = candidates[0]
    ledger = begin_ledger(candidate, source_snapshot)
    ledger_path = write_fix_ledger(root, ledger)

    patch_sha256 = None
    changed_files: Tuple[str, ...] = ()
    worker_receipt = None
    try:
        import asyncio
        from omniroute_delegation.local_worker_mcp import dispatch_opencode_worker

        task = (
            "Apply the smallest safe remediation for this already independently "
            f"verified finding. Finding: {candidate.title}. "
            f"Type: {candidate.finding_type}. "
            f"Recommendation: {candidate.recommendation or 'Use the minimal evidence-grounded remediation.'} "
            f"Target file: {candidate.location_file}. "
            "Do not modify any other file. Do not change dependencies or configuration outside this file. "
            "Do not weaken unrelated controls. Return a normal code patch."
        )

        async def dispatch():
            raw = await dispatch_opencode_worker(
                task=task,
                target_file=candidate.location_file,
                workspace_dir=str(root),
                isolated_memory=True,
            )
            return json.loads(raw)

        worker_receipt = asyncio.run(dispatch())
        if worker_receipt.get("state") != "SUCCESS":
            raise AutoFixError(
                "L3W did not complete successfully: "
                + str(worker_receipt.get("state") or "UNKNOWN")
            )

        patch = str(worker_receipt.get("diff") or "")
        changed_files = validate_worker_patch(
            patch,
            expected_file=candidate.location_file,
        )
        patch_sha256 = apply_patch(root, patch)

        # Snapshot B is captured after the patch and before the re-audit. The
        # re-audit itself gets a dedicated state/output namespace so the source
        # run's immutable artifacts are never overwritten.
        snapshot_b_pre_audit = current_snapshot(root, target_mode=TargetMode.WORKTREE)
        reaudit_root = root / ".audit" / "fixes" / ledger.fix_id / "reaudit"
        reaudited = _run_full_audit_unlocked(
            str(root),
            state_dir=str(reaudit_root / "runs"),
            output_dir=str(reaudit_root / "artifacts"),
            target_mode=TargetMode.WORKTREE,
            overwrite_artifacts=False,
            normalize=True,
            normalize_command=normalize_command,
            semantic_worker=semantic_worker,
            semantic_egress_policy=semantic_egress_policy,
        )
        normalized_path = reaudited.normalization.output_dir if reaudited.normalization else None
        if normalized_path is None:
            # The result object does not guarantee an output path, so resolve
            # the dedicated output namespace deterministically.
            normalized_file = reaudit_root / "artifacts" / "normalized" / "report_data.json"
        else:
            normalized_file = Path(normalized_path) / "report_data.json"
        if not normalized_file.is_file():
            raise AutoFixError("Post-fix normalization did not produce report_data.json.")
        post_report = json.loads(normalized_file.read_text(encoding="utf-8"))
        key = logical_finding_key(
            category=candidate.category,
            subcategory=candidate.subcategory,
            finding_type=candidate.finding_type,
            location_file=candidate.location_file,
        )
        after_present = finding_present_in_report(post_report, key)
        snapshot_b = snapshot_b_pre_audit

        completed = complete_ledger(
            ledger,
            snapshot_b=snapshot_b,
            patch_sha256=patch_sha256 or "",
            changed_files=changed_files,
            after_present=after_present,
            worker_receipt=worker_receipt,
        )
        write_fix_ledger(root, completed)
        return completed
    except Exception as exc:
        failed = FixLedger(
            **{
                **ledger.__dict__,
                "patch_sha256": patch_sha256,
                "changed_files": changed_files,
                "worker_receipt": worker_receipt,
                "outcome": "FAILED",
                "lifecycle": "PERSISTING",
                "reason": str(exc),
            }
        )
        write_fix_ledger(root, failed)
        # A partially applied patch must never masquerade as FIXED.
        raise
