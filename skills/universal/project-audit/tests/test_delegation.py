"""
test_delegation.py — Tests for Delegation Boundary

Tests the WorkerPort and DelegationBackend abstractions to ensure the Core Engine
can delegate execution without coupling to OmniRoute or concrete models.
"""

from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from project_audit.delegation import (
    DelegationBackend,
    DelegationRequest,
    DelegationResult,
    DelegationStatus,
    WorkerPort,
)
from tests.conftest import make_work_item


class FakeDelegationBackend(DelegationBackend):
    """A deterministic mock backend for testing the Delegation Boundary."""

    def __init__(self, result_to_return: DelegationResult):
        self.result_to_return = result_to_return
        self.last_request = None

    def delegate(self, request: DelegationRequest) -> DelegationResult:
        self.last_request = request
        return self.result_to_return


def test_worker_port_success_translation():
    """WorkerPort translates a successful DelegationResult into Receipt + Evidence."""
    wi = make_work_item(plan_id="plan-1", auditor="test-auditor")
    context = {"test_key": "test_value"}
    started_at = datetime.now(timezone.utc)

    # Mock backend returns SUCCESS
    mock_result = DelegationResult(
        request_id="req-1",
        status=DelegationStatus.SUCCESS,
        output_payload={"findings": ["vuln-1"]},
        error_message=None,
        provider_info="fake-provider/v1",
        usage_tokens=100,
    )
    backend = FakeDelegationBackend(mock_result)
    port = WorkerPort(backend=backend, actor_identity="test-actor")

    receipt, evidence = port.execute_delegation(wi, context, started_at)

    # Validate Request sent to backend
    assert backend.last_request is not None
    assert backend.last_request.work_item_ref == wi.work_item_id
    assert backend.last_request.context_payload == context
    assert backend.last_request.execution_policy == wi.effective_execution_policy

    # Validate translated Receipt
    assert receipt.exit_code == 0
    assert receipt.environment_summary is None
    assert receipt.work_item_ref == wi.work_item_id
    assert receipt.started_at == started_at

    # Validate translated Evidence
    assert evidence is not None
    assert evidence.work_item_ref == wi.work_item_id
    # Provenance should combine actor and provider
    assert "test-actor" in evidence.provenance.actor
    assert "fake-provider/v1" in evidence.provenance.actor
    # Fingerprint must be populated
    assert evidence.fingerprint is not None
    assert len(evidence.fingerprint) == 64


def test_worker_port_blocked_translation():
    """WorkerPort translates a BLOCKED result into exit_code=126 and NO Evidence."""
    wi = make_work_item(plan_id="plan-1")
    
    mock_result = DelegationResult(
        request_id="req-2",
        status=DelegationStatus.BLOCKED,
        output_payload=None,
        error_message="Policy violation: unauthorized network access",
        provider_info="safety-gate",
        usage_tokens=0,
    )
    backend = FakeDelegationBackend(mock_result)
    port = WorkerPort(backend=backend, actor_identity="test-actor")

    receipt, evidence = port.execute_delegation(wi, {}, datetime.now(timezone.utc))

    # Exit code 126 signifies BLOCKED (Safety Gate convention)
    assert receipt.exit_code == 126
    assert "Policy violation: unauthorized network access" in str(receipt.environment_summary)
    assert evidence is None


def test_worker_port_failed_translation():
    """WorkerPort translates a FAILED result into exit_code=1 and NO Evidence."""
    wi = make_work_item(plan_id="plan-1")
    
    mock_result = DelegationResult(
        request_id="req-3",
        status=DelegationStatus.FAILED,
        output_payload=None,
        error_message="Provider timeout",
        provider_info="omniroute",
        usage_tokens=0,
    )
    backend = FakeDelegationBackend(mock_result)
    port = WorkerPort(backend=backend, actor_identity="test-actor")

    receipt, evidence = port.execute_delegation(wi, {}, datetime.now(timezone.utc))

    assert receipt.exit_code == 1
    assert "Provider timeout" in str(receipt.environment_summary)
    assert evidence is None
