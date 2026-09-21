"""Metrics derivation module for audit-normalize."""

from typing import Any, Dict, List


def compute_metrics(
    findings: List[Dict[str, Any]],
    controls: List[Dict[str, Any]],
    inspections: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Derive metrics strictly from normalized findings, controls, and inspections.
    
    Declared counts from source documents are never trusted.
    The source of truth is the normalized collection per NCS-0039.
    """
    severity_counts = {
        "P0": 0,
        "P1": 0,
        "P2": 0,
        "P3": 0,
        "INFO": 0,
    }

    for f in findings:
        sev_field = f.get("severity", {})
        sev_val = sev_field.get("value")
        if sev_val in severity_counts:
            severity_counts[sev_val] += 1

    return {
        "findings_total": len(findings),
        "severity": severity_counts,
        "controls_total": len(controls),
        "inspections_total": len(inspections),
    }
