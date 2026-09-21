# Normative Reference Contract: `audit-normalize`

This reference formalizes the normative specifications, contracts, policies, and invariants governing `audit-normalize`, based on the canonical V8 specification (`v8_current.md`, `report_data.schema.json`, and the Normative Contract Surface).

---

## 1. Identity & Role Boundary

1. **Non-Auditing Identity**: `audit-normalize` is exclusively a data-engineering normalizer and validator. It does **not** perform technical auditing, code analysis, threat modeling, vulnerability scanning, or project discovery.
2. **Input Boundary**: Inputs are existing Markdown documents produced by external audit agents/tools (e.g., `project-audit`).
3. **Output Boundary**: Produces canonical JSON artifacts:
   - `report_data.json`
   - `report_data.schema.json`
   - `validation_report.json`
   - `source_manifest.json`
4. **Prohibition of Invention**: Missing source data must remain `NOT_PROVIDED_BY_SOURCE` or `NOT_DETERMINABLE`. Inferring environmental values (e.g., executing `git rev-parse HEAD` when commit is missing in Markdown) is strictly prohibited.

---

## 2. Source Roles & Precedence Policy

Each discovered audit document is classified into a canonical `source_role`:

| Source Role | Description | Precedence Rank |
| :--- | :--- | :--- |
| `UNKNOWN` | Source role cannot be determined with certainty | 0 |
| `AUDIT_LEDGER` | Structured ledger containing concrete findings and controls | 1 |
| `ANALYTICAL_REPORT` | Narrative analytical report of the audit | 2 |
| `INVENTORY` | Asset and component inventory | 3 |
| `THREAT_MODEL` | Threat modeling analysis | 3 |
| `COVERAGE_MANIFEST` | Scope, applicability, and inspection coverage | 3 |
| `EXTERNAL_REVIEW` | Third-party or external review | 4 |
| `ENVIRONMENT` | Direct environmental inspection source | Unranked (N/A) |
| `VCS` | Version control inspection source | Unranked (N/A) |

### Precedence Semantics
- **Rule**: Lower numeric rank indicates higher precedence (`rank 1 > rank 2 > rank 3 > rank 4`).
- **Trigger**: Conflicting values across sources with different precedence ranks.
- **Resolution**:
  - The value from the higher-precedence source is selected.
  - The field retains its selected state (e.g., `PRESENT`) and value.
  - A conflict record is registered in `conflicts[]` with:
    - `resolution.status = "RESOLVED"`
    - `resolution.policy_applied = "SOURCE_ROLE_PRECEDENCE"`
    - `resolution.selected_source = <source_id>`
  - The history of divergence is permanently preserved.
- **Tie Policy (Equal Ranks)**:
  - If sources have the same precedence rank and disagree on a value:
    - `state = "CONFLICT"`
    - `value = null`
    - `conflict_id = "CONFLICT-XXX"` (required)
    - `resolution.status = "UNRESOLVED"`
    - `resolution.selected_source = null`
  - Arbitrary resolution (e.g., "highest severity wins", "first occurrence wins", "last occurrence wins") is strictly prohibited.

---

## 3. Deduplication & Merge Policy

`MERGE` and `PRECEDENCE` are distinct operations:
- `PRECEDENCE` selects a normative value in case of incompatible divergence.
- `MERGE` combines compatible, non-conflicting representations.

### Deduplication Order
1. **Explicit ID Match**:
   - Entities with the same ID (e.g., `SEC-009`) are compared for `category` and `type`.
   - If compatible: deduplicate and merge provenance.
   - If divergent on fields: detect and record conflicts.
   - If semantically incompatible: flag as `ID_COLLISION` anomaly; do not merge blindly.
2. **Findings without ID**:
   - Merge **only** if strong structural match is proven:
     - Exact match on `location.file`.
     - Compatible `location.line` or line range (single line within range, identical range, etc.).
     - Compatible `category` and `type`.
     - Evidence consistency when available.
   - **Textual similarity alone never authorizes merge.**
3. **No Merge**:
   - If structural match conditions are not met, entities remain distinct.

### Non-Destructive Field Merge
- If Source A provides a known value (`PRESENT`) and Source B lacks it (`NOT_PROVIDED_BY_SOURCE`), this is **not** a conflict. The known value is preserved.

---

## 4. Critical Conflict Fields

Conflict detection must explicitly evaluate:
- `severity`
- `status`
- `confidence`
- `type`
- `location`
- `field_value` (title, description, evidence, cause, impact, exploitability, recommendation)
- `target_project`

An unresolved conflict on a critical field must never collapse into a single synthesized value.

---

## 5. Anomaly Taxonomy

Anomalies represent structural or technical inconsistencies that are not entity conflicts:
- `TECHNICAL_INCONSISTENCY`: Incompatible technical claims (e.g., PostgreSQL DB claimed with MySQL configuration directives).
- `SOURCE_FORMAT_ANOMALY`: Malformed or unexpected syntax in source.
- `CONTRADICTORY_STATEMENT`: Contradictory claims within a single document or narrative.
- `POSSIBLE_TRANSCRIPTION_ERROR`: Suspected typographical or transcription errors.
- `UNEXPECTED_CONFIGURATION_REFERENCE`: Reference to non-existent configurations.
- `ID_COLLISION`: Two distinct findings sharing the same identifier with incompatible categories/types.
- `UNMAPPED_TAXONOMY`: Severity, category, or type that cannot be safely mapped to the canonical enum.
- `OTHER`: Other verifiable structural defects.

---

## 6. Information States

Semantic text, status, and severity fields use explicit formal states:
- `PRESENT`: Information was explicitly provided by the source. `value` is non-null; `conflict_id` is null.
- `NOT_PROVIDED_BY_SOURCE`: The source did not address this aspect. `value` is null; `conflict_id` is null.
- `NOT_DETERMINABLE`: The source attempted to evaluate but could not determine the result. `value` is null; `reason` is required; `conflict_id` is null.
- `CONFLICT`: Unresolved disagreement between sources. `value` is null; `conflict_id` is required.

Artificial placeholder strings (e.g., `"NÃO INFORMADO"`, `"N/A"`, `"-"`, `"?"`) are prohibited.

---

## 7. Metrics Derivation

Metrics must be derived exclusively from the normalized collections:
- `findings_total = len(findings)`
- `severity.P0 = count(findings with severity == "P0")`
- `severity.P1 = count(findings with severity == "P1")`
- `severity.P2 = count(findings with severity == "P2")`
- `severity.P3 = count(findings with severity == "P3")`
- `severity.INFO = count(findings with severity == "INFO")`
- `controls_total = len(controls)`
- `inspections_total = len(inspections)`

Declared counts in source documents must never override calculated metrics.

---

## 8. Validation Requirements

A dataset is valid only if all verification gates pass:
1. **Schema Validation**: Conformance to `report_data.schema.json` via JSON Schema Draft 2020-12.
2. **Semantic Validation**:
   - Calculated metrics match entity counts.
   - Information states satisfy structural dependencies (`reason` on `NOT_DETERMINABLE`, `conflict_id` on `CONFLICT`).
   - Line numbers: `line_end >= line_start`.
   - Finding status cannot be `NOT_FOUND`.
3. **Referential Validation**:
   - Every `provenance.source_id` exists in `audit_snapshot.sources`.
   - Every `conflict_id` references a declared entry in `conflicts[]`.
   - Every `finding_id` in conflicts references an existing finding in `findings[]`.
   - Every `selected_source` in resolved conflicts exists in the conflict's `values[].source_id`.
4. **Integrity Validation**:
   - Source files exist on disk.
   - Raw bytes SHA-256 matches manifest hashes.
   - `snapshot_id` matches SHA-256 of canonical manifest JSON.
5. **Determinism Validation**:
   - Repeated normalization on identical inputs yields logically identical output and identical canonical serialization.
