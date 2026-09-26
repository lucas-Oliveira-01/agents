# Project Audit — Current State

**Status em 2026-09-26: Swarm Architecture (L2/L3) estável; integrado na `main`.**

## Baseline e Arquitetura Swarm

O Project Audit (PA) evoluiu do estágio *Single-Agent MVP* para uma verdadeira orquestração Swarm de L2. As refatorações mais recentes conectaram a skill nativamente ao `omniroute-delegation` (OD), delegando a execução tática (L3) a agentes especializados através do `DelegationGateway`.

**1. Separação de Responsabilidades (Trust Boundary):**
- **Orquestrador (PA - L2):** Gerencia o plano de auditoria, cria os `WorkItems`, monitora o snapshot do repositório e agrega resultados.
- **Delegação (OD - L3):** Gerencia a comunicação com os modelos de linguagem, parser tolerante, execução assíncrona, e sandboxing. Não há mais chamadas MCP diretas originadas no PA (Bug C-007 resolvido).

**2. Integração Pydantic e Contratos:**
A comunicação entre as camadas ocorre através dos contratos oficiais `AuditContract` e `LeafContract`. O PA não constrói mais chamadas MCP manuais e nem lida com strings brutas, promovendo tipagem forte end-to-end.

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
