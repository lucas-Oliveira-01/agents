# Project Audit — Current State

**Status em 2026-09-24: MVP Single-Agent estável localmente; pronto para revisão do Arquiteto antes de merge.**

## Baseline e autoridade

- Branch de implementação: `feat/project-audit-single-agent-mvp`.
- Base revisada nesta sessão Codex: `15e761d`, ref remota já disponível localmente. O fetch adicional falhou por autenticação SSH; não se afirma sincronização posterior com o GitHub.
- Autoridade: [ADR-11](../decisions/ADR-11-v1-single-agent-deterministic-first.md).
- Critérios executados: [handoff de implementação V1](../procedures/v1-implementation-handoff.md), passos 1–8 verificados antes desta atualização.
- ADR-11 e handoff preservados sem alteração de conteúdo a partir de `fix/ingest-local-rule@1a87910`; esses arquivos ainda não existiam na branch candidata.

## Resultado implementado

| Item | Estado | Evidência executável |
|---|---|---|
| P-001 — Evidence lifecycle | PASS | WorkerPort real retorna o envelope com resposta, receipt e Evidence serializável, `validity=NOT_DETERMINABLE` e snapshot concreto. Schema e persistência exercitados. |
| P-002 — Policy binding | PASS | SecurityAuditor usa as políticas do AuditPlan; testes percorrem gate real, execução permitida/bloqueada e StateStore. Corrigida também a perda de `max_retries` ao recarregar a política. |
| Snapshot drift | PASS | Novo Discovery e hashes de todos os inputs auditados entre passos. Alterações abortam com `failure_state=SNAPSHOT_DRIFT`, `audit_status=STALE` e `NOT_PUBLISHED`. |
| Wipe & Re-run | PASS | Evidências da execução ficam STALE; seus outputs são descartados, outputs anteriores são preservados e nova execução usa novos run/plan/work items. Nenhum grafo incremental foi introduzido. |
| Isolamento | PASS | `.audit/.git` independente, `/.audit/` no `.gitignore` do alvo, estado em `.audit/runs` e Markdown em `.audit/`. Overrides externos e escape do diretório de estado por symlink são rejeitados. |
| E2E determinístico | PASS | Discovery → Classification → Plan → Engineering → Security → quatro Markdown → audit-normalize. |
| Layer 1 / Layer 2 | PASS | Observações e findings separados no Markdown; Evidence mantém seu contrato de estado sem `findings[]`. |
| Normalização real | PASS | CLI local do audit-normalize e validador independente: `VALID`, quatro eixos `PASS`, zero erros e avisos no dummy. |

A base `15e761d` não coletava a suíte: `classifiers.py` havia sido truncado em `68eb9f4` e `delegation.py` em `46e3d80`. Foram restauradas as definições existentes em `69ff243` e `444bd18`, preservando a normalização de separadores e completando o retorno `WorkerExecution`.

Os testes de sucesso usam componentes reais. Somente respostas de rede são simuladas na escalada semântica. Reintroduções temporárias de `validity=None` e policy nula fizeram os testes de regressão falhar; as correções foram restauradas antes da suíte final.

## Verificação local

Executado em Python 3.14.7 nesta sessão, sem inferir sucesso de CI remoto:

| Suíte completa (`python -m pytest -q` no respectivo pacote) | Resultado |
|---|---|
| `skills/universal/project-audit` | **250 passed**, nenhum skip |
| `skills/universal/omniroute-delegation` | **196 passed** |
| `skills/universal/audit-normalize` | **55 passed, 1 skipped** — fixture externa `audit-v1` ausente |

O teste de instalação limpa do normalizador passou após permitir o download das dependências do PyPI. Os novos E2Es do project-audit invocam o executável real do normalizador; por isso o ambiente de teste e o workflow CI instalam os pacotes locais audit-normalize e omniroute-delegation junto de project-audit.

Cobertura de regressão: edição, criação, exclusão e binários; mutação durante Engineering, Security, resposta semântica, renderização e normalização; vertical slice; restauração dos outputs anteriores; re-run integral; modo COMMIT mantendo o Git do alvo limpo. A escalada semântica mantém findings no JSON normalizado; observações determinísticas não são inventadas como findings.

## Artefatos da execução manual

Alvo dummy: `/tmp/project-audit-v1-e2e`.
Run: `f659741d-d918-40df-9df2-235bfb52961a`.
TargetSnapshot: `6593d235b08fd04553efcd67c9fda237d711b13a310c678b9d9a56c1da4cc9e1`.

Arquivos físicos em `/tmp/project-audit-v1-e2e/.audit/`:

- `00_inventory.md`
- `01_coverage.md`
- `02_analytical.md`
- `03_audit_ledger.md`
- `normalized/report_data.json` e seus três artefatos de validação/proveniência.

O dummy produziu 13 inspeções e zero findings formais. Isso demonstra a separação entre observação e achado; não significa ausência de vulnerabilidades. Os testes também cobrem findings semânticos não vazios com resposta de rede controlada.

Reprodução a partir da raiz, após instalar os pacotes no mesmo virtualenv:

```bash
python -m pip install -e 'skills/universal/project-audit[test]' -e skills/universal/audit-normalize -e skills/universal/omniroute-delegation
python -m project_audit --target /caminho/do/dummy --phase full --normalize
```

Para reexecutar substituindo outputs existentes, usar `--overwrite-audit`. O modo COMMIT exige que o `.gitignore` com `/.audit/` já esteja commitado e o worktree esteja limpo.

## Revisão e promoção

A implementação local atende ao handoff. Revisão estrutural assíncrona pelo Arquiteto e aprovação de merge continuam pendentes. Nenhum merge, push ou promoção à `main` foi realizado. Não foram adicionados Swarm de runtime, grafos de dependência ou nova arquitetura.
