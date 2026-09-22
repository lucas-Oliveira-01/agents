# Deterministic Intelligence Layer

## Overview
The `project-audit` system employs a **Deterministic Intelligence Layer** to minimize reliance on Large Language Models (LLMs) for tasks that can be resolved via structural or deterministic analysis. LLMs act as a semantic fallback of high cost, not the default execution mechanism.

## Core Flow
```text
                    ┌──────────────────┐
                    │  TARGET SNAPSHOT │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ DISCOVERY        │
                    │ (deterministic)  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ DETERMINISTIC    │
                    │ INTELLIGENCE     │
                    │ LAYER            │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ AUDIT PLAN       │
                    │ + WORK ITEMS     │
                    └────────┬─────────┘
                             │
                ┌────────────┴────────────┐
                ▼                         ▼
         Deterministic               Semantic Worker
           Worker                         (LLM)
                │                         │
                └────────────┬────────────┘
                             ▼
                          EVIDENCE
```

## Architectural Capabilities

This layer is composed of specialized classification capabilities. These are not a single monolithic component, but distinct deterministic steps.

### 1. File and Language Classification
Inspired by GitHub Linguist and Tree-sitter.
* **Mechanism:** Extension -> Basename -> First-line/Shebang -> Content Signatures -> Parser.
* **Goal:** Quickly identify file types, source code languages, and structural purpose without LLMs.

### 2. Stack and Technology Classification
* **Mechanism:** Parsing manifests (e.g., `pom.xml`, `package.json`, `build.gradle`), configuration files, and dependency trees.
* **Goal:** Establish the technological stack (frameworks, DBs, build systems).

### 3. Applicability Classification
* **Mechanism:** Rule-based heuristics evaluating structural evidence (e.g., presence of HTTP clients implies SSRF is applicable).
* **States:** `APPLICABLE`, `NOT_APPLICABLE`, `NOT_DETERMINABLE`.
* **Rule:** `NOT_DETERMINABLE` preserves the possibility of inspection. Uncertainty never excludes scope.

### 4. Task and Complexity Classification
* **Mechanism:** Evaluates the `AuditWorkItem` against scope size, context needs, and analytical requirements.
* **Outputs:** Defines execution requirements (e.g., `DETERMINISTIC_EXTRACTION`, `SEMANTIC_ANALYSIS`) and complexity levels (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`). This influences the execution policy and budget.

### 5. Sensitivity and Egress Classification
* **Mechanism:** Pattern matching, secret detection, and strict access rules applied *before* delegation.
* **States:** `PUBLIC`, `INTERNAL`, `SENSITIVE`, `SECRET`, `UNKNOWN`.
* **Rule:** If `UNKNOWN`, the system must fail-closed and prevent external egress.

### 6. Context Requirements
* **Mechanism:** Dependency graphs, imports, and symbol indexing.
* **Goal:** Limits the context provided to a Specialized Auditor to the strict minimum required for the task (Progressive Disclosure), avoiding full-repository dumps.

## Escalation Gate
The decision to invoke an LLM is governed by an explicit escalation path:
1. Attempt deterministic execution.
2. If evidence is sufficient, generate `Evidence`.
3. If ambiguous, or if semantic reasoning is strictly required by the `AuditWorkItem`'s task classification, escalate to Semantic Analysis (LLM).

## ClassificationResult Entity
Classification decisions are formally recorded using a structure that allows for provenance auditing:
```json
{
  "classifier_id": "applicability-ssrf",
  "classifier_version": "1.0",
  "input_refs": ["file:///pom.xml"],
  "result": "APPLICABLE",
  "confidence": "HIGH",
  "rationale": "Found 'spring-boot-starter-web' dependency",
  "provenance": "..."
}
```
This ensures we can always answer *why* a deterministic path was chosen or why an LLM was invoked.
