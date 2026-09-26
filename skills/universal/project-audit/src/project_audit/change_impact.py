"""Deterministic Change Impact analysis for incremental audits.

Phase 11 computes inter-snapshot change events from canonical TargetSnapshot
input fingerprints. It does not invoke LLMs and does not mutate audit state.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional, Tuple

from .incremental import normalize_input_ref


class ChangeKind(str, Enum):
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"
    DEPENDENCY_CHANGE = "DEPENDENCY_CHANGE"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    METHODOLOGY_CHANGE = "METHODOLOGY_CHANGE"


@dataclass(frozen=True)
class ChangeEvent:
    kind: ChangeKind
    path: str
    old_path: Optional[str] = None
    old_fingerprint: Optional[str] = None
    new_fingerprint: Optional[str] = None
    qualifiers: Tuple[ChangeKind, ...] = ()

    @property
    def all_kinds(self) -> Tuple[ChangeKind, ...]:
        return (self.kind,) + tuple(self.qualifiers)


@dataclass(frozen=True)
class EvidenceImpact:
    source_paths: Tuple[str, ...]
    dependency_paths: Tuple[str, ...]
    change_kinds: Tuple[ChangeKind, ...]

    @property
    has_source_impact(self) -> bool:
        return bool(self.source_paths)

    @property
    has_dependency_impact(self) -> bool:
        return bool(self.dependency_paths)


@dataclass(frozen=True)
class ChangeImpact:
    previous_snapshot_ref: str
    current_snapshot_ref: str
    events: Tuple[ChangeEvent, ...]
    rename_map: Mapping[str, str]

    @property
    methodology_changed(self) -> bool:
        return any(event.kind == ChangeKind.METHODOLOGY_CHANGE for event in self.events)

    @property
    changed_paths(self) -> Tuple[str, ...]:
        values = set()
        for event in self.events:
            values.add(event.path)
            if event.old_path:
                values.add(event.old_path)
        return tuple(sorted(values))

    def impact_for_evidence(self, source_refs, dependencies) -> EvidenceImpact:
        source_hits = set()
        dependency_hits = set()
        kinds = set()
        by_path = {}
        for event in self.events:
            by_path.setdefault(event.path, []).append(event)
            if event.old_path:
                by_path.setdefault(event.old_path, []).append(event)

        for ref in source_refs:
            key = normalize_input_ref(ref)
            for event in by_path.get(key, ()):
                source_hits.add(key)
                kinds.update(event.all_kinds)
        for ref in dependencies:
            key = normalize_input_ref(ref)
            for event in by_path.get(key, ()):
                dependency_hits.add(key)
                kinds.update(event.all_kinds)

        return EvidenceImpact(
            source_paths=tuple(sorted(source_hits)),
            dependency_paths=tuple(sorted(dependency_hits)),
            change_kinds=tuple(sorted(kinds, key=lambda item: item.value)),
        )


def _snapshot_inputs(snapshot) -> Mapping[str, str]:
    return {
        item.path.replace("\\\\", "/").lstrip("./"): item.fingerprint
        for item in snapshot.project_state.tracked_input_fingerprints
    }


def _path_qualifiers(path: str) -> Tuple[ChangeKind, ...]:
    lower = path.lower().replace("\\", "/")
    name = lower.rsplit("/", 1)[-1]
    dependency_names = {
        "package.json", "package-lock.json", "npm-shrinkwrap.json",
        "pnpm-lock.yaml", "yarn.lock", "pyproject.toml", "poetry.lock",
        "requirements.txt", "pipfile", "pipfile.lock", "pom.xml",
        "build.gradle", "build.gradle.kts", "gradle.lockfile",
        "cargo.toml", "cargo.lock", "go.mod", "go.sum",
    }
    config_suffixes = (".yml", ".yaml", ".toml", ".ini", ".properties", ".env")
    if name in dependency_names or name.endswith(".lock"):
        return (ChangeKind.DEPENDENCY_CHANGE,)
    if lower.startswith(".github/workflows/") or lower.startswith(".gitlab/") or name in {"dockerfile", "compose.yml", "compose.yaml", "docker-compose.yml", "docker-compose.yaml"}:
        return (ChangeKind.CONFIG_CHANGE,)
    if name.endswith(config_suffixes):
        return (ChangeKind.CONFIG_CHANGE,)
    return ()


def build_change_impact(previous_snapshot, current_snapshot) -> ChangeImpact:
    """Compute a deterministic, immutable impact report between snapshots."""
    previous = _snapshot_inputs(previous_snapshot)
    current = _snapshot_inputs(current_snapshot)
    events = []

    added = set(current) - set(previous)
    deleted = set(previous) - set(current)

    # A rename is proven only when one deleted path and one added path share a
    # fingerprint uniquely. Ambiguous matches remain ADDED/DELETED.
    old_by_fp = {}
    new_by_fp = {}
    for path in deleted:
        old_by_fp.setdefault(previous[path], []).append(path)
    for path in added:
        new_by_fp.setdefault(current[path], []).append(path)
    rename_map = {}
    renamed_old = set()
    renamed_new = set()
    for fingerprint, old_paths in old_by_fp.items():
        new_paths = new_by_fp.get(fingerprint, [])
        if len(old_paths) == 1 and len(new_paths) == 1:
            old_path = old_paths[0]
            new_path = new_paths[0]
            rename_map[old_path] = new_path
            renamed_old.add(old_path)
            renamed_new.add(new_path)
            events.append(ChangeEvent(
                kind=ChangeKind.RENAMED,
                path=new_path,
                old_path=old_path,
                old_fingerprint=fingerprint,
                new_fingerprint=fingerprint,
                qualifiers=_path_qualifiers(new_path),
            ))

    for path in sorted(added - renamed_new):
        events.append(ChangeEvent(
            kind=ChangeKind.ADDED,
            path=path,
            new_fingerprint=current[path],
            qualifiers=_path_qualifiers(path),
        ))
    for path in sorted(deleted - renamed_old):
        events.append(ChangeEvent(
            kind=ChangeKind.DELETED,
            path=path,
            old_fingerprint=previous[path],
            qualifiers=_path_qualifiers(path),
        ))
    for path in sorted(set(previous).intersection(current)):
        if previous[path] != current[path]:
            events.append(ChangeEvent(
                kind=ChangeKind.MODIFIED,
                path=path,
                old_fingerprint=previous[path],
                new_fingerprint=current[path],
                qualifiers=_path_qualifiers(path),
            ))

    if (
        previous_snapshot.methodology_state.audit_contract_version
        != current_snapshot.methodology_state.audit_contract_version
        or previous_snapshot.methodology_state.policy_version
        != current_snapshot.methodology_state.policy_version
        or dict(previous_snapshot.methodology_state.auditor_versions)
        != dict(current_snapshot.methodology_state.auditor_versions)
    ):
        events.append(ChangeEvent(
            kind=ChangeKind.METHODOLOGY_CHANGE,
            path="methodology:*",
        ))

    return ChangeImpact(
        previous_snapshot_ref=previous_snapshot.snapshot_fingerprint,
        current_snapshot_ref=current_snapshot.snapshot_fingerprint,
        events=tuple(sorted(events, key=lambda item: (item.path, item.kind.value, item.old_path or ""))),
        rename_map=dict(sorted(rename_map.items())),
    )