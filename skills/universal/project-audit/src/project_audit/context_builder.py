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


def _relationship_refs(content: str) -> Tuple[str, ...]:
    """Extract deterministic relationship references from source text."""
    refs = set()

    for match in re.findall(
        r"^\s*(?:import|using)\s+(?:static\s+)?([A-Za-z_][A-Za-z0-9_.]*)",
        content,
        flags=re.MULTILINE,
    ):
        refs.add(match)

    for match in re.findall(
        r"^\s*from\s+([A-Za-z_][A-Za-z0-9_.]*)\s+import\s+([A-Za-z_][A-Za-z0-9_,*\s]*)",
        content,
        flags=re.MULTILINE,
    ):
        module, imported = match
        refs.add(module)
        for symbol in imported.split(","):
            symbol = symbol.strip().split(" as ", 1)[0].strip()
            if symbol and symbol != "*":
                refs.add(symbol)
                refs.add(module + "." + symbol)

    for pattern in (
        r"\bnew\s+([A-Z][A-Za-z0-9_]*)",
        r"\b([A-Z][A-Za-z0-9_]*(?:Service|Repository|Controller|Client|Provider|Manager|Gateway|Dao|Store|Handler|UseCase))\s+[a-z_][A-Za-z0-9_]*\b",
        r"\b([A-Z][A-Za-z0-9_]*)::[A-Za-z_][A-Za-z0-9_]*",
    ):
        refs.update(re.findall(pattern, content))

    return tuple(sorted(refs))


def _relationship_indexes(
    candidates: List[FileClassification],
) -> Tuple[dict, dict]:
    """Build exact normalized path/stem indexes for symbol resolution."""
    by_path = {
        item.path.lower().replace("\\\\", "/"): item.path
        for item in candidates
    }
    by_stem = {}
    for item in candidates:
        stem = Path(item.path).stem.lower()
        by_stem.setdefault(stem, []).append(item.path)
    return by_path, by_stem


def _resolve_relationship_refs(
    refs: Tuple[str, ...],
    *,
    by_path: dict,
    by_stem: dict,
) -> Tuple[str, ...]:
    """Resolve FQNs/modules and exact symbols to repository files.

    Resolution is intentionally narrow: exact normalized path/module matches
    and exact unique filename stems only. No substring or fuzzy matching is
    used, which avoids collisions such as UserService/UserServiceTest.
    """
    resolved = set()
    known_suffixes = (".py", ".java", ".kt", ".kts", ".scala", ".go", ".ts", ".tsx", ".js", ".jsx", ".cs", ".rb", ".rs")

    for ref in refs:
        clean = ref.strip().strip(";")
        if not clean:
            continue

        dotted = clean.replace("::", ".")
        slash = dotted.replace(".", "/").strip("/").lower()
        if slash:
            for suffix in known_suffixes:
                candidate = slash + suffix
                if candidate in by_path:
                    resolved.add(by_path[candidate])
            init_path = slash + "/__init__.py"
            if init_path in by_path:
                resolved.add(by_path[init_path])

        symbol = clean.rsplit(".", 1)[-1].rsplit("::", 1)[-1]
        matches = by_stem.get(symbol.lower(), ())
        if len(matches) == 1:
            resolved.add(matches[0])

    return tuple(sorted(resolved))


def _relationship_paths(
    snapshot: DiscoverySnapshot,
    classification: FileClassification,
    candidates: List[FileClassification],
    *,
    max_bytes_per_file: int,
    by_path: dict,
    by_stem: dict,
) -> Tuple[str, ...]:
    content = _read(snapshot, classification.path, max_bytes_per_file)
    if not content:
        return ()
    refs = _relationship_refs(content)
    return _resolve_relationship_refs(refs, by_path=by_path, by_stem=by_stem)


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

    # Bounded breadth-first expansion: select the strongest seed, resolve
    # exact relationships from that file, consume the relationship frontier
    # before falling back to global score ranking, and stop at the same hard
    # file/byte limits as the legacy selector.
    ranked = sorted(
        candidates,
        key=lambda item: (-base_scores[item.path], item.path),
    )
    by_path, by_stem = _relationship_indexes(candidates)

    selected: List[ContextItem] = []
    selected_paths = set()
    total_bytes = 0

    # frontier[path] = (graph_depth, parent_rank, base_score)
    frontier = {}
    next_seed_index = 0
    relation_depth = {}

    def add_relationships(source_path: str, depth: int, parent_rank: int) -> None:
        source = next(
            (item for item in candidates if item.path == source_path),
            None,
        )
        if source is None:
            return
        for related_path in _relationship_paths(
            snapshot,
            source,
            candidates,
            max_bytes_per_file=max_bytes_per_file,
            by_path=by_path,
            by_stem=by_stem,
        ):
            if related_path in selected_paths:
                continue
            candidate_depth = depth + 1
            previous_depth = relation_depth.get(related_path)
            if previous_depth is not None and previous_depth <= candidate_depth:
                continue
            relation_depth[related_path] = candidate_depth
            related_score = base_scores[related_path]
            frontier[related_path] = (
                candidate_depth,
                parent_rank,
                related_score,
            )

    while len(selected) < max_files:
        chosen = None

        if frontier:
            chosen_path = min(
                frontier,
                key=lambda item: (
                    frontier[item][0],
                    -frontier[item][2],
                    frontier[item][1],
                    item,
                ),
            )
            chosen = next(
                item for item in candidates if item.path == chosen_path
            )
            frontier.pop(chosen_path, None)
        else:
            while next_seed_index < len(ranked) and ranked[next_seed_index].path in selected_paths:
                next_seed_index += 1
            if next_seed_index >= len(ranked):
                break
            chosen = ranked[next_seed_index]
            next_seed_index += 1

        if chosen is None:
            break

        record = snapshot.file(chosen.path)
        if record is None or record.sha256 is None:
            continue
        content = _read(snapshot, chosen.path, max_bytes_per_file)
        if not content:
            continue

        encoded_size = len(content.encode("utf-8"))
        if total_bytes + encoded_size > max_total_bytes:
            remaining = max_total_bytes - total_bytes
            if remaining <= 0:
                break
            content = content.encode("utf-8")[:remaining].decode("utf-8", errors="ignore")

        selected_paths.add(chosen.path)
        selected.append(
            ContextItem(
                path=chosen.path,
                content=content,
                sha256=record.sha256,
            )
        )
        total_bytes += len(content.encode("utf-8"))

        if total_bytes >= max_total_bytes:
            break

        parent_rank = ranked.index(chosen)
        current_depth = relation_depth.get(chosen.path, 0)
        add_relationships(chosen.path, current_depth, parent_rank)

    canonical = {
        "target_surface": target_surface,
        "items": [
            {"path": item.path, "sha256": item.sha256, "content": item.content}
            for item in selected
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return ContextBundle(
        task="Audit " + target_surface,
        target_surface=target_surface,
        items=tuple(selected),
        fingerprint=fingerprint,
    )
