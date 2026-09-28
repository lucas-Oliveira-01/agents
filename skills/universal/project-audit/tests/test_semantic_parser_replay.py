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


def test_semantic_parser_normalizes_documented_type_status_evidence_and_location_aliases():
    payload = {
        "findings": [
            {
                "title": "Alias finding",
                "category": "SECURITY",
                "type": "CSRF",
                "status": "POSSIBLE",
                "severity": "HIGH",
                "confidence": "MEDIUM",
                "location": {"files": ["src/app.py"], "lines": [23, 25]},
                "evidence": ["First observation", "Second observation"],
                "description": "Candidate emitted using documented alternate forms.",
            }
        ]
    }

    from project_audit.semantic_auditor import _parse_output
    candidates = _parse_output(payload)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.finding_type == "VULNERABILITY"
    assert candidate.raw_type == "CSRF"
    assert candidate.type_normalization_rule == "CSRF->VULNERABILITY"
    assert candidate.status == "NOT_DETERMINABLE"
    assert candidate.raw_status == "POSSIBLE"
    assert candidate.status_normalization_rule == "POSSIBLE->NOT_DETERMINABLE"
    assert candidate.severity == "P1"
    assert candidate.location == {"file": "src/app.py", "line_start": 23, "line_end": 25}
    assert candidate.evidence == "First observation\nSecond observation"


def test_semantic_parser_preserves_multi_file_locations():
    payload = {
        "findings": [{
            "title": "Cross-file authorization candidate",
            "category": "SECURITY",
            "subcategory": "AUTHORIZATION",
            "type": "IDOR",
            "status": "PROBABLE",
            "severity": "HIGH",
            "confidence": "MEDIUM",
            "location": {
                "locations": [
                    {"file": "src/controller/Orders.java", "line": 10},
                    {"file": "src/service/OrderService.java", "line_start": 42, "line_end": 48}
                ]
            },
            "evidence": "The resource identifier is propagated without ownership validation.",
            "description": "Cross-file candidate requiring confirmation.",
        }]
    }

    from project_audit.semantic_auditor import _parse_output
    candidates = _parse_output(payload)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert len(candidate.locations) == 2
    assert candidate.location == candidate.locations[0]
    assert candidate.locations[1]["file"] == "src/service/OrderService.java"


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


def test_semantic_parser_accepts_smartserv_observed_type_aliases():
    aliases = {
        "STORED_XSS": "VULNERABILITY",
        "REFLECTED_XSS": "VULNERABILITY",
        "MISSING_AUTHORIZATION_CHECK": "VULNERABILITY",
        "OVERLY_PERMISSIVE_CORS": "VULNERABILITY",
        "SESSION_MANAGEMENT": "RISK",
        "LOGIC_FLAW": "BUG",
        "IMPLEMENTATION": "TECHNICAL_DEFECT",
    }
    from project_audit.semantic_auditor import _parse_output

    payload = {
        "findings": [
            {
                **{
                    "title": "Alias " + raw_type,
                    "category": "SECURITY",
                    "type": raw_type,
                    "status": "PROBABLE",
                    "severity": "HIGH",
                    "confidence": "MEDIUM",
                    "evidence": "Observed in source.",
                    "description": "Candidate.",
                },
            }
            for raw_type in aliases
        ]
    }
    candidates = _parse_output(payload)
    assert [candidate.finding_type for candidate in candidates] == list(aliases.values())
    assert all(candidate.type_normalization_rule for candidate in candidates)

def test_semantic_parser_normalizes_all_observed_severity_aliases():
    from project_audit.semantic_auditor import _parse_output
    base_finding = {
        "title": "base",
        "category": "SECURITY",
        "type": "RISK",
        "status": "PROBABLE",
        "severity": "P2",
        "confidence": "MEDIUM",
        "evidence": "Observed",
        "description": "Candidate",
    }
    payload = {
        "findings": [
            {
                **base_finding,
                "title": "severity-" + severity,
                "severity": severity,
            }
            for severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        ]
    }
    candidates = _parse_output(payload)
    assert [candidate.severity for candidate in candidates] == ["P0", "P1", "P2", "P3"]
