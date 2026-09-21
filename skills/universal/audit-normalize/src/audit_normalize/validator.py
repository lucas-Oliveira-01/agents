"""Independent validator for audit-normalize canonical datasets."""

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import jsonschema


def get_default_schema_path() -> str:
    """Resolve path to report_data.schema.json across package and source installations."""
    pkg_ref = os.path.join(os.path.dirname(os.path.abspath(__file__)), "references", "report_data.schema.json")
    if os.path.isfile(pkg_ref):
        return pkg_ref
    skill_ref = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "references", "report_data.schema.json"))
    if os.path.isfile(skill_ref):
        return skill_ref
    cwd_ref = os.path.abspath("references/report_data.schema.json")
    if os.path.isfile(cwd_ref):
        return cwd_ref
    return pkg_ref


class AuditDataValidator:
    """Independent validator verifying report_data.json against schema, semantic, referential, and integrity contracts."""

    def __init__(self, schema_data: Dict[str, Any]):
        self.schema_data = schema_data
        self.validator_cls = jsonschema.Draft202012Validator
        self.validator_cls.check_schema(self.schema_data)

        # Enable format checker including strict RFC 3339 / ISO 8601 date-time format checking
        fc = jsonschema.FormatChecker()

        rfc3339_dt_re = re.compile(
            r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
            r"[tT](?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?"
            r"(?:[zZ]|[+-](?:[01]\d|2[0-3]):[0-5]\d)$"
        )

        @fc.checks("date-time")
        def _validate_datetime(val: Any) -> bool:
            if not isinstance(val, str):
                return True
            if not rfc3339_dt_re.match(val):
                return False
            try:
                from datetime import datetime
                datetime.fromisoformat(val.upper().replace("Z", "+00:00"))
                return True
            except Exception:
                return False

        self.format_checker = fc
        self.jsonschema_validator = self.validator_cls(
            self.schema_data,
            format_checker=self.format_checker,
        )

    def validate_all(
        self,
        report_data: Dict[str, Any],
        base_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute full validation suite: schema, semantics, referential, and integrity."""
        errors: List[str] = []
        warnings: List[str] = []

        # 1. JSON Schema validation
        schema_ok, schema_errs = self.validate_schema(report_data)
        errors.extend(schema_errs)

        # 2. Semantic validation
        sem_ok, sem_errs, sem_warns = self.validate_semantics(report_data)
        errors.extend(sem_errs)
        warnings.extend(sem_warns)

        # 3. Referential validation
        ref_ok, ref_errs = self.validate_referential(report_data)
        errors.extend(ref_errs)

        # 4. Integrity validation
        int_ok, int_errs = self.validate_integrity(report_data, base_dir=base_dir)
        errors.extend(int_errs)

        # Check existing anomalies for warning/error classification
        for anom in report_data.get("anomalies", []):
            sev = anom.get("severity", "WARNING")
            msg = f"[ANOMALY:{anom.get('type')}] {anom.get('description')}"
            if sev == "ERROR":
                errors.append(msg)
            else:
                warnings.append(msg)

        if errors:
            overall_status = "INVALID"
        elif warnings:
            overall_status = "VALID_WITH_WARNINGS"
        else:
            overall_status = "VALID"

        return {
            "overall_status": overall_status,
            "validations": {
                "schema_validation": {"status": "PASS" if schema_ok else "FAIL", "errors": schema_errs},
                "semantic_validation": {"status": "PASS" if sem_ok else "FAIL", "errors": sem_errs, "warnings": sem_warns},
                "referential_validation": {"status": "PASS" if ref_ok else "FAIL", "errors": ref_errs},
                "integrity_validation": {"status": "PASS" if int_ok else "FAIL", "errors": int_errs},
            },
            "errors": errors,
            "warnings": warnings,
            "metrics_summary": report_data.get("metrics", {}),
        }

    def validate_schema(self, report_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate instance against canonical JSON schema."""
        errors = []
        for err in self.jsonschema_validator.iter_errors(report_data):
            path = " -> ".join(str(p) for p in err.path) or "root"
            errors.append(f"Schema error at [{path}]: {err.message}")
        return len(errors) == 0, errors

    def validate_semantics(self, report_data: Dict[str, Any]) -> Tuple[bool, List[str], List[str]]:
        """Validate semantic invariants, metric counts, and information state rules."""
        errors = []
        warnings = []

        findings = report_data.get("findings", [])
        controls = report_data.get("controls", [])
        inspections = report_data.get("inspections", [])
        metrics = report_data.get("metrics", {})

        # Metrics checks
        if metrics.get("findings_total") != len(findings):
            errors.append(
                f"Metrics mismatch: findings_total={metrics.get('findings_total')} != len(findings)={len(findings)}"
            )

        if metrics.get("controls_total") != len(controls):
            errors.append(
                f"Metrics mismatch: controls_total={metrics.get('controls_total')} != len(controls)={len(controls)}"
            )

        if metrics.get("inspections_total") != len(inspections):
            errors.append(
                f"Metrics mismatch: inspections_total={metrics.get('inspections_total')} != len(inspections)={len(inspections)}"
            )

        sev_counts = metrics.get("severity", {})
        actual_sev = {"P0": 0, "P1": 0, "P2": 0, "P3": 0, "INFO": 0}
        for f in findings:
            s_val = f.get("severity", {}).get("value")
            if s_val in actual_sev:
                actual_sev[s_val] += 1

        for k, v in actual_sev.items():
            if sev_counts.get(k) != v:
                errors.append(f"Metrics severity mismatch for {k}: declared={sev_counts.get(k)} != actual={v}")

        # Semantic field invariants
        for f in findings:
            fid = f.get("id", "UNKNOWN")
            st_val = f.get("status", {}).get("value")
            if st_val == "NOT_FOUND":
                errors.append(f"Finding {fid} has prohibited status 'NOT_FOUND'. NOT_FOUND is not a valid finding status.")

            loc = f.get("location", {})
            if loc.get("state") == "PRESENT":
                l_val = loc.get("value")
                if isinstance(l_val, dict) and "line_start" in l_val and "line_end" in l_val:
                    if l_val["line_end"] < l_val["line_start"]:
                        errors.append(f"Finding {fid} location invalid: line_end ({l_val['line_end']}) < line_start ({l_val['line_start']})")

            for fname in ("severity", "status", "confidence", "type", "evidence", "description", "cause", "impact", "exploitability", "recommendation"):
                fdict = f.get(fname)
                if not isinstance(fdict, dict):
                    continue
                state = fdict.get("state")
                val = fdict.get("value")
                cid = fdict.get("conflict_id")
                reason = fdict.get("reason")

                if state == "PRESENT":
                    if val is None:
                        errors.append(f"Finding {fid} field '{fname}' has state PRESENT but value is null.")
                    if cid is not None:
                        errors.append(f"Finding {fid} field '{fname}' has state PRESENT but conflict_id is not null.")
                elif state == "NOT_PROVIDED_BY_SOURCE":
                    if val is not None:
                        errors.append(f"Finding {fid} field '{fname}' has state NOT_PROVIDED_BY_SOURCE but value is not null.")
                    if cid is not None:
                        errors.append(f"Finding {fid} field '{fname}' has state NOT_PROVIDED_BY_SOURCE but conflict_id is not null.")
                elif state == "NOT_DETERMINABLE":
                    if val is not None:
                        errors.append(f"Finding {fid} field '{fname}' has state NOT_DETERMINABLE but value is not null.")
                    if not reason or not reason.strip():
                        errors.append(f"Finding {fid} field '{fname}' has state NOT_DETERMINABLE but reason is missing or empty.")
                    if cid is not None:
                        errors.append(f"Finding {fid} field '{fname}' has state NOT_DETERMINABLE but conflict_id is not null.")
                elif state == "CONFLICT":
                    if val is not None:
                        errors.append(f"Finding {fid} field '{fname}' has state CONFLICT but value is not null.")
                    if not cid or not re.match(r"^CONFLICT-[0-9]{3,}$", str(cid)):
                        errors.append(f"Finding {fid} field '{fname}' has state CONFLICT but conflict_id is missing or malformed.")

        return len(errors) == 0, errors, warnings

    def validate_referential(self, report_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate referential integrity across sources, conflicts, and findings."""
        errors = []

        sources = report_data.get("audit_snapshot", {}).get("sources", [])
        valid_source_ids = {s.get("source_id") for s in sources if s.get("source_id")}

        findings = report_data.get("findings", [])
        valid_finding_ids = {f.get("id") for f in findings if f.get("id")}

        conflicts = report_data.get("conflicts", [])
        valid_conflict_ids = {c.get("id") for c in conflicts if c.get("id")}

        def check_prov(prov_list: List[Dict[str, Any]], context: str):
            for p in prov_list:
                sid = p.get("source_id")
                if sid not in valid_source_ids:
                    errors.append(f"Referential error in {context}: provenance source_id '{sid}' not in audit_snapshot.sources")

        for f in findings:
            check_prov(f.get("provenance", []), f"finding {f.get('id')}")

        for c in report_data.get("controls", []):
            check_prov(c.get("provenance", []), f"control {c.get('id')}")

        for app in report_data.get("applicability", []):
            check_prov(app.get("provenance", []), f"applicability {app.get('category')}")

        for insp in report_data.get("inspections", []):
            check_prov(insp.get("provenance", []), f"inspection {insp.get('category')}")

        for lim in report_data.get("limitations", []):
            check_prov(lim.get("provenance", []), f"limitation {lim.get('id')}")

        for ref in report_data.get("references", []):
            check_prov(ref.get("provenance", []), f"reference {ref.get('value')}")

        for tp_field, tp_obj in report_data.get("target_project", {}).items():
            if isinstance(tp_obj, dict):
                check_prov(tp_obj.get("provenance", []), f"target_project.{tp_field}")
                if tp_obj.get("conflict_id"):
                    ref_cid = tp_obj["conflict_id"]
                    if ref_cid not in valid_conflict_ids:
                        errors.append(f"target_project.{tp_field} references non-existent conflict_id '{ref_cid}'")

        for conf in conflicts:
            cid = conf.get("id")
            fid = conf.get("finding_id")
            if fid is not None and fid not in valid_finding_ids:
                errors.append(f"Conflict {cid} references non-existent finding_id '{fid}'")

            values = conf.get("values", [])
            for val_entry in values:
                vsid = val_entry.get("source_id")
                if vsid not in valid_source_ids:
                    errors.append(f"Conflict {cid} value references non-existent source_id '{vsid}'")

            res = conf.get("resolution", {})
            if res.get("status") == "RESOLVED":
                sel_src = res.get("selected_source")
                if sel_src not in valid_source_ids:
                    errors.append(f"Resolved conflict {cid} selected_source '{sel_src}' not in audit_snapshot.sources")
                val_sids = {v.get("source_id") for v in values}
                if sel_src not in val_sids:
                    errors.append(f"Resolved conflict {cid} selected_source '{sel_src}' not in conflict values sources")

        for f in findings:
            for fname, fdict in f.items():
                if isinstance(fdict, dict) and fdict.get("conflict_id"):
                    ref_cid = fdict["conflict_id"]
                    if ref_cid not in valid_conflict_ids:
                        errors.append(f"Finding {f.get('id')} field '{fname}' references non-existent conflict_id '{ref_cid}'")

        return len(errors) == 0, errors

    def validate_integrity(
        self,
        report_data: Dict[str, Any],
        base_dir: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """Validate hash integrity, source snapshot consistency, and file hashes."""
        errors = []
        snapshot = report_data.get("audit_snapshot", {})
        sources = snapshot.get("sources", [])
        snapshot_id = snapshot.get("snapshot_id", "")

        if sources and snapshot_id:
            manifest_list = [
                {
                    "file": s["file"],
                    "sha256": s["sha256"],
                    "source_id": s["source_id"],
                    "source_role": s["source_role"],
                }
                for s in sources
            ]
            canonical_manifest = json.dumps(manifest_list, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            expected_snapshot_id = "sha256:" + hashlib.sha256(canonical_manifest.encode("utf-8")).hexdigest()
            if snapshot_id != expected_snapshot_id:
                errors.append(f"Snapshot integrity error: snapshot_id '{snapshot_id}' does not match canonical manifest hash '{expected_snapshot_id}'")

        if base_dir and os.path.isdir(base_dir):
            for s in sources:
                rel_file = s.get("file", "")
                disk_path = os.path.join(base_dir, rel_file) if not os.path.isabs(rel_file) else rel_file
                if not os.path.exists(disk_path):
                    disk_path_alt = os.path.join(base_dir, os.path.basename(rel_file))
                    if os.path.exists(disk_path_alt):
                        disk_path = disk_path_alt
                    else:
                        errors.append(f"Source file missing on disk: {disk_path}")
                        continue

                with open(disk_path, "rb") as f:
                    content_bytes = f.read()
                actual_hash = hashlib.sha256(content_bytes).hexdigest()
                if actual_hash != s.get("sha256"):
                    errors.append(f"Hash mismatch for source '{rel_file}': manifest={s.get('sha256')} != disk={actual_hash}")

        return len(errors) == 0, errors


def main():
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="audit-validate: Independent validator for audit report_data.json")
    parser.add_argument("report_file", help="Path to report_data.json to validate")
    parser.add_argument("--schema", default=None, help="Path to report_data.schema.json")
    parser.add_argument("--base-dir", default=None, help="Base directory to verify source files integrity")

    args = parser.parse_args()

    schema_path = args.schema or get_default_schema_path()
    if not os.path.exists(schema_path):
        print(f"ERROR: Schema not found at: {schema_path}", file=sys.stderr)
        sys.exit(1)

    with open(args.report_file, "r", encoding="utf-8") as rf:
        report_data = json.load(rf)

    with open(schema_path, "r", encoding="utf-8") as sf:
        schema_data = json.load(sf)

    validator = AuditDataValidator(schema_data)
    res = validator.validate_all(report_data, base_dir=args.base_dir)

    print(json.dumps(res, indent=2, ensure_ascii=False))
    if res["overall_status"] == "INVALID":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
