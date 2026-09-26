"""Tolerant semantic parser with explicit provenance and partial coverage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple, Iterable

from .contracts import AuditContract, ExecutionState, LeafFinding, LeafContract
from .exceptions import SchemaViolationError, SemanticCoverageFailedError

_SEVERITY_ALIASES = {
    "CRITICAL": "P0",
    "HIGH": "P1",
    "MEDIUM": "P2",
    "LOW": "P3",
    "INFO": "INFO",
    "P0": "P0",
    "P1": "P1",
    "P2": "P2",
    "P3": "P3",
    "P4": "INFO",
}


@dataclass(frozen=True)
class SemanticPayload:
    """Transport envelope preserving the exact model output and routing identity."""
    payload: Any
    raw_output: str
    provider: Optional[str] = None
    model: Optional[str] = None


def _raw_output_for(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    try:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return repr(payload)


def _extract_json_candidates(text: str) -> Iterable[str]:
    """Extract balanced JSON objects or arrays from arbitrary model chatter."""
    for start, char in enumerate(text):
        if char not in "[{":
            continue
        stack: List[str] = []
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            current = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue
            if current == '"':
                in_string = True
            elif current in "[{":
                stack.append(current)
            elif current in "]}":
                if not stack:
                    break
                opener = stack.pop()
                if (opener, current) not in {("[", "]"), ("{", "}")}:
                    break
                if not stack:
                    yield text[start:index + 1]
                    break


def extract_json(text: str) -> Any:
    """Extract the first valid JSON value from prose or fenced output."""
    stripped = text.strip()
    candidates = [stripped]
    if stripped.startswith("FENCE") and stripped.endswith("FENCE"):
        candidates.insert(0, stripped.strip("FENCE").strip())
    candidates.extend(_extract_json_candidates(stripped))
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    raise SchemaViolationError("No valid JSON object or array could be extracted.")


def _candidate_from_item(item: Any) -> LeafFinding:
    if not isinstance(item, dict):
        raise SchemaViolationError("Finding candidate must be an object.")

    required = (
        "title", "category", "type", "status",
        "severity", "confidence", "evidence", "description",
    )
    missing = [field for field in required if not isinstance(item.get(field), str)]
    if missing:
        raise SchemaViolationError(
            "Finding candidate is missing required string fields: " + ", ".join(missing)
        )

    raw_severity = item["severity"].strip().upper()
    normalized = _SEVERITY_ALIASES.get(raw_severity)
    if normalized is None:
        raise SchemaViolationError("Unsupported severity: " + raw_severity)

    payload = dict(item)
    payload["severity"] = normalized
    payload["raw_severity"] = raw_severity
    payload["normalization_rule"] = (
        None if normalized == raw_severity else raw_severity + "->" + normalized
    )
    return LeafFinding.model_validate(payload)


def parse_leaf_output(payload: Any) -> Tuple[List[LeafFinding], List[Dict[str, Any]]]:
    """Parse valid findings while preserving malformed items as raw errors."""
    if isinstance(payload, str):
        payload = extract_json(payload)

    if isinstance(payload, list):
        raw_findings = payload
    elif isinstance(payload, dict):
        raw_findings = payload.get("findings")
        if not isinstance(raw_findings, list):
            raise SchemaViolationError("Semantic output must contain a findings array.")
    else:
        raise SchemaViolationError("Semantic output must be a JSON object or array.")

    findings: List[LeafFinding] = []
    raw_errors: List[Dict[str, Any]] = []
    for index, item in enumerate(raw_findings):
        try:
            findings.append(_candidate_from_item(item))
        except SchemaViolationError as exc:
            raw_errors.append({
                "index": index,
                "error_type": type(exc).__name__,
                "message": str(exc),
                "raw": item,
            })
    return findings, raw_errors


class SemanticRecoveryLoop:
    """Retry semantic delegation and preserve partial evidence."""

    def __init__(self, delegate: Callable[[int], Any], max_attempts: int = 2) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        self._delegate = delegate
        self._max_attempts = max_attempts

    def run(self) -> AuditContract:
        last_error: Optional[Exception] = None
        accumulated_errors: List[Dict[str, Any]] = []
        last_raw_output: Optional[str] = None
        last_provider: Optional[str] = None
        last_model: Optional[str] = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                delegated = self._delegate(attempt)
                if isinstance(delegated, SemanticPayload):
                    payload = delegated.payload
                    raw_output = delegated.raw_output
                    provider = delegated.provider
                    model = delegated.model
                else:
                    payload = delegated
                    raw_output = _raw_output_for(delegated)
                    provider = None
                    model = None

                last_raw_output = raw_output
                last_provider = provider
                last_model = model
                findings, raw_errors = parse_leaf_output(payload)
                accumulated_errors.extend(raw_errors)
                leaf = LeafContract(
                    findings=findings,
                    raw_output=raw_output,
                )
                if raw_errors:
                    return AuditContract(
                        state=ExecutionState.PARTIAL_COVERAGE,
                        findings=findings,
                        raw_errors=accumulated_errors,
                        attempts=attempt,
                        leaf=leaf,
                        provider=provider,
                        model=model,
                        raw_output=raw_output,
                    )
                return AuditContract(
                    state=ExecutionState.SUCCESS,
                    findings=findings,
                    attempts=attempt,
                    leaf=leaf,
                    provider=provider,
                    model=model,
                    raw_output=raw_output,
                )
            except SchemaViolationError as exc:
                last_error = exc
                if 'payload' in locals():
                    last_raw_output = _raw_output_for(payload)
                accumulated_errors.append({
                    "attempt": attempt,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                })

        result = AuditContract(
            state=ExecutionState.SCHEMA_VIOLATION,
            findings=[],
            raw_errors=accumulated_errors,
            attempts=self._max_attempts,
            leaf=LeafContract(findings=[], raw_output=last_raw_output),
            provider=last_provider,
            model=last_model,
            raw_output=last_raw_output,
        )
        raise SemanticCoverageFailedError(result) from last_error
