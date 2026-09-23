from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from .classifiers import FileClassification, FileKind, classify_files
from .discovery import DiscoverySnapshot


@dataclass(frozen=True)
class ContextItem:
    path: str
    content: str
    sha256: str


@dataclass(frozen=True)
class ContextBundle:
    task: str
    target_surface: str
    items: Tuple[ContextItem, ...]
    fingerprint: str


def _read(snapshot: DiscoverySnapshot, path: str, limit: int) -> str:
    try:
        return (snapshot.root / path).read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _score(path: str, classification: FileClassification, category: str, subcategory: str) -> int:
    lower = path.lower()
    score = 0

    if classification.kind == FileKind.SOURCE:
        score += 30
    if classification.kind == FileKind.DATABASE:
        score += 25 if category == "DATABASE" or subcategory == "SQL_INJECTION" else 5
    if classification.kind == FileKind.TEST:
        score += 25 if category == "TESTING" else 2
    if classification.kind == FileKind.BUILD:
        score += 30 if category in {"BUILD", "CI_CD"} else 5
    if classification.kind == FileKind.CI_CD:
        score += 35 if category == "CI_CD" else 0
    if classification.kind == FileKind.INFRASTRUCTURE:
        score += 30 if category == "INFRASTRUCTURE" or category == "CI_CD" else 5
    if classification.kind == FileKind.CONFIG:
        score += 20

    keyword_map = {
        "SQL_INJECTION": ("dao", "repository", "jdbc", "query", "sql"),
        "SSRF": ("http", "client", "request", "web", "url"),
        "XSS": ("html", "template", "view", "frontend", "component", "jsx", "tsx"),
        "AUTHENTICATION": ("auth", "login", "jwt", "oauth", "session", "security"),
        "AUTHORIZATION": ("auth", "role", "permission", "owner", "tenant", "policy"),
        "FILE_SECURITY": ("upload", "download", "file", "path", "attachment"),
        "DATABASE": ("database", "schema", "migration", "sql", "repository", "dao"),
        "ARCHITECTURE": ("controller", "service", "domain", "repository", "adapter", "infra"),
        "TEST_SUITE": ("test", "spec"),
        "PIPELINE": (".github/workflows", "gitlab", "docker"),
    }
    for token in keyword_map.get(subcategory, ()):
        if token in lower:
            score += 10

    return score


def build_context(
    snapshot: DiscoverySnapshot,
    target_surface: str,
    *,
    max_files: int = 12,
    max_bytes_per_file: int = 24_000,
) -> ContextBundle:
    category, _, subcategory = target_surface.partition("/")
    classifications = classify_files(snapshot)
    candidates = [
        item
        for item in classifications
        if item.kind not in {FileKind.GENERATED, FileKind.UNKNOWN}
        and not item.path.startswith(".git/")
    ]

    ranked = sorted(
        candidates,
        key=lambda item: (-_score(item.path, item, category, subcategory), item.path),
    )

    items: List[ContextItem] = []
    for classification in ranked[:max_files]:
        record = snapshot.file(classification.path)
        if record is None or record.sha256 is None:
            continue
        content = _read(snapshot, classification.path, max_bytes_per_file)
        if not content:
            continue
        items.append(
            ContextItem(
                path=classification.path,
                content=content,
                sha256=record.sha256,
            )
        )

    canonical = {
        "target_surface": target_surface,
        "items": [
            {"path": item.path, "sha256": item.sha256, "content": item.content}
            for item in items
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return ContextBundle(
        task="Audit " + target_surface,
        target_surface=target_surface,
        items=tuple(items),
        fingerprint=fingerprint,
    )
