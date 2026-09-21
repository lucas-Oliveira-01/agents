"""Data models, enums, taxonomy mappings, and formal helpers for audit-normalize."""

from enum import Enum
import re
from typing import Any, Dict, List, Optional, Tuple


class SourceRole(str, Enum):
    AUDIT_LEDGER = "AUDIT_LEDGER"
    ANALYTICAL_REPORT = "ANALYTICAL_REPORT"
    INVENTORY = "INVENTORY"
    THREAT_MODEL = "THREAT_MODEL"
    COVERAGE_MANIFEST = "COVERAGE_MANIFEST"
    EXTERNAL_REVIEW = "EXTERNAL_REVIEW"
    ENVIRONMENT = "ENVIRONMENT"
    VCS = "VCS"
    UNKNOWN = "UNKNOWN"


# Precedence policy ranking (lower numeric rank = higher precedence)
# As formally specified in v8_current.md (L988-L1008) & NCS-0032:
# AUDIT_LEDGER: 1
# ANALYTICAL_REPORT: 2
# INVENTORY: 3, THREAT_MODEL: 3, COVERAGE_MANIFEST: 3
# EXTERNAL_REVIEW: 4
# UNKNOWN: 0
PRECEDENCE_RANKING: Dict[str, int] = {
    "UNKNOWN": 0,
    "AUDIT_LEDGER": 1,
    "ANALYTICAL_REPORT": 2,
    "INVENTORY": 3,
    "THREAT_MODEL": 3,
    "COVERAGE_MANIFEST": 3,
    "EXTERNAL_REVIEW": 4,
}

CANONICAL_CATEGORIES = {
    "SECURITY",
    "ARCHITECTURE",
    "DOMAIN",
    "DATABASE",
    "BUILD",
    "TESTING",
    "CI_CD",
    "INFRASTRUCTURE",
    "CONFIGURATION",
    "DOCUMENTATION",
    "OPERATIONS",
    "CODE_QUALITY",
}

CANONICAL_FINDING_TYPES = {
    "BUG",
    "TECHNICAL_DEFECT",
    "VULNERABILITY",
    "RISK",
    "INCONSISTENCY",
    "TECH_DEBT",
    "OPERATIONAL_PROBLEM",
    "ARCHITECTURAL_DEFECT",
    "ARCHITECTURAL_IMPROVEMENT",
    "REQUIREMENT_DEPENDENT",
}

CANONICAL_FINDING_STATUSES = {
    "CONFIRMED",
    "PROBABLE",
    "NOT_DETERMINABLE",
}

CANONICAL_SEVERITIES = {
    "P0",
    "P1",
    "P2",
    "P3",
    "INFO",
}

CANONICAL_CONFIDENCES = {
    "HIGH",
    "MEDIUM",
    "LOW",
}

CANONICAL_APPLICABILITY_STATES = {
    "APPLICABLE",
    "NOT_APPLICABLE",
    "NOT_DETERMINABLE",
}

CANONICAL_INSPECTION_STATES = {
    "INSPECTED",
    "PARTIALLY_INSPECTED",
    "NOT_INSPECTED",
    "NOT_DETERMINABLE",
}

CANONICAL_INSPECTION_RESULTS = {
    "FINDINGS_PRESENT",
    "NOT_FOUND",
    "NOT_DETERMINABLE",
}

CANONICAL_ANOMALY_TYPES = {
    "TECHNICAL_INCONSISTENCY",
    "SOURCE_FORMAT_ANOMALY",
    "CONTRADICTORY_STATEMENT",
    "POSSIBLE_TRANSCRIPTION_ERROR",
    "UNEXPECTED_CONFIGURATION_REFERENCE",
    "ID_COLLISION",
    "UNMAPPED_TAXONOMY",
    "OTHER",
}

CANONICAL_CONFLICT_TYPES = {
    "SEVERITY_CONFLICT",
    "STATUS_CONFLICT",
    "CONFIDENCE_CONFLICT",
    "TYPE_CONFLICT",
    "LOCATION_CONFLICT",
    "FIELD_VALUE_CONFLICT",
    "IDENTITY_CONFLICT",
    "TARGET_PROJECT_CONFLICT",
}

CANONICAL_REFERENCE_TYPES = {
    "SOURCE_DOCUMENT",
    "REPOSITORY",
    "COMMIT",
    "REQUIREMENT",
    "STANDARD",
    "EXTERNAL_REFERENCE",
    "OTHER",
}


def map_severity(raw: Optional[str]) -> Tuple[Optional[str], bool]:
    """Map raw severity text to canonical severity.
    
    Returns (canonical_severity, is_mapped).
    Only explicit normative mappings per v8_current.md L777-L781 are accepted.
    """
    if not raw or not str(raw).strip():
        return None, True
    cleaned = str(raw).strip().upper()
    if cleaned in CANONICAL_SEVERITIES:
        return cleaned, True

    # Explicit taxonomy mappings per NCS-0023 / v8_current.md L777-L781
    normative_mapping = {
        "CRITICAL": "P0",
        "HIGH": "P1",
        "MEDIUM": "P2",
        "LOW": "P3",
        "INFORMATIONAL": "INFO",
        "INFO": "INFO",
    }
    if cleaned in normative_mapping:
        return normative_mapping[cleaned], True
    return None, False


def map_category(raw: Optional[str]) -> Tuple[Optional[str], bool]:
    """Map raw category text to canonical category.

    Accepts canonical categories and direct Portuguese translations.
    """
    if not raw or not str(raw).strip():
        return None, True
    cleaned = str(raw).strip().upper().replace(" ", "_").replace("-", "_").replace("/", "_")
    if cleaned in CANONICAL_CATEGORIES:
        return cleaned, True

    translations = {
        "SEGURANÇA": "SECURITY",
        "SEGURANCA": "SECURITY",
        "BANCO_DE_DADOS": "DATABASE",
        "BANCO_DADOS": "DATABASE",
        "ARQUITETURA": "ARCHITECTURE",
        "TESTES": "TESTING",
        "TESTE": "TESTING",
        "CONSTRUÇÃO": "BUILD",
        "CONSTRUCAO": "BUILD",
        "INFRAESTRUTURA": "INFRASTRUCTURE",
        "CONFIGURAÇÃO": "CONFIGURATION",
        "CONFIGURACAO": "CONFIGURATION",
        "DOCUMENTAÇÃO": "DOCUMENTATION",
        "DOCUMENTACAO": "DOCUMENTATION",
        "OPERAÇÕES": "OPERATIONS",
        "OPERACOES": "OPERATIONS",
        "QUALIDADE_DE_CÓDIGO": "CODE_QUALITY",
        "QUALIDADE_DE_CODIGO": "CODE_QUALITY",
        "QUALIDADE": "CODE_QUALITY",
        "DOMÍNIO": "DOMAIN",
        "DOMINIO": "DOMAIN",
    }
    if cleaned in translations:
        return translations[cleaned], True
    return None, False


def map_finding_type(raw: Optional[str]) -> Tuple[Optional[str], bool]:
    """Map raw finding type text to canonical finding type."""
    if not raw or not str(raw).strip():
        return None, True
    cleaned = str(raw).strip().upper().replace(" ", "_").replace("-", "_")
    if cleaned in CANONICAL_FINDING_TYPES:
        return cleaned, True

    type_synonyms = {
        "DEFECT": "TECHNICAL_DEFECT",
        "DEFEITO": "TECHNICAL_DEFECT",
        "DEFEITO_TECNICO": "TECHNICAL_DEFECT",
        "DEFEITO_TÉCNICO": "TECHNICAL_DEFECT",
        "VULNERABILIDADE": "VULNERABILITY",
        "RISCO": "RISK",
        "INCONSISTÊNCIA": "INCONSISTENCY",
        "INCONSISTENCIA": "INCONSISTENCY",
        "DÍVIDA_TÉCNICA": "TECH_DEBT",
        "DIVIDA_TECNICA": "TECH_DEBT",
        "PROBLEMA_OPERACIONAL": "OPERATIONAL_PROBLEM",
        "DEFEITO_ARQUITETURAL": "ARCHITECTURAL_DEFECT",
        "MELHORIA_ARQUITETURAL": "ARCHITECTURAL_IMPROVEMENT",
    }
    if cleaned in type_synonyms:
        return type_synonyms[cleaned], True
    return None, False


def map_finding_status(raw: Optional[str]) -> Tuple[Optional[str], bool]:
    """Map raw finding status text to canonical status."""
    if not raw or not str(raw).strip():
        return None, True
    cleaned = str(raw).strip().upper().replace(" ", "_").replace("-", "_")
    if cleaned in CANONICAL_FINDING_STATUSES:
        return cleaned, True

    status_synonyms = {
        "CONFIRMADO": "CONFIRMED",
        "CONFIRMADA": "CONFIRMED",
        "PROVÁVEL": "PROBABLE",
        "PROVAVEL": "PROBABLE",
        "NÃO_DETERMINÁVEL": "NOT_DETERMINABLE",
        "NAO_DETERMINAVEL": "NOT_DETERMINABLE",
    }
    if cleaned in status_synonyms:
        return status_synonyms[cleaned], True
    return None, False


def map_confidence(raw: Optional[str]) -> Tuple[Optional[str], bool]:
    """Map raw confidence text to canonical confidence."""
    if not raw or not str(raw).strip():
        return None, True
    cleaned = str(raw).strip().upper()
    if cleaned in CANONICAL_CONFIDENCES:
        return cleaned, True
    return None, False


def make_semantic_field(
    state: str,
    value: Any = None,
    reason: Optional[str] = None,
    conflict_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a schema-compliant semantic field."""
    field: Dict[str, Any] = {"state": state, "value": value}
    if state == "PRESENT":
        field["conflict_id"] = None
        if reason is not None:
            field["reason"] = reason
    elif state == "NOT_PROVIDED_BY_SOURCE":
        field["value"] = None
        field["conflict_id"] = None
    elif state == "NOT_DETERMINABLE":
        field["value"] = None
        field["conflict_id"] = None
        field["reason"] = reason or "Source could not determine value"
    elif state == "CONFLICT":
        field["value"] = None
        field["conflict_id"] = conflict_id
    else:
        if reason is not None:
            field["reason"] = reason
        if conflict_id is not None:
            field["conflict_id"] = conflict_id

    return field


def make_source_backed_string(
    state: str,
    value: Optional[str] = None,
    provenance: Optional[List[Dict[str, Any]]] = None,
    reason: Optional[str] = None,
    conflict_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a schema-compliant sourceBackedString object."""
    res: Dict[str, Any] = {
        "state": state,
        "value": value if state == "PRESENT" else None,
        "provenance": provenance if provenance and len(provenance) > 0 else [{"source_id": "src-001", "file": "UNKNOWN"}],
    }
    if state == "PRESENT":
        res["conflict_id"] = None
        if reason is not None:
            res["reason"] = reason
    elif state == "NOT_PROVIDED_BY_SOURCE":
        res["conflict_id"] = None
    elif state == "NOT_DETERMINABLE":
        res["conflict_id"] = None
        res["reason"] = reason or "Source could not determine value"
    elif state == "CONFLICT":
        res["conflict_id"] = conflict_id

    return res


def make_provenance(
    source_id: str,
    file: str,
    line_range: Optional[List[int]] = None,
    confidence_at_source: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a schema-compliant provenance entry."""
    entry: Dict[str, Any] = {
        "source_id": source_id,
        "file": file,
    }
    if line_range is not None and len(line_range) == 2:
        if line_range[1] >= line_range[0]:
            entry["line_range"] = line_range
    if confidence_at_source is not None and confidence_at_source in CANONICAL_CONFIDENCES:
        entry["confidence_at_source"] = confidence_at_source
    return entry
