from __future__ import annotations

import hashlib
import json
import re
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


def _relationship_terms(content: str) -> Tuple[str, ...]:
    """Extract deterministic cross-file identifiers used for context expansion."""
    terms = set()
    for pattern in (
        r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"\b(?:from|import)\s+([A-Za-z_][A-Za-z0-9_.]*)",
        r"\bnew\s+([A-Za-z_][A-Za-z0-9_]*)",
    ):
        terms.update(match.lower() for match in re.findall(pattern, content))
    return tuple(sorted(terms))

def build_context(
    snapshot: DiscoverySnapshot,
    target_surface: str,
    *,
    max_files: int = 12,
    max_bytes_per_file: int = 24_000,
    max_total_bytes: int = 96_000,
) -> ContextBundle:
    category, _, subcategory = target_surface.partition("/")
    classifications = classify_files(snapshot)
    candidates = [
        item
        for item in classifications
        if item.kind not in {FileKind.GENERATED, FileKind.UNKNOWN}
        and not item.path.startswith(".git/")
    ]

    base_scores = {
        item.path: _score(item.path, item, category, subcategory)
        for item in candidates
    }

    # Deterministic one-hop context expansion: first rank the strongest files,
    # then reward candidates referenced by their class/import symbols. This
    # keeps the hard max_files/max_total_bytes bounds while improving
    # route -> controller -> service -> DAO style coverage.
    seed_count = min(max_files, 4)
    seeds = sorted(
        candidates,
        key=lambda item: (-base_scores[item.path], item.path),
    )[:seed_count]
    relationship_terms = set()
    for classification in seeds:
        relationship_terms.update(
            _relationship_terms(_read(snapshot, classification.path, max_bytes_per_file // 2))
        )

    relationship_scores = {}
    for classification in candidates:
        lower_path = classification.path.lower()
        stem = Path(lower_path).stem
        basename = Path(lower_path).name
        bonus = 0
        for term in relationship_terms:
            if term and (term in lower_path or term in stem or term in basename):
                bonus += 8
        relationship_scores[classification.path] = min(bonus, 24)

    ranked = sorted(
        candidates,
        key=lambda item: (
            -(base_scores[item.path] + relationship_scores[item.path]),
            item.path,
        ),
    )

    items: List[ContextItem] = []
    total_bytes = 0
    for classification in ranked[:max_files]:
        record = snapshot.file(classification.path)
        if record is None or record.sha256 is None:
            continue
        content = _read(snapshot, classification.path, max_bytes_per_file)
        if not content:
            continue
        encoded_size = len(content.encode("utf-8"))
        if total_bytes + encoded_size > max_total_bytes:
            remaining = max_total_bytes - total_bytes
            if remaining <= 0:
                break
            content = content.encode("utf-8")[:remaining].decode("utf-8", errors="ignore")
        items.append(
            ContextItem(
                path=classification.path,
                content=content,
                sha256=record.sha256,
            )
        )
        total_bytes += len(content.encode("utf-8"))

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
