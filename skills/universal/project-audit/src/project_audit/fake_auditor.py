"""
fake_auditor.py — Deterministic Fake Worker for Core Engine V1 testing

The FakeAuditor produces deterministic, predictable outputs for testing
the engine without requiring a real LLM or specialized auditor.

Purpose (instruction §6):
  "Utilize um worker fake/determinístico para os testes do primeiro slice.
   A finalidade é validar o engine, não a inteligência dos auditores."

The FakeAuditor NEVER:
  - Uses an LLM
  - Makes network calls
  - Accesses credentials
  - Authorizes policy changes

It only produces Evidence objects with deterministic content based on its
configuration, exercising the full orchestration pipeline.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from .models import (
    AuditWorkItem,
    Evidence,
    EvidenceValidity,
    ExecutionPolicy,
    ExecutionReceipt,
    FilesystemAccess,
    NetworkAccess,
    CredentialAccess,
    Provenance,
    WorkItemFailureState,
)


class FakeAuditorResult(str, Enum):
    SUCCESS = "success"
    FAIL = "fail"
    BLOCK = "block"


class FakeAuditor:
    """
    Deterministic worker for engine validation.

    All outputs are derived from work_item_id + configured result mode,
    ensuring reproducibility across test runs (determinism invariant, §30).
    """

    COMMAND = "fake-auditor"
    ACTOR = "fake-auditor/v1"

    def __init__(self, result: FakeAuditorResult = FakeAuditorResult.SUCCESS) -> None:
        self.result = result

    def execute(
        self,
        work_item: AuditWorkItem,
        started_at: Optional[datetime] = None,
    ) -> tuple:  # tuple[ExecutionReceipt, Optional[Evidence]]
        """
        Simulates auditor execution.
        Returns (ExecutionReceipt, Evidence|None).
        Evidence is None on FAIL or BLOCK.
        """
        now = started_at or datetime.now(timezone.utc)
        receipt_id = str(uuid.uuid4())

        if self.result == FakeAuditorResult.BLOCK:
            receipt = ExecutionReceipt(
                receipt_id=receipt_id,
                work_item_ref=work_item.work_item_id,
                command=self.COMMAND,
                arguments=["--target", work_item.target_surface, "--mode", "block"],
                policy_snapshot=work_item.effective_execution_policy,
                started_at=now,
                finished_at=now,
                exit_code=126,  # Permission denied convention
                artifact_refs=[],
                environment_summary="sandbox=strict",
            )
            return receipt, None

        if self.result == FakeAuditorResult.FAIL:
            receipt = ExecutionReceipt(
                receipt_id=receipt_id,
                work_item_ref=work_item.work_item_id,
                command=self.COMMAND,
                arguments=["--target", work_item.target_surface, "--mode", "fail"],
                policy_snapshot=work_item.effective_execution_policy,
                started_at=now,
                finished_at=now,
                exit_code=1,
                artifact_refs=[],
                environment_summary="sandbox=strict",
            )
            return receipt, None

        # SUCCESS: produce deterministic Evidence
        # The fingerprint is derived from work_item_id to ensure determinism
        observation_content = {
            "work_item_id": work_item.work_item_id,
            "auditor": work_item.auditor,
            "target_surface": work_item.target_surface,
            "fake_observation": "deterministic_observation_v1",
        }
        content_hash = hashlib.sha256(
            json.dumps(observation_content, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        provenance = Provenance(
            actor=self.ACTOR,
            generated_at=now,
        )

        evidence = Evidence(
            evidence_id=str(uuid.uuid4()),
            target_snapshot_ref=work_item.data_egress_policy.destination.value,  # placeholder
            work_item_ref=work_item.work_item_id,
            source_refs=(f"{work_item.target_surface}:1-10",),
            dependencies=(),
            validity=EvidenceValidity.VALID,
            provenance=provenance,
            fingerprint=content_hash,
        )

        receipt = ExecutionReceipt(
            receipt_id=receipt_id,
            work_item_ref=work_item.work_item_id,
            command=self.COMMAND,
            arguments=["--target", work_item.target_surface, "--mode", "success"],
            policy_snapshot=work_item.effective_execution_policy,
            started_at=now,
            finished_at=now,
            exit_code=0,
            artifact_refs=[f"evidence/{evidence.evidence_id}.json"],
            environment_summary="sandbox=strict",
        )

        return receipt, evidence


class FakeAuditorWithSnapshot:
    """
    FakeAuditor that correctly sets target_snapshot_ref on produced Evidence.
    Used in integration tests where the full TargetSnapshot is available.
    """

    def __init__(
        self,
        snapshot_fingerprint: str,
        result: FakeAuditorResult = FakeAuditorResult.SUCCESS,
    ) -> None:
        self._fingerprint = snapshot_fingerprint
        self._inner = FakeAuditor(result=result)

    def execute(
        self,
        work_item: AuditWorkItem,
        started_at: Optional[datetime] = None,
    ) -> tuple:
        receipt, evidence = self._inner.execute(work_item, started_at)
        if evidence is not None:
            # Replace the placeholder snapshot ref with the real one
            evidence = Evidence(
                evidence_id=evidence.evidence_id,
                target_snapshot_ref=self._fingerprint,
                work_item_ref=evidence.work_item_ref,
                source_refs=evidence.source_refs,
                dependencies=evidence.dependencies,
                validity=evidence.validity,
                provenance=evidence.provenance,
                fingerprint=evidence.fingerprint,
            )
        return receipt, evidence
