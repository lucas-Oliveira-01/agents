"""Regression tests for tolerant semantic parsing and partial coverage."""

import pytest

from omniroute_delegation.contracts import ExecutionState
from omniroute_delegation.exceptions import SemanticCoverageFailedError
from omniroute_delegation.semantic_parser import (
    SemanticRecoveryLoop,
    extract_json,
    parse_leaf_output,
)


def finding(title="Finding", severity="HIGH"):
    return {
        "title": title,
        "category": "SECURITY",
        "description": "Observed security issue.",
        "severity": severity,
        "confidence": "HIGH",
        "evidence": "Observed in source.",
    }


def test_extracts_json_from_model_chatter():
    payload = 'I found one issue. {"findings": [' + str(finding()).replace("'", '"') + "]}"
    result = extract_json(payload)
    assert result["findings"][0]["title"] == "Finding"


def test_accepts_direct_findings_array():
    findings, errors = parse_leaf_output([finding()])
    assert len(findings) == 1
    assert errors == []


def test_normalizes_severity_with_provenance():
    findings, errors = parse_leaf_output([finding(severity="CRITICAL")])
    assert errors == []
    assert findings[0].severity == "P0"
    assert findings[0].raw_severity == "CRITICAL"
    assert findings[0].normalization_rule == "CRITICAL->P0"


def test_preserves_valid_findings_and_isolates_invalid_items():
    findings, errors = parse_leaf_output(
        [
            finding(title="Valid"),
            {"title": "Invalid", "category": "SECURITY", "description": "bad", "severity": "VERY_BAD"},
        ]
    )
    assert [item.title for item in findings] == ["Valid"]
    assert len(errors) == 1
    assert errors[0]["index"] == 1


def test_recovery_failure_never_becomes_zero_finding_success():
    calls = []

    def failing_delegate(attempt):
        calls.append(attempt)
        return "not json"

    with pytest.raises(SemanticCoverageFailedError) as exc:
        SemanticRecoveryLoop(failing_delegate, max_attempts=2).run()

    assert calls == [1, 2]
    assert exc.value.result.state == ExecutionState.SCHEMA_VIOLATION
    assert exc.value.result.attempts == 2
    assert exc.value.result.raw_errors


def test_partial_result_is_explicit():
    result = SemanticRecoveryLoop(
        lambda attempt: [finding(), {"bad": "shape"}],
        max_attempts=1,
    ).run()

    assert result.state == ExecutionState.PARTIAL_COVERAGE
    assert len(result.findings) == 1
    assert len(result.raw_errors) == 1
