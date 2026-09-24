from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

from .classifiers import FileClassification, FileKind, classify_files
from .discovery import DiscoverySnapshot


@dataclass(frozen=True)
class SecurityObservation:
    code: str
    subcategory: str
    state: str
    summary: str
    source_refs: Tuple[str, ...] = ()


@dataclass(frozen=True)
class SecurityInspectionResult:
    work_item_ref: str
    target_surface: str
    observations: Tuple[SecurityObservation, ...]
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


def _read_text(snapshot: DiscoverySnapshot, path: str, limit: int = 160_000) -> str:
    try:
        return (snapshot.root / path).read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _scan(
    classifications: Tuple[FileClassification, ...],
    snapshot: DiscoverySnapshot,
    patterns: Tuple[str, ...],
) -> Tuple[str, ...]:
    matches = []
    compiled = tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for item in classifications:
        if item.kind in {FileKind.GENERATED, FileKind.UNKNOWN}:
            continue
        if item.path.startswith(".git/"):
            continue
        text = _read_text(snapshot, item.path)
        if text and any(regex.search(text) for regex in compiled):
            matches.append(item.path)
    return tuple(matches)


def _inspect(
    snapshot: DiscoverySnapshot,
    work_item_ref: str,
    target_surface: str,
    classifications: Tuple[FileClassification, ...],
) -> SecurityInspectionResult:
    _, _, subcategory = target_surface.partition("/")
    observations = []
    refs = ()

    if subcategory == "SQL_INJECTION":
        refs = _scan(
            classifications,
            snapshot,
            (
                r'(?i)(select|insert|update|delete)\b.{0,120}[+][^\n]+',
                r'createStatement\s*\(',
                r'execute\s*\([^)]*\+',
                r'query\s*\([^)]*\+',
            ),
        )
        observations.append(
            SecurityObservation(
                "SEC-SQL-001",
                subcategory,
                "OBSERVED" if refs else "NOT_FOUND",
                (
                    f"Dynamic SQL/query construction signals were found in {len(refs)} file(s); "
                    "this observation does not by itself establish an exploitable injection path."
                    if refs
                    else "No dynamic SQL construction pattern matched the deterministic rules."
                ),
                refs[:30],
            )
        )

    elif subcategory == "XSS":
        refs = _scan(
            classifications,
            snapshot,
            (
                r'innerHTML\s*=',
                r'dangerouslySetInnerHTML',
                r'v-html\b',
                r'javascript:\s*',
                r'eval\s*\(',
                r'new\s+Function\s*\(',
            ),
        )
        observations.append(
            SecurityObservation(
                "SEC-XSS-001",
                subcategory,
                "OBSERVED" if refs else "NOT_FOUND",
                (
                    f"Potential HTML/script sink pattern(s) were found in {len(refs)} file(s); "
                    "input controllability and output encoding require semantic verification."
                    if refs
                    else "No known unsafe HTML/script sink pattern matched the deterministic rules."
                ),
                refs[:30],
            )
        )

    elif subcategory == "SSRF":
        refs = _scan(
            classifications,
            snapshot,
            (
                r'\brequests\.(get|post|put|delete)\s*\(',
                r'\baxios\.(get|post|put|delete)\s*\(',
                r'\bfetch\s*\(',
                r'\bHttpClient\b',
                r'\bRestTemplate\b',
                r'\bWebClient\b',
                r'\bhttpx\.',
                r'\burllib\.(request|parse)\b',
            ),
        )
        observations.append(
            SecurityObservation(
                "SEC-SSRF-001",
                subcategory,
                "OBSERVED" if refs else "NOT_FOUND",
                (
                    f"Server-side HTTP client signal(s) were found in {len(refs)} file(s); "
                    "user-controlled URL flow and destination validation remain to be established."
                    if refs
                    else "No outbound HTTP client pattern matched the deterministic rules."
                ),
                refs[:30],
            )
        )

    elif subcategory == "SECRET_EXPOSURE":
        name_refs = tuple(
            item.path
            for item in snapshot.files
            if Path(item.path).name.lower() in {
                ".env", ".env.local", ".env.production",
                "credentials.json", "secrets.yaml", "secrets.yml",
            }
        )
        pattern_refs = _scan(
            classifications,
            snapshot,
            (
                r'(?i)\b(api[_-]?key|secret|password|token)\s*[:=]\s*["\'][^"\']{8,}["\']',
                r'-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----',
            ),
        )
        refs = tuple(sorted(set(name_refs) | set(pattern_refs)))
        observations.append(
            SecurityObservation(
                "SEC-SECRET-001",
                subcategory,
                "OBSERVED" if refs else "NOT_FOUND",
                (
                    f"Potential secret-bearing file/content signals were found in {len(refs)} file(s). "
                    "Values are intentionally not emitted."
                    if refs
                    else "No secret-bearing filename or credential-pattern signal matched the deterministic rules."
                ),
                refs[:30],
            )
        )

    elif subcategory == "AUTHENTICATION":
        refs = _scan(
            classifications,
            snapshot,
            (
                r'(?i)\b(jwt|oauth|bcrypt|argon2|passwordencoder|authentication|login|refresh\s*token)\b',
            ),
        )
        observations.append(
            SecurityObservation(
                "SEC-AUTHN-001",
                subcategory,
                "OBSERVED" if refs else "NOT_DETERMINABLE",
                (
                    f"Authentication-related implementation signals were found in {len(refs)} file(s)."
                    if refs
                    else "No deterministic authentication signal was found; absence of a signal does not prove authentication is absent."
                ),
                refs[:30],
            )
        )

    elif subcategory == "AUTHORIZATION":
        refs = _scan(
            classifications,
            snapshot,
            (
                r'(?i)\b(role|roles|permission|permissions|authorize|authorization|owner[_-]?id|tenant[_-]?id|access\s+control)\b',
            ),
        )
        observations.append(
            SecurityObservation(
                "SEC-AUTHZ-001",
                subcategory,
                "OBSERVED" if refs else "NOT_DETERMINABLE",
                (
                    f"Authorization/ownership-related signals were found in {len(refs)} file(s); "
                    "this is not evidence that every protected operation enforces authorization."
                    if refs
                    else "No deterministic authorization signal was found."
                ),
                refs[:30],
            )
        )

    elif subcategory == "DEBUG_EXPOSURE":
        refs = _scan(
            classifications,
            snapshot,
            (
                r'printStackTrace\s*\(',
                r'(?i)debug\s*=\s*true',
                r'(?i)stacktrace',
                r'(?i)traceback',
            ),
        )
        observations.append(
            SecurityObservation(
                "SEC-DEBUG-001",
                subcategory,
                "OBSERVED" if refs else "NOT_FOUND",
                f"Debug/diagnostic exposure signals were found in {len(refs)} file(s)." if refs else "No deterministic debug-exposure pattern matched.",
                refs[:30],
            )
        )

    elif subcategory == "FILE_SECURITY":
        refs = _scan(
            classifications,
            snapshot,
            (
                r'(?i)(upload|download).{0,160}(filename|path|join|resolve)',
                r'\.\./',
                r'Path\s*\(',
                r'os\.path\.(join|abspath|normpath)\s*\(',
            ),
        )
        observations.append(
            SecurityObservation(
                "SEC-FILE-001",
                subcategory,
                "OBSERVED" if refs else "NOT_FOUND",
                (
                    f"File path/transfer handling signals were found in {len(refs)} file(s); "
                    "a traversal vulnerability requires a controllable input path and missing canonicalization/authorization."
                    if refs
                    else "No deterministic file-transfer/path-handling pattern matched."
                ),
                refs[:30],
            )
        )

    else:
        observations.append(
            SecurityObservation(
                "SEC-INV-001",
                subcategory,
                "NOT_DETERMINABLE",
                "No deterministic inspector exists for this security subcategory yet.",
            )
        )

    canonical = {
        "work_item_ref": work_item_ref,
        "target_surface": target_surface,
        "observations": [
            {
                "code": item.code,
                "subcategory": item.subcategory,
                "state": item.state,
                "summary": item.summary,
                "source_refs": list(item.source_refs),
            }
            for item in observations
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return SecurityInspectionResult(
        work_item_ref=work_item_ref,
        target_surface=target_surface,
        observations=tuple(observations),
        source_refs=refs,
        fingerprint=fingerprint,
    )


class DeterministicSecurityAuditor:
    """Security PASS 2 inspector. It emits observations, not automatic vulnerabilities."""

    ACTOR = "project-audit/single-agent/security-v1"

    def inspect(
        self,
        snapshot: DiscoverySnapshot,
        work_item_ref: str,
        target_surface: str,
    ) -> SecurityInspectionResult:
        return _inspect(snapshot, work_item_ref, target_surface, classify_files(snapshot))
