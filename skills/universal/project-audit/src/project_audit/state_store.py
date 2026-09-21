"""
state_store.py — Local Durable State Store for project-audit Core Engine V1

Implements atomic, single-writer persistence for the Orchestrator Layer 2 state.

Design decisions (canonical-data-model.md §5, ADR-07):
  - Local durable state (no distributed infrastructure)
  - Atomic writes via tempfile + rename (POSIX atomic)
  - Single writer (Orchestrator is the sole authority)
  - JSON files on disk — recoverable after crash (ADR-07 Recovery semantics)
  - Separate files per entity type for isolation

Storage layout under <store_root>/:
  target_snapshots/<fingerprint>.json
  audit_plans/<plan_id>.json
  audit_work_items/<work_item_id>.json
  evidences/<evidence_id>.json
  audit_runs/<run_id>.json
  execution_receipts/<receipt_id>.json

Recovery (ADR-07): load by ID from disk, reconstruct state.
The Orchestrator reconciles recovered state against the disk artifacts.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from .models import (
    ApplicabilityDecision,
    Attempt,
    AuditPlan,
    AuditRun,
    AuditWorkItem,
    BudgetEnvelope,
    CredentialAccess,
    EgressDestination,
    EgressPolicy,
    Evidence,
    EvidenceValidity,
    ExecutionPolicy,
    ExecutionReceipt,
    ExecutionState,
    FilesystemAccess,
    MethodologyState,
    NetworkAccess,
    ProjectState,
    Provenance,
    RunBudgetState,
    RunCoverageCompleteness,
    RunExecutionCompleteness,
    RunFailureState,
    RunPublicationState,
    SubmoduleState,
    TargetMode,
    TargetSnapshot,
    TrackedInputFingerprint,
    WorkItemAction,
    WorkItemFailureState,
    WorkingTreeState,
)

from datetime import datetime, timezone


class StateStoreError(RuntimeError):
    """Raised on state store I/O or corruption errors."""


def _atomic_write(path: Path, data: dict) -> None:
    """
    Atomic write via tempfile + rename.
    POSIX rename is atomic — prevents partial writes on crash.
    (ADR-07: enables Recovery after interruption)
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent), prefix=".tmp_", suffix=".json"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.rename(tmp_path, str(path))
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise StateStoreError(f"State file not found: {path}")
    except json.JSONDecodeError as e:
        raise StateStoreError(f"Corrupted state file {path}: {e}")


# ---------------------------------------------------------------------------
# Deserialization helpers
# ---------------------------------------------------------------------------


def _dt(s: Optional[str]) -> Optional[datetime]:
    if s is None:
        return None
    return datetime.fromisoformat(s)


def _req_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _load_provenance(d: dict) -> Provenance:
    return Provenance(
        actor=d["actor"],
        generated_at=_req_dt(d["generated_at"]),
        policy_version=d.get("policy_version"),
    )


def _load_execution_policy(d: dict) -> ExecutionPolicy:
    return ExecutionPolicy(
        filesystem=FilesystemAccess(d["filesystem"]),
        network=NetworkAccess(d["network"]),
        credentials=CredentialAccess(d["credentials"]),
        timeout_ms=d.get("timeout_ms"),
    )


def _load_egress_policy(d: dict) -> EgressPolicy:
    return EgressPolicy(
        destination=EgressDestination(d["destination"]),
        allow_sensitive=d["allow_sensitive"],
    )


def _load_attempt(d: dict) -> Attempt:
    a = Attempt(
        attempt_id=d["attempt_id"],
        started_at=_req_dt(d["started_at"]),
        finished_at=_dt(d.get("finished_at")),
        failure_reason=d.get("failure_reason"),
        receipt_ref=d.get("receipt_ref"),
    )
    return a


# ---------------------------------------------------------------------------
# StateStore
# ---------------------------------------------------------------------------


class StateStore:
    """
    Local, file-system backed state store.

    All writes are atomic (tempfile + rename).
    All reads are idempotent and safe for recovery.

    This is the single writer interface — the Orchestrator must use this
    store; workers produce isolated outputs that the Orchestrator then
    commits here after validation.
    """

    def __init__(self, store_root: Path) -> None:
        self.root = store_root
        self.root.mkdir(parents=True, exist_ok=True)
        self._dirs = {
            "snapshots": self.root / "target_snapshots",
            "plans": self.root / "audit_plans",
            "work_items": self.root / "audit_work_items",
            "evidences": self.root / "evidences",
            "runs": self.root / "audit_runs",
            "receipts": self.root / "execution_receipts",
        }
        for d in self._dirs.values():
            d.mkdir(parents=True, exist_ok=True)

    # ---- TargetSnapshot ----

    def save_snapshot(self, snapshot: TargetSnapshot) -> None:
        path = self._dirs["snapshots"] / f"{snapshot.snapshot_fingerprint}.json"
        _atomic_write(path, snapshot.to_dict())

    def load_snapshot(self, fingerprint: str) -> TargetSnapshot:
        path = self._dirs["snapshots"] / f"{fingerprint}.json"
        d = _read_json(path)
        ps_d = d["project_state"]
        ms_d = d["methodology_state"]
        ps = ProjectState(
            repository_identity=ps_d["repository_identity"],
            revision_identity=ps_d["revision_identity"],
            working_tree_state=WorkingTreeState(ps_d["working_tree_state"]),
            submodules_state=tuple(
                SubmoduleState(path=s["path"], revision=s["revision"])
                for s in ps_d.get("submodules_state", [])
            ),
            tracked_input_fingerprints=tuple(
                TrackedInputFingerprint(path=t["path"], fingerprint=t["fingerprint"])
                for t in ps_d.get("tracked_input_fingerprints", [])
            ),
        )
        ms = MethodologyState(
            audit_contract_version=ms_d["audit_contract_version"],
            auditor_versions=dict(ms_d["auditor_versions"]),
            policy_version=ms_d["policy_version"],
        )
        return TargetSnapshot(
            target_mode=TargetMode(d["target_mode"]),
            project_state=ps,
            methodology_state=ms,
            snapshot_fingerprint=d["snapshot_fingerprint"],
        )

    def snapshot_exists(self, fingerprint: str) -> bool:
        return (self._dirs["snapshots"] / f"{fingerprint}.json").exists()

    # ---- AuditPlan ----

    def save_plan(self, plan: AuditPlan) -> None:
        path = self._dirs["plans"] / f"{plan.plan_id}.json"
        _atomic_write(path, plan.to_dict())

    def load_plan(self, plan_id: str, work_items: Optional[List[AuditWorkItem]] = None) -> AuditPlan:
        path = self._dirs["plans"] / f"{plan_id}.json"
        d = _read_json(path)
        applicability = [
            ApplicabilityDecision(
                domain=a["domain"],
                applicable=a["applicable"],
                decision_basis=a["decision_basis"],
                evidence_refs=list(a.get("evidence_refs", [])),
            )
            for a in d.get("applicability_decisions", [])
        ]
        budget = None
        if "budget_envelope" in d and d["budget_envelope"]:
            be = d["budget_envelope"]
            budget = BudgetEnvelope(
                max_tokens=be.get("max_tokens"),
                max_cost_usd=be.get("max_cost_usd"),
                max_duration_seconds=be.get("max_duration_seconds"),
            )
        plan = AuditPlan(
            plan_id=d["plan_id"],
            target_snapshot_ref=d["target_snapshot_ref"],
            requested_scope=list(d.get("requested_scope", [])),
            applicability_decisions=applicability,
            resolved_scope=list(d.get("resolved_scope", [])),
            work_items=work_items or [],
            execution_policy=_load_execution_policy(d["execution_policy"]),
            egress_policy=_load_egress_policy(d["egress_policy"]),
            budget_envelope=budget,
            frozen_at=_dt(d.get("frozen_at")),
        )
        return plan

    # ---- AuditWorkItem ----

    def save_work_item(self, work_item: AuditWorkItem) -> None:
        path = self._dirs["work_items"] / f"{work_item.work_item_id}.json"
        _atomic_write(path, work_item.to_dict())

    def load_work_item(self, work_item_id: str) -> AuditWorkItem:
        path = self._dirs["work_items"] / f"{work_item_id}.json"
        d = _read_json(path)
        attempts = [_load_attempt(a) for a in d.get("attempts", [])]
        return AuditWorkItem(
            work_item_id=d["work_item_id"],
            plan_ref=d["plan_ref"],
            auditor=d["auditor"],
            target_surface=d["target_surface"],
            action=WorkItemAction(d["action"]),
            decision_basis=d["decision_basis"],
            effective_execution_policy=_load_execution_policy(d["effective_execution_policy"]),
            data_egress_policy=_load_egress_policy(d["data_egress_policy"]),
            execution_state=ExecutionState(d["execution_state"]),
            failure_state=WorkItemFailureState(d["failure_state"]),
            attempts=attempts,
            artifact_refs=list(d.get("artifact_refs", [])),
        )

    # ---- Evidence ----

    def save_evidence(self, evidence: Evidence) -> None:
        path = self._dirs["evidences"] / f"{evidence.evidence_id}.json"
        _atomic_write(path, evidence.to_dict())

    def load_evidence(self, evidence_id: str) -> Evidence:
        path = self._dirs["evidences"] / f"{evidence_id}.json"
        d = _read_json(path)
        return Evidence(
            evidence_id=d["evidence_id"],
            target_snapshot_ref=d["target_snapshot_ref"],
            work_item_ref=d["work_item_ref"],
            source_refs=tuple(d.get("source_refs", [])),
            dependencies=tuple(d.get("dependencies", [])),
            validity=EvidenceValidity(d["validity"]),
            provenance=_load_provenance(d["provenance"]),
            fingerprint=d["fingerprint"],
        )

    # ---- AuditRun ----

    def save_run(self, run: AuditRun) -> None:
        path = self._dirs["runs"] / f"{run.run_id}.json"
        _atomic_write(path, run.to_dict())

    def load_run(self, run_id: str) -> AuditRun:
        path = self._dirs["runs"] / f"{run_id}.json"
        d = _read_json(path)
        return AuditRun(
            run_id=d["run_id"],
            target_snapshot_ref=d["target_snapshot_ref"],
            plan_ref=d["plan_ref"],
            work_item_refs=list(d.get("work_item_refs", [])),
            execution_completeness=RunExecutionCompleteness(d["execution_completeness"]),
            coverage_completeness=RunCoverageCompleteness(d["coverage_completeness"]),
            failure_state=RunFailureState(d["failure_state"]),
            budget_state=RunBudgetState(d["budget_state"]),
            publication_state=RunPublicationState(d["publication_state"]),
            artifact_refs=list(d.get("artifact_refs", [])),
            previous_run_ref=d.get("previous_run_ref"),
            recovery_from_ref=d.get("recovery_from_ref"),
        )

    def run_exists(self, run_id: str) -> bool:
        return (self._dirs["runs"] / f"{run_id}.json").exists()

    # ---- ExecutionReceipt ----

    def save_receipt(self, receipt: ExecutionReceipt) -> None:
        path = self._dirs["receipts"] / f"{receipt.receipt_id}.json"
        _atomic_write(path, receipt.to_dict())

    def load_receipt(self, receipt_id: str) -> ExecutionReceipt:
        path = self._dirs["receipts"] / f"{receipt_id}.json"
        d = _read_json(path)
        return ExecutionReceipt(
            receipt_id=d["receipt_id"],
            work_item_ref=d["work_item_ref"],
            command=d["command"],
            arguments=list(d.get("arguments", [])),
            policy_snapshot=_load_execution_policy(d["policy_snapshot"]),
            started_at=_req_dt(d["started_at"]),
            finished_at=_dt(d.get("finished_at")),
            exit_code=d.get("exit_code"),
            artifact_refs=list(d.get("artifact_refs", [])),
            environment_summary=d.get("environment_summary"),
        )

    # ---- Recovery support ----

    def list_run_ids(self) -> List[str]:
        """List all persisted run IDs. Used during recovery."""
        return [p.stem for p in self._dirs["runs"].glob("*.json")]

    def list_work_item_ids(self) -> List[str]:
        return [p.stem for p in self._dirs["work_items"].glob("*.json")]

    def list_evidence_ids(self) -> List[str]:
        return [p.stem for p in self._dirs["evidences"].glob("*.json")]
