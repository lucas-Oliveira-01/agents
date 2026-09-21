"""Adversarial tests for semantic extraction, non-finding separation, and ledger preservation.

Verifies:
- recommendation != finding
- roadmap != finding
- prioritization != finding
- conclusion != finding
- ANALYTICAL_REPORT recommendations do NOT replace AUDIT_LEDGER descriptions
"""

import json
import os
import tempfile
import pytest
from audit_normalize.normalize import normalize
from audit_normalize.validator import get_default_schema_path


def test_adversarial_non_finding_sections_not_extracted_as_findings():
    """Verify that roadmap, prioritization, conclusions, and improvement lists are NOT findings."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        doc_path = os.path.join(tmp_dir, "strategic_report.md")
        with open(doc_path, "w") as f:
            f.write("""# STRATEGIC AUDIT & ROADMAP

## Executive Summary
This document outlines our findings and strategic recommendations for Q3/Q4.

## Prioritization Matrix
- P0: Critical emergency patching of OpenSSL vulnerabilities
- P1: Migrate authentication layer to OIDC
- P2: Implement automated SAST in GitLab CI pipeline
- P3: Refactor legacy database access layers

| Priority | Initiative | Effort | Target Quarter |
| High | Zero Trust Network Architecture | High | Q4 2026 |
| Medium | Database Connection Pool Hardening | Low | Q3 2026 |

## Recommendations
1. Upgrade Java runtime from 17 to 21 LTS.
2. Replace all MD5 hashes with SHA-256 or bcrypt.
3. Configure rate limiting on all public API endpoints.
4. Establish quarterly penetration testing cadence.

## Roadmap 2026-2027
- Milestone 1: Core infrastructure modernization
- Milestone 2: Cloud migration to multi-region setup
- Milestone 3: Compliance audit readiness (ISO 27001)

## Improvement List
- Refactor transaction handling in order service
- Improve logging formatting for ELK ingestion
- Document API schemas in OpenAPI 3.1

## Conclusion
The application architecture is sound but requires operational discipline.

## Findings
### SEC-001: SQL Injection in Search Endpoint
Category: SECURITY
Type: VULNERABILITY
Severity: P0
Status: CONFIRMED
Location: src/search/SearchController.java:54
Description: Unsanitized search query parameter concatenated into SQL statement.
Recommendation: Utilize JPA Criteria API or parameterized queries.
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

        # Strictly only SEC-001 must be extracted as a finding!
        # None of the 4 priorities, 4 recommendations, 3 roadmap milestones,
        # 3 improvements, or conclusion bullets may become findings.
        assert len(data["findings"]) == 1
        finding = data["findings"][0]
        assert finding["id"] == "SEC-001"
        assert finding["category"] == "SECURITY"
        assert finding["severity"]["value"] == "P0"
        assert data["metrics"]["findings_total"] == 1


def test_adversarial_analytical_report_recommendation_does_not_replace_ledger_description():
    """Verify that ANALYTICAL_REPORT recommendations do not silently replace AUDIT_LEDGER canonical description."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Audit Ledger (rank 1): Canonical source of the finding description
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Findings
### SEC-001: Missing JWT Verification
Category: SECURITY
Subcategory: AUTHENTICATION
Type: VULNERABILITY
Status: CONFIRMED
Severity: P1
Confidence: HIGH
Location: src/auth/JwtFilter.java:33
Description: The HTTP request filter parses the JWT header but skips signature verification when algorithm is 'none'.
""")

        # 2. Analytical Report (rank 2): Contains recommendations and editorial summary
        with open(os.path.join(tmp_dir, "02_analytical_report.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## Executive Summary
Audit analysis of authentication infrastructure.

## Recommendations
### SEC-001
Recommendation: Disallow the 'none' algorithm explicitly in JJWT parser configuration and mandate RSA public key pinning.

## Prioritization
- SEC-001 should be addressed before next production deployment.
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

        assert len(data["findings"]) == 1
        finding = data["findings"][0]
        assert finding["id"] == "SEC-001"

        # Canonical description MUST remain the one from the Audit Ledger!
        assert finding["description"]["state"] == "PRESENT"
        assert "algorithm is 'none'" in finding["description"]["value"]
        assert "Disallow the 'none' algorithm" not in finding["description"]["value"]

        # The recommendation from the Analytical Report is preserved in recommendation field non-destructively
        assert finding["recommendation"]["state"] == "PRESENT"
        assert "Disallow the 'none' algorithm" in finding["recommendation"]["value"]
