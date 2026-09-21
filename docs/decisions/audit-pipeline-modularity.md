# Architecture Decision Record: Audit Pipeline Modularity & Classifier Funnel

**Status:** accepted

## Context
The original `project-audit` skill acted as a monolithic auditor. This led to wasted tokens (auditing databases when none exist), execution bias, and brittle context windows.
Furthermore, relying on LLMs to perform normalization or applicability checks proved economically inefficient and epistemologically flawed.

## Decision
We are adopting a strictly modular, funnel-based audit pipeline:

1. **Role of `project-audit`:** It is now strictly an **Orchestrator**. It understands the project via `project-context`, determines applicability, plans the audit, coordinates specialized auditors, and consolidates the final Output Set. It *does not* audit code directly.
2. **Specialized Auditors:** `security-audit`, `code-audit`, `database-audit`, etc. They are decoupled and only executed when applicable.
3. **The Classifier Funnel:** We enforce a strict separation of concerns to minimize cost and maximize quality:
   - **Deterministic Classifiers (Free):** Scripts identify file types, stack, git changes, and basic applicability.
   - **Cheap LLM Classifiers (Low Cost):** Lightweight models (via OmniRoute) flag "candidates" (e.g., "this function looks suspicious"). *They do not confirm vulnerabilities.*
   - **Strong LLM Auditors (High Cost):** Advanced models investigate candidates, build attack paths, and confirm findings.
   - **Deterministic Normalizer (`audit-normalize`):** A strict Python compiler that deduplicates and validates findings without LLM hallucination.
4. **Universal Output Contract:** Every auditor, regardless of domain, must produce the exact same 4-part Audit Output Set:
   - `00_inventory_and_threat_model.md`
   - `01_coverage_manifest.md`
   - `02_analytical_report.md`
   - `03_audit_ledger.md`

## Consequences
- **Positive:** Massive reduction in token costs by filtering noise before it reaches expensive models.
- **Positive:** Guaranteed consistency in output formats, enabling perfect downstream JSON normalization.
- **Negative:** Increased orchestration complexity; the Orchestrator must accurately manage context slicing and delegation pipelines.
