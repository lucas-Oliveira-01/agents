# Project Audit — Current State

**Status em 2026-09-26: Swarm Architecture (L2/L3) estável; integrado na `main`.**

## Baseline e Arquitetura Swarm

O Project Audit (PA) evoluiu do estágio *Single-Agent MVP* para uma verdadeira orquestração Swarm de L2. As refatorações mais recentes conectaram a skill nativamente ao `omniroute-delegation` (OD), delegando a execução tática (L3) a agentes especializados através do `DelegationGateway`.

**1. Separação de Responsabilidades (Trust Boundary):**
- **Orquestrador (PA - L2):** Gerencia o plano de auditoria, cria os `WorkItems`, monitora o snapshot do repositório e agrega resultados.
- **Delegação (OD - L3):** Gerencia a comunicação com os modelos de linguagem, parser tolerante, execução assíncrona, e sandboxing. Não há mais chamadas MCP diretas originadas no PA (Bug C-007 resolvido).

**2. Integração Pydantic e Contratos:**
A comunicação entre as camadas ocorre através dos contratos oficiais `AuditContract` e `LeafContract`. O PA não constrói mais chamadas MCP manuais e nem lida com strings brutas, promovendo tipagem forte end-to-end.

## Phase 8 — Operational Validation

A pós-condição da Phase 7 agora passa por uma camada explícita de aceitação operacional. O branch da Phase 8 adiciona um corpus determinístico, testes de repetição do runtime e um exercício completo do FindingLifecycle.

A suíte também valida uma propriedade necessária para repetibilidade: fingerprints de inspeções determinísticas não dependem de IDs voláteis de WorkItems. O resultado de um mesmo alvo, metodologia e conteúdo observado deve permanecer canonicamente estável entre execuções.

## Phase 9 — Explicit Deterministic Classification Layer

A camada de Deterministic Intelligence agora possui um contrato explícito. `prepare_audit()` materializa um `ProjectProfile` e registros imutáveis `ClassificationResult` antes do planejamento, cobrindo classificação de arquivos, stack, superfícies tecnológicas, aplicabilidade e tipo de tarefa.

Os resultados carregam `classifier_id`, versão, entradas, resultado, confiança, justificativa e provenance. Nenhuma dessas decisões usa LLM, rede ou mutação do projeto.

## Phase 10 — Runtime Incremental Reuse

A matriz incremental agora participa da execução real. WorkItems regenerados são associados por identidade lógica (auditor + target_surface); ausência ou ambiguidade de Evidence falha fechado para REAUDIT. Quando REUSE é provado seguro, o runtime cria uma nova Evidence imutável vinculada ao WorkItem/Snapshot atuais e preserva a linhagem por derived_from_evidence_ref. Findings não corrigidos de superfícies reutilizadas são carregados para a reconciliação de lifecycle, evitando falsos FIXED.

## Resultados Implementados e Escalabilidade

| Feature | Estado | Descrição Técnica |
|---|---|---|
| Injeção de Dependência | PASS | O PA agora depende do pacote local `omniroute-delegation` no workspace (`uv.sources`), sendo as duas skills provisionadas de forma unificada. |
| Tratamento de Cobertura Parcial | PASS | A política de "Fail-Closed" que mascarava falhas semânticas gerando "0 findings" foi substituída. Falhas de parsing resultam em estado `PARTIAL_COVERAGE`, preservando findings que já haviam sido extraídos e isolando lixo na lista de `raw_errors`. |
| Grafo de Evidência e Snapshot Drift | PASS | O aborto global de auditoria por alteração de hash foi substituído por uma invalidação em nível de nó (Node-Level Invalidation). Mudanças em arquivos marcam como `STALE` apenas a `Evidence` daquele arquivo. |
| Stateful Sandboxing (L3W) | PASS | A execução local dos agentes de auditoria ocorre através do `L3WDelegate` usando `git worktree` em formato detached, Memory Bubbles e ciclo de vida assíncrono blindado contra processos zumbis (`WorkerManager`). |

## Artefatos e Testes
O conjunto atual passou em CI com 100% de sucesso nas versões Py 3.9 e 3.13, possuindo regressões específicas para:
- Cobertura de deriva parcial (Snapshot Drift em arquivo isolado).
- Extração de *findings* com LLM tagarela (`SCHEMA_VIOLATION` contornado).
- Detecção e Bloqueio de credenciais antes do transporte MCP.

Com a consolidação na `main`, a suíte do Project Audit deixou de ser um projeto isolado e atua agora como o Orquestrador L2 principal do framework Antigravity Skills.


## Phase 11 — Change Impact & Reaudit Necessity

A análise incremental agora possui um elo determinístico explícito entre mudança de snapshot e decisão de execução. Para auditorias com `previous_run_ref`, o runtime calcula eventos de Change Impact, propaga o impacto por source/dependency Evidence e registra a justificativa da decisão no `AuditWorkItem.decision_basis`.

A matriz existente continua sendo a autoridade de execução: `INVALIDATE > REAUDIT > REVALIDATE > REUSE`. Renames só preservam REUSE quando a continuidade é demonstrada por uma correspondência única de fingerprint; Evidence derivada recebe referências de caminho atualizadas sem alterar o registro histórico.

Não houve expansão do schema canônico, introdução de SLM/LLM para Change Impact ou mudança de responsabilidade do OmniRoute.


## Phase 12 — Classification Lineage & Reclassification

O runtime agora persiste um lineage imutável e auxiliar de `ClassificationResult` indexado pelo `TargetSnapshot`. Auditorias incrementais com `previous_run_ref` comparam deterministicamente os resultados históricos e atuais; mudanças materiais em `task-classifier` ou em classificações de applicability reconsideram somente os WorkItems demonstravelmente dependentes.

Quando o lineage histórico não existe, a decisão falha fechado para `REAUDIT`. Mudanças globais de ProjectProfile, stack, technology-surface ou file classification não ampliam o escopo sem uma dependência explícita.

Não houve nova entidade canônica de Layer 2 nem alteração dos schemas JSON canônicos.
