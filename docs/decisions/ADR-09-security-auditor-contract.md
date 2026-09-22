# ADR 09: Security Auditor Contract

## Context
The Security Auditor component was architecturally expected but blocked due to a missing formal Data Model and Execution Contract. It needs a structured definition of Inputs, Prompts, Outputs, and architectural boundaries.

## Decision
We define the formal contract for the Security Auditor as follows:

1. **Input:** The Security Auditor receives the `TargetSnapshot` (including the git reference and fingerprint) and a `scope` (FULL/EXCEPT/ONLY).
2. **WorkItem generation:** The auditor is responsible for generating `AuditWorkItem`s with the type `SECURITY_VULNERABILITY_SCAN`.
3. **Output per WorkItem:** The execution of a work item results in an `Evidence` object containing `findings: list[Finding]`. Each finding MUST contain `category`, `severity`, `location`, and `description`.
4. **Prompt template:** The auditor must use a structured prompt template containing `<untrusted_project_data>` tags to strictly isolate the audited source code from the instructions, preventing prompt injection.
5. **Progressive disclosure:** The auditor should start by exposing only the specific file relevant to the `AuditWorkItem` being executed.
6. **Responsibilities NOT owned by Security Auditor:**
   - **StateStore ownership:** The auditor must NOT access or manage the `StateStore` directly.
   - **AuditRun lifecycle:** The auditor does not mutate the `AuditRun` state.
   - **ExecutionGate:** The auditor does not evaluate execution policies (handled by the orchestrator).
   - **EgressPolicy:** The auditor does not decide what can leave the system.

## Consequences
- **Positive:** Enables the safe implementation of the Security Auditor while maintaining the Orchestrator's single-writer invariant. Ensures structured vulnerability reporting.
- **Negative:** Requires rigorous prompt engineering to guarantee `<untrusted_project_data>` isolation.
