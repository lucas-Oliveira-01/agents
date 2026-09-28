# OmniRoute Delegation & Architecture Memory Audit

**Date of Audit:** 2026-09-25
**Sources:** `ai-memory` durable pages, decisions, and session notes across all projects (global search).

## 1. OmniRoute Delegation Package Validation
- **Package Status:** `omniroute-delegation v1.0.0` was downgraded from a hallucinated "PRODUCTION-READY" status to **READY_WITH_WARNINGS**. While solidly tested, it lacks exhaustive concurrency tests and a V2 regression baseline.
- **Test Metrics:** Verified to have exactly 196 passing tests across 9 files (6 test modules + 3 support files). Previous higher numbers were identified as AI hallucinations.
- **Security & Scans:** Clean dependency scans (`pip-audit`) and security checks (`bandit` verified after a minor false positive fix).
- **Snapshot Tag:** A verifiable byte-for-byte snapshot is frozen at commit `28db403dd13e2e9ab7f56e7e3f006bf6d6b5f366` (`v1.0.0-frozen`).

## 2. OmniRoute Execution & SCHEMA_VIOLATION Errors (`test3` Benchmark)
- **The Issue:** During the `test3` benchmark of the Engine V2 architecture, LLM tasks delegated via **OmniRoute** encountered severe bottlenecks at the semantic contract/output schema layer.
- **SCHEMA_VIOLATION:** OmniRoute delegations failed successively with `SCHEMA_VIOLATION` (5 out of 7 semantic domains were rejected by the parser).
- **Impact:** These parsing failures resulted in the system erroneously reporting "0 findings", completely masking real underlying security issues (e.g., an IDOR vulnerability).

## 3. Engine V3 "Fail-Closed" Specification
To resolve the `SCHEMA_VIOLATION` failures introduced via OmniRoute, Engine V3 incorporates a fail-closed design:
- **No More "0 findings" on Failure:** If the semantic worker parser fails (e.g., `SCHEMA_VIOLATION` or `TIMEOUT`), the system MUST force a `SEMANTIC_COVERAGE_FAILED` and `INCOMPLETE` status rather than returning 0 findings.
- **Tolerant Normalization:** The parser will tolerate varied structures (like lists instead of objects) but must document explicit conversion rules (e.g., `raw_severity` and `normalization_rule`). Fallbacks for entirely malformed data will return a `VALIDATION_ERROR`.

## 4. MCP & Backend Contradictions
- **Validation Bypass Bug (C-007):** According to the confirmed documentation contradictions (`notes/confirmed-doc-contradictions.md`), the `MCPOmniRouteBackend` currently bypasses normal `MCPClient` validations. It calls the `delegar_tarefa` tool directly without going through credential scanning or schema verification.
- **Session Evidence:** Session `01a0cb93-f480-7b41-831f-0bd82ccdd3d4` recorded a user explicitly exploring the OmniRoute MCP, checking its tools, and executing `delegar_tarefa` to generate executable Python scripts.

## Summary
The OmniRoute package itself has been heavily vetted and frozen (`v1.0.0`), but its integration as an MCP/delegation layer faces structural issues. The primary point of failure lies in strict schema validation (`SCHEMA_VIOLATION`) leading to dropped findings, coupled with a documented architectural contradiction where the backend bypasses essential validation steps when calling `delegar_tarefa`.
