# Publicação remota

Estado preparado sem modificar nem apagar o checkout original. O `.git` do checkout principal está em filesystem montado `ro`, portanto a publicação foi reconstruída em `/tmp/agents-publish` a partir de `origin/main`.

| campo | valor |
|---|---|
| `local_candidate_sha` | `3fc557c376988899f0fdb9b17f61d5b4c3c414ef` |
| `origin_main_sha` | `19d9076a32fdcad6b2b464c2db72f2968f25fb10` |
| `branch_name` | `audit/smartserv-final-validation` |
| `prepared_commit_shas` | `5c1abf6`, `33f9bce`, `cc0e2f2`; documentação nesta ponta da branch |
| `push_timestamp_utc` | `2026-09-28T05:55:21Z` (preparação; push real não autorizado) |
| `tests_executed` | publicação: project-audit 401; delegation 219; gateway + acceptance 36; regressões finais 17; normalize direcionado; `git diff --check`; `py_compile` |
| `push_status` | `BLOCKED`: GitHub mutation API e aprovação de shell recusadas por limite automático do avaliador |
| `pr_status` | `BLOCKED`: branch remota ainda não existe; criação de branch/PR exige operação de mutação |

Os commits preparados preservam a estrutura sem squash destrutivo. O diretório `smartserv_final_audit_20260928T051559Z/` permanece apenas local, conforme a política de não publicar artefatos grandes de runtime; o dossiê e seus documentos são incluídos na branch.

O veredicto da auditoria continua `RED`. A publicação do código não prova transporte MCP sem bloqueio nem a matriz semântica completa.
