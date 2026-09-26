"""Tests for precedence policy and conflict handling in audit-normalize.

Verifies:
- Precedence ranking per v8_current.md (AUDIT_LEDGER > ANALYTICAL_REPORT > INVENTORY > EXTERNAL_REVIEW)
- Conflict resolution and history preservation
- Tie policy producing UNRESOLVED conflicts with null values and valid conflict_id
- Prohibited fallback policies (highest severity, first occurrence, last occurrence)
"""

import json
import os
import tempfile
import pytest
from audit_normalize.normalize import normalize
from audit_normalize.validator import get_default_schema_path


def test_precedence_ledger_over_analytical():
    """Verify that AUDIT_LEDGER (rank 1) takes precedence over ANALYTICAL_REPORT (rank 2)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # File 1: Analytical Report (rank 2)
        with open(os.path.join(tmp_dir, "02_analytical_report.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## SEC-001
Title: Wildcard CORS configuration
Category: SECURITY
Type: RISK
Severity: P2
Confidence: MEDIUM
""")

        # File 2: Audit Ledger (rank 1)
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## SEC-001
Title: Permissive wildcard CORS configuration
Category: SECURITY
Type: RISK
Severity: P3
Confidence: HIGH
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

        f_sec = next(f for f in data["findings"] if f["id"] == "SEC-001")
        # AUDIT_LEDGER (rank 1) wins over ANALYTICAL_REPORT (rank 2)
        # Severity must be P3 (from ledger), not P2 (from analytical)
        assert f_sec["severity"]["value"] == "P3"
        assert f_sec["confidence"]["value"] == "HIGH"

        # A resolved conflict must be recorded in data["conflicts"]
        assert len(data["conflicts"]) > 0
        sev_conflict = next(c for c in data["conflicts"] if c["field"] == "severity")
        assert sev_conflict["resolution"]["status"] == "RESOLVED"
        assert sev_conflict["resolution"]["policy_applied"] == "SOURCE_ROLE_PRECEDENCE"
        # Selected source must be the ledger
        ledger_source = next(s for s in data["audit_snapshot"]["sources"] if s["source_role"] == "AUDIT_LEDGER")
        assert sev_conflict["resolution"]["selected_source"] == ledger_source["source_id"]


def test_adversarial_highest_severity_does_not_win():
    """Adversarial check: higher severity must NOT win over higher precedence rank.
    
    If ANALYTICAL_REPORT (rank 2) says P3 (low), and THREAT_MODEL (rank 3) says P0 (critical),
    the higher precedence source (rank 2) MUST win with P3.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        # File 1: Analytical report (rank 2)
        with open(os.path.join(tmp_dir, "analytical.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## BUG-101
Title: Buffer alignment defect
Category: SECURITY
Type: BUG
Severity: P3
Status: CONFIRMED
""")

        # File 2: Threat model (rank 3)
        with open(os.path.join(tmp_dir, "threat_model.md"), "w") as f:
            f.write("""# THREAT MODEL
## BUG-101
Title: Buffer alignment defect
Category: SECURITY
Type: BUG
Severity: P0
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

        assert result["schema_validity"] == "VALID"
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        f_bug = next(f for f in data["findings"] if f["id"] == "BUG-101")
        # Rank 2 (P3) must win over Rank 3 (P0) despite P0 being higher severity!
        assert f_bug["severity"]["value"] == "P3"
        assert data["metrics"]["severity"]["P3"] == 1
        assert data["metrics"]["severity"]["P0"] == 0


def test_adversarial_first_or_last_occurrence_does_not_win():
    """Adversarial check: first occurrence or last occurrence must NOT dictate precedence."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # File 1 alphabetically: external review (rank 4) -> Severity P0
        with open(os.path.join(tmp_dir, "a_external.md"), "w") as f:
            f.write("""# EXTERNAL REVIEW
## SEC-050
Title: Outdated OpenSSL
Category: SECURITY
Type: VULNERABILITY
Severity: P0
Status: CONFIRMED
""")

        # File 2 alphabetically: audit ledger (rank 1) -> Severity P2
        with open(os.path.join(tmp_dir, "m_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## SEC-050
Title: Outdated OpenSSL
Category: SECURITY
Type: VULNERABILITY
Severity: P2
Status: CONFIRMED
""")

        # File 3 alphabetically: external review (rank 4) -> Severity P1
        with open(os.path.join(tmp_dir, "z_external.md"), "w") as f:
            f.write("""# EXTERNAL REVIEW
## SEC-050
Title: Outdated OpenSSL
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

        assert result["schema_validity"] == "VALID"
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        f_sec = next(f for f in data["findings"] if f["id"] == "SEC-050")
        # Ledger (rank 1) is in the middle, yet it must win with P2!
        # First occurrence was P0; last was P1; winner is P2!
        assert f_sec["severity"]["value"] == "P2"


def test_tie_policy_unresolved_conflict():
    """Verify that a tie between sources of identical rank results in state: CONFLICT, value: null, and conflict_id."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Two analytical reports (both rank 2) disagreeing on severity
        with open(os.path.join(tmp_dir, "analytical_team_a.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## ARCH-010
Title: Synchronous HTTP calls in loop
Category: ARCHITECTURE
Type: ARCHITECTURAL_DEFECT
Severity: P1
Status: CONFIRMED
""")

        with open(os.path.join(tmp_dir, "analytical_team_b.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## ARCH-010
Title: Synchronous HTTP calls in loop
Category: ARCHITECTURE
Type: ARCHITECTURAL_DEFECT
Severity: P2
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

        assert result["schema_validity"] == "VALID"
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        f_arch = next(f for f in data["findings"] if f["id"] == "ARCH-010")
        # Due to tie, severity state must be CONFLICT, value null, and conflict_id set
        assert f_arch["severity"]["state"] == "CONFLICT"
        assert f_arch["severity"]["value"] is None
        assert f_arch["severity"]["conflict_id"].startswith("CONFLICT-")

        # Conflict record must be UNRESOLVED
        conf = next(c for c in data["conflicts"] if c["id"] == f_arch["severity"]["conflict_id"])
        assert conf["resolution"]["status"] == "UNRESOLVED"
        assert conf["resolution"]["policy_applied"] is None
        assert conf["resolution"]["selected_source"] is None
