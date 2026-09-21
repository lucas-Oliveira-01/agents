# Architecture Decision Record: Typed JSON Handoffs & Durable Finding Emission

**Status:** accepted

## Context
During long-running operations (like security audits), the agent relies on the LLM's volatile context window as its primary working memory. When this context truncates, all unpersisted state—including identified vulnerabilities, hypotheses, and coverage blind spots—is permanently lost. This constitutes a Single Point of Continuity Failure.
Furthermore, inter-agent handoffs (e.g., `project-audit` -> `audit-normalize`) were historically treated as free-text prose. Prose cannot reliably preserve strict epistemic states (e.g., distinguishing a confirmed vulnerability from a hypothesis, or tracking explicitly ignored files).

## Decision
1. **Durable Finding Emission:** We replace voluntary `memory_write_page` calls for audit findings with a synchronous `finding_emit()` side-effect. Agents must durably log findings (severity, epistemic status, location, evidence) immediately upon discovery, writing ahead of the context window. Findings unrecorded by this tool effectively do not exist for downstream pipelines.
2. **Typed JSON Handoffs:** Handoff payloads must be machine-readable JSON contracts.
3. **Mandatory Epistemology & Coverage:** The handoff contract must explicitly track:
   - `blind_spots`: Files or components intentionally skipped, with associated downstream risk.
   - `epistemic_status`: `OBSERVATION`, `INFERENCE`, `HYPOTHESIS`, `CONFIRMED`, `NOT_AUDITED`.
   - `coverage_attestation`: An explicit boolean. Absence of evidence must never be silently converted into evidence of absence.

## Consequences
- **Positive:** Systemic resilience against context truncation. Findings survive session restarts.
- **Positive:** Downstream agents (like `audit-normalize`) consume deterministic data structures, eliminating hallucinations caused by parsing free-form narrative handoffs.
- **Positive:** Forces the agent to formally declare its blind spots, converting unknown risks into managed, auditable gaps.
