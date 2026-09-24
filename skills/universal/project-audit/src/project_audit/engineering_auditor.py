from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

from .classifiers import FileClassification, FileKind, classify_files, classify_stack
from .discovery import DiscoverySnapshot


@dataclass(frozen=True)
class Observation:
    code: str
    category: str
    subcategory: str
    state: str
    summary: str
    source_refs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class EngineeringInspectionResult:
    work_item_ref: str
    target_surface: str
    observations: Tuple[Observation, ...]
    source_refs: Tuple[str, ...]
    fingerprint: str

    def to_markdown(self) -> str:
        lines = [f"## {self.target_surface}", ""]
        for observation in self.observations:
            lines.append(f"### {observation.code}")
            lines.append(f"- State: {observation.state}")
            lines.append(f"- {observation.summary}")
            if observation.source_refs:
                lines.append(f"- Sources: {', '.join(observation.source_refs)}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def _read_text(snapshot: DiscoverySnapshot, path: str, limit: int = 128_000) -> str:
    try:
        raw = (snapshot.root / path).read_bytes()[:limit]
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace")


def _refs(items: Iterable[FileClassification], *kinds: FileKind) -> Tuple[str, ...]:
    wanted = set(kinds)
    return tuple(item.path for item in items if item.kind in wanted)


def _inspect_surface(
    snapshot: DiscoverySnapshot,
    work_item_ref: str,
    target_surface: str,
    classifications: Tuple[FileClassification, ...],
) -> EngineeringInspectionResult:
    category, _, subcategory = target_surface.partition("/")
    observations = []
    source_refs = ()

    by_kind = {
        FileKind.SOURCE: _refs(classifications, FileKind.SOURCE),
        FileKind.TEST: _refs(classifications, FileKind.TEST),
        FileKind.BUILD: _refs(classifications, FileKind.BUILD),
        FileKind.DATABASE: _refs(classifications, FileKind.DATABASE),
        FileKind.CONFIG: _refs(classifications, FileKind.CONFIG),
        FileKind.DOCUMENTATION: _refs(classifications, FileKind.DOCUMENTATION),
        FileKind.INFRASTRUCTURE: _refs(classifications, FileKind.INFRASTRUCTURE),
        FileKind.CI_CD: _refs(classifications, FileKind.CI_CD),
        FileKind.GIT: _refs(classifications, FileKind.GIT),
    }

    if category == "ARCHITECTURE":
        source_refs = by_kind[FileKind.SOURCE]
        top_levels = sorted({path.split("/", 1)[0] for path in source_refs})
        observations.append(
            Observation(
                "ARCH-INV-001",
                category,
                subcategory,
                "OBSERVED" if source_refs else "NOT_DETERMINABLE",
                "Source inventory contains "
                f"{len(source_refs)} source file(s) across top-level areas: "
                f"{', '.join(top_levels[:12]) if top_levels else 'none'}.",
                source_refs[:20],
            )
        )
        if source_refs:
            layer_tokens = ("controller", "service", "domain", "repository", "dao", "infra", "adapter")
            layered = tuple(
                path for path in source_refs
                if any(token in path.lower().split("/") for token in layer_tokens)
            )
            observations.append(
                Observation(
                    "ARCH-INV-002",
                    category,
                    subcategory,
                    "OBSERVED" if layered else "NOT_FOUND",
                    "Deterministic layer/path signals "
                    + ("were found." if layered else "were not found; this does not establish architectural absence."),
                    layered[:20],
                )
            )

    elif category == "CODE_QUALITY":
        source_refs = by_kind[FileKind.SOURCE]
        todo_refs = []
        broad_exception_refs = []
        for path in source_refs:
            text = _read_text(snapshot, path)
            if "TODO" in text or "FIXME" in text:
                todo_refs.append(path)
            if "except Exception:" in text or "catch (Exception" in text:
                broad_exception_refs.append(path)
        observations.extend(
            [
                Observation(
                    "CODE-INV-001",
                    category,
                    subcategory,
                    "OBSERVED",
                    f"{len(source_refs)} source file(s) classified for engineering review.",
                    source_refs[:20],
                ),
                Observation(
                    "CODE-INV-002",
                    category,
                    subcategory,
                    "OBSERVED" if todo_refs else "NOT_FOUND",
                    (
                        f"TODO/FIXME markers were found in {len(todo_refs)} source file(s)."
                        if todo_refs
                        else "No TODO/FIXME markers were found in the inspected source files."
                    ),
                    tuple(todo_refs[:20]),
                ),
                Observation(
                    "CODE-INV-003",
                    category,
                    subcategory,
                    "OBSERVED" if broad_exception_refs else "NOT_FOUND",
                    (
                        f"Broad exception handlers were found in {len(broad_exception_refs)} source file(s)."
                        if broad_exception_refs
                        else "No broad exception handlers matched the deterministic patterns."
                    ),
                    tuple(broad_exception_refs[:20]),
                ),
            ]
        )

    elif category == "DATABASE":
        source_refs = by_kind[FileKind.DATABASE]
        stack = classify_stack(snapshot)
        if source_refs:
            constraint_signals = []
            for path in source_refs:
                text = _read_text(snapshot, path).lower()
                if any(token in text for token in ("primary key", "foreign key", "unique", "check constraint")):
                    constraint_signals.append(path)
            observations.extend(
                [
                    Observation(
                        "DB-INV-001",
                        category,
                        subcategory,
                        "OBSERVED",
                        f"{len(source_refs)} database artifact(s) were found; persistence signals: {', '.join(stack) or 'not detected'}.",
                        source_refs[:20],
                    ),
                    Observation(
                        "DB-INV-002",
                        category,
                        subcategory,
                        "OBSERVED" if constraint_signals else "NOT_FOUND",
                        (
                            f"Schema constraint declarations were found in {len(constraint_signals)} artifact(s)."
                            if constraint_signals
                            else "No constraint declarations matched the deterministic patterns."
                        ),
                        tuple(constraint_signals[:20]),
                    ),
                ]
            )
        else:
            observations.append(
                Observation(
                    "DB-INV-001",
                    category,
                    subcategory,
                    "NOT_DETERMINABLE",
                    "No SQL/schema artifacts were classified; persistence may still exist through code or configuration.",
                )
            )

    elif category == "BUILD":
        source_refs = by_kind[FileKind.BUILD]
        observations.append(
            Observation(
                "BUILD-INV-001",
                category,
                subcategory,
                "OBSERVED" if source_refs else "NOT_DETERMINABLE",
                f"Detected {len(source_refs)} build/dependency manifest(s): {', '.join(source_refs) if source_refs else 'none'}.",
                source_refs,
            )
        )

    elif category == "TESTING":
        source_refs = by_kind[FileKind.TEST]
        observations.append(
            Observation(
                "TEST-INV-001",
                category,
                subcategory,
                "OBSERVED" if source_refs else "NOT_FOUND",
                f"Detected {len(source_refs)} test file(s)." if source_refs else "No test files matched deterministic naming/path rules.",
                source_refs[:30],
            )
        )
        if source_refs:
            frameworks = []
            for path in source_refs:
                text = _read_text(snapshot, path, 32_000).lower()
                for token in ("pytest", "junit", "assertj", "unittest", "vitest", "jest"):
                    if token in text and token not in frameworks:
                        frameworks.append(token)
            observations.append(
                Observation(
                    "TEST-INV-002",
                    category,
                    subcategory,
                    "OBSERVED" if frameworks else "NOT_FOUND",
                    "Test framework signals: " + (", ".join(frameworks) if frameworks else "none detected"),
                    source_refs[:12],
                )
            )

    elif category == "CI_CD":
        source_refs = by_kind[FileKind.CI_CD]
        observations.append(
            Observation(
                "CI-INV-001",
                category,
                subcategory,
                "OBSERVED" if source_refs else "NOT_FOUND",
                f"Detected {len(source_refs)} CI configuration file(s)." if source_refs else "No CI configuration files matched the deterministic paths.",
                source_refs[:30],
            )
        )

    elif category == "DOCUMENTATION":
        source_refs = by_kind[FileKind.DOCUMENTATION]
        observations.append(
            Observation(
                "DOC-INV-001",
                category,
                subcategory,
                "OBSERVED" if source_refs else "NOT_FOUND",
                f"Detected {len(source_refs)} documentation artifact(s).",
                source_refs[:30],
            )
        )
        readmes = [path for path in source_refs if Path(path).name.lower().startswith("readme")]
        if readmes:
            text = _read_text(snapshot, readmes[0], 64_000).lower()
            sections = [
                token
                for token in ("install", "usage", "configuration", "test", "architecture")
                if token in text
            ]
            observations.append(
                Observation(
                    "DOC-INV-002",
                    category,
                    subcategory,
                    "OBSERVED" if sections else "NOT_FOUND",
                    "README operational sections detected: " + (", ".join(sections) if sections else "none"),
                    tuple(readmes),
                )
            )

    elif category == "INFRASTRUCTURE":
        source_refs = by_kind[FileKind.INFRASTRUCTURE]
        observations.append(
            Observation(
                "INFRA-INV-001",
                category,
                subcategory,
                "OBSERVED" if source_refs else "NOT_FOUND",
                f"Detected {len(source_refs)} infrastructure/container artifact(s).",
                source_refs[:30],
            )
        )

    elif category == "CONFIGURATION":
        source_refs = by_kind[FileKind.CONFIG]
        observations.append(
            Observation(
                "CONFIG-INV-001",
                category,
                subcategory,
                "OBSERVED" if source_refs else "NOT_FOUND",
                f"Detected {len(source_refs)} configuration artifact(s).",
                source_refs[:30],
            )
        )

    elif category == "SECURITY":
        observations.append(
            Observation(
                "SEC-NOT-PASS1",
                category,
                subcategory,
                "NOT_INSPECTED",
                "Security surfaces are reserved for PASS 2 and are not interpreted by the engineering auditor.",
            )
        )

    else:
        observations.append(
            Observation(
                "ENG-INV-001",
                category,
                subcategory,
                "NOT_DETERMINABLE",
                "No engineering inspection handler exists yet for this surface.",
            )
        )

    canonical = {
        "work_item_ref": work_item_ref,
        "target_surface": target_surface,
        "observations": [
            {
                "code": item.code,
                "category": item.category,
                "subcategory": item.subcategory,
                "state": item.state,
                "summary": item.summary,
                "source_refs": list(item.source_refs),
            }
            for item in observations
        ],
    }
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fingerprint = hashlib.sha256(raw).hexdigest()
    return EngineeringInspectionResult(
        work_item_ref=work_item_ref,
        target_surface=target_surface,
        observations=tuple(observations),
        source_refs=source_refs,
        fingerprint=fingerprint,
    )


class EngineeringAuditor:
    """Deterministic PASS 1 auditor for the single-agent product."""

    ACTOR = "project-audit/single-agent/engineering-v1"

    def inspect(
        self,
        snapshot: DiscoverySnapshot,
        work_item_ref: str,
        target_surface: str,
    ) -> EngineeringInspectionResult:
        return _inspect_surface(
            snapshot,
            work_item_ref,
            target_surface,
            classify_files(snapshot),
        )
