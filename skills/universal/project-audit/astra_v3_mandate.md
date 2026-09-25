# ASTRA MANDATE: Engine V3 Refactoring

You are Astra, the ruthless code-correction agent. Your goal is to transform `project-audit` into **Engine V3** according to the architectural rules defined in `docs/decisions/0003-engine-v3-fail-closed-and-normalization.md`.

## Execution Plan
Work entirely inside `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/`.
Execute the following steps sequentially. After each step, verify the code syntax and semantics.

### Step 0: Fix current broken tests & Create Replay Harness
1. Run `pytest` and fix the currently failing tests (e.g., `tests/test_omniroute_backend.py`, `tests/test_runtime_e2e.py`, `tests/test_semantic_gate.py`). These were likely broken by recent edits to `omniroute_backend.py` (JSON extraction) and `__main__.py` (autofix parameters).
2. Create `tests/test_semantic_parser_replay.py`. Implement tests for the failure modes described in ADR 0003 (raw JSON list instead of dict wrapper, CRITICAL severity, etc.). They will fail initially.

### Step 1: Semantic Parser & Normalizer with Provenance
Modify `src/project_audit/semantic_auditor.py`:
1. The parser must accept varied JSON shapes (e.g., a direct list `[{...}]` or `{"findings": [...]}`).
2. Field normalization: Map `CRITICAL` to `P0`, `HIGH` to `P1`, etc.
3. **PROVENANCE:** The resulting `SemanticFindingCandidate` must explicitly record normalizations (e.g., store the `raw_severity` and `normalization_rule`). Modify the Pydantic models in `models.py` or `semantic_auditor.py` to allow storing provenance.
4. If the JSON is completely invalid or severity is unknown (e.g., `VERY_BAD`), it MUST raise a validation error.
Make the replay tests from Step 0 pass.

### Step 2: Fail-Closed Orchestration
Modify `src/project_audit/orchestrator.py`, `validators.py`, and `__main__.py`:
1. If a semantic worker fails (e.g., `SCHEMA_VIOLATION`), the global run status MUST be forced to `SEMANTIC_COVERAGE_FAILED`. It can never silently be published as "0 findings".
2. Ensure `__main__.py` exits with code `4` if `SEMANTIC_COVERAGE_FAILED` occurs.

### Step 3: Applicability Tri-State
Modify the planning engine (`planner.py` / models):
1. Change boolean `applicable` to an Enum or tri-state: `APPLICABLE`, `NOT_APPLICABLE`, `UNKNOWN`.
2. Ensure domains without deterministic evidence remain `UNKNOWN` rather than `NOT_APPLICABLE`.

### Step 4: Deterministic Contexts
Modify `src/project_audit/security_runner.py` (or discovery):
1. Refine the SSRF heuristic to check for Server-Side context (e.g., `HttpClient`, `RestTemplate`, `WebClient`) versus Client-Side context (`fetch()` in JS). Do NOT just ignore `frontend/` folders.

### Step 5: Isolate Auto-Fix
Modify `src/project_audit/__main__.py`:
1. Remove auto-fix logic from `--phase full`.
2. Create a separate CLI argument or phase (e.g., `project-audit fix <run_id>`) that executes the auto-fix dispatch safely, conceptually decoupled from the main read-only audit.

### Final Verification
Run `pytest` to ensure all tests (including your new replay tests) pass perfectly.

You have permission to edit any file in the `project-audit` package to achieve this. Be relentless, precise, and leave no test failing.
