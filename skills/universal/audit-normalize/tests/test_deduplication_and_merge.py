"""Tests for deduplication, non-destructive merging, and ID collisions in audit-normalize.

Verifies:
- Explicit ID deduplication across multiple sources
- Non-destructive merging of complementary fields
- ID collision detection for semantically incompatible entities with same ID
- Adversarial verification that textual similarity alone does not authorize merge
"""

import json
import os
import tempfile
import pytest
from audit_normalize.normalize import normalize
from audit_normalize.validator import get_default_schema_path


def test_non_destructive_field_merge():
    """Verify non-destructive merge: complementary fields across sources are united without conflict."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Source 1 provides Title, Location, and Evidence
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## SEC-001
Title: Permissive CORS configuration
Category: SECURITY
Type: RISK
Status: CONFIRMED
Severity: P3
Location: backend/CorsConfig.java:12
Evidence: it.anyHost() configured
""")

        # Source 2 provides Description, Cause, and Impact
        with open(os.path.join(tmp_dir, "02_analytical_report.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## SEC-001
Title: Permissive CORS configuration
Category: SECURITY
Type: RISK
Cause: Convenience during local development
Impact: Cross-origin authenticated requests if cookies lack SameSite
Recommendation: Enforce strict origin checking in production
""")

        out_dir = os.path.join(tmp_dir, "normalized")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        assert result["schema_validity"] == "VALID"
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        assert len(data["findings"]) == 1
        f_sec = data["findings"][0]

        # Location and evidence from Source 1 preserved
        assert f_sec["location"]["state"] == "PRESENT"
        assert f_sec["location"]["value"]["file"] == "backend/CorsConfig.java"
        assert f_sec["evidence"]["state"] == "PRESENT"
        assert "it.anyHost()" in f_sec["evidence"]["value"]

        # Cause and impact from Source 2 preserved
        assert f_sec["cause"]["state"] == "PRESENT"
        assert "Convenience" in f_sec["cause"]["value"]
        assert f_sec["impact"]["state"] == "PRESENT"
        assert "Cross-origin" in f_sec["impact"]["value"]

        # No conflicts should be generated for complementary absent fields
        assert len(data["conflicts"]) == 0


def test_id_collision_detection():
    """Verify that identical IDs with fundamentally incompatible categories trigger an ID_COLLISION anomaly."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # File 1 defines SEC-001 as a database defect
        with open(os.path.join(tmp_dir, "db_audit.md"), "w") as f:
            f.write("""# Database Audit
## SEC-001
Title: Missing primary key in audit logs table
Category: DATABASE
Type: TECHNICAL_DEFECT
Severity: P2
Status: CONFIRMED
""")

        # File 2 defines SEC-001 as a security vulnerability
        with open(os.path.join(tmp_dir, "sec_audit.md"), "w") as f:
            f.write("""# Security Audit
## SEC-001
Title: Stored XSS in comments field
Category: SECURITY
Type: VULNERABILITY
Severity: P1
Status: CONFIRMED
""")

        out_dir = os.path.join(tmp_dir, "normalized")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        # An ID_COLLISION anomaly must be recorded
        collision_anom = next((a for a in data["anomalies"] if a["type"] == "ID_COLLISION"), None)
        assert collision_anom is not None
        assert "SEC-001" in collision_anom["description"]

        # The findings must NOT have been merged into one
        assert len(data["findings"]) == 2


def test_adversarial_text_similarity_does_not_merge():
    """Adversarial check: two findings with similar text descriptions but different IDs/locations must NOT merge."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## SEC-001
Title: Insecure cookie missing HttpOnly flag
Category: SECURITY
Type: RISK
Severity: P3
Location: backend/src/main/java/auth/CookieService.java:45
Description: The session cookie is created without the HttpOnly attribute.

## SEC-002
Title: Insecure cookie missing HttpOnly flag
Category: SECURITY
Type: RISK
Severity: P3
Location: backend/src/main/java/web/RememberMeService.java:88
Description: The remember-me cookie is created without the HttpOnly attribute.
""")

        out_dir = os.path.join(tmp_dir, "normalized")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        assert result["schema_validity"] == "VALID"
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        # Must keep both findings separate despite identical titles and near-identical descriptions
        assert len(data["findings"]) == 2
        f_ids = {f["id"] for f in data["findings"]}
        assert "SEC-001" in f_ids
        assert "SEC-002" in f_ids
