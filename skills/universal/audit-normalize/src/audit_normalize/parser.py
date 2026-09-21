"""Markdown parser and structural extractor for audit-normalize."""

import os
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Tuple

import markdown

from .models import (
    CANONICAL_APPLICABILITY_STATES,
    CANONICAL_CATEGORIES,
    CANONICAL_CONFIDENCES,
    CANONICAL_FINDING_STATUSES,
    CANONICAL_FINDING_TYPES,
    CANONICAL_INSPECTION_RESULTS,
    CANONICAL_INSPECTION_STATES,
    CANONICAL_SEVERITIES,
    SourceRole,
    make_provenance,
    make_semantic_field,
    make_source_backed_string,
    map_category,
    map_confidence,
    map_finding_status,
    map_finding_type,
    map_severity,
)

# Semantic non-finding section markers (adversarial rejection per NCS-0005, NCS-0008, Sec 40, and Sec 9)
NON_FINDING_SECTIONS = (
    "RECOMMENDATION",
    "RECOMMENDATIONS",
    "RECOMENDAÇÕES",
    "RECOMENDACOES",
    "ROADMAP",
    "PRIORITIZATION",
    "PRIORIZAÇÃO",
    "PRIORIZACAO",
    "CONCLUSION",
    "CONCLUSÃO",
    "CONCLUSAO",
    "REFERENCES",
    "REFERÊNCIAS",
    "REFERENCIAS",
    "APPENDIX",
    "APÊNDICE",
    "APENDICE",
    "RELATED ISSUES",
    "ISSUES RELACIONADAS",
    "BIBLIOGRAPHY",
    "BIBLIOGRAFIA",
    "EXECUTIVE SUMMARY",
    "RESUMO EXECUTIVO",
    "IMPROVEMENT",
    "IMPROVEMENTS",
    "MELHORIAS",
    "IMPROVEMENT LIST",
    "LISTA DE MELHORIAS",
    "FUTURE WORK",
    "TRABALHOS FUTUROS",
    "ACTION PLAN",
    "PLANO DE AÇÃO",
    "PLANO DE ACAO",
    "NEXT STEPS",
    "PRÓXIMOS PASSOS",
    "PROXIMOS PASSOS",
    "SUMMARY",
    "RESUMO",
    "OVERVIEW",
    "VISÃO GERAL",
    "VISAO GERAL",
    "METHODOLOGY",
    "METODOLOGIA",
    "SCOPE",
    "ESCOPO",
)


def classify_source_role(file_path: str, raw_text: str) -> str:
    """Classify the role of an audit markdown document using filename, headings, and content signals."""
    name = os.path.basename(file_path).lower()
    text_upper = raw_text.upper()

    # Filename signals
    if "ledger" in name or "03_audit_ledger" in name:
        return SourceRole.AUDIT_LEDGER.value
    if "analytical" in name or "02_analytical_report" in name:
        return SourceRole.ANALYTICAL_REPORT.value
    if "coverage" in name or "01_coverage_manifest" in name:
        return SourceRole.COVERAGE_MANIFEST.value
    if "inventory" in name and "threat" in name:
        return SourceRole.INVENTORY.value
    if "threat_model" in name or "threat-model" in name:
        return SourceRole.THREAT_MODEL.value
    if "inventory" in name or "00_inventory" in name:
        return SourceRole.INVENTORY.value
    if "external" in name or "third_party" in name:
        return SourceRole.EXTERNAL_REVIEW.value
    if "environment" in name or "env" in name:
        return SourceRole.ENVIRONMENT.value
    if "vcs" in name or "git" in name:
        return SourceRole.VCS.value

    # Heading & content signals
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()][:35]
    header_block = " ".join(lines).upper()

    if "# AUDIT LEDGER" in header_block or "## AUDIT LEDGER" in header_block:
        return SourceRole.AUDIT_LEDGER.value
    if "# ANALYTICAL REPORT" in header_block or "## ANALYTICAL REPORT" in header_block:
        return SourceRole.ANALYTICAL_REPORT.value
    if "# COVERAGE MANIFEST" in header_block or "## COVERAGE MANIFEST" in header_block or "APPLICABILITY MATRIX" in header_block:
        return SourceRole.COVERAGE_MANIFEST.value
    if "# THREAT MODEL" in header_block or "## THREAT MODEL" in header_block:
        return SourceRole.THREAT_MODEL.value
    if "# INVENTORY" in header_block or "## INVENTORY" in header_block:
        return SourceRole.INVENTORY.value
    if "# EXTERNAL REVIEW" in header_block or "## EXTERNAL REVIEW" in header_block:
        return SourceRole.EXTERNAL_REVIEW.value

    return SourceRole.UNKNOWN.value


def parse_markdown_to_tree(raw_text: str) -> ET.Element:
    """Convert Markdown text into an ElementTree XML root."""
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])
    html_content = md.convert(raw_text)
    try:
        root = ET.fromstring(f"<root>{html_content}</root>")
    except ET.ParseError:
        # Clean up XML void tags if needed
        clean_html = re.sub(r"<(hr|br|img|input)([^>]*)>", r"<\1\2/>", html_content)
        root = ET.fromstring(f"<root>{clean_html}</root>")
    return root


def extract_table_rows(element: ET.Element) -> List[List[str]]:
    """Extract rows of cells from either an HTML <table> element or a pipe-delimited text block."""
    rows: List[List[str]] = []
    if element.tag == "table":
        tbody = element.find("tbody")
        tr_elements = tbody.findall("tr") if tbody is not None else element.findall("tr")
        for tr in tr_elements:
            cells = ["".join(td.itertext()).strip() for td in tr.findall("td")]
            if not cells:
                cells = ["".join(th.itertext()).strip() for th in tr.findall("th")]
            if cells:
                rows.append(cells)
    else:
        text = "".join(element.itertext())
        for line in text.splitlines():
            line_str = line.strip()
            if "|" in line_str:
                parts = [p.strip() for p in line_str.strip("|").split("|")]
                if all(re.match(r"^:?-+:?$", p) for p in parts if p):
                    continue
                if len(parts) >= 2:
                    rows.append(parts)
    return rows


def extract_raw_target_projects(sources: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract raw declared target project values per source without Git/environment inference."""
    raw_projects: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []

    for s in sources:
        rp: Dict[str, Any] = {
            "source_id": s["source_id"],
            "source_role": s.get("source_role", "UNKNOWN"),
            "file": s["file"],
            "repository": None,
            "commit": None,
            "branch": None,
            "version": None,
            "build_version": None,
        }
        root = parse_markdown_to_tree(s["raw_text"])
        for i, child in enumerate(root):
            text_upper = "".join(child.itertext()).strip().upper()
            if child.tag in ("h1", "h2", "h3") and any(
                k in text_upper for k in ("IDENTITY", "IDENTIDADE", "TARGET PROJECT", "PROJETO ALVO", "METADATA")
            ):
                j = i + 1
                while j < len(root) and root[j].tag not in ("h1", "h2", "h3"):
                    elem = root[j]
                    table_rows = extract_table_rows(elem)
                    if table_rows:
                        for row in table_rows:
                            if len(row) >= 2:
                                k_col = row[0].strip().lower()
                                v_col = row[1].strip().strip("`'\" ")
                                if any(x in k_col for x in ("repository", "repo", "git repo", "git repository", "repositório", "repositorio")) and not any(p in k_col for p in ("project", "projeto", "nome")):
                                    if not rp["repository"] and v_col:
                                        rp["repository"] = v_col
                                elif any(x in k_col for x in ("commit", "target commit")):
                                    if not rp["commit"] and v_col:
                                        rp["commit"] = v_col
                                elif "branch" in k_col:
                                    if not rp["branch"] and v_col:
                                        rp["branch"] = v_col
                                elif any(x in k_col for x in ("build version", "build_version")):
                                    if not rp["build_version"] and v_col:
                                        rp["build_version"] = v_col
                                elif "version" in k_col:
                                    if not rp["version"] and v_col:
                                        rp["version"] = v_col
                    else:
                        elem_text = "".join(elem.itertext())
                        for line in elem_text.splitlines():
                            line_str = line.strip().lstrip("-*• ")
                            if not line_str:
                                continue
                            lower_line = line_str.lower()
                            if any(x in lower_line for x in ("repository:", "repo:", "git repository:", "git repo:", "repositório:", "repositorio:")) and not any(p in lower_line for p in ("project name:", "projeto:", "project:")):
                                val = re.split(r":\s*", line_str, maxsplit=1)[1].strip().strip("`'\" ")
                                if val and not rp["repository"]:
                                    rp["repository"] = val
                            elif any(x in lower_line for x in ("target commit:", "commit:")):
                                val = re.split(r":\s*", line_str, maxsplit=1)[1].strip()
                                if "=" in val:
                                    val = val.split("=")[1].strip()
                                val = val.strip("`'\" ")
                                if val and not rp["commit"]:
                                    rp["commit"] = val
                            elif "branch:" in lower_line:
                                val = re.split(r":\s*", line_str, maxsplit=1)[1].strip().strip("`'\" ")
                                if val and not rp["branch"]:
                                    rp["branch"] = val
                            elif any(x in lower_line for x in ("build version:", "build_version:")):
                                val = re.split(r":\s*", line_str, maxsplit=1)[1].strip().strip("`'\" ")
                                if val and not rp["build_version"]:
                                    rp["build_version"] = val
                            elif "version:" in lower_line:
                                val = re.split(r":\s*", line_str, maxsplit=1)[1].strip().strip("`'\" ")
                                if val and not rp["version"]:
                                    rp["version"] = val
                    j += 1

        raw_projects.append(rp)

    return raw_projects, anomalies


def extract_applicability(sources: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract applicability matrix entries from sources, preserving provenances and recording unmapped taxonomies."""
    applicabilities: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []

    for s in sources:
        root = parse_markdown_to_tree(s["raw_text"])
        prov = make_provenance(s["source_id"], s["file"])
        for i, child in enumerate(root):
            text_upper = "".join(child.itertext()).strip().upper()
            if child.tag in ("h1", "h2", "h3") and any(
                k in text_upper for k in ("APPLICABILITY MATRIX", "MATRIZ DE APLICABILIDADE", "APPLICABILITY", "APLICABILIDADE")
            ):
                j = i + 1
                while j < len(root) and root[j].tag not in ("h1", "h2", "h3"):
                    elem = root[j]
                    rows = extract_table_rows(elem)
                    for r in rows:
                        if r and r[0].upper() in ("CATEGORY", "CATEGORIA", "CAT"):
                            continue
                        if len(r) >= 3:
                            raw_cat = r[0]
                            raw_subcat = r[1]
                            raw_state = r[2]

                            canon_cat, is_cat_mapped = map_category(raw_cat)
                            if canon_cat:
                                cat = canon_cat
                            elif raw_cat and not is_cat_mapped:
                                cat = None
                                anomalies.append({
                                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                                    "type": "UNMAPPED_TAXONOMY",
                                    "severity": "WARNING",
                                    "description": f"Unmapped taxonomy value '{raw_cat}' for category in applicability matrix",
                                    "provenance": [prov],
                                })
                            else:
                                cat = None
                                anomalies.append({
                                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                                    "type": "SOURCE_FORMAT_ANOMALY",
                                    "severity": "WARNING",
                                    "description": "Category not provided by source for applicability matrix entry",
                                    "provenance": [prov],
                                })

                            subcat = raw_subcat if raw_subcat and raw_subcat not in ("-", "N/A", "null", "") else None

                            st_raw = str(raw_state).strip()
                            st_upper = st_raw.upper().replace(" ", "_")
                            if st_upper in CANONICAL_APPLICABILITY_STATES:
                                state = st_upper
                            elif st_raw:
                                state = "NOT_DETERMINABLE"
                                anomalies.append({
                                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                                    "type": "UNMAPPED_TAXONOMY",
                                    "severity": "WARNING",
                                    "description": f"Unmapped taxonomy value '{raw_state}' for state in applicability matrix",
                                    "provenance": [prov],
                                })
                            else:
                                state = "NOT_DETERMINABLE"
                                anomalies.append({
                                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                                    "type": "SOURCE_FORMAT_ANOMALY",
                                    "severity": "WARNING",
                                    "description": "State not provided by source for applicability matrix entry",
                                    "provenance": [prov],
                                })

                            key = (cat, subcat)
                            existing = next((a for a in applicabilities if (a["category"], a["subcategory"]) == key), None)
                            if existing is None:
                                applicabilities.append({
                                    "category": cat,
                                    "subcategory": subcat,
                                    "state": state,
                                    "provenance": [prov],
                                })
                            else:
                                if not any(p["source_id"] == prov["source_id"] and p["file"] == prov["file"] for p in existing["provenance"]):
                                    existing["provenance"].append(prov)
                    j += 1
    return applicabilities, anomalies


def extract_inspections(sources: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract inspection coverage entries from sources, preserving provenances and recording unmapped taxonomies."""
    inspections: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []

    for s in sources:
        root = parse_markdown_to_tree(s["raw_text"])
        prov = make_provenance(s["source_id"], s["file"])
        for i, child in enumerate(root):
            text_upper = "".join(child.itertext()).strip().upper()
            if child.tag in ("h1", "h2", "h3") and any(
                k in text_upper for k in ("INSPECTION COVERAGE", "COBERTURA DE INSPEÇÃO", "COBERTURA DE INSPECAO", "INSPECTIONS", "COBERTURA")
            ):
                j = i + 1
                while j < len(root) and root[j].tag not in ("h1", "h2", "h3"):
                    elem = root[j]
                    rows = extract_table_rows(elem)
                    for r in rows:
                        if r and r[0].upper() in ("CATEGORY", "CATEGORIA", "CAT"):
                            continue
                        if len(r) >= 4:
                            raw_cat = r[0]
                            raw_subcat = r[1]
                            raw_state = r[2]
                            raw_result = r[3]

                            canon_cat, is_cat_mapped = map_category(raw_cat)
                            if canon_cat:
                                cat = canon_cat
                            elif raw_cat and not is_cat_mapped:
                                cat = None
                                anomalies.append({
                                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                                    "type": "UNMAPPED_TAXONOMY",
                                    "severity": "WARNING",
                                    "description": f"Unmapped taxonomy value '{raw_cat}' for category in inspection coverage",
                                    "provenance": [prov],
                                })
                            else:
                                cat = None
                                anomalies.append({
                                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                                    "type": "SOURCE_FORMAT_ANOMALY",
                                    "severity": "WARNING",
                                    "description": "Category not provided by source for inspection coverage entry",
                                    "provenance": [prov],
                                })

                            subcat = raw_subcat if raw_subcat and raw_subcat not in ("-", "N/A", "null", "") else None

                            st_raw = str(raw_state).strip()
                            st_upper = st_raw.upper().replace(" ", "_")
                            if st_upper in CANONICAL_INSPECTION_STATES:
                                state = st_upper
                            elif st_raw:
                                state = "NOT_DETERMINABLE"
                                anomalies.append({
                                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                                    "type": "UNMAPPED_TAXONOMY",
                                    "severity": "WARNING",
                                    "description": f"Unmapped taxonomy value '{raw_state}' for state in inspection coverage",
                                    "provenance": [prov],
                                })
                            else:
                                state = "NOT_DETERMINABLE"
                                anomalies.append({
                                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                                    "type": "SOURCE_FORMAT_ANOMALY",
                                    "severity": "WARNING",
                                    "description": "State not provided by source for inspection coverage entry",
                                    "provenance": [prov],
                                })

                            res_raw = str(raw_result).strip()
                            res_upper = res_raw.upper().replace(" ", "_")
                            if res_upper in CANONICAL_INSPECTION_RESULTS:
                                result = res_upper
                            elif res_raw:
                                result = "NOT_DETERMINABLE"
                                anomalies.append({
                                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                                    "type": "UNMAPPED_TAXONOMY",
                                    "severity": "WARNING",
                                    "description": f"Unmapped taxonomy value '{raw_result}' for result in inspection coverage",
                                    "provenance": [prov],
                                })
                            else:
                                result = "NOT_DETERMINABLE"
                                anomalies.append({
                                    "id": f"ANOM-{len(anomalies) + 1:03d}",
                                    "type": "SOURCE_FORMAT_ANOMALY",
                                    "severity": "WARNING",
                                    "description": "Result not provided by source for inspection coverage entry",
                                    "provenance": [prov],
                                })

                            key = (cat, subcat)
                            existing = next((ins for ins in inspections if (ins["category"], ins["subcategory"]) == key), None)
                            if existing is None:
                                inspections.append({
                                    "category": cat,
                                    "subcategory": subcat,
                                    "state": state,
                                    "result": result,
                                    "provenance": [prov],
                                })
                            else:
                                if not any(p["source_id"] == prov["source_id"] and p["file"] == prov["file"] for p in existing["provenance"]):
                                    existing["provenance"].append(prov)
                    j += 1
    return inspections, anomalies


def extract_limitations(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract limitation entries from sources, preserving provenances across sources."""
    limitations: List[Dict[str, Any]] = []
    idx = 1

    for s in sources:
        root = parse_markdown_to_tree(s["raw_text"])
        prov = make_provenance(s["source_id"], s["file"])
        for i, child in enumerate(root):
            text_upper = "".join(child.itertext()).strip().upper()
            if child.tag in ("h1", "h2", "h3") and any(
                k in text_upper for k in ("LIMITATIONS", "LIMITAÇÕES", "LIMITACOES", "LIMITES DE ESCOPO", "SCOPE LIMITATIONS")
            ):
                j = i + 1
                while j < len(root) and root[j].tag not in ("h1", "h2", "h3"):
                    elem = root[j]
                    if elem.tag in ("ul", "ol"):
                        for li in elem.findall("li"):
                            desc = "".join(li.itertext()).strip()
                            if desc:
                                existing = next((lim for lim in limitations if lim["description"].strip().lower() == desc.strip().lower()), None)
                                if existing is None:
                                    limitations.append({
                                        "id": f"LIMIT-{idx:03d}",
                                        "description": desc,
                                        "provenance": [prov],
                                    })
                                    idx += 1
                                else:
                                    if not any(p["source_id"] == prov["source_id"] and p["file"] == prov["file"] for p in existing["provenance"]):
                                        existing["provenance"].append(prov)
                    elif elem.tag == "p":
                        desc = "".join(elem.itertext()).strip()
                        if desc:
                            existing = next((lim for lim in limitations if lim["description"].strip().lower() == desc.strip().lower()), None)
                            if existing is None:
                                limitations.append({
                                    "id": f"LIMIT-{idx:03d}",
                                    "description": desc,
                                    "provenance": [prov],
                                })
                                idx += 1
                            else:
                                if not any(p["source_id"] == prov["source_id"] and p["file"] == prov["file"] for p in existing["provenance"]):
                                    existing["provenance"].append(prov)
                    j += 1
    return limitations


def parse_location(raw: Optional[str]) -> Dict[str, Any]:
    """Parse raw location string into canonical locationField structure."""
    if not raw:
        return make_semantic_field("NOT_PROVIDED_BY_SOURCE", value=None)

    clean = raw.strip()
    first_line = clean.splitlines()[0].strip().lstrip("-*• ")
    if not first_line:
        return make_semantic_field("NOT_PROVIDED_BY_SOURCE", value=None)

    # Extract backticks if present
    bt_match = re.search(r"`([^`]+)`", first_line)
    if bt_match:
        target = bt_match.group(1).strip()
        # Check if line number follows backticks, e.g. `file.py`:12
        post = first_line[bt_match.end():].strip()
        if post.startswith(":") and not target.endswith(":"):
            target += post.split()[0]
    else:
        # Strip parenthetical notes like (ausente), (missing), etc.
        target = re.sub(r"\s*\([^)]*\)", "", first_line).strip().strip("`'\":")

    # Check for line range or line number
    if ":" in target:
        parts = target.rsplit(":", 1)
        file_path = parts[0].strip().strip("`'\"")
        line_info = parts[1].strip()
        if "-" in line_info:
            sub = line_info.split("-", 1)
            try:
                l_start, l_end = int(sub[0]), int(sub[1])
                if l_end >= l_start:
                    return make_semantic_field(
                        "PRESENT",
                        value={"file": file_path, "line_start": l_start, "line_end": l_end},
                    )
            except ValueError:
                pass
        else:
            try:
                l_single = int(line_info)
                return make_semantic_field(
                    "PRESENT",
                    value={"file": file_path, "line": l_single},
                )
            except ValueError:
                pass
        return make_semantic_field("PRESENT", value={"file": file_path})

    return make_semantic_field("PRESENT", value={"file": target})


KNOWN_FIELD_MAP = {
    "title": "Title",
    "titulo": "Title",
    "título": "Title",
    "category": "Category",
    "categoria": "Category",
    "subcategory": "Subcategory",
    "subcategoria": "Subcategory",
    "type": "Type",
    "tipo": "Type",
    "status": "Status",
    "estado": "Status",
    "severity": "Severity",
    "severidade": "Severity",
    "criticidade": "Severity",
    "gravidade": "Severity",
    "confidence": "Confidence",
    "confianca": "Confidence",
    "confiança": "Confidence",
    "location": "Location",
    "localizacao": "Location",
    "localização": "Location",
    "local": "Location",
    "evidence": "Evidence",
    "evidencia": "Evidence",
    "evidência": "Evidence",
    "description": "Description",
    "descricao": "Description",
    "descrição": "Description",
    "cause": "Cause",
    "causa": "Cause",
    "impact": "Impact",
    "impacto": "Impact",
    "exploitability": "Exploitability",
    "explorabilidade": "Exploitability",
    "recommendation": "Recommendation",
    "recomendacao": "Recommendation",
    "recomendação": "Recommendation",
}
SCALAR_FIELDS = {"Category", "Subcategory", "Type", "Status", "Severity", "Confidence"}
MULTILINE_FIELDS = {"Location", "Evidence", "Description", "Cause", "Impact", "Exploitability", "Recommendation"}


def parse_field_header(line: str) -> Optional[Tuple[str, str]]:
    """Check if a line declares a known field header, returning (canonical_field_name, remainder_value)."""
    clean = line.strip().lstrip("-*• ")
    if not clean:
        return None
    cand_no_colon = clean.strip("#*_` :").lower()
    if cand_no_colon in KNOWN_FIELD_MAP and not any(c in clean for c in ("(", "[", "{", "/", "\\", "=")):
        return KNOWN_FIELD_MAP[cand_no_colon], ""
    if ":" in clean:
        parts = clean.split(":", 1)
        k = parts[0].strip("*_`# ").lower()
        if k in KNOWN_FIELD_MAP:
            val = parts[1].strip()
            if val.startswith("**"):
                val = val[2:].strip()
            elif val.startswith("__"):
                val = val[2:].strip()
            return KNOWN_FIELD_MAP[k], val
    return None


def extract_raw_entities(
    sources: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Extract raw findings, controls, references, and initial anomalies from markdown sources."""
    findings: List[Dict[str, Any]] = []
    controls: List[Dict[str, Any]] = []
    references: List[Dict[str, Any]] = []
    anomalies: List[Dict[str, Any]] = []

    seen_refs = set()

    for s in sources:
        root = parse_markdown_to_tree(s["raw_text"])
        prov = [make_provenance(s["source_id"], s["file"])]

        current_entity: Optional[Dict[str, Any]] = None
        current_type: Optional[str] = None
        active_field: Optional[str] = None
        active_lines: List[str] = []
        in_findings_section = False
        in_non_finding_section = False
        findings_section_level = 0
        non_finding_section_level = 0
        current_non_finding_name = ""

        def finalize_active_field():
            nonlocal active_field, active_lines
            if current_entity is not None and active_field is not None:
                val = "\n".join(active_lines).strip()
                current_entity["_raw"][active_field] = val
            active_field = None
            active_lines = []

        def finalize_entity():
            nonlocal current_entity, current_type
            finalize_active_field()
            if current_entity is not None:
                if current_type == "FINDING":
                    findings.append(current_entity)
                elif current_type == "CONTROL":
                    controls.append(current_entity)
            current_entity = None
            current_type = None

        lines = s["raw_text"].splitlines()
        for line in lines:
            line_stripped = line.strip()

            if line_stripped in ("---", "***", "___") and current_entity is not None:
                finalize_entity()
                continue

            h_match = re.match(r"^(#{1,6})\s+(.*)", line_stripped)
            if h_match:
                tag_level = len(h_match.group(1))
                heading_text = h_match.group(2).strip()
                heading_upper = heading_text.upper()

                if any(nf in heading_upper for nf in NON_FINDING_SECTIONS):
                    finalize_entity()
                    in_non_finding_section = True
                    non_finding_section_level = tag_level
                    current_non_finding_name = heading_upper
                    in_findings_section = False
                    continue
                elif in_non_finding_section and tag_level <= non_finding_section_level:
                    in_non_finding_section = False
                    current_non_finding_name = ""

                if in_non_finding_section:
                    is_rec_section = any(rk in current_non_finding_name for rk in ("RECOMMENDATION", "RECOMENDAÇÃO", "RECOMENDACOES"))
                    match_id = re.search(r"\b([A-Z][A-Z0-9_-]*-[0-9]{3,})\b", heading_text)
                    if is_rec_section and match_id:
                        finalize_entity()
                        eid = match_id.group(1)
                        title_part = heading_text[match_id.end():].lstrip(" :-–—").strip()
                        current_type = "CONTROL" if eid.startswith("CONTROL") else "FINDING"
                        current_entity = {
                            "id": eid,
                            "title": title_part or heading_text,
                            "source_id": s["source_id"],
                            "file": s["file"],
                            "source_role": s["source_role"],
                            "_raw": {},
                            "_body_lines": [],
                            "_in_recommendations": True,
                        }
                        continue
                    else:
                        finalize_entity()
                        continue

                if tag_level <= 2 and any(k in heading_upper for k in ("FINDINGS", "ACHADOS", "VULNERABILIDADES", "PROBLEMAS", "DEFECTS", "SECURITY ISSUES", "THREATS")):
                    finalize_entity()
                    in_findings_section = True
                    findings_section_level = tag_level
                    continue
                elif tag_level <= findings_section_level:
                    in_findings_section = False

                if current_entity is not None:
                    fhead = parse_field_header(heading_text)
                    if fhead:
                        finalize_active_field()
                        fn, fval = fhead
                        if fn in SCALAR_FIELDS or fn == "Title":
                            current_entity["_raw"][fn] = fval
                            if fn == "Title" and fval:
                                current_entity["title"] = fval
                        else:
                            active_field = fn
                            if fval:
                                active_lines.append(fval)
                        continue

                match_id = re.search(r"\b([A-Z][A-Z0-9_-]*-[0-9]{3,})\b", heading_text)
                if match_id:
                    finalize_entity()
                    eid = match_id.group(1)
                    title_part = heading_text[match_id.end():].lstrip(" :-–—").strip()
                    current_type = "CONTROL" if eid.startswith("CONTROL") else "FINDING"
                    current_entity = {
                        "id": eid,
                        "title": title_part or heading_text,
                        "source_id": s["source_id"],
                        "file": s["file"],
                        "source_role": s["source_role"],
                        "_raw": {},
                        "_body_lines": [],
                        "_in_recommendations": in_non_finding_section,
                    }
                    continue
                elif in_findings_section and not in_non_finding_section and tag_level > findings_section_level and not any(k in heading_upper for k in ("SUMMARY", "RESUMO", "MÉTRICA", "METRICA", "METRIC", "OVERVIEW", "TOTAL")):
                    finalize_entity()
                    current_type = "FINDING"
                    current_entity = {
                        "id": None,
                        "title": heading_text,
                        "source_id": s["source_id"],
                        "file": s["file"],
                        "source_role": s["source_role"],
                        "_raw": {},
                        "_body_lines": [],
                        "_in_recommendations": False,
                    }
                    continue
                else:
                    finalize_entity()
                    continue

            if current_entity is not None:
                fhead = parse_field_header(line_stripped)
                if fhead:
                    finalize_active_field()
                    fn, fval = fhead
                    if fn in SCALAR_FIELDS or fn == "Title":
                        current_entity["_raw"][fn] = fval
                        if fn == "Title" and fval:
                            current_entity["title"] = fval
                    else:
                        active_field = fn
                        if fval:
                            active_lines.append(fval)
                else:
                    if active_field is not None:
                        if line_stripped:
                            active_lines.append(line_stripped)
                    else:
                        if line_stripped:
                            current_entity["_body_lines"].append(line_stripped)

        finalize_entity()

        # 2. Extract list-based findings (e.g., "- SEC-001 (P3): Permissive wildcard CORS configuration")
        # BUT strictly ignore lists inside non-finding sections (recommendations, roadmap, prioritization, references)
        # We parse the XML tree sequentially to track current section context
        current_section_is_non_finding = False
        sec_level = 0

        for child in root:
            if child.tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                h_text = "".join(child.itertext()).strip().upper()
                t_level = int(child.tag[1]) if child.tag[1:].isdigit() else 1
                if any(nf in h_text for nf in NON_FINDING_SECTIONS):
                    current_section_is_non_finding = True
                    sec_level = t_level
                elif current_section_is_non_finding and t_level <= sec_level:
                    current_section_is_non_finding = False

            if not current_section_is_non_finding:
                if child.tag in ("ul", "ol"):
                    for li in child.findall("li"):
                        text = "".join(li.itertext()).strip()
                        list_match = re.match(r"^([A-Z][A-Z0-9_-]*-[0-9]{3,})\s*(?:\(([^)]+)\))?\s*[:—–-]\s*(.*)", text)
                        if list_match:
                            eid = list_match.group(1)
                            sev = list_match.group(2)
                            rest = list_match.group(3)
                            existing = next((f for f in findings if f["id"] == eid and f["source_id"] == s["source_id"]), None)
                            if not existing:
                                f_entry = {
                                    "id": eid,
                                    "title": rest.split(".")[0].strip() if rest else "Untitled",
                                    "source_id": s["source_id"],
                                    "file": s["file"],
                                    "source_role": s["source_role"],
                                    "_raw": {"Severity": sev, "Description": rest} if sev else {"Description": rest},
                                    "_body_lines": [rest] if rest else [],
                                    "_in_recommendations": False,
                                }
                                if eid.startswith("CONTROL"):
                                    controls.append(f_entry)
                                else:
                                    findings.append(f_entry)

        # 3. Extract table-based findings strictly under Findings sections
        for i, child in enumerate(root):
            heading_text = "".join(child.itertext()).strip().upper()
            if child.tag in ("h1", "h2", "h3") and any(k in heading_text for k in ("FINDINGS", "VULNERABILIDADES", "PROBLEMAS", "ACHADOS")):
                if not any(nf in heading_text for nf in NON_FINDING_SECTIONS):
                    if i + 1 < len(root):
                        table_elem = root[i + 1]
                        table_rows = extract_table_rows(table_elem)
                        if table_rows and len(table_rows) > 1:
                            raw_headers = [h.upper() for h in table_rows[0]]
                            for row in table_rows[1:]:
                                if not any(cell.strip() for cell in row):
                                    continue
                                row_dict = {}
                                for h_idx, h_name in enumerate(raw_headers):
                                    if h_idx < len(row):
                                        row_dict[h_name] = row[h_idx]

                                id_col = next((row_dict[k] for k in row_dict if "ID" in k), None)
                                fid = None
                                if id_col and re.match(r"^[A-Z][A-Z0-9_-]*-[0-9]{3,}$", id_col.strip()):
                                    fid = id_col.strip()

                                desc_col = next((row_dict[k] for k in row_dict if any(x in k for x in ("DESC", "TITLE", "ACHADO", "FINDING", "NOME"))), "")
                                sev_col = next((row_dict[k] for k in row_dict if any(x in k for x in ("SEV", "CRITICIDADE", "GRAVIDADE"))), None)
                                cat_col = next((row_dict[k] for k in row_dict if any(x in k for x in ("CAT", "TIPO", "TYPE"))), None)
                                loc_col = next((row_dict[k] for k in row_dict if any(x in k for x in ("LOC", "ARQUIVO", "FILE", "LOCAL"))), None)

                                if any(k in desc_col.upper() for k in ("TOTAL", "SOMA")) or any(k in (fid or "").upper() for k in ("TOTAL", "SOMA")):
                                    continue

                                if fid and any(f["id"] == fid and f["source_id"] == s["source_id"] for f in findings):
                                    continue

                                raw_dict = {}
                                if sev_col: raw_dict["Severity"] = sev_col
                                if cat_col: raw_dict["Category"] = cat_col
                                if loc_col: raw_dict["Location"] = loc_col
                                if desc_col: raw_dict["Description"] = desc_col

                                if fid or desc_col or sev_col or loc_col:
                                    findings.append({
                                        "id": fid,
                                        "title": desc_col or "Untitled",
                                        "source_id": s["source_id"],
                                        "file": s["file"],
                                        "source_role": s["source_role"],
                                        "_raw": raw_dict,
                                        "_body_lines": [desc_col] if desc_col else [],
                                        "_in_recommendations": False,
                                    })

        # 4. Check declared counts in source text vs extracted findings count
        declared_counts = []
        count_patterns = [
            r"(?i)(?:total\s+(?:de\s+)?(?:achados|findings|vulnerabilidades|problemas)|findings\s+total)\s*[:=]\s*(\d+)",
            r"(?i)\b(\d+)\s+(?:achados|findings|vulnerabilidades)\s+(?:identificados|encontrados|reportados|detectados)\b",
        ]
        for pat in count_patterns:
            for m in re.finditer(pat, s["raw_text"]):
                try:
                    declared_counts.append(int(m.group(1)))
                except ValueError:
                    pass

        for elem in root.iter():
            for row in extract_table_rows(elem):
                if len(row) >= 2:
                    c0 = row[0].strip().upper()
                    c1 = row[1].strip()
                    if c0 in ("TOTAL", "TOTAL FINDINGS", "TOTAL DE ACHADOS", "TOTAL VULNERABILIDADES") and re.match(r"^\d+$", c1):
                        declared_counts.append(int(c1))

        if declared_counts:
            actual_count = sum(1 for f in findings if f["source_id"] == s["source_id"])
            for dc in sorted(set(declared_counts)):
                if dc != actual_count:
                    anomalies.append({
                        "id": f"ANOM-{len(anomalies) + 1:03d}",
                        "type": "TECHNICAL_INCONSISTENCY",
                        "severity": "WARNING",
                        "description": f"Declared findings count ({dc}) in '{s['file']}' differs from extracted findings count ({actual_count})",
                        "provenance": [make_provenance(s["source_id"], s["file"])],
                    })

        # 5. Extract external and standard references, preserving provenances across sources
        def add_ref(ref_type: str, ref_val: str):
            existing = next((r for r in references if r["type"] == ref_type and r["value"] == ref_val), None)
            if existing is None:
                references.append({
                    "type": ref_type,
                    "value": ref_val,
                    "provenance": list(prov),
                })
            else:
                for p in prov:
                    if not any(ep["source_id"] == p["source_id"] and ep["file"] == p["file"] for ep in existing["provenance"]):
                        existing["provenance"].append(p)

        cve_matches = re.findall(r"\bCVE-\d{4}-\d+\b", s["raw_text"])
        for cve in cve_matches:
            add_ref("STANDARD", cve)

        cwe_matches = re.findall(r"\bCWE-\d+\b", s["raw_text"])
        for cwe in cwe_matches:
            add_ref("STANDARD", cwe)

        std_matches = re.findall(r"\b(OWASP\s+[A-Za-z0-9:-]+|NIST\s+SP\s+[0-9-]+|ISO\s+[0-9]+)\b", s["raw_text"], flags=re.IGNORECASE)
        for std in std_matches:
            add_ref("STANDARD", std.strip().upper())

        urls = re.findall(r"https?://[^\s)\]\"'>]+", s["raw_text"])
        for url in urls:
            url_clean = url.rstrip(".,;:")
            ref_type = "REPOSITORY" if any(h in url_clean for h in ("github.com", "gitlab.com", "bitbucket.org")) else "EXTERNAL_REFERENCE"
            add_ref(ref_type, url_clean)

    return findings, controls, references, anomalies
