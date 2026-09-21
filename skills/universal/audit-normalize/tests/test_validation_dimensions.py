"""Tests for multi-dimensional validation in audit-normalize.

Verifies:
- JSON Schema validation
- Semantic validation (metrics, invariants, information states, location bounds)
- Referential validation (provenances, conflict IDs, finding references)
- Integrity validation (file hashes, snapshot ID)
"""

import json
import os
import tempfile
import pytest
from audit_normalize.validator import AuditDataValidator


@pytest.fixture
def minimal_valid_report():
    return {
        "metadata": {
            "schema_version": "1.0",
            "generator": "audit-normalize",
            "generated_at": "2026-09-18T00:00:00Z",
        },
        "target_project": {
            "repository": {"state": "NOT_PROVIDED_BY_SOURCE", "value": None, "provenance": [{"source_id": "src-001", "file": "audit.md"}]},
            "commit": {"state": "NOT_PROVIDED_BY_SOURCE", "value": None, "provenance": [{"source_id": "src-001", "file": "audit.md"}]},
            "branch": {"state": "NOT_PROVIDED_BY_SOURCE", "value": None, "provenance": [{"source_id": "src-001", "file": "audit.md"}]},
            "version": {"state": "NOT_PROVIDED_BY_SOURCE", "value": None, "provenance": [{"source_id": "src-001", "file": "audit.md"}]},
            "build_version": {"state": "NOT_PROVIDED_BY_SOURCE", "value": None, "provenance": [{"source_id": "src-001", "file": "audit.md"}]},
        },
        "audit_snapshot": {
            "snapshot_id": "sha256:18cc7b78cab41ffe9b5f369225bc86242c7fbb88d34b177fc46e14239292ca91",
            "created_at": "2026-09-18T00:00:00Z",
            "sources": [
                {
                    "source_id": "src-001",
                    "file": "audit.md",
                    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                    "source_role": "AUDIT_LEDGER",
                }
            ],
        },
        "applicability": [],
        "inspections": [],
        "findings": [
            {
                "id": "SEC-001",
                "title": "SQL Injection in User Lookup",
                "category": "SECURITY",
                "subcategory": "INJECTION",
                "type": {"state": "PRESENT", "value": "VULNERABILITY"},
                "status": {"state": "PRESENT", "value": "CONFIRMED"},
                "severity": {"state": "PRESENT", "value": "P0"},
                "confidence": {"state": "PRESENT", "value": "HIGH"},
                "location": {"state": "PRESENT", "value": {"file": "UserDAO.java", "line": 42}},
                "evidence": {"state": "PRESENT", "value": "query concatenation detected"},
                "description": {"state": "PRESENT", "value": "User input concatenated directly into SQL query"},
                "cause": {"state": "PRESENT", "value": "Lack of prepared statements"},
                "impact": {"state": "PRESENT", "value": "Full database breach"},
                "exploitability": {"state": "PRESENT", "value": "Trivial via username parameter"},
                "recommendation": {"state": "PRESENT", "value": "Use parameterized queries"},
                "provenance": [{"source_id": "src-001", "file": "audit.md"}],
            }
        ],
        "controls": [],
        "anomalies": [],
        "conflicts": [],
        "metrics": {
            "findings_total": 1,
            "severity": {"P0": 1, "P1": 0, "P2": 0, "P3": 0, "INFO": 0},
            "controls_total": 0,
            "inspections_total": 0,
        },
        "limitations": [],
        "references": [],
    }


def test_validator_valid_dataset(canonical_schema, minimal_valid_report):
    validator = AuditDataValidator(canonical_schema)
    res = validator.validate_all(minimal_valid_report)
    assert res["overall_status"] == "VALID"
    assert len(res["errors"]) == 0


def test_validator_detects_metric_count_mismatch(canonical_schema, minimal_valid_report):
    validator = AuditDataValidator(canonical_schema)
    minimal_valid_report["metrics"]["findings_total"] = 99
    res = validator.validate_all(minimal_valid_report)
    assert res["overall_status"] == "INVALID"
    assert any("findings_total=99 != len(findings)=1" in err for err in res["errors"])


def test_validator_detects_severity_count_mismatch(canonical_schema, minimal_valid_report):
    validator = AuditDataValidator(canonical_schema)
    minimal_valid_report["metrics"]["severity"]["P0"] = 0
    res = validator.validate_all(minimal_valid_report)
    assert res["overall_status"] == "INVALID"
    assert any("Metrics severity mismatch for P0" in err for err in res["errors"])


def test_validator_prohibits_not_found_as_finding_status(canonical_schema, minimal_valid_report):
    validator = AuditDataValidator(canonical_schema)
    minimal_valid_report["findings"][0]["status"]["value"] = "NOT_FOUND"
    res = validator.validate_all(minimal_valid_report)
    assert res["overall_status"] == "INVALID"
    assert any("prohibited status 'NOT_FOUND'" in err for err in res["errors"])


def test_validator_detects_invalid_line_range(canonical_schema, minimal_valid_report):
    validator = AuditDataValidator(canonical_schema)
    minimal_valid_report["findings"][0]["location"]["value"] = {
        "file": "UserDAO.java",
        "line_start": 50,
        "line_end": 40,  # line_end < line_start
    }
    res = validator.validate_all(minimal_valid_report)
    assert res["overall_status"] == "INVALID"
    assert any("line_end (40) < line_start (50)" in err for err in res["errors"])


def test_validator_detects_missing_not_determinable_reason(canonical_schema, minimal_valid_report):
    validator = AuditDataValidator(canonical_schema)
    minimal_valid_report["findings"][0]["status"] = {
        "state": "NOT_DETERMINABLE",
        "value": None,
    }
    res = validator.validate_all(minimal_valid_report)
    assert res["overall_status"] == "INVALID"
    assert any("reason is missing or empty" in err for err in res["errors"])


def test_validator_detects_invalid_provenance_source(canonical_schema, minimal_valid_report):
    validator = AuditDataValidator(canonical_schema)
    minimal_valid_report["findings"][0]["provenance"] = [{"source_id": "src-999", "file": "ghost.md"}]
    res = validator.validate_all(minimal_valid_report)
    assert res["overall_status"] == "INVALID"
    assert any("provenance source_id 'src-999' not in audit_snapshot.sources" in err for err in res["errors"])


def test_validator_detects_orphan_conflict_id(canonical_schema, minimal_valid_report):
    validator = AuditDataValidator(canonical_schema)
    minimal_valid_report["findings"][0]["severity"] = {
        "state": "CONFLICT",
        "value": None,
        "conflict_id": "CONFLICT-999",
    }
    res = validator.validate_all(minimal_valid_report)
    assert res["overall_status"] == "INVALID"
    assert any("non-existent conflict_id 'CONFLICT-999'" in err for err in res["errors"])
