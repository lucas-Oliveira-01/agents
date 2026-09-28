# Matriz suportada

| Execução | Contrato atual | Situação |
|---|---|---|
| 012_full_normalize | run_full_audit(normalize=True), MCP real | BLOCKED: transporte sandbox |
| 001_full_worktree | full, WORKTREE, MCP real | BLOCKED: `GatewayUnreachableError`, `Operation not permitted`; retry escalado rejeitado |
| 002_full_commit | full, COMMIT; HEAD limpo materializado e cada blob conferido | NOT RUN: depende do transporte full |
| 003_transient | prepare --no-persist | Renomeado: full --no-persist histórico nunca era transitório; combinação agora rejeitada |
| 004_incremental | API previous_run_ref apontando baseline desta sessão | NOT RUN: baseline semântico depende do transporte full |
| 005_snapshot_drift | Mutação controlada após inspeção real; publicação bloqueada/Evidence preservada | CONTROL PASSED (`005_snapshot_drift_final4`): PARTIAL/PARTIAL, 2 stale Evidence, not published |
| 006_prepare_only | CLI prepare | PASS (`006_prepare_only_final`) |
| 007_engineering_only | CLI engineering (somente pass determinístico correspondente) | PASS (`007_engineering_only_final`), 9 inspections/9 Evidence |
| 008_fix_guard | CLI fix exige run-id/finding-id; mutação corretiva do SmartServ fora da aceitação READ_ONLY | Pendente validação de guard; execução de correção não aplicável sem candidato autorizado |

Uma cópia nova do alvo, um ambiente principal; output/state sob `.audit`. Exclusão via `core.excludesFile` externo à árvore, sem modificar `.git/.gitignore` do alvo. O smoke real passou antes de qualquer full. As tentativas falhas foram preservadas em `executions/`; o primeiro drift falhou por import ausente e o segundo por reuso de state, ambos corrigidos/isolados antes do `CONTROL PASSED` final.
