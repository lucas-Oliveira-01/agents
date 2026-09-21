"""Contractual closure test suite for audit-normalize.

Covers:
1. Absence is not value (Section 5 & 6)
2. Unmapped taxonomy preservation & UNMAPPED_TAXONOMY anomaly (Section 7 & 8)
3. False positive rejection across References, Roadmap, Related Issues, Prioritization, Conclusion (Section 9 & 10)
4. Provenance preservation across deduplication for applicability, inspections, limitations, references (Section 11 & 12)
5. Identity collision on incompatible type, location, and structure (Section 13 & 14)
6. Persisted validation_report.json disk re-read and semantic integrity check (Section 15 & 16)
7. JSON Schema format checking with Draft202012Validator (Section 17)
8. Semantic determinism across multiple runs (Section 18 & 19)
9. CWD-independent determinism (Section 20)
"""

import json
import os
import shutil
import tempfile
import pytest

from audit_normalize.normalize import normalize, verify_persisted_validation_report
from audit_normalize.validator import AuditDataValidator, get_default_schema_path


def test_absence_is_not_value():
    """Verify that absent fields become NOT_PROVIDED_BY_SOURCE and never invented defaults."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Document with Project Name but NO repository, and findings/controls missing fields
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Project Name: smartserv
- Target Commit: 1234567890abcdef1234567890abcdef12345678
- Branch: main

## Findings
### FIND-001: Minimal finding without status or severity
Location: src/main.py:10
Description: Minimal issue description without explicit severity or status.

### CONTROL-001: Minimal control without status
Description: Control with no explicit status provided.
""")

        out_dir = os.path.join(tmp_dir, "out")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        assert result["overall_status"] == "INVALID"
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        # 1. Target project repository: Project Name alone NEVER becomes repository
        repo = data["target_project"]["repository"]
        assert repo["state"] == "NOT_PROVIDED_BY_SOURCE"
        assert repo["value"] is None

        # 2. Finding: missing severity, status, and type must be NOT_PROVIDED_BY_SOURCE
        f1 = next(f for f in data["findings"] if f["id"] == "FIND-001")
        assert f1["severity"]["state"] == "NOT_PROVIDED_BY_SOURCE"
        assert f1["severity"]["value"] is None

        assert f1["status"]["state"] == "NOT_PROVIDED_BY_SOURCE"
        assert f1["status"]["value"] is None

        assert f1["type"]["state"] == "NOT_PROVIDED_BY_SOURCE"
        assert f1["type"]["value"] is None

        # Category absent: must NOT be invented as SECURITY or inferred from ID prefix
        assert f1.get("category") is None

        # 3. Control: missing status must NOT default silently to CONFIRMED; must be NOT_DETERMINABLE
        c1 = next(c for c in data["controls"] if c["id"] == "CONTROL-001")
        assert c1["status"] == "NOT_DETERMINABLE"
        # Control category absent: must NOT be invented as SECURITY
        assert c1.get("category") is None

        # Anomalies for missing category
        cat_anoms = [a for a in data["anomalies"] if a["type"] == "SOURCE_FORMAT_ANOMALY" and "Category" in a["description"]]
        assert len(cat_anoms) >= 2


def test_unmapped_taxonomy():
    """Verify that unknown taxonomy values are preserved in reason/field and flagged with UNMAPPED_TAXONOMY."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Repository: my-repo
- Target Commit: 1234567890abcdef1234567890abcdef12345678

## Findings
### SEC-001: Finding with bizarre unmapped taxonomy values
Category: COSMOLOGY
Type: COSMIC_GLITCH
Status: UNDER_INVESTIGATION
Severity: EXTREME
Confidence: UNCERTAIN
Location: src/core.py:42
Description: Finding with non-canonical taxonomy values.

### CONTROL-001: Control with unmapped status and category
Category: ASTROPHYSICS
Status: HALF_ACTIVE
Description: Control with non-canonical status.
""")

        out_dir = os.path.join(tmp_dir, "out")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        f1 = next(f for f in data["findings"] if f["id"] == "SEC-001")

        # Category COSMOLOGY is NOT in schema enum, so canonical field is None and raw value is preserved in UNMAPPED_TAXONOMY
        assert f1["category"] is None

        # Severity EXTREME
        assert f1["severity"]["state"] == "NOT_DETERMINABLE"
        assert f1["severity"]["value"] is None
        assert "EXTREME" in f1["severity"]["reason"]

        # Type COSMIC_GLITCH
        assert f1["type"]["state"] == "NOT_DETERMINABLE"
        assert f1["type"]["value"] is None
        assert "COSMIC_GLITCH" in f1["type"]["reason"]

        # Status UNDER_INVESTIGATION
        assert f1["status"]["state"] == "NOT_DETERMINABLE"
        assert f1["status"]["value"] is None
        assert "UNDER_INVESTIGATION" in f1["status"]["reason"]

        # Confidence UNCERTAIN
        assert f1["confidence"]["state"] == "NOT_DETERMINABLE"
        assert f1["confidence"]["value"] is None
        assert "UNCERTAIN" in f1["confidence"]["reason"]

        # Control category and status: unmapped category is None, unmapped status is NOT_DETERMINABLE
        c1 = next(c for c in data["controls"] if c["id"] == "CONTROL-001")
        assert c1["category"] is None
        assert c1["status"] == "NOT_DETERMINABLE"

        # UNMAPPED_TAXONOMY anomalies must be recorded
        unmapped_anoms = [a for a in data["anomalies"] if a["type"] == "UNMAPPED_TAXONOMY"]
        assert len(unmapped_anoms) >= 6
        descriptions = " ".join(a["description"] for a in unmapped_anoms)
        assert "COSMOLOGY" in descriptions
        assert "ASTROPHYSICS" in descriptions
        assert "EXTREME" in descriptions
        assert "COSMIC_GLITCH" in descriptions
        assert "UNDER_INVESTIGATION" in descriptions
        assert "UNCERTAIN" in descriptions
        assert "HALF_ACTIVE" in descriptions

        # Schema validation is INVALID because category cannot be represented as valid enum without inventing
        assert result["overall_status"] == "INVALID"
        assert result["validations"]["schema_validation"]["status"] == "FAIL"


def test_unmapped_taxonomy_with_canonical_category_maintains_schema_validity():
    """Verify that unmapped taxonomy in scalar fields preserves raw value and keeps dataset valid under schema."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Repository: my-repo
- Target Commit: 1234567890abcdef1234567890abcdef12345678

## Findings
### FIND-010: Finding with valid category but unmapped scalar taxonomies
Category: SECURITY
Type: STRANGE_BUG
Status: IN_REVIEW
Severity: SUPER_CRITICAL
Confidence: ABSOLUTE
Location: src/login.py:10
Description: Issue with unmapped scalar taxonomy values.
""")

        out_dir = os.path.join(tmp_dir, "out")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        f = next(item for item in data["findings"] if item["id"] == "FIND-010")
        assert f["category"] == "SECURITY"
        assert f["severity"]["state"] == "NOT_DETERMINABLE"
        assert "SUPER_CRITICAL" in f["severity"]["reason"]
        assert f["type"]["state"] == "NOT_DETERMINABLE"
        assert "STRANGE_BUG" in f["type"]["reason"]
        assert f["status"]["state"] == "NOT_DETERMINABLE"
        assert "IN_REVIEW" in f["status"]["reason"]
        assert f["confidence"]["state"] == "NOT_DETERMINABLE"
        assert "ABSOLUTE" in f["confidence"]["reason"]

        # Schema validation PASSES because state=NOT_DETERMINABLE with reason is canonical!
        assert result["validations"]["schema_validation"]["status"] == "PASS"


def test_adversarial_extraction_false_positive_rejection():
    """Verify that lists or text mentioning IDs in non-finding sections are NOT extracted as findings."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "analytical.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## References
- SEC-001 — external reference

## Roadmap
- SEC-002 — future improvement

## Related Issues
- SEC-003 — issue reference

## Prioritization
1. ARCH-001 — improve architecture

## Conclusion
SEC-004 remains a future consideration.

## Appendix
- TEST-001 — appendix test reference

## Bibliography
- BOOK-001 — reference manual

## Findings
- SEC-005 — real finding
""")

        out_dir = os.path.join(tmp_dir, "out")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        finding_ids = [f["id"] for f in data["findings"]]
        # ONLY SEC-005 should be extracted!
        assert finding_ids == ["SEC-005"]
        assert "SEC-001" not in finding_ids
        assert "SEC-002" not in finding_ids
        assert "SEC-003" not in finding_ids
        assert "ARCH-001" not in finding_ids
        assert "SEC-004" not in finding_ids
        assert "TEST-001" not in finding_ids
        assert "BOOK-001" not in finding_ids


def test_provenance_preservation_across_deduplication():
    """Verify that deduplicating applicability, inspections, limitations, and references preserves both source provenances."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Source A
        with open(os.path.join(tmp_dir, "source_a.md"), "w") as f:
            f.write("""# COVERAGE MANIFEST A
## Matriz de Aplicabilidade
| Categoria | Subcategoria | Estado |
| SECURITY | AUTH | APPLICABLE |

## Cobertura de Inspeção
| Categoria | Subcategoria | Estado | Resultado |
| SECURITY | AUTH | INSPECTED | FINDINGS_PRESENT |

## Limitations
- Staging environment was unavailable.

## References
- CWE-798
- https://github.com/example/repo
""")

        # Source B (same entities declared from another file)
        with open(os.path.join(tmp_dir, "source_b.md"), "w") as f:
            f.write("""# COVERAGE MANIFEST B
## Matriz de Aplicabilidade
| Categoria | Subcategoria | Estado |
| SECURITY | AUTH | APPLICABLE |

## Cobertura de Inspeção
| Categoria | Subcategoria | Estado | Resultado |
| SECURITY | AUTH | INSPECTED | FINDINGS_PRESENT |

## Limitations
- Staging environment was unavailable.

## References
- CWE-798
- https://github.com/example/repo
""")

        out_dir = os.path.join(tmp_dir, "out")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        # 1. Applicability: single canonical entity with 2 provenances
        assert len(data["applicability"]) == 1
        app = data["applicability"][0]
        assert len(app["provenance"]) == 2
        source_ids = {p["source_id"] for p in app["provenance"]}
        assert len(source_ids) == 2

        # 2. Inspections: single canonical entity with 2 provenances
        assert len(data["inspections"]) == 1
        insp = data["inspections"][0]
        assert len(insp["provenance"]) == 2
        assert len({p["source_id"] for p in insp["provenance"]}) == 2

        # 3. Limitations: single canonical entity with 2 provenances
        assert len(data["limitations"]) == 1
        lim = data["limitations"][0]
        assert len(lim["provenance"]) == 2
        assert len({p["source_id"] for p in lim["provenance"]}) == 2

        # 4. References: 2 references, each with 2 provenances
        assert len(data["references"]) == 2
        for ref in data["references"]:
            assert len(ref["provenance"]) == 2
            assert len({p["source_id"] for p in ref["provenance"]}) == 2


def test_identity_collision_detection():
    """Verify that same ID with incompatible type or location triggers ID_COLLISION and does NOT merge."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # File 1: SEC-009 as VULNERABILITY in src/a.py:10
        with open(os.path.join(tmp_dir, "file1.md"), "w") as f:
            f.write("""# AUDIT LEDGER A
## Findings
### SEC-009: Injection in Alpha
Category: SECURITY
Type: VULNERABILITY
Severity: P1
Location: src/a.py:10
Description: SQL injection vulnerability.
""")

        # File 2: SEC-009 as TECH_DEBT in src/b.py:900
        with open(os.path.join(tmp_dir, "file2.md"), "w") as f:
            f.write("""# AUDIT LEDGER B
## Findings
### SEC-009: Outdated Beta
Category: SECURITY
Type: TECH_DEBT
Severity: P3
Location: src/b.py:900
Description: Legacy dependency tech debt.
""")

        out_dir = os.path.join(tmp_dir, "out")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        # ID_COLLISION must be detected
        collisions = [a for a in data["anomalies"] if a["type"] == "ID_COLLISION"]
        assert len(collisions) == 1
        assert collisions[0]["severity"] == "ERROR"

        # Entities must NOT be merged; 2 separate findings with disambiguated IDs
        assert len(data["findings"]) == 2
        f_ids = {f["id"] for f in data["findings"]}
        assert "SEC-009-001" in f_ids
        assert "SEC-009-002" in f_ids

        # Schema validation remains valid
        assert result["validations"]["schema_validation"]["status"] == "PASS"


def test_persisted_validation_report_integrity():
    """Verify that persisted validation_report.json is completely verified and alterations are caught."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "audit.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Findings
### SEC-001: Issue
Location: src/foo.py:1
Description: Test finding.
""")

        out_dir = os.path.join(tmp_dir, "out")
        schema_path = get_default_schema_path()

        val_report = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        val_file = os.path.join(out_dir, "validation_report.json")
        assert os.path.isfile(val_file)

        # Reopen and compare all fields physically
        with open(val_file, "r", encoding="utf-8") as f:
            persisted = json.load(f)

        for field in ("overall_status", "errors", "warnings", "validations", "metrics_summary", "snapshot_id", "sources_processed"):
            assert persisted[field] == val_report[field]


def test_json_schema_format_checking():
    """Verify that FormatChecker catches invalid RFC 3339 date-time formats."""
    schema_path = get_default_schema_path()
    with open(schema_path) as f:
        schema = json.load(f)

    validator = AuditDataValidator(schema)

    valid_report = {
        "metadata": {
            "schema_version": "1.0",
            "generator": "audit-normalize",
            "generated_at": "2026-09-18T12:00:00Z",
        },
        "target_project": {
            "repository": {"state": "NOT_PROVIDED_BY_SOURCE", "value": None, "provenance": [{"source_id": "src-001", "file": "f.md"}]},
            "commit": {"state": "NOT_PROVIDED_BY_SOURCE", "value": None, "provenance": [{"source_id": "src-001", "file": "f.md"}]},
            "branch": {"state": "NOT_PROVIDED_BY_SOURCE", "value": None, "provenance": [{"source_id": "src-001", "file": "f.md"}]},
            "version": {"state": "NOT_PROVIDED_BY_SOURCE", "value": None, "provenance": [{"source_id": "src-001", "file": "f.md"}]},
            "build_version": {"state": "NOT_PROVIDED_BY_SOURCE", "value": None, "provenance": [{"source_id": "src-001", "file": "f.md"}]},
        },
        "audit_snapshot": {
            "snapshot_id": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
            "created_at": "2026-09-18T12:00:00Z",
            "sources": [{"source_id": "src-001", "file": "f.md", "sha256": "0000000000000000000000000000000000000000000000000000000000000000", "source_role": "UNKNOWN"}],
        },
        "applicability": [],
        "inspections": [],
        "findings": [],
        "controls": [],
        "conflicts": [],
        "anomalies": [],
        "limitations": [],
        "references": [],
        "metrics": {
            "findings_total": 0,
            "severity": {"P0": 0, "P1": 0, "P2": 0, "P3": 0, "INFO": 0},
            "controls_total": 0,
            "inspections_total": 0,
        },
    }

    ok, errs = validator.validate_schema(valid_report)
    assert ok, f"Expected valid report to pass: {errs}"

    # 1. Valid RFC 3339 with timezone offset (+02:00)
    rep_offset = dict(valid_report)
    rep_offset["metadata"] = dict(valid_report["metadata"])
    rep_offset["metadata"]["generated_at"] = "2026-09-18T15:30:00+02:00"
    ok_off, errs_off = validator.validate_schema(rep_offset)
    assert ok_off, f"Expected timezone offset to pass: {errs_off}"

    # 2. Invalid: string not a datetime
    rep_inv = dict(valid_report)
    rep_inv["metadata"] = dict(valid_report["metadata"])
    rep_inv["metadata"]["generated_at"] = "NOT-A-DATETIME"
    ok_inv, errs_inv = validator.validate_schema(rep_inv)
    assert not ok_inv, "Expected invalid date-time format to be rejected by FormatChecker"
    assert any("date-time" in e for e in errs_inv)

    # 3. Invalid: missing timezone offset (naive datetime rejected by strict RFC 3339)
    rep_notz = dict(valid_report)
    rep_notz["metadata"] = dict(valid_report["metadata"])
    rep_notz["metadata"]["generated_at"] = "2026-09-18T12:00:00"
    ok_notz, errs_notz = validator.validate_schema(rep_notz)
    assert not ok_notz, "Expected datetime without timezone to be rejected by RFC 3339 checker"
    assert any("date-time" in e for e in errs_notz)

    # 4. Invalid: space instead of 'T' separator
    rep_sp = dict(valid_report)
    rep_sp["metadata"] = dict(valid_report["metadata"])
    rep_sp["metadata"]["generated_at"] = "2026-09-18 12:00:00Z"
    ok_sp, errs_sp = validator.validate_schema(rep_sp)
    assert not ok_sp, "Expected space separator to be rejected by RFC 3339 checker"
    assert any("date-time" in e for e in errs_sp)

    # 5. Invalid: calendar error (February 31)
    rep_cal = dict(valid_report)
    rep_cal["metadata"] = dict(valid_report["metadata"])
    rep_cal["metadata"]["generated_at"] = "2026-02-31T12:00:00Z"
    ok_cal, errs_cal = validator.validate_schema(rep_cal)
    assert not ok_cal, "Expected non-existent date to be rejected"
    assert any("date-time" in e for e in errs_cal)


def test_controls_absence_and_unmapped_taxonomy_explicit():
    """Verify that absent control category/status and unmapped control category/status never invent values."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Repository: acme-repo
- Target Commit: abcdef1234567890abcdef1234567890abcdef12

## Controls
### CONTROL-001: Control missing category
Status: CONFIRMED
Description: Control without category.

### CONTROL-002: Control missing status
Category: SECURITY
Description: Control without status.

### CONTROL-003: Control with unmapped category
Category: QUANTUM_FIREWALL
Status: CONFIRMED
Description: Control with unmapped category.

### CONTROL-004: Control with unmapped status
Category: SECURITY
Status: SOMEWHAT_IMPLEMENTED
Description: Control with unmapped status.
""")

        out_dir = os.path.join(tmp_dir, "out")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        ctrls = {c["id"]: c for c in data["controls"]}

        # CONTROL-001: category absent -> None (never SECURITY), status CONFIRMED
        assert ctrls["CONTROL-001"]["category"] is None
        assert ctrls["CONTROL-001"]["status"] == "CONFIRMED"

        # CONTROL-002: category SECURITY, status absent -> NOT_DETERMINABLE (never CONFIRMED)
        assert ctrls["CONTROL-002"]["category"] == "SECURITY"
        assert ctrls["CONTROL-002"]["status"] == "NOT_DETERMINABLE"

        # CONTROL-003: unmapped category QUANTUM_FIREWALL -> None (never invented enum)
        assert ctrls["CONTROL-003"]["category"] is None
        assert ctrls["CONTROL-003"]["status"] == "CONFIRMED"

        # CONTROL-004: category SECURITY, unmapped status SOMEWHAT_IMPLEMENTED -> NOT_DETERMINABLE
        assert ctrls["CONTROL-004"]["category"] == "SECURITY"
        assert ctrls["CONTROL-004"]["status"] == "NOT_DETERMINABLE"

        # Check anomalies recorded for absence and unmapped
        anoms = data["anomalies"]
        assert any(a["type"] == "SOURCE_FORMAT_ANOMALY" and "CONTROL-001" in a["description"] for a in anoms)
        assert any(a["type"] == "SOURCE_FORMAT_ANOMALY" and "CONTROL-002" in a["description"] for a in anoms)
        assert any(a["type"] == "UNMAPPED_TAXONOMY" and "QUANTUM_FIREWALL" in a["description"] for a in anoms)
        assert any(a["type"] == "UNMAPPED_TAXONOMY" and "SOMEWHAT_IMPLEMENTED" in a["description"] for a in anoms)


def test_project_name_present_without_repository_explicit():
    """Verify that Project Name is NEVER inferred or assigned to target_project.repository."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Project Name: smartserv
- Target Commit: abcdef1234567890abcdef1234567890abcdef12
- Branch: main

## Findings
### SEC-001: Buffer overflow
Category: SECURITY
Type: VULNERABILITY
Severity: P0
Status: CONFIRMED
Location: src/net.c:100
Description: Remote code execution via buffer overflow.
""")

        out_dir = os.path.join(tmp_dir, "out")
        schema_path = get_default_schema_path()

        result = normalize(
            input_paths=[tmp_dir],
            output_dir=out_dir,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )

        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        repo = data["target_project"]["repository"]
        assert repo["state"] == "NOT_PROVIDED_BY_SOURCE"
        assert repo["value"] is None
        assert repo["value"] != "smartserv"


def test_semantic_determinism_across_runs():
    """Verify that two independent runs produce semantically identical datasets."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "03_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Repository: acme/portal
- Target Commit: abcdef1234567890abcdef1234567890abcdef12
- Branch: main

## Findings
### SEC-001: Hardcoded API Secret
Category: SECURITY
Type: VULNERABILITY
Severity: P0
Status: CONFIRMED
Location: src/auth.py:22
Description: API secret is stored in cleartext.
""")

        out_a = os.path.join(tmp_dir, "out_a")
        out_b = os.path.join(tmp_dir, "out_b")
        schema_path = get_default_schema_path()

        normalize(input_paths=[tmp_dir], output_dir=out_a, schema_path=schema_path, base_dir=tmp_dir)
        normalize(input_paths=[tmp_dir], output_dir=out_b, schema_path=schema_path, base_dir=tmp_dir)

        with open(os.path.join(out_a, "report_data.json")) as fa, open(os.path.join(out_b, "report_data.json")) as fb:
            data_a = json.load(fa)
            data_b = json.load(fb)

        # Semantic dataset must be 100% identical
        for collection in ("findings", "controls", "applicability", "inspections", "conflicts", "anomalies", "limitations", "references", "metrics", "target_project"):
            assert data_a[collection] == data_b[collection]

        # Snapshot ID must be byte-deterministic
        assert data_a["audit_snapshot"]["snapshot_id"] == data_b["audit_snapshot"]["snapshot_id"]
        assert data_a["audit_snapshot"]["sources"] == data_b["audit_snapshot"]["sources"]


def test_cwd_independent_determinism():
    """Verify that executing normalization from different working directories produces identical snapshot and datasets."""
    with tempfile.TemporaryDirectory() as base_tmp:
        inputs_dir = os.path.join(base_tmp, "inputs")
        os.makedirs(inputs_dir)
        with open(os.path.join(inputs_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Repository: my-project
- Target Commit: aabbccddeeff00112233445566778899aabbccdd

## Findings
### SEC-001: SQL Injection
Category: SECURITY
Type: VULNERABILITY
Severity: P1
Location: src/db.py:50
Description: Unsanitized SQL query.
""")

        work_dir_a = os.path.join(base_tmp, "run_a")
        work_dir_b = os.path.join(base_tmp, "run_b")
        os.makedirs(work_dir_a)
        os.makedirs(work_dir_b)

        out_a = os.path.join(work_dir_a, "normalized")
        out_b = os.path.join(work_dir_b, "normalized")
        schema_path = get_default_schema_path()

        orig_cwd = os.getcwd()
        try:
            # Execution from run_a CWD
            os.chdir(work_dir_a)
            normalize(input_paths=[inputs_dir], output_dir=out_a, schema_path=schema_path)

            # Execution from run_b CWD
            os.chdir(work_dir_b)
            normalize(input_paths=[inputs_dir], output_dir=out_b, schema_path=schema_path)
        finally:
            os.chdir(orig_cwd)

        with open(os.path.join(out_a, "report_data.json")) as fa, open(os.path.join(out_b, "report_data.json")) as fb:
            data_a = json.load(fa)
            data_b = json.load(fb)

        with open(os.path.join(out_a, "source_manifest.json")) as ma, open(os.path.join(out_b, "source_manifest.json")) as mb:
            man_a = json.load(ma)
            man_b = json.load(mb)

        # Semantic collections must be 100% identical
        for field in ("target_project", "applicability", "inspections", "findings", "controls", "anomalies", "conflicts", "metrics", "limitations", "references"):
            assert data_a[field] == data_b[field], f"Mismatch in field '{field}' across CWD execution"

        # Snapshot ID and sources must be byte-deterministic across CWD
        assert data_a["audit_snapshot"]["snapshot_id"] == data_b["audit_snapshot"]["snapshot_id"]
        assert data_a["audit_snapshot"]["sources"] == data_b["audit_snapshot"]["sources"]
        assert man_a["snapshot_id"] == man_b["snapshot_id"]
        assert man_a["sources"] == man_b["sources"]


def test_identity_collision_category_mismatch():
    """Verify that same ID with incompatible category triggers ID_COLLISION."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "f1.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Findings
### SEC-010: Security Issue
Category: SECURITY
Type: VULNERABILITY
Location: src/app.py:10
Description: Security issue.
""")
        with open(os.path.join(tmp_dir, "f2.md"), "w") as f:
            f.write("""# ARCHITECTURE REPORT
## Findings
### SEC-010: Architecture Issue
Category: ARCHITECTURE
Type: ARCHITECTURAL_DEFECT
Location: src/app.py:10
Description: Architecture issue.
""")
        out_dir = os.path.join(tmp_dir, "out")
        res = normalize(input_paths=[tmp_dir], output_dir=out_dir, schema_path=get_default_schema_path(), base_dir=tmp_dir)
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        collisions = [a for a in data["anomalies"] if a["type"] == "ID_COLLISION"]
        assert len(collisions) == 1
        assert collisions[0]["severity"] == "ERROR"
        assert len(data["findings"]) == 2
        ids = {item["id"] for item in data["findings"]}
        assert "SEC-010-001" in ids
        assert "SEC-010-002" in ids


def test_identity_collision_non_overlapping_lines():
    """Verify that same ID in same file but non-overlapping line ranges triggers ID_COLLISION."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "f1.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Findings
### SEC-020: First Defect
Category: SECURITY
Type: VULNERABILITY
Location: src/app.py:10-15
Description: Defect at start of file.
""")
        with open(os.path.join(tmp_dir, "f2.md"), "w") as f:
            f.write("""# REVIEW
## Findings
### SEC-020: Second Defect
Category: SECURITY
Type: VULNERABILITY
Location: src/app.py:80-95
Description: Defect at end of file.
""")
        out_dir = os.path.join(tmp_dir, "out")
        res = normalize(input_paths=[tmp_dir], output_dir=out_dir, schema_path=get_default_schema_path(), base_dir=tmp_dir)
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        collisions = [a for a in data["anomalies"] if a["type"] == "ID_COLLISION"]
        assert len(collisions) == 1
        assert collisions[0]["severity"] == "ERROR"
        assert len(data["findings"]) == 2
        ids = {item["id"] for item in data["findings"]}
        assert "SEC-020-001" in ids
        assert "SEC-020-002" in ids


def test_provenance_deduplication_idempotency_run_twice():
    """Verify that running deduplication does not grow provenance count unnaturally."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "source_1.md"), "w") as f:
            f.write("""# COVERAGE MANIFEST 1
## Matriz de Aplicabilidade
| Categoria | Subcategoria | Estado |
| SECURITY | AUTH | APPLICABLE |
""")
        with open(os.path.join(tmp_dir, "source_2.md"), "w") as f:
            f.write("""# COVERAGE MANIFEST 2
## Matriz de Aplicabilidade
| Categoria | Subcategoria | Estado |
| SECURITY | AUTH | APPLICABLE |
""")
        out_1 = os.path.join(tmp_dir, "out_1")
        normalize(input_paths=[tmp_dir], output_dir=out_1, schema_path=get_default_schema_path(), base_dir=tmp_dir)

        with open(os.path.join(out_1, "report_data.json")) as f:
            data1 = json.load(f)

        assert len(data1["applicability"]) == 1
        assert len(data1["applicability"][0]["provenance"]) == 2

        out_2 = os.path.join(tmp_dir, "out_2")
        normalize(input_paths=[tmp_dir], output_dir=out_2, schema_path=get_default_schema_path(), base_dir=tmp_dir)

        with open(os.path.join(out_2, "report_data.json")) as f:
            data2 = json.load(f)

        assert len(data2["applicability"]) == 1
        # Provenance must NOT grow on second run!
        assert len(data2["applicability"][0]["provenance"]) == 2


def test_source_manifest_and_input_isolation():
    """Verify that input files are completely untouched and modifications trigger new snapshot_id."""
    import hashlib

    with tempfile.TemporaryDirectory() as tmp_dir:
        doc_path = os.path.join(tmp_dir, "ledger.md")
        content = """# AUDIT LEDGER
## Findings
### SEC-001: SQL Injection
Category: SECURITY
Type: VULNERABILITY
Location: src/db.py:10
Description: SQL Injection in login.
"""
        with open(doc_path, "w") as f:
            f.write(content)

        hash_before = hashlib.sha256(content.encode("utf-8")).hexdigest()

        out_dir = os.path.join(tmp_dir, "out")
        res1 = normalize(input_paths=[tmp_dir], output_dir=out_dir, schema_path=get_default_schema_path(), base_dir=tmp_dir)

        # 1. Inputs must NOT be modified by normalize
        with open(doc_path, "r") as f:
            after_content = f.read()
        hash_after = hashlib.sha256(after_content.encode("utf-8")).hexdigest()
        assert hash_before == hash_after

        # 2. Manifest must capture exact SHA-256
        snap1_id = res1["snapshot_id"]
        with open(os.path.join(out_dir, "source_manifest.json")) as f:
            manifest = json.load(f)
        assert manifest["sources"][0]["sha256"] == hash_before

        # 3. Controlled modification changes SHA-256 and snapshot_id
        with open(doc_path, "w") as f:
            f.write(content + "\n<!-- modification -->\n")

        res2 = normalize(input_paths=[tmp_dir], output_dir=os.path.join(tmp_dir, "out2"), schema_path=get_default_schema_path(), base_dir=tmp_dir)
        snap2_id = res2["snapshot_id"]
        assert snap1_id != snap2_id


def test_analytical_report_and_ledger_description_preservation():
    """Verify that analytical report recommendation does not overwrite ledger technical description."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Findings
### SEC-001: Hardcoded Key
Category: SECURITY
Type: VULNERABILITY
Severity: P0
Location: src/key.py:1
Description: Technical evidence of hardcoded RSA private key.
""")
        with open(os.path.join(tmp_dir, "04_analytical_report.md"), "w") as f:
            f.write("""# ANALYTICAL REPORT
## Recommendations
### SEC-001: Hardcoded Key
Recommendation: Store private keys in external secret management service.
""")
        out_dir = os.path.join(tmp_dir, "out")
        res = normalize(input_paths=[tmp_dir], output_dir=out_dir, schema_path=get_default_schema_path(), base_dir=tmp_dir)
        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        assert len(data["findings"]) == 1
        finding = data["findings"][0]

        # Description must preserve ledger technical evidence
        assert finding["description"]["state"] == "PRESENT"
        assert "Technical evidence of hardcoded RSA private key" in finding["description"]["value"]

        # Recommendation must be populated from analytical report
        assert finding["recommendation"]["state"] == "PRESENT"
        assert "Store private keys in external secret management service" in finding["recommendation"]["value"]


def test_applicability_and_inspections_unmapped_taxonomy_cosmology():
    """Verify that unmapped categories in applicability and inspections do not invent enum values and are recorded as UNMAPPED_TAXONOMY."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Repository: acme/portal
- Target Commit: 1234567890abcdef1234567890abcdef12345678

## Applicability Matrix
| Category | Subcategory | State |
| :--- | :--- | :--- |
| COSMOLOGY | ASTRO_DYNAMICS | APPLICABLE |

## Inspection Coverage
| Category | Subcategory | State | Result |
| :--- | :--- | :--- | :--- |
| COSMOLOGY | ASTRO_DYNAMICS | INSPECTED | FINDINGS_PRESENT |
""")
        out_dir = os.path.join(tmp_dir, "out")
        res = normalize(input_paths=[tmp_dir], output_dir=out_dir, schema_path=get_default_schema_path(), base_dir=tmp_dir)

        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        # 1. Applicability category: raw value COSMOLOGY is NOT put into canonical category field
        assert len(data["applicability"]) == 1
        app = data["applicability"][0]
        assert app["category"] is None
        assert app["category"] != "COSMOLOGY"
        assert app["category"] != "SECURITY"
        assert app["state"] == "APPLICABLE"

        # 2. Inspection category: raw value COSMOLOGY is NOT put into canonical category field
        assert len(data["inspections"]) == 1
        insp = data["inspections"][0]
        assert insp["category"] is None
        assert insp["category"] != "COSMOLOGY"
        assert insp["category"] != "SECURITY"
        assert insp["state"] == "INSPECTED"

        # 3. Both unmapped values must be preserved in UNMAPPED_TAXONOMY anomalies
        anoms = [a for a in data["anomalies"] if a["type"] == "UNMAPPED_TAXONOMY"]
        descriptions = " ".join(a["description"] for a in anoms)
        assert "COSMOLOGY" in descriptions

        # 4. Because category is required enum and cannot be represented validly without inventing, schema validator declares INVALID
        assert res["overall_status"] == "INVALID"
        assert res["validations"]["schema_validation"]["status"] == "FAIL"


def test_applicability_and_inspections_canonical_category_maintains_schema_validity():
    """Verify that mapped canonical categories in applicability and inspections pass schema validation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Repository: acme/portal
- Target Commit: 1234567890abcdef1234567890abcdef12345678

## Applicability Matrix
| Category | Subcategory | State |
| :--- | :--- | :--- |
| SECURITY | AUTH | APPLICABLE |

## Inspection Coverage
| Category | Subcategory | State | Result |
| :--- | :--- | :--- | :--- |
| SECURITY | AUTH | INSPECTED | NOT_FOUND |
""")
        out_dir = os.path.join(tmp_dir, "out")
        res = normalize(input_paths=[tmp_dir], output_dir=out_dir, schema_path=get_default_schema_path(), base_dir=tmp_dir)

        with open(os.path.join(out_dir, "report_data.json")) as f:
            data = json.load(f)

        assert len(data["applicability"]) == 1
        assert data["applicability"][0]["category"] == "SECURITY"

        assert len(data["inspections"]) == 1
        assert data["inspections"][0]["category"] == "SECURITY"

        assert res["overall_status"] == "VALID"
        assert res["validations"]["schema_validation"]["status"] == "PASS"


def test_persisted_validation_report_negative_tamper_detection():
    """Verify that any divergence between persisted validation_report.json and in-memory state is detected and rejected."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Identity
- Repository: acme/clean
- Target Commit: 1234567890abcdef1234567890abcdef12345678
""")
        out_dir = os.path.join(tmp_dir, "out")
        val_report = normalize(input_paths=[tmp_dir], output_dir=out_dir, schema_path=get_default_schema_path(), base_dir=tmp_dir)
        val_report_file = os.path.join(out_dir, "validation_report.json")

        # Baseline: untouched file must pass verification
        verify_persisted_validation_report(val_report, val_report_file)

        # 1. Tamper overall_status
        with open(val_report_file, "w") as f:
            tampered = dict(val_report)
            tampered["overall_status"] = "TAMPERED_STATUS"
            json.dump(tampered, f)
        with pytest.raises(RuntimeError, match="overall_status"):
            verify_persisted_validation_report(val_report, val_report_file)

        # 2. Tamper counts
        with open(val_report_file, "w") as f:
            tampered = dict(val_report)
            tampered["counts"] = {"findings": 999, "controls": 0, "anomalies": 0, "conflicts": 0}
            json.dump(tampered, f)
        with pytest.raises(RuntimeError, match="counts"):
            verify_persisted_validation_report(val_report, val_report_file)

        # 3. Tamper snapshot_id
        with open(val_report_file, "w") as f:
            tampered = dict(val_report)
            tampered["snapshot_id"] = "sha256:tampered"
            json.dump(tampered, f)
        with pytest.raises(RuntimeError, match="snapshot_id"):
            verify_persisted_validation_report(val_report, val_report_file)

        # 4. Tamper errors
        with open(val_report_file, "w") as f:
            tampered = dict(val_report)
            tampered["errors"] = ["Injected error"]
            json.dump(tampered, f)
        with pytest.raises(RuntimeError, match="errors"):
            verify_persisted_validation_report(val_report, val_report_file)
