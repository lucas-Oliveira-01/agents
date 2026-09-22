"""
Tests for Security Auditor
"""
import pytest
from unittest.mock import Mock
from datetime import datetime, timezone

from project_audit.models import (
    TargetSnapshot,
    TrackedInputFingerprint,
    ProjectState,
    TargetMode,
    ExecutionPolicy,
    EgressPolicy,
    EgressDestination,
)
from project_audit.delegation import WorkerPort, DelegationResult, DelegationStatus
from project_audit.security_auditor import SecurityAuditor


@pytest.fixture
def dummy_snapshot():
    return TargetSnapshot(
        target_mode=TargetMode.COMMIT,
        project_state=ProjectState(
            repository_identity="test-repo",
            revision_identity="test-rev",
            working_tree_state="CLEAN",
            submodules_state=[],
            tracked_input_fingerprints=[
                TrackedInputFingerprint(path="src/main.py", fingerprint="1234"),
                TrackedInputFingerprint(path="src/auth.py", fingerprint="5678"),
            ]
        ),
        methodology_state=Mock(),
        snapshot_fingerprint="abc"
    )


def test_generate_work_items(dummy_snapshot):
    port = Mock(spec=WorkerPort)
    auditor = SecurityAuditor(port, dummy_snapshot, "FULL")
    
    items = auditor.generate_work_items("plan-123")
    
    assert len(items) == 2
    assert items[0].target_surface == "src/main.py"
    assert items[1].target_surface == "src/auth.py"
    assert items[0].auditor == "security-auditor"


def test_execute_delegates_to_worker_port(dummy_snapshot):
    port = Mock(spec=WorkerPort)
    auditor = SecurityAuditor(port, dummy_snapshot, "FULL")
    items = auditor.generate_work_items("plan-123")
    work_item = items[0]
    
    # Mock WorkerPort execution
    mock_receipt = Mock()
    mock_receipt.exit_code = 0
    mock_evidence = Mock()
    port.execute_delegation.return_value = (mock_receipt, mock_evidence)
    
    receipt, evidence = auditor.execute(work_item)
    
    assert receipt == mock_receipt
    assert evidence == mock_evidence
    
    # Ensure proper delegation payload was passed
    port.execute_delegation.assert_called_once()
    args, kwargs = port.execute_delegation.call_args
    assert args[0] == work_item
    
    payload = args[1]
    assert "<untrusted_project_data>" in payload["prompt"]
    assert "src/main.py" in payload["prompt"]
    assert payload["target"] == "src/main.py"
    assert payload["scope"] == "FULL"

def test_failure_handling(dummy_snapshot):
    port = Mock(spec=WorkerPort)
    auditor = SecurityAuditor(port, dummy_snapshot, "FULL")
    items = auditor.generate_work_items("plan-123")
    work_item = items[0]
    
    mock_receipt = Mock()
    mock_receipt.exit_code = 1
    port.execute_delegation.return_value = (mock_receipt, None)
    
    receipt, evidence = auditor.execute(work_item)
    assert receipt.exit_code == 1
    assert evidence is None

