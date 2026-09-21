# Architectural Precedents & External References

*Status: ARCHITECTURE FROZEN*

This document catalogs the external standards, frameworks, and tools that inspired the architecture of the Orchestrator and `project-audit`. These precedents serve to illuminate and justify the design choices we made.

> **CRITICAL RULE:** These references are precedents, NOT authority. They justify decisions already captured in our ADRs and Canonical Data Model. They must not be used to introduce new requirements after `Architecture Frozen`.

---

## 1. Core Architecture & Data Contracts

### 1.1. JSON Schema (Draft 2020-12)
- **Source:** [json-schema-org/json-schema-spec](https://github.com/json-schema-org/json-schema-spec)
- **Relevant Subsystem:** Orchestrator State Persistence (Layer 2)
- **Architectural Concept:** Structural contracts, `$defs`, strict validation (`additionalProperties: false`).
- **What We Learn:** How to build strict, referentially consistent state serialization without encoding business logic directly into the schema.
- **What We Explicitly DO NOT Adopt:** We do not use JSON Schema to enforce cross-object semantic invariants (which belong to Semantic Validators).

### 1.2. SARIF (Static Analysis Results Interchange Format)
- **Source:** [oasis-tcs/sarif-spec](https://github.com/oasis-tcs/sarif-spec)
- **Relevant Subsystem:** `audit-normalize` (Layer 3) and Specialized Auditors (Layer 1).
- **Architectural Concept:** Interoperability of heterogeneous tools, separating rules/locations/findings.
- **What We Learn:** How an ecosystem of different tools (code-audit, security-audit) can produce findings that aggregate cleanly into a unified canonical output.
- **What We Explicitly DO NOT Adopt:** We do not adopt the massive, complex SARIF XML/JSON schema directly. Our Layer 1 is human-readable Markdown, and our Layer 3 (`report_data.json`) is a bespoke simplified model.

### 1.3. OpenLineage
- **Source:** [OpenLineage/OpenLineage](https://github.com/OpenLineage/OpenLineage)
- **Relevant Subsystem:** `Evidence` and `TargetSnapshot`.
- **Architectural Concept:** Data/Job Lineage and Provenance.
- **What We Learn:** Crucial relationships (Run -> Plan -> WorkItem -> Evidence -> Source) must be explicit and immutable.
- **What We Explicitly DO NOT Adopt:** Full telemetry/pipeline standard; we use a lightweight `provenance` object tailored to our trust boundaries.

---

## 2. Execution, Safety & Policies

### 2.1. Temporal
- **Source:** [temporalio/temporal](https://github.com/temporalio/temporal)
- **Relevant Subsystem:** `AuditRun` and `AuditWorkItem` (State Machines).
- **Architectural Concept:** Durable execution, deterministic retries, recovery after crashes.
- **What We Learn:** The strict semantic difference between `RETRY` (re-executing an idempotent action) and `RECOVERY` (reconstructing state from disk without re-executing).
- **What We Explicitly DO NOT Adopt:** We are not running a heavy event-sourcing engine or external Temporal cluster; we maintain a simplified state machine managed locally by the Orchestrator.

### 2.2. Open Policy Agent (OPA)
- **Source:** [open-policy-agent/opa](https://github.com/open-policy-agent/opa)
- **Relevant Subsystem:** Execution Safety Gate and Data Egress (ADR-05).
- **Architectural Concept:** Policy-as-Code. Separation of policy decision from execution.
- **What We Learn:** The Orchestrator sets the policy, the Validator evaluates the capability request against it, and the runner executes. Unknowns default to `DENY`.
- **What We Explicitly DO NOT Adopt:** Rego language. We use our own deterministic semantic validators.

---

## 3. Auditing & Security Models

### 3.1. Cloudflare Security Audit Skill
- **Source:** [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill)
- **Relevant Subsystem:** `security-audit` and `audit-normalize`.
- **Architectural Concept:** Separation of findings vs hardening notes; demanding concrete file:line evidence for vulnerability claims.
- **What We Learn:** The pipeline model where audits require validation, evidence extraction, and machine-readable structuring.

### 3.2. OpenSSF Scorecard
- **Source:** [ossf/scorecard](https://github.com/ossf/scorecard)
- **Relevant Subsystem:** Specialized Auditors.
- **Architectural Concept:** Composing audits from independent checks (source code, build, dependencies).
- **What We Learn:** Decomposing problems into specialized, automatable verifications rather than a single monolithic "Audit Everything" prompt.

### 3.3. OSV Schema (Open Source Vulnerability)
- **Source:** [ossf/osv-schema](https://github.com/ossf/osv-schema)
- **Relevant Subsystem:** Canonical `FindingFingerprint` and `report_data.json`.
- **Architectural Concept:** Vulnerability identification across affected ranges and ecosystem versions.
- **What We Learn:** How to construct a stable identity descriptor (Fingerprint) for a vulnerability that survives code refactoring.

---

## 4. Agent Frameworks

### 4.1. Sentry Agent Skills
- **Source:** [getsentry/skills](https://github.com/getsentry/skills)
- **Relevant Subsystem:** Specialized Auditors (Layer 1).
- **Architectural Concept:** Separation of responsibility into distinct skill tools.
- **What We Learn:** The Sub-auditor architecture. How to build small, scoped, highly reliable AI workers instead of generic multi-purpose agents.
