import uuid

from omniroute_delegation.contracts import ExecutionState
from project_audit.delegation import DelegationRequest, DelegationStatus
from project_audit.models import CredentialAccess, ExecutionPolicy, FilesystemAccess, NetworkAccess
from project_audit.omniroute_backend import OmniRouteDelegationBackend


class FakeGateway:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def delegate(self, task):
        self.calls.append(task)
        return self.result


def _request() -> DelegationRequest:
    return DelegationRequest(
        request_id="test-req",
        work_item_ref=str(uuid.uuid4()),
        target_surface="CODE_QUALITY/STATIC_REVIEW",
        auditor_name="semantic-auditor",
        context_payload={"source": "print('hello')"},
        execution_policy=ExecutionPolicy(
            filesystem=FilesystemAccess.READ_ONLY,
            network=NetworkAccess.DISABLED,
            credentials=CredentialAccess.NONE,
        ),
    )


def test_backend_delegates_only_through_gateway():
    gateway = FakeGateway(
        {"content": [{"type": "text", "text": '{"findings": []}'}]}
    )
    backend = OmniRouteDelegationBackend(gateway)
    result = backend.delegate(_request())

    assert result.status == DelegationStatus.SUCCESS
    assert result.provider == "omniroute"
    assert result.model == "UNREPORTED"
    assert result.raw_output == '{"findings": []}'
    assert gateway.calls
    task = gateway.calls[0]
    assert task.task_id == "test-req"
    assert task.temperature == 0
    assert "print('hello')" in task.context
    assert "Return exactly one valid JSON object" in task.task
    assert "Do not use Markdown or code fences" in task.task
    assert "Canonical type values" in task.task


def test_backend_unwraps_known_result_envelope_with_markdown_json():
    finding = {
        "title": "Envelope finding",
        "category": "CODE_QUALITY",
        "type": "BUG",
        "status": "PROBABLE",
        "severity": "P2",
        "confidence": "MEDIUM",
        "evidence": "Observed",
        "description": "Candidate",
    }
    import json
    gateway = FakeGateway({
        "result": "```json\n" + json.dumps({"findings": [finding]}) + "\n```"
    })
    result = OmniRouteDelegationBackend(gateway).delegate(_request())

    assert result.status == DelegationStatus.SUCCESS
    assert result.audit_contract is not None
    assert len(result.audit_contract.findings) == 1
    assert result.audit_contract.findings[0].title == "Envelope finding"
    assert result.raw_output is not None
    assert "Envelope finding" in result.raw_output


def test_backend_preserves_partial_audit_contract():
    finding = {
        "title": "Valid finding",
        "category": "CODE_QUALITY",
        "description": "Observed defect.",
        "severity": "HIGH",
        "confidence": "HIGH",
        "type": "BUG",
        "status": "PROBABLE",
        "subcategory": "STATIC_REVIEW",
        "location": {"file": "app.py", "line": 1},
        "evidence": "Observed evidence.",
    }
    payload = {
        "content": [{
            "type": "text",
            "text": (
                '{"findings": ['
                + __import__("json").dumps(finding)
                + ', {"title": "invalid", "category": "CODE_QUALITY"}]}'
            ),
        }]
    }

    backend = OmniRouteDelegationBackend(FakeGateway(payload))
    result = backend.delegate(_request())

    assert result.status == DelegationStatus.SUCCESS
    assert result.audit_contract is not None
    assert result.audit_contract.state == ExecutionState.PARTIAL_COVERAGE
    assert len(result.audit_contract.findings) == 1
    assert result.audit_contract.raw_errors
    assert result.raw_output is not None
    assert "Valid finding" in result.raw_output
    assert result.audit_contract.raw_output == result.raw_output
    assert result.output_payload["findings"][0]["title"] == "Valid finding"


def test_backend_surfaces_whole_document_schema_failure():
    backend = OmniRouteDelegationBackend(
        FakeGateway({"content": [{"type": "text", "text": "not json"}]})
    )
    result = backend.delegate(_request())

    assert result.status == DelegationStatus.FAILED
    assert result.audit_contract is not None
    assert result.audit_contract.state == ExecutionState.SCHEMA_VIOLATION
    assert result.audit_contract.raw_errors

def test_backend_recursively_unwraps_structured_content():
    import json
    finding = {
        "title": "Nested structured finding",
        "category": "SECURITY",
        "type": "BUG",
        "status": "CONFIRMED",
        "severity": "P1",
        "confidence": "HIGH",
        "evidence": "Observed in structured content",
        "description": "Candidate",
    }
    payload = {
        "structuredContent": {
            "result": "```json\n" + json.dumps({"findings": [finding]}) + "\n```"
        }
    }
    gateway = FakeGateway(payload)
    result = OmniRouteDelegationBackend(gateway).delegate(_request())

    assert result.status == DelegationStatus.SUCCESS
    assert result.audit_contract is not None
    assert len(result.audit_contract.findings) == 1
    assert result.audit_contract.findings[0].title == "Nested structured finding"
    assert result.raw_output is not None
    assert "Nested structured finding" in result.raw_output


def test_backend_invalid_meta_falls_back_without_attribute_error():
    gateway = FakeGateway({
        '_omniroute_meta': 'invalid',
        'structuredContent': {'result': '{"findings": []}'},
    })
    result = OmniRouteDelegationBackend(gateway).delegate(_request())
    assert result.status == DelegationStatus.SUCCESS
    assert result.provider == 'omniroute'
    assert result.model == 'UNREPORTED'
