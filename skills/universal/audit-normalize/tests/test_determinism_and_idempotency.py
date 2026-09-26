"""Tests for determinism, idempotency, and ordering invariance in audit-normalize."""

import json
import os
import tempfile
import pytest
from audit_normalize.normalize import normalize
from audit_normalize.validator import get_default_schema_path


def test_logical_determinism_and_idempotency():
    """Verify that normalizing the same input multiple times produces identical logical datasets."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Create input audit documents
        doc1 = os.path.join(tmp_dir, "03_audit_ledger.md")
        with open(doc1, "w") as f:
            f.write("""# AUDIT LEDGER
## SEC-001
Title: Insecure CORS
Category: SECURITY
Type: RISK
Status: CONFIRMED
Severity: P3
Location: CorsConfig.java:12

## ARCH-001
Title: Missing transaction boundaries
Category: ARCHITECTURE
Type: ARCHITECTURAL_DEFECT
Status: CONFIRMED
Severity: P2
Location: PedidoService.java:303-307
""")

        doc2 = os.path.join(tmp_dir, "01_coverage_manifest.md")
        with open(doc2, "w") as f:
            f.write("""# COVERAGE MANIFEST
## APPLICABILITY MATRIX
| Category | Subcategory | State |
| SECURITY | CORS | APPLICABLE |
| ARCHITECTURE | TRANSACTION_MANAGEMENT | APPLICABLE |

## INSPECTION COVERAGE
| Category | Subcategory | State | Result |
| SECURITY | CORS | INSPECTED | FINDINGS_PRESENT |
| ARCHITECTURE | TRANSACTION_MANAGEMENT | INSPECTED | FINDINGS_PRESENT |
""")

        out1 = os.path.join(tmp_dir, "norm1")
        out2 = os.path.join(tmp_dir, "norm2")
        schema_path = get_default_schema_path()

        # Run 1
        res1 = normalize(
            input_paths=[tmp_dir],
            output_dir=out1,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )
        assert res1["schema_validity"] == "VALID"

        # Run 2
        res2 = normalize(
            input_paths=[tmp_dir],
            output_dir=out2,
            schema_path=schema_path,
            base_dir=tmp_dir,
        )
        assert res2["schema_validity"] == "VALID"

        with open(os.path.join(out1, "report_data.json")) as f:
            d1 = json.load(f)
        with open(os.path.join(out2, "report_data.json")) as f:
            d2 = json.load(f)

        # Snapshot ID must be byte-for-byte identical
        assert d1["audit_snapshot"]["snapshot_id"] == d2["audit_snapshot"]["snapshot_id"]

        # Findings, metrics, applicability, inspections must be logically identical
        assert d1["metrics"] == d2["metrics"]
        assert len(d1["findings"]) == len(d2["findings"])
        for f1, f2 in zip(d1["findings"], d2["findings"]):
            assert f1["id"] == f2["id"]
            assert f1["severity"]["value"] == f2["severity"]["value"]
            assert f1["location"] == f2["location"]

        assert d1["applicability"] == d2["applicability"]
        assert d1["inspections"] == d2["inspections"]


def test_source_ordering_invariance():
    """Verify that passing inputs in reverse order produces identical canonical manifest and snapshot_id."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        f_a = os.path.join(tmp_dir, "doc_a.md")
        f_b = os.path.join(tmp_dir, "doc_b.md")

        with open(f_a, "w") as f:
            f.write("# DOC A\n## SEC-001\nCategory: SECURITY\nSeverity: P1\n")
        with open(f_b, "w") as f:
            f.write("# DOC B\n## ARCH-001\nCategory: ARCHITECTURE\nSeverity: P2\n")

        schema_path = get_default_schema_path()
        out1 = os.path.join(tmp_dir, "out1")
        out2 = os.path.join(tmp_dir, "out2")

        # In order [f_a, f_b]
        normalize(input_paths=[f_a, f_b], output_dir=out1, schema_path=schema_path, base_dir=tmp_dir)
        # In reverse order [f_b, f_a]
        normalize(input_paths=[f_b, f_a], output_dir=out2, schema_path=schema_path, base_dir=tmp_dir)

        with open(os.path.join(out1, "report_data.json")) as f:
            d1 = json.load(f)
        with open(os.path.join(out2, "report_data.json")) as f:
            d2 = json.load(f)

        assert d1["audit_snapshot"]["snapshot_id"] == d2["audit_snapshot"]["snapshot_id"]
        assert d1["audit_snapshot"]["sources"] == d2["audit_snapshot"]["sources"]
