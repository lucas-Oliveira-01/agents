"""Tests for refinements, edge cases, findings without ID, target project conflicts, and portability."""

import json
import os
import shutil
import tempfile
import pytest
from audit_normalize.normalize import normalize
from audit_normalize.validator import get_default_schema_path


def test_finding_without_id_zero_match():
    """Verify that a finding without ID that matches 0 other findings gets a generated canonical ID."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "report.md"), "w") as f:
            f.write("""# AUDIT REPORT
## Findings
### Hardcoded JWT Secret Key
Category: SECURITY
Type: VULNERABILITY
Severity: P1
Status: CONFIRMED
Location: src/auth/jwt.py:42
Description: JWT secret key is hardcoded in source repository.
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
        assert finding["id"].startswith("FINDING-")
        assert finding["category"] == "SECURITY"
        assert finding["severity"]["value"] == "P1"
        assert finding["location"]["value"]["file"] == "src/auth/jwt.py"
        assert finding["location"]["value"]["line"] == 42


def test_finding_without_id_one_match_with_explicit_id():
    """Verify that a finding without ID matching exactly 1 explicit ID finding merges into it with precedence."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Source 1: Analytical Report (rank 2) with finding without ID
        with open(os.path.join(tmp_dir, "02_report.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## Findings
### Insecure Token Validation
Category: SECURITY
Type: VULNERABILITY
Severity: P0
Location: src/auth/token.py:50-55
Description: Detailed narrative about cryptographic signature bypass.
""")

        # Source 2: Audit Ledger (rank 1) with explicit ID
        with open(os.path.join(tmp_dir, "03_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Findings
### SEC-001: Signature validation bypass
Category: SECURITY
Type: VULNERABILITY
Severity: P1
Location: src/auth/token.py:52
Description: Token signature is not verified against public key.
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

        # Must merge into single finding with the explicit ID SEC-001
        assert len(data["findings"]) == 1
        finding = data["findings"][0]
        assert finding["id"] == "SEC-001"

        # Provenance must include both sources
        prov_sources = {p["source_id"] for p in finding["provenance"]}
        assert len(prov_sources) == 2

        # Precedence: Audit Ledger (rank 1) wins over Analytical Report (rank 2)
        # Severity must be P1 (from Ledger)
        assert finding["severity"]["value"] == "P1"

        # Severity conflict must be recorded as RESOLVED
        sev_conf = next(c for c in data["conflicts"] if c["field"] == "severity")
        assert sev_conf["resolution"]["status"] == "RESOLVED"
        assert sev_conf["resolution"]["policy_applied"] == "SOURCE_ROLE_PRECEDENCE"


def test_finding_without_id_match_between_no_id_findings():
    """Verify that two findings without ID matching structurally merge and receive a generated ID."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Source 1: Analytical Report (rank 2)
        with open(os.path.join(tmp_dir, "02_report.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## Findings
### Weak Password Policy
Category: SECURITY
Type: DEFECT
Severity: P2
Location: src/user/policy.py:20-30
Description: Password policy allows 6-character passwords.
""")

        # Source 2: External Review (rank 4)
        with open(os.path.join(tmp_dir, "04_external_review.md"), "w") as f:
            f.write("""# EXTERNAL REVIEW
## Findings
### Insufficient Credential Complexity
Category: SECURITY
Type: DEFECT
Severity: P1
Location: src/user/policy.py:25
Description: Policy does not mandate special characters.
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
        assert finding["id"].startswith("FINDING-")
        assert len(finding["provenance"]) == 2

        # Rank 2 (Analytical) beats Rank 4 (External Review) -> Severity P2 wins
        assert finding["severity"]["value"] == "P2"

        sev_conf = next(c for c in data["conflicts"] if c["field"] == "severity")
        assert sev_conf["resolution"]["status"] == "RESOLVED"


def test_finding_without_id_ambiguous_two_matches():
    """Verify that a finding without ID that ambiguously matches 2 candidates is kept distinct."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Source 1: Has two findings in overlapping ranges in the same file
        with open(os.path.join(tmp_dir, "03_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Findings
### SEC-001: Issue A
Category: SECURITY
Type: VULNERABILITY
Severity: P2
Location: src/service.py:10-30

### SEC-002: Issue B
Category: SECURITY
Type: VULNERABILITY
Severity: P3
Location: src/service.py:20-40
""")

        # Source 2: Has a finding without ID overlapping both (line 25)
        with open(os.path.join(tmp_dir, "02_report.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## Findings
### Ambiguous Middle Defect
Category: SECURITY
Type: VULNERABILITY
Severity: P1
Location: src/service.py:25
Description: Intersects both range 10-30 and range 20-40.
""")

        out_dir = os.path.join(tmp_dir, "normalized")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        assert result["overall_status"] in ("VALID", "VALID_WITH_WARNINGS")
        assert len(result["errors"]) == 0
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        # Ambiguous match cannot merge into either; must produce 3 separate findings
        assert len(data["findings"]) == 3
        ids = {f["id"] for f in data["findings"]}
        assert "SEC-001" in ids
        assert "SEC-002" in ids
        assert any(x.startswith("FINDING-") for x in ids)

        # Anomaly logged for ambiguous match
        anom_types = {a["type"] for a in data["anomalies"]}
        assert "CONTRADICTORY_STATEMENT" in anom_types


def test_finding_without_id_multiple_sources():
    """Verify 3 distinct sources matching structurally merge into 1 finding with full provenance."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "03_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Findings
### SEC-001: Weak Encryption
Category: SECURITY
Type: VULNERABILITY
Severity: P1
Location: src/crypto/cipher.py:100-110
""")

        with open(os.path.join(tmp_dir, "02_report.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## Findings
### Inadequate Cipher Mode
Category: SECURITY
Type: VULNERABILITY
Severity: P2
Location: src/crypto/cipher.py:105
""")

        with open(os.path.join(tmp_dir, "04_external_review.md"), "w") as f:
            f.write("""# EXTERNAL REVIEW
## Findings
### Cryptographic Flaw in Cipher
Category: SECURITY
Type: VULNERABILITY
Severity: P0
Location: src/crypto/cipher.py:102
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
        assert len(finding["provenance"]) == 3

        # AUDIT_LEDGER (rank 1) wins over ANALYTICAL (rank 2) and EXTERNAL (rank 4) -> P1
        assert finding["severity"]["value"] == "P1"


def test_target_project_precedence_resolution():
    """Verify precedence resolution for divergent target commit values."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # File 1: Audit Ledger (rank 1)
        with open(os.path.join(tmp_dir, "03_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Project Name: smartserv
- Target Commit: aaaaaaa111111111111111111111111111111111
""")

        # File 2: Analytical Report (rank 2)
        with open(os.path.join(tmp_dir, "02_report.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## Metadata
- Repository: smartserv
- Commit: bbbbbbb222222222222222222222222222222222
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

        # Audit Ledger (rank 1) wins over Analytical Report (rank 2)
        assert data["target_project"]["commit"]["state"] == "PRESENT"
        assert data["target_project"]["commit"]["value"] == "aaaaaaa111111111111111111111111111111111"

        # Conflict recorded
        tp_conf = next(c for c in data["conflicts"] if c["type"] == "TARGET_PROJECT_CONFLICT")
        assert tp_conf["field"] == "commit"
        assert tp_conf["resolution"]["status"] == "RESOLVED"
        assert tp_conf["resolution"]["policy_applied"] == "SOURCE_ROLE_PRECEDENCE"


def test_target_project_precedence_tie():
    """Verify tie policy for divergent target commit values with equal precedence rank."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Two Ledger files (both rank 1)
        with open(os.path.join(tmp_dir, "03_ledger_a.md"), "w") as f:
            f.write("""# AUDIT LEDGER PART A
## Identity
- Project Name: smartserv
- Target Commit: aaaaaaa111111111111111111111111111111111
""")

        with open(os.path.join(tmp_dir, "03_ledger_b.md"), "w") as f:
            f.write("""# AUDIT LEDGER PART B
## Identity
- Project Name: smartserv
- Target Commit: bbbbbbb222222222222222222222222222222222
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

        # Equal rank tie -> state CONFLICT, value null, conflict_id set
        commit_field = data["target_project"]["commit"]
        assert commit_field["state"] == "CONFLICT"
        assert commit_field["value"] is None
        assert commit_field["conflict_id"].startswith("CONFLICT-")

        tp_conf = next(c for c in data["conflicts"] if c["id"] == commit_field["conflict_id"])
        assert tp_conf["type"] == "TARGET_PROJECT_CONFLICT"
        assert tp_conf["resolution"]["status"] == "UNRESOLVED"
        assert tp_conf["resolution"]["selected_source"] is None


def test_declared_count_discrepancy_anomaly():
    """Verify anomaly detection when declared summary count diverges from actual extracted count."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Summary
Total de achados: 5

## Findings
### SEC-001: SQL Injection
Category: SECURITY
Type: VULNERABILITY
Severity: P0
Location: src/db.py:10

### SEC-002: Cross-Site Scripting
Category: SECURITY
Type: VULNERABILITY
Severity: P1
Location: src/view.py:20
""")

        out_dir = os.path.join(tmp_dir, "normalized")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        assert result["overall_status"] in ("VALID", "VALID_WITH_WARNINGS")
        assert len(result["errors"]) == 0
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        # Actual findings total is 2, despite declared 5
        assert len(data["findings"]) == 2
        assert data["metrics"]["findings_total"] == 2

        # Discrepancy logged as TECHNICAL_INCONSISTENCY anomaly
        discrepancy_anom = next(a for a in data["anomalies"] if a["type"] == "TECHNICAL_INCONSISTENCY")
        assert "5" in discrepancy_anom["description"]
        assert "2" in discrepancy_anom["description"]


def test_validation_report_artifacts_serialization():
    """Verify validation_report.json on disk includes artifacts, sources_processed, and snapshot_id."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "audit.md"), "w") as f:
            f.write("""# AUDIT
## SEC-001: Sample Finding
Category: SECURITY
Type: RISK
Severity: P2
""")

        out_dir = os.path.join(tmp_dir, "normalized")
        schema_path = get_default_schema_path()

        normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        val_path = os.path.join(out_dir, "validation_report.json")
        with open(val_path, "r") as f:
            val_data = json.load(f)

        assert "artifacts" in val_data
        assert "report_data" in val_data["artifacts"]
        assert "validation_report" in val_data["artifacts"]
        assert "source_manifest" in val_data["artifacts"]
        assert "report_data_schema" in val_data["artifacts"]
        assert val_data["sources_processed"] == 1
        assert val_data["snapshot_id"].startswith("sha256:")


def test_portability_isolated_run():
    """Verify audit-normalize runs completely in an isolated directory without hardcoded workspace paths."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create input markdown in isolated directory
        docs_dir = os.path.join(tmp_dir, "audit_docs")
        os.makedirs(docs_dir)
        with open(os.path.join(docs_dir, "01_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## SEC-001: Critical API Leak
Category: SECURITY
Type: VULNERABILITY
Severity: P0
Location: src/api/leak.py:15
""")

        out_dir = os.path.join(tmp_dir, "output")

        val_result = normalize(
            input_paths=[docs_dir],
            output_dir=out_dir,
            base_dir=tmp_dir,
        )

        assert val_result["overall_status"] == "VALID"
        assert os.path.exists(os.path.join(out_dir, "report_data.json"))
        assert os.path.exists(os.path.join(out_dir, "validation_report.json"))
        assert os.path.exists(os.path.join(out_dir, "source_manifest.json"))
        assert os.path.exists(os.path.join(out_dir, "report_data.schema.json"))


def test_realistic_multi_document_four_sources():
    """Verify normalization across the 4 canonical audit documents: inventory, analytical report, ledger, coverage manifest."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. 01_inventory.md
        with open(os.path.join(tmp_dir, "01_inventory.md"), "w") as f:
            f.write("""# INVENTORY OF ASSETS AND SCOPE
## Identity
- Project Name: smartserv
- Repository: smartserv
- Target Commit: 9876543210abcdef0123456789abcdef01234567
- Branch: main
- Version: 2.1.0

## Components
- Service: backend (Spring Boot 3.2, Java 21)
- Service: frontend (React 18, TypeScript)
- Database: PostgreSQL 16
""")

        # 2. 02_analytical_report.md
        with open(os.path.join(tmp_dir, "02_analytical_report.md"), "w") as f:
            f.write("""# ANALYTICAL AUDIT REPORT
## Executive Summary
Comprehensive security and architecture evaluation of smartserv.

## Findings
### Permissive CORS Configuration
Category: SECURITY
Type: RISK
Severity: P2
Confidence: MEDIUM
Location: backend/src/main/java/config/CorsConfig.java:12-15
Description: Wildcard origin enabled without restricting credentials.
Recommendation: Define whitelist of authorized origins.
""")

        # 3. 03_audit_ledger.md
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Project Name: smartserv
- Target Commit: 9876543210abcdef0123456789abcdef01234567

## Findings
### SEC-001: Wildcard origin on CORS configuration
Category: SECURITY
Subcategory: CORS
Type: RISK
Status: CONFIRMED
Severity: P1
Confidence: HIGH
Location: backend/src/main/java/config/CorsConfig.java:12
Evidence: `registry.addMapping("/**").allowedOrigins("*")`
Description: Application allows arbitrary origin headers.

### SEC-002: Insecure payment callback verification
Category: SECURITY
Subcategory: PAYMENT
Type: VULNERABILITY
Status: CONFIRMED
Severity: P0
Confidence: HIGH
Location: backend/src/main/java/service/PaymentService.java:88
Evidence: Missing webhook HMAC signature check.
Description: Payment webhooks are processed without cryptographic validation.

### CONTROL-001: Password Hashing with Argon2id
Category: SECURITY
Subcategory: AUTHENTICATION
Status: CONFIRMED
Description: User authentication utilizes Argon2id password hashing.
""")

        # 4. 04_coverage_manifest.md
        with open(os.path.join(tmp_dir, "04_coverage_manifest.md"), "w") as f:
            f.write("""# COVERAGE MANIFEST
## Matriz de Aplicabilidade
| Categoria | Subcategoria | Estado |
| SECURITY | AUTHENTICATION | APPLICABLE |
| SECURITY | CORS | APPLICABLE |
| DATABASE | TRANSACTIONS | APPLICABLE |

## Cobertura de Inspeção
| Categoria | Subcategoria | Estado | Resultado | Escopo |
| SECURITY | AUTHENTICATION | INSPECTED | FINDINGS_PRESENT | auth service |
| SECURITY | CORS | INSPECTED | FINDINGS_PRESENT | web mvc config |
| DATABASE | TRANSACTIONS | INSPECTED | NOT_FOUND | payment repository |

## Limitations
- Performance and stress tests under production traffic were out of scope.
- Third-party payment provider staging sandbox was simulated with mocks.

## References
- OWASP Top 10 2021
- CWE-942
- https://github.com/example/smartserv
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

        # Snapshot verification
        assert len(data["audit_snapshot"]["sources"]) == 4
        source_roles = {s["source_role"] for s in data["audit_snapshot"]["sources"]}
        assert source_roles == {"INVENTORY", "ANALYTICAL_REPORT", "AUDIT_LEDGER", "COVERAGE_MANIFEST"}

        # Target project verification
        assert data["target_project"]["repository"]["value"] == "smartserv"
        assert data["target_project"]["commit"]["value"] == "9876543210abcdef0123456789abcdef01234567"
        assert data["target_project"]["version"]["value"] == "2.1.0"

        # Deduplication & Merge verification
        # SEC-001 (ledger) and Permissive CORS (analytical report) merged!
        assert len(data["findings"]) == 2
        sec001 = next(f for f in data["findings"] if f["id"] == "SEC-001")
        assert len(sec001["provenance"]) == 2
        # Precedence: Audit Ledger (P1) beats Analytical Report (P2)
        assert sec001["severity"]["value"] == "P1"
        assert sec001["confidence"]["value"] == "HIGH"
        # Non-destructive merge: recommendation from analytical report was merged into SEC-001!
        assert sec001["recommendation"]["state"] == "PRESENT"
        assert "whitelist" in sec001["recommendation"]["value"].lower()

        # SEC-002 preserved
        sec002 = next(f for f in data["findings"] if f["id"] == "SEC-002")
        assert sec002["severity"]["value"] == "P0"

        # Controls
        assert len(data["controls"]) == 1
        assert data["controls"][0]["id"] == "CONTROL-001"

        # Applicability, Inspections, Limitations
        assert len(data["applicability"]) == 3
        assert len(data["inspections"]) == 3
        assert len(data["limitations"]) == 2

        # Metrics strictly derived from normalized dataset
        assert data["metrics"]["findings_total"] == 2
        assert data["metrics"]["severity"]["P0"] == 1
        assert data["metrics"]["severity"]["P1"] == 1
        assert data["metrics"]["severity"]["P2"] == 0
        assert data["metrics"]["controls_total"] == 1
        assert data["metrics"]["inspections_total"] == 3
