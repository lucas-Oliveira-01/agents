---
name: model-routing
description: >
  Use this skill when choosing which reasoning model, model tier,
  or subagent configuration should be used for a task. Covers
  coding, debugging, architecture, research, long-horizon work,
  tool-heavy workflows, cost-sensitive tasks, and verification.
---

# Model Routing Policy

This skill dictates the model selection process when delegating tasks to subagents or configuring workflows. The model choice must be based on task characteristics, not on a static global ranking.

## 1. Subagent Invocation Model Tiers
When calling `invoke_subagent`, you must supply a `Model` tier. Do not blindly default to `pro` or `inherit`.
*   **`flash_lite` / `flash`:** Use for high-volume, repetitive, mechanically straightforward, or latency-sensitive tasks. (e.g., massive renaming, lint fixing, generating simple tests, summarizing short text).
*   **`pro`:** Use for deep reasoning, complex debugging, system architecture design, tracking obscure regressions, or tasks with a high cost of failure.

## 2. Escalation Protocol (Fallback)
1.  **Estimate Difficulty:** Always classify the task's complexity before delegating.
2.  **Start Low:** Prefer the lowest model tier (`flash`) that can reliably perform the task.
3.  **Validate:** Have the orchestrator or a verifier check the output.
4.  **Escalate:** If the `flash` model fails or hallucinates, only then escalate the task to a `pro` model or use parallel verification (`/boost`).

## 3. Role-Based Subagent Architecture
When creating or invoking a subagent, define it by its **Role** and assign the appropriate model tier based on the function.
*   *Implementer / Data Extractor / Refactorer* -> `flash`
*   *Architect / Security Auditor / Complex Debugger* -> `pro`

## 4. Consult the References
Before making hard decisions on specific models, consult the volatile reference data in this skill:
*   Read `references/routing-matrix.md` for a quick mapping of common tasks to optimal model tiers.
*   Read `references/model-inventory.md` for observed strengths and weaknesses of currently available model slugs.

Never choose a model solely because it is ranked higher globally; choose it because its profile fits the task envelope.
