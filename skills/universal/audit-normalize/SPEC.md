# Audit Normalize Specification

## 1. Intent and Scope
This skill normalizes free-form technical audit Markdown documents into deterministic, schema-validated JSON datasets (`report_data.json`). It is intended to be universally applicable to any agentic platform that can execute Python.

## 2. Maintenance Boundaries
*   **SKILL.md:** Must remain abstract and focus on *when* and *why* an agent should use this tool, rather than the internal Python implementation details.
*   **src/ & tests/:** Contains the actual Python implementation. Changes here must pass the pytest suite to ensure idempotency and schema validation are not broken.
*   **references/:** Contains the expected JSON schema against which the output is validated.

## 3. Anti-Patterns
*   Do not modify this skill to perform active source code auditing. This skill is strictly a data normalizer, not an auditor.
*   Do not hardcode project-specific rules into the Python source; it must remain generic.
