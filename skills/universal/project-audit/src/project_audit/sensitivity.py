from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Tuple


class SensitivityState(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    SENSITIVE = "SENSITIVE"
    SECRET = "SECRET"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SensitivityAssessment:
    state: SensitivityState
    evidence: Tuple[str, ...]
    reason: str

    @property
    def is_sensitive(self) -> bool:
        return self.state in {
            SensitivityState.SENSITIVE,
            SensitivityState.SECRET,
            SensitivityState.UNKNOWN,
        }


_SECRET_NAME_PATTERNS = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "secret",
    "secrets.yaml",
    "secrets.yml",
}

_SECRET_CONTENT_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|PRIVATE) KEY-----"),
    re.compile(r"(?i)\baws_secret_access_key\b\s*[:=]\s*['\"][^'\"]+"),
    re.compile(r"(?i)\b(api[_-]?key|access[_-]?token|client[_-]?secret)\b\s*[:=]\s*['\"][^'\"]{8,}"),
    re.compile(r"(?i)\b(password|passwd|db_password)\b\s*[:=]\s*['\"][^'\"]{8,}"),
)

_SENSITIVE_CONTENT_PATTERNS = (
    re.compile(r"(?i)\bjw?t[_-]?secret\b"),
    re.compile(r"(?i)\bprivate[_-]?key\b"),
    re.compile(r"(?i)\brefresh[_-]?token\b"),
)


def assess_text(text: str, path: Optional[str] = None) -> SensitivityAssessment:
    evidence = []
    if path:
        name = Path(path).name.lower()
        if name in _SECRET_NAME_PATTERNS or "secret" in name:
            evidence.append("secret-bearing filename")
            return SensitivityAssessment(
                SensitivityState.SECRET,
                tuple(evidence),
                "Secret-bearing filename matched a deterministic rule.",
            )

    for pattern in _SECRET_CONTENT_PATTERNS:
        if pattern.search(text):
            evidence.append("secret-bearing content pattern")
            return SensitivityAssessment(
                SensitivityState.SECRET,
                tuple(evidence),
                "Secret-bearing content matched a deterministic rule.",
            )

    for pattern in _SENSITIVE_CONTENT_PATTERNS:
        if pattern.search(text):
            evidence.append("sensitive credential/token pattern")
            return SensitivityAssessment(
                SensitivityState.SENSITIVE,
                tuple(evidence),
                "Sensitive credential/token content matched a deterministic rule.",
            )

    return SensitivityAssessment(
        SensitivityState.UNKNOWN,
        tuple(),
        "The available deterministic evidence does not establish that the data is safe for external egress.",
    )


def aggregate_assessments(assessments: Tuple[SensitivityAssessment, ...]) -> SensitivityAssessment:
    if not assessments:
        return SensitivityAssessment(
            SensitivityState.UNKNOWN,
            tuple(),
            "No context was classified; sensitivity is therefore unknown.",
        )

    rank = {
        SensitivityState.SECRET: 5,
        SensitivityState.SENSITIVE: 4,
        SensitivityState.UNKNOWN: 3,
        SensitivityState.INTERNAL: 2,
        SensitivityState.PUBLIC: 1,
    }
    selected = max(assessments, key=lambda item: rank[item.state])
    evidence = tuple(sorted({entry for item in assessments for entry in item.evidence}))
    return SensitivityAssessment(selected.state, evidence, selected.reason)
