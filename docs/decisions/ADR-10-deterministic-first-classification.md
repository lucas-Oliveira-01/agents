# ADR 10: Deterministic-First Classification and Escalation Gate

## Status
Accepted

## Context
The `project-audit` system historically relied heavily on Large Language Models (LLMs) as the primary engine for analyzing and classifying software artifacts. While powerful, utilizing LLMs as the default path for every decision leads to prohibitive token costs, unnecessary latency, and non-deterministic behavior for tasks that can be solved via structural analysis. 
The system needs a formal separation between cheap, reproducible deterministic classification and expensive semantic reasoning.

## Decision
We establish a **Deterministic-First Principle** for the `project-audit` execution pipeline:
**Whenever a decision can be resolved by algorithms, rules, parsers, structural analysis, static analysis, or deterministic heuristics without a material loss of quality, it MUST be made without invoking an LLM.**

To implement this, we introduce the **Deterministic Intelligence Layer**, consisting of specific classifiers that sit between Discovery and Audit Planning. 

### Key Classifiers
1. **File & Language Classifier:** Determines file type and language using extensions, basenames, and AST parsers (e.g., Tree-sitter, GitHub Linguist concepts).
2. **Stack Classifier:** Detects frameworks, build systems, and dependencies via manifests.
3. **Applicability Classifier:** Evaluates if a given audit (e.g., SQL Injection) is applicable. Produces `APPLICABLE`, `NOT_APPLICABLE`, or `NOT_DETERMINABLE` (uncertainty defaults to keeping it in scope).
4. **Task & Complexity Classifier:** Determines the execution kind (`DETERMINISTIC`, `SEMANTIC_REQUIRED`) and complexity (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) for `AuditWorkItems`.
5. **Sensitivity Classifier:** Evaluates data payload before egress (`PUBLIC`, `INTERNAL`, `SENSITIVE`, `SECRET`, `UNKNOWN`). Unidentified data defaults to `FAIL CLOSED` (DO NOT SEND).
6. **Context Classifier:** Filters only the necessary scope required for the task.

### Escalation Gate
All `AuditWorkItem`s will pass through an **Escalation Gate**:
1. Can the task be solved by deterministic machinery? 
2. If YES, use a Deterministic Worker to produce Evidence.
3. If NO (or if deterministic results are ambiguous/inconclusive), escalate to Semantic Analysis (LLM).

### Relationship with OmniRoute
The classification layer belongs to the Core/Orchestrator domain. It decides *WHAT* needs to be done, *WHICH CONTEXT* is relevant, and *IF* an LLM is necessary. The OmniRoute system remains strictly responsible for *WHICH MODEL* and *PROVIDER* to use, along with fallback and health checks.

## Consequences
- **Positive:** Massive reduction in LLM usage (token and compute economy), faster execution, better caching (REUSE/REVALIDATE/REAUDIT) due to deterministic inputs.
- **Positive:** Progressive disclosure reduces context sizes sent to specialized auditors.
- **Positive:** Enhanced security through the explicit Sensitivity Classifier.
- **Negative:** Requires building and maintaining parsers and deterministic rules (e.g., AST queries, Semgrep-like rules).
