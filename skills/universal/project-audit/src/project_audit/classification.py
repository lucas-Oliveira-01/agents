"""Explicit deterministic classification layer for Project Audit.

This module wraps existing deterministic signals in auditable ClassificationResult
records and produces a compact ProjectProfile for the planner. No LLM, network
call, or mutable state is used.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

from .classifiers import (
    ApplicabilityDecision,
    ApplicabilityState,
    FileClassification,
    FileKind,
    TaskClassification,
    classify_task,
)
from .discovery import DiscoverySnapshot


@dataclass(frozen=True)
class ClassificationResult:
    """Auditable result emitted by one deterministic classifier decision."""

    classifier_id: str
    classifier_version: str
    input_refs: Tuple[str, ...]
    result: str
    confidence: str
    rationale: str
    provenance: str = "project-audit/deterministic-classification"

    def to_dict(self) -> dict:
        return {
            "classifier_id": self.classifier_id,
            "classifier_version": self.classifier_version,
            "input_refs": list(self.input_refs),
            "result": self.result,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "provenance": self.provenance,
        }


@dataclass(frozen=True)
class ProjectProfile:
    """Deterministic project profile used as planning context."""

    complexity: str
    application: str
    persistence: str
    network: str
    auth: str
    frontend: str
    container: str
    ci: str
    risk_surfaces: Tuple[str, ...]
    technology_surfaces: Tuple[str, ...]
    fingerprint: str

    def to_dict(self) -> dict:
        return {
            "complexity": self.complexity,
            "application": self.application,
            "persistence": self.persistence,
            "network": self.network,
            "auth": self.auth,
            "frontend": self.frontend,
            "container": self.container,
            "ci": self.ci,
            "risk_surfaces": list(self.risk_surfaces),
            "technology_surfaces": list(self.technology_surfaces),
            "fingerprint": self.fingerprint,
        }


_SURFACE_PATTERNS = {
    "HTTP": (
        r"\brequests\.(get|post|put|delete|patch)\s*\(",
        r"\baxios\.(get|post|put|delete|patch)\s*\(",
        r"\bfetch\s*\(",
        r"\bHttpClient\b",
        r"\bRestTemplate\b",
        r"\bWebClient\b",
        r"\bhttpx\.",
        r"\burllib\.(request|parse)\b",
        r"\bnet/http\b",
    ),
    "DATABASE": (
        r"\bjdbc\b",
        r"\bpostgresql\b",
        r"\bmysql\b",
        r"\bsequelize\b",
        r"\bprisma\b",
        r"\bsqlalchemy\b",
        r"\bhibernate\b",
        r"\bjakarta\.persistence\b",
        r"\bselect\b.{0,120}\bfrom\b",
    ),
    "FILESYSTEM": (
        r"\bopen\s*\(",
        r"\bPath\s*\(",
        r"\bos\.path\.",
        r"\breadFile\b",
        r"\bwriteFile\b",
        r"\bupload\b",
        r"\bdownload\b",
    ),
    "AUTH": (
        r"\bjwt\b",
        r"\boauth\b",
        r"\brefresh[_-]?token\b",
        r"\bsession\b",
        r"\bauthentication\b",
        r"\bauthorization\b",
        r"\bpassword\b",
    ),
    "CRYPTO": (
        r"\bcryptography\b",
        r"\bhashlib\b",
        r"\bbcrypt\b",
        r"\bargon2\b",
        r"\bsha(1|224|256|384|512)\b",
    ),
    "SERIALIZATION": (
        r"\bjson\.",
        r"\byaml\b",
        r"\bxml\b",
        r"\bpickle\b",
        r"\bdeserialize\b",
        r"\bserialize\b",
    ),
    "PROCESS_EXECUTION": (
        r"\bsubprocess\b",
        r"\bos\.system\s*\(",
        r"\bProcessBuilder\b",
        r"\bRuntime\.getRuntime\b",
        r"\bchild_process\b",
        r"\bexec\s*\(",
    ),
    "EXTERNAL_SERVICES": (
        r"\bwebhook\b",
        r"\bs3\b",
        r"\bstripe\b",
        r"\bslack\b",
        r"\bgithub\b",
        r"\bsendgrid\b",
    ),
}


def _read_text(snapshot: DiscoverySnapshot, path: str, limit: int = 48_000) -> str:
    try:
        return (snapshot.root / path).read_text(
            encoding="utf-8", errors="replace"
        )[:limit]
    except OSError:
        return ""


def _all_text(snapshot: DiscoverySnapshot, classifications: Iterable[FileClassification]) -> str:
    chunks = []
    for item in classifications:
        if item.kind in {FileKind.GENERATED, FileKind.UNKNOWN, FileKind.DOCUMENTATION}:
            continue
        text = _read_text(snapshot, item.path)
        if text:
            chunks.append(text)
    return "\n".join(chunks)


def classify_technology_surfaces(
    snapshot: DiscoverySnapshot,
    classifications: Tuple[FileClassification, ...],
) -> Tuple[str, ...]:
    paths = {item.path.lower() for item in snapshot.files}
    text = _all_text(snapshot, classifications).lower()
    surfaces = set()

    if any(re.search(pattern, text) for pattern in _SURFACE_PATTERNS["HTTP"]):
        surfaces.add("HTTP")
        surfaces.add("NETWORK")
    if any(re.search(pattern, text) for pattern in _SURFACE_PATTERNS["DATABASE"]) or any(
        item.kind == FileKind.DATABASE for item in classifications
    ):
        surfaces.add("DATABASE")
    if any(re.search(pattern, text) for pattern in _SURFACE_PATTERNS["FILESYSTEM"]) or any(
        token in path for path in paths for token in ("/upload", "/download", "/attachment")
    ):
        surfaces.add("FILESYSTEM")
    if any(re.search(pattern, text) for pattern in _SURFACE_PATTERNS["AUTH"]):
        surfaces.add("AUTH")
    if any(re.search(pattern, text) for pattern in _SURFACE_PATTERNS["CRYPTO"]):
        surfaces.add("CRYPTO")
    if any(re.search(pattern, text) for pattern in _SURFACE_PATTERNS["SERIALIZATION"]):
        surfaces.add("SERIALIZATION")
    if any(re.search(pattern, text) for pattern in _SURFACE_PATTERNS["PROCESS_EXECUTION"]):
        surfaces.add("PROCESS_EXECUTION")
    if any(re.search(pattern, text) for pattern in _SURFACE_PATTERNS["EXTERNAL_SERVICES"]):
        surfaces.add("EXTERNAL_SERVICES")
        surfaces.add("NETWORK")

    if any(item.kind == FileKind.INFRASTRUCTURE for item in classifications):
        surfaces.add("CONTAINERS")

    return tuple(sorted(surfaces))


def _application(
    classifications: Tuple[FileClassification, ...],
    technology_surfaces: Tuple[str, ...],
    text: str,
) -> str:
    frontend = any(
        Path(item.path).suffix.lower() in {".html", ".jsx", ".tsx", ".vue", ".svelte"}
        for item in classifications
    )
    backend = any(
        token in text.lower()
        for token in (
            "flask", "django", "fastapi", "express", "spring boot",
            "springframework", "app.listen", "http.server",
        )
    )
    cli = bool(re.search(r"\b(argparse|click|typer|commander)\b", text, re.IGNORECASE))

    if frontend and backend:
        return "FULLSTACK"
    if frontend:
        return "WEB_FRONTEND"
    if backend:
        return "WEB_BACKEND"
    if cli:
        return "CLI"
    return "LIBRARY"


def _persistence(stack: Tuple[str, ...], surfaces: Tuple[str, ...]) -> str:
    if "POSTGRESQL" in stack:
        return "POSTGRESQL"
    if "MYSQL" in stack:
        return "MYSQL"
    if "MONGO" in stack:
        return "MONGO"
    if "REDIS" in stack:
        return "REDIS"
    if "DATABASE" in surfaces:
        return "UNKNOWN_DATABASE"
    return "NONE"


def _auth(text: str) -> str:
    lower = text.lower()
    if "oauth2" in lower or "oauth" in lower:
        return "OAUTH2"
    if "jwt" in lower:
        return "JWT"
    if "session" in lower and any(token in lower for token in ("login", "authenticate", "auth")):
        return "SESSION"
    if any(token in lower for token in ("authenticate", "authentication", "password")):
        return "CUSTOM_OR_UNKNOWN"
    return "NONE"


def _network(text: str, surfaces: Tuple[str, ...]) -> str:
    lower = text.lower()
    inbound = any(
        token in lower
        for token in ("app.listen", "@restcontroller", "flask(", "django", "fastapi")
    )
    outbound = "HTTP" in surfaces or "EXTERNAL_SERVICES" in surfaces
    if inbound and outbound:
        return "INBOUND_AND_OUTBOUND"
    if inbound:
        return "INBOUND_HTTP"
    if outbound:
        return "OUTBOUND_REST"
    return "NONE"


def _complexity(file_count: int, source_count: int) -> str:
    weighted = file_count + source_count
    if weighted <= 20:
        return "LOW"
    if weighted <= 100:
        return "MEDIUM"
    if weighted <= 500:
        return "HIGH"
    return "CRITICAL"


def profile_project(
    snapshot: DiscoverySnapshot,
    classifications: Tuple[FileClassification, ...],
    stack: Tuple[str, ...],
) -> ProjectProfile:
    text = _all_text(snapshot, classifications)
    surfaces = classify_technology_surfaces(snapshot, classifications)
    source_count = sum(
        1 for item in classifications if item.kind in {FileKind.SOURCE, FileKind.TEST}
    )
    frontend = "WEB" if any(
        Path(item.path).suffix.lower() in {".html", ".jsx", ".tsx", ".vue", ".svelte"}
        for item in classifications
    ) else "NONE"
    container = "DOCKER" if any(
        Path(item.path).name.lower() in {
            "dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"
        }
        for item in classifications
    ) else ("KUBERNETES" if any("/k8s/" in f"/{item.path.lower()}/" for item in classifications) else "NONE")
    ci = "GITHUB_ACTIONS" if any(
        item.path.lower().startswith(".github/workflows/")
        for item in classifications
    ) else ("GITLAB_CI" if any(item.path.lower().startswith(".gitlab/") for item in classifications) else "NONE")

    risks = []
    if "DATABASE" in surfaces:
        risks.append("DATABASE")
    if "FILESYSTEM" in surfaces:
        risks.append("FILESYSTEM")
    if "PROCESS_EXECUTION" in surfaces:
        risks.append("PROCESS_EXECUTION")
    if "NETWORK" in surfaces or "HTTP" in surfaces:
        risks.append("NETWORK")

    payload = {
        "complexity": _complexity(len(snapshot.files), source_count),
        "application": _application(classifications, surfaces, text),
        "persistence": _persistence(stack, surfaces),
        "network": _network(text, surfaces),
        "auth": _auth(text),
        "frontend": frontend,
        "container": container,
        "ci": ci,
        "risk_surfaces": sorted(set(risks)),
        "technology_surfaces": list(surfaces),
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return ProjectProfile(
        complexity=payload["complexity"],
        application=payload["application"],
        persistence=payload["persistence"],
        network=payload["network"],
        auth=payload["auth"],
        frontend=payload["frontend"],
        container=payload["container"],
        ci=payload["ci"],
        risk_surfaces=tuple(payload["risk_surfaces"]),
        technology_surfaces=surfaces,
        fingerprint=fingerprint,
    )


def build_classification_results(
    snapshot: DiscoverySnapshot,
    classifications: Tuple[FileClassification, ...],
    stack: Tuple[str, ...],
    applicability: Tuple[ApplicabilityDecision, ...],
    work_items: Iterable[object],
    profile: ProjectProfile,
) -> Tuple[ClassificationResult, ...]:
    results = []

    file_refs = tuple(item.path for item in classifications)
    results.append(
        ClassificationResult(
            "file-classifier",
            "1",
            file_refs,
            "CLASSIFIED",
            "HIGH",
            f"Classified {len(classifications)} discovered file(s) deterministically.",
        )
    )
    results.append(
        ClassificationResult(
            "stack-classifier",
            "1",
            file_refs,
            ",".join(stack) or "NONE",
            "HIGH",
            "Technology stack derived from repository manifests and deterministic source signals.",
        )
    )
    results.append(
        ClassificationResult(
            "technology-surface-classifier",
            "1",
            file_refs,
            ",".join(profile.technology_surfaces) or "NONE",
            "HIGH",
            "Technology surfaces derived from deterministic path/content signatures.",
        )
    )
    results.append(
        ClassificationResult(
            "project-profile-classifier",
            "1",
            file_refs,
            profile.application,
            "HIGH",
            "Project profile is an aggregate of deterministic file, stack, and surface signals.",
        )
    )

    for decision in sorted(applicability, key=lambda item: (item.category, item.subcategory)):
        refs = tuple(decision.evidence_paths)
        results.append(
            ClassificationResult(
                f"applicability:{decision.category.lower()}:{decision.subcategory.lower()}",
                "1",
                refs,
                decision.state.value,
                "HIGH" if decision.state != ApplicabilityState.NOT_DETERMINABLE else "MEDIUM",
                decision.reason,
            )
        )

    for work_item in sorted(
        tuple(work_items),
        key=lambda item: str(getattr(item, "target_surface", "")),
    ):
        classification: TaskClassification = classify_task(
            "Audit " + str(work_item.target_surface)
        )
        results.append(
            ClassificationResult(
                "task-classifier",
                "1",
                (str(work_item.target_surface),),
                classification.kind.value,
                "HIGH",
                classification.reason,
            )
        )

    return tuple(results)
