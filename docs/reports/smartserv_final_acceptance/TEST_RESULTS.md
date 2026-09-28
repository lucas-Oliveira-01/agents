# Testes

Python: 3.13.15.

| conjunto | resultado | duração/log |
|---|---:|---|
| project-audit | 400 passed | `tests/candidate_project_audit`, 9.89s |
| omniroute-delegation | 219 passed | `tests/candidate_delegation`, 1.83s |
| gateway determinístico | 33 passed | `tests/gateway_green`, 0.71s |
| gateway + acceptance counters | 35 passed | `tests/candidate_gateway_counters`, 0.88s |
| audit-normalize sem packaging | 56 passed, 1 skipped | `tests/candidate_normalize`, 5.97s |
| audit-normalize semântica | 10 passed | `tests/normalize_semantic_green` |
| audit-normalize packaging corrigido | 2 passed | `tests/packaging_final`, 4.73s |
| audit-normalize completo no sandbox | 57 passed, 1 skipped, 1 falha ambiental | `tests/final_normalize_after_fix`; DNS não resolve `pypi.org` para setuptools |
| snapshot drift regressão | 6 passed | `tests/security_drift_import_green` |
| verificação direcionada final | 17 passed | `tests/final_targeted_green`; `git diff --check` e `py_compile` também passaram |
| smoke MCP real | PASS | `integration/mcp_smoke`; resposta, telemetria e hash conferidos |

Verificação da branch preparada para publicação: project-audit `401 passed in 10.47s`; delegation `219 passed in 2.70s`; gateway + acceptance `36 passed in 0.95s`.

As execuções red foram preservadas; nenhuma falha foi apagada.
