import pytest
from project_audit.semantic_auditor import SemanticAuditor
from project_audit.delegation import WorkerPort, DelegationBackend, DelegationResult, DelegationStatus

class DummyBackend(DelegationBackend):
    def __init__(self, payload):
        self.payload = payload

    def delegate(self, request):
        return DelegationResult(
            request_id=request.request_id,
            status=DelegationStatus.SUCCESS,
            output_payload=self.payload,
            error_message=None,
            provider_info="dummy",
            usage_tokens=10,
        )

def test_semantic_parser_accepts_raw_json_list():
    # ADR 0003: Raw JSON list instead of dict wrapper
    payload = [
        {
            "title": "A finding",
            "category": "SECURITY",
            "subcategory": "AUTHENTICATION",
            "type": "RISK",
            "status": "PROBABLE",
            "severity": "P2",
            "confidence": "MEDIUM",
            "location": {"file": "src/app.py", "line": 1},
            "evidence": "Observed",
            "description": "Candidate requires confirmation."
        }
    ]
    from project_audit.semantic_auditor import _parse_output
    
    candidates = _parse_output(payload)
    assert len(candidates) == 1
    assert candidates[0].title == "A finding"


def test_semantic_parser_normalizes_severity():
    # ADR 0003: CRITICAL severity -> P0, HIGH -> P1, etc.
    # And PROVENANCE must be recorded.
    payload = {
        "findings": [
            {
                "title": "A critical finding",
                "category": "SECURITY",
                "subcategory": "AUTHENTICATION",
                "type": "RISK",
                "status": "PROBABLE",
                "severity": "CRITICAL",
                "confidence": "MEDIUM",
                "location": {"file": "src/app.py", "line": 1},
                "evidence": "Observed",
                "description": "Candidate requires confirmation."
            },
            {
                "title": "A high finding",
                "category": "SECURITY",
                "subcategory": "AUTHENTICATION",
                "type": "RISK",
                "status": "PROBABLE",
                "severity": "HIGH",
                "confidence": "MEDIUM",
                "location": {"file": "src/app.py", "line": 1},
                "evidence": "Observed",
                "description": "Candidate requires confirmation."
            }
        ]
    }
    from project_audit.semantic_auditor import _parse_output
    
    candidates = _parse_output(payload)
    assert len(candidates) == 2
    
    assert candidates[0].raw_severity == "CRITICAL"
    assert candidates[0].severity == "P0"
    assert candidates[0].normalization_rule == "CRITICAL->P0"

    assert candidates[1].raw_severity == "HIGH"
    assert candidates[1].severity == "P1"
    assert candidates[1].normalization_rule == "HIGH->P1"


def test_semantic_parser_rejects_unknown_severity():
    payload = {
        "findings": [
            {
                "title": "A bad finding",
                "category": "SECURITY",
                "type": "RISK",
                "status": "PROBABLE",
                "severity": "VERY_BAD",
                "confidence": "MEDIUM",
                "evidence": "Observed",
                "description": "Candidate"
            }
        ]
    }
    from project_audit.semantic_auditor import _parse_output, SemanticOutputError
    import pytest
    
    with pytest.raises(SemanticOutputError, match="unsupported severity: VERY_BAD"):
        _parse_output(payload)

