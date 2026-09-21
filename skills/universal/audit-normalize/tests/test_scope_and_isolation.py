"""Tests demonstrating scope enforcement and non-auditing invariants.

Verifies that audit-normalize NEVER audits source code, never invents findings,
never treats recommendations as findings, and never transforms absence of findings into findings.
"""

import json
import os
import tempfile
import pytest
from audit_normalize.normalize import normalize, discover_sources
from audit_normalize.validator import get_default_schema_path


def test_scope_no_audit_on_source_code():
    """Verify that audit-normalize does NOT audit projects or source code files.
    
    Given a directory containing only source code files (e.g. Java, Python) and no audit markdown,
    audit-normalize must refuse to audit, must invent zero findings, and must report lack of audit sources.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create dummy project source code files
        src_dir = os.path.join(tmp_dir, "src", "main", "java")
        os.makedirs(src_dir, exist_ok=True)
        
        with open(os.path.join(src_dir, "VulnerableAuth.java"), "w") as f:
            f.write("""
            public class VulnerableAuth {
                // Hardcoded password and SQL injection vulnerability
                String password = "admin";
                public void login(String query) {
                    execute("SELECT * FROM users WHERE user = '" + query + "'");
                }
            }
            """)

        out_dir = os.path.join(tmp_dir, "normalized")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        # Must report absence of audit markdown sources and refuse to audit
        assert result["overall_status"] == "INVALID"
        assert result["sources_processed"] == 0
        assert any("No candidate Markdown audit sources found" in err for err in result["errors"])
        # Must not generate report_data.json
        assert not os.path.exists(os.path.join(out_dir, "report_data.json"))


def test_recommendation_is_not_finding():
    """Verify adversarial case: a recommendation in an audit text does NOT become a new finding."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        doc_path = os.path.join(tmp_dir, "report.md")
        with open(doc_path, "w") as f:
            f.write("""# Audit Report
## Summary
The system has some issues.

## Recommendations
- We recommend upgrading PostgreSQL to version 16.
- We recommend enforcing multi-factor authentication for all administrators.
- We recommend setting up automated unit tests in CI.

## Findings
### SEC-001
Title: Permissive CORS
Category: SECURITY
Type: RISK
Status: CONFIRMED
Severity: P3
Confidence: HIGH
Recommendation: Restrict allowed origins to trusted domains.
""")

        out_dir = os.path.join(tmp_dir, "normalized")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        assert result["overall_status"] == "VALID"
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        # Only SEC-001 must exist as a finding; the 3 recommendations must NOT become findings
        assert len(data["findings"]) == 1
        assert data["findings"][0]["id"] == "SEC-001"
        assert data["metrics"]["findings_total"] == 1


def test_absence_of_findings_does_not_create_finding():
    """Verify adversarial case: inspecting an area with no findings does NOT create a finding."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        doc_path = os.path.join(tmp_dir, "coverage.md")
        with open(doc_path, "w") as f:
            f.write("""# Coverage Manifest
## Inspection Coverage
| Category | Subcategory | State | Result |
| DATABASE | CONNECTION_POOLING | INSPECTED | NOT_FOUND |
| SECURITY | SQL_INJECTION | INSPECTED | NOT_FOUND |
""")

        out_dir = os.path.join(tmp_dir, "normalized")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        assert result["overall_status"] == "VALID"
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        # NOT_FOUND result must NOT create findings!
        assert len(data["findings"]) == 0
        assert data["metrics"]["findings_total"] == 0
        assert len(data["inspections"]) == 2
