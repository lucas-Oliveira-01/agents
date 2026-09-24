"""P-001/P-002 integration: real policies, WorkerPort and canonical persistence."""
from pathlib import Path

import pytest

from project_audit.classifiers import classify_applicability, classify_files, classify_stack
from project_audit.delegation import DelegationBackend, DelegationResult, DelegationStatus, WorkerPort
from project_audit.discovery import discover
from project_audit.models import ExecutionPolicy, EgressPolicy, EgressDestination
from project_audit.orchestrator import Orchestrator
from project_audit.planner import prepare_audit
from project_audit.schema_validator import validate_evidence
from project_audit.security_auditor import SecurityAuditor
from project_audit.state_store import StateStore


class NetworkResponse(DelegationBackend):
    def __init__(self):
        self.requests = []

    def delegate(self, request):
        self.requests.append(request)
        return DelegationResult(request.request_id, DelegationStatus.SUCCESS,
                                {"findings": []}, None, "test-network", 0)


@pytest.mark.parametrize("allow_egress", [True, False])
def test_security_auditor_binds_plan_policies_through_real_worker_and_store(tmp_path: Path, allow_egress):
    (tmp_path / "app.py").write_text("print('ok')\n")
    discovery = discover(tmp_path)
    prepared = prepare_audit(discovery, classify_files(discovery),
                             classify_applicability(discovery, classify_stack(discovery)))
    if allow_egress:
        prepared.plan.egress_policy = EgressPolicy(EgressDestination.APPROVED_EXTERNAL, True)
    backend = NetworkResponse()
    auditor = SecurityAuditor(WorkerPort(backend, "test"), prepared.snapshot)
    items = auditor.generate_work_items(prepared.plan)
    prepared.plan.work_items = items
    assert items
    assert all(isinstance(item.effective_execution_policy, ExecutionPolicy) for item in items)
    assert all(item.effective_execution_policy == prepared.plan.execution_policy for item in items)
    assert all(item.data_egress_policy == prepared.plan.egress_policy for item in items)

    store = StateStore(tmp_path / ".audit" / "runs")
    run = Orchestrator(store).execute_vertical_slice(prepared.snapshot, prepared.plan, items, auditor)
    assert run.audit_status == ("COMPLETE" if allow_egress else "BLOCKED")
    assert len(backend.requests) == (len(items) if allow_egress else 0)
    assert len(store.list_evidence_ids()) == (len(items) if allow_egress else 0)
    for evidence_id in store.list_evidence_ids():
        data = store.load_evidence(evidence_id).to_dict()
        assert data["validity"] == "NOT_DETERMINABLE"
        assert not validate_evidence(data)
        assert "findings" not in data
    for item in items:
        persisted = store.load_work_item(item.work_item_id)
        assert persisted.effective_execution_policy == prepared.plan.execution_policy
        assert persisted.data_egress_policy == prepared.plan.egress_policy
