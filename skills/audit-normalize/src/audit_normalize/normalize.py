"""Canonical normalization pipeline for audit-normalize."""

import argparse
from datetime import datetime, timezone
import glob
import hashlib
import json
import os
import shutil
import sys
from typing import Any, Dict, List, Optional

from .merger import merge_and_resolve_controls, merge_and_resolve_findings, resolve_target_project
from .metrics import compute_metrics
from .parser import (
    classify_source_role,
    extract_applicability,
    extract_inspections,
    extract_limitations,
    extract_raw_entities,
    extract_raw_target_projects,
)
from .validator import AuditDataValidator, get_default_schema_path


def compute_sha256(data: bytes) -> str:
    """Compute hex SHA-256 digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def discover_sources(
    input_paths: List[str],
    base_dir: str,
) -> List[Dict[str, Any]]:
    """Discover, filter, freeze, and canonically order input sources."""
    candidate_files: List[str] = []

    for inp in input_paths:
        if os.path.isfile(inp):
            candidate_files.append(os.path.abspath(inp))
        elif os.path.isdir(inp):
            for root, dirs, files in os.walk(inp):
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith(".")
                    and d not in ("node_modules", "target", "build", "dist", "__pycache__", "normalized")
                ]
                for f in files:
                    if f.endswith(".md"):
                        candidate_files.append(os.path.abspath(os.path.join(root, f)))

    prohibited_names = {
        "report_data.json",
        "validation_report.json",
        "source_manifest.json",
        "report_data.schema.json",
    }
    filtered_files = [
        f for f in candidate_files
        if os.path.basename(f) not in prohibited_names
    ]

    filtered_files = sorted(list(set(filtered_files)))

    sources: List[Dict[str, Any]] = []
    for idx, fpath in enumerate(filtered_files):
        with open(fpath, "rb") as f:
            raw_bytes = f.read()

        try:
            raw_text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            raw_text = raw_bytes.decode("latin-1", errors="replace")

        try:
            rel_path = os.path.relpath(fpath, base_dir).replace("\\", "/")
        except ValueError:
            rel_path = os.path.basename(fpath)

        role = classify_source_role(fpath, raw_text)
        sources.append({
            "source_id": f"src-{idx + 1:03d}",
            "file": rel_path,
            "abs_path": fpath,
            "sha256": compute_sha256(raw_bytes),
            "source_role": role,
            "raw_text": raw_text,
        })

    return sources


def build_audit_snapshot(sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Construct canonical snapshot manifest and compute deterministic snapshot_id."""
    manifest_list = [
        {
            "file": s["file"],
            "sha256": s["sha256"],
            "source_id": s["source_id"],
            "source_role": s["source_role"],
        }
        for s in sources
    ]
    canonical_bytes = json.dumps(
        manifest_list,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    snapshot_id = "sha256:" + compute_sha256(canonical_bytes)

    return {
        "snapshot_id": snapshot_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources": manifest_list,
    }


def normalize(
    input_paths: List[str],
    output_dir: str,
    schema_path: Optional[str] = None,
    base_dir: Optional[str] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """Execute the end-to-end normalization pipeline."""
    if base_dir:
        calc_base_dir = os.path.abspath(base_dir)
    else:
        resolved_inps = [os.path.abspath(p) for p in input_paths]
        if len(resolved_inps) == 1 and os.path.isdir(resolved_inps[0]):
            calc_base_dir = resolved_inps[0]
        else:
            try:
                common = os.path.commonpath(resolved_inps)
                if os.path.isfile(common):
                    calc_base_dir = os.path.dirname(common)
                else:
                    calc_base_dir = common
            except ValueError:
                calc_base_dir = os.path.dirname(resolved_inps[0])

    resolved_schema = schema_path or get_default_schema_path()

    # Step 1-3: Discover and freeze sources
    sources = discover_sources(input_paths, calc_base_dir)
    if not sources:
        print("[audit-normalize] No valid Markdown audit sources found.", file=sys.stderr)
        print("[audit-normalize] Prohibited from performing source code auditing or synthesizing audit results.", file=sys.stderr)
        return {
            "overall_status": "INVALID",
            "errors": ["No candidate Markdown audit sources found. audit-normalize does not audit projects."],
            "warnings": [],
            "sources_processed": 0,
        }

    sources_dict = {s["source_id"]: s for s in sources}

    # Step 4-8: Snapshot and hashing
    snapshot = build_audit_snapshot(sources)

    # Step 9: Extract target project
    raw_target_projects, project_anomalies = extract_raw_target_projects(sources)

    # Step 10-12: Extract entities
    applicability, app_anomalies = extract_applicability(sources)
    inspections, insp_anomalies = extract_inspections(sources)
    limitations = extract_limitations(sources)

    raw_findings, raw_controls, references, parse_anomalies = extract_raw_entities(sources)

    all_anomalies: List[Dict[str, Any]] = []
    all_anomalies.extend(project_anomalies)
    all_anomalies.extend(app_anomalies)
    all_anomalies.extend(insp_anomalies)
    all_anomalies.extend(parse_anomalies)

    # Step 13-17: Deduplication, merge, precedence, conflicts
    conflict_counter = 0
    target_project, tp_conflicts, conflict_counter = resolve_target_project(
        raw_target_projects, sources_dict, conflict_counter
    )

    findings, f_conflicts, merge_anomalies, conflict_counter = merge_and_resolve_findings(
        raw_findings, sources_dict, conflict_counter
    )
    all_anomalies.extend(merge_anomalies)

    all_conflicts = []
    all_conflicts.extend(tp_conflicts)
    all_conflicts.extend(f_conflicts)
    all_conflicts.sort(key=lambda c: c["id"])

    controls, control_anomalies = merge_and_resolve_controls(raw_controls, sources_dict)
    all_anomalies.extend(control_anomalies)

    # Step 18: Re-index anomalies
    for i, a in enumerate(all_anomalies):
        a["id"] = f"ANOM-{i + 1:03d}"

    # Step 19: Compute metrics
    metrics = compute_metrics(findings, controls, inspections)

    # Step 20: Assemble report_data.json
    report_data = {
        "metadata": {
            "schema_version": "1.0",
            "generator": "audit-normalize",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "target_project": target_project,
        "audit_snapshot": snapshot,
        "applicability": applicability,
        "inspections": inspections,
        "findings": findings,
        "controls": controls,
        "conflicts": all_conflicts,
        "anomalies": all_anomalies,
        "limitations": limitations,
        "references": references,
        "metrics": metrics,
    }

    # Step 21-24: Multi-axis validation
    if not os.path.exists(resolved_schema):
        raise FileNotFoundError(f"Canonical schema not found at: {resolved_schema}")

    with open(resolved_schema, "r", encoding="utf-8") as sf:
        schema_data = json.load(sf)

    validator = AuditDataValidator(schema_data)
    val_report = validator.validate_all(report_data, base_dir=calc_base_dir)
    val_report["sources_processed"] = len(sources)
    val_report["snapshot_id"] = snapshot["snapshot_id"]
    val_report["schema_version"] = report_data.get("schema_version", "1.0")
    val_report["counts"] = {
        "findings": len(report_data.get("findings", [])),
        "controls": len(report_data.get("controls", [])),
        "anomalies": len(report_data.get("anomalies", [])),
        "conflicts": len(report_data.get("conflicts", [])),
    }

    # Step 25-26: Serialize output artifacts
    os.makedirs(output_dir, exist_ok=True)

    report_data_file = os.path.join(output_dir, "report_data.json")
    val_report_file = os.path.join(output_dir, "validation_report.json")
    manifest_file = os.path.join(output_dir, "source_manifest.json")
    schema_dest_file = os.path.join(output_dir, "report_data.schema.json")

    val_report["artifacts"] = {
        "report_data": report_data_file,
        "validation_report": val_report_file,
        "source_manifest": manifest_file,
        "report_data_schema": schema_dest_file,
    }

    # Write artifacts and explicitly close
    with open(report_data_file, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    with open(val_report_file, "w", encoding="utf-8") as f:
        json.dump(val_report, f, indent=2, ensure_ascii=False)

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    shutil.copyfile(resolved_schema, schema_dest_file)

    # Section 15, 16, 17 & 31 requirement: reopen from filesystem and verify all semantic fields against in-memory state
    verify_persisted_validation_report(val_report, val_report_file)

    with open(report_data_file, "r", encoding="utf-8") as f:
        persisted_report_data = json.load(f)
    if persisted_report_data.get("audit_snapshot", {}).get("snapshot_id") != snapshot["snapshot_id"]:
        raise RuntimeError("Integrity violation: persisted report_data diverges from in-memory snapshot")
    if len(persisted_report_data.get("findings", [])) != len(report_data.get("findings", [])):
        raise RuntimeError("Integrity violation: persisted report_data findings count diverges from in-memory state")

    return val_report


def verify_persisted_validation_report(val_report: Dict[str, Any], val_report_file: str) -> None:
    """Reopen persisted validation_report.json and strictly verify every semantic field against in-memory state."""
    with open(val_report_file, "r", encoding="utf-8") as f:
        persisted_val_report = json.load(f)

    for check_field in (
        "overall_status",
        "errors",
        "warnings",
        "validations",
        "metrics_summary",
        "snapshot_id",
        "schema_version",
        "sources_processed",
        "counts",
        "artifacts",
    ):
        if persisted_val_report.get(check_field) != val_report.get(check_field):
            raise RuntimeError(
                f"Integrity violation: persisted validation report diverges from in-memory state on field '{check_field}'"
            )


def main():
    parser = argparse.ArgumentParser(
        description="audit-normalize: Transform Markdown audit results into canonical, structured, validated JSON dataset."
    )
    parser.add_argument(
        "-i", "--input",
        nargs="+",
        default=["docs/audit"],
        help="Input markdown file(s) or directory containing audit documents.",
    )
    parser.add_argument(
        "-o", "--output",
        default="docs/audit/normalized",
        help="Directory where canonical JSON artifacts will be written.",
    )
    parser.add_argument(
        "-s", "--schema",
        default=None,
        help="Path to report_data.schema.json.",
    )
    parser.add_argument(
        "--base-dir",
        default=None,
        help="Base directory for calculating relative paths.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail if any warning is detected.",
    )

    args = parser.parse_args()

    val_report = normalize(
        input_paths=args.input,
        output_dir=args.output,
        schema_path=args.schema,
        base_dir=args.base_dir,
        strict=args.strict,
    )

    # Concise report output per v8_current.md L1533-1558 / NCS-0057
    print("==================================================")
    print(f"Status: {val_report['overall_status']}")
    print(f"Fontes processadas: {val_report.get('sources_processed', 0)}")
    print(f"Snapshot ID: {val_report.get('snapshot_id', 'N/A')}")
    metrics = val_report.get("metrics_summary", {})
    print(f"Findings total: {metrics.get('findings_total', 0)}")
    print(f"Distribuição de severidade: {metrics.get('severity', {})}")
    print(f"Controls total: {metrics.get('controls_total', 0)}")
    print(f"Inspections total: {metrics.get('inspections_total', 0)}")
    print(f"Warnings: {len(val_report.get('warnings', []))}")
    print(f"Errors: {len(val_report.get('errors', []))}")
    artifacts = val_report.get("artifacts", {})
    if artifacts:
        print("Localização dos artefatos:")
        for k, p in artifacts.items():
            print(f"  - {k}: {p}")
    print("==================================================")

    if val_report["overall_status"] == "INVALID":
        for err in val_report.get("errors", []):
            print(f"ERROR: {err}", file=sys.stderr)
        sys.exit(1)
    elif args.strict and val_report["overall_status"] == "VALID_WITH_WARNINGS":
        for w in val_report.get("warnings", []):
            print(f"WARNING: {w}", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
