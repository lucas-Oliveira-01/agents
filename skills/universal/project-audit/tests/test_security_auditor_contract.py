from __future__ import annotations

from pathlib import Path

from project_audit.classifiers import classify_applicability, classify_files, classify_stack
from project_audit.discovery import discover
from project_audit.models import AuditPlan
from project_audit.planner import prepare_audit
from project_audit.security_auditor import SecurityAuditor


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class DummyWorker:
    def execute_delegation(self, work_item, context_payload, started_at):
        raise AssertionError("delegation must not be invoked in this test")


def test_security_auditor_uses_plan_execution_and_egress_policies(tmp_path: Path) -> None:
    _write(tmp_path, "src/app.py", "print('ok')\n")
    discovery = discover(tmp_path)
    prepared = prepare_audit(
        discovery,
        classify_files(discovery),
        classify_applicability(discovery, classify_stack(discovery)),
    )

    auditor = SecurityAuditor(DummyWorker(), prepared.snapshot)
    items = auditor.generate_work_items(prepared.plan)

    assert items
    assert all(item.plan_ref == prepared.plan.plan_id for item in items)
    assert all(item.effective_execution_policy == prepared.plan.execution_policy for item in items)
    assert all(item.data_egress_policy == prepared.plan.egress_policy for item in items)
