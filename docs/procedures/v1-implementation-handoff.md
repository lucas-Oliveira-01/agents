# MISSÃO: Fechamento do MVP Single-Agent (Project-Audit V1)

**Para:** Modelo Implementador (Ex: Astra)
**Revisor de Memória:** Modelo Observador (Ex: Antigravity-cli/Gemini)
**Contexto Supremo:** ADR-11 (Single-Agent, Deterministic-First)

Sua missão é estritamente **fechar e estabilizar o fluxo E2E (Ponta a Ponta) real** do MVP na branch pendente, consolidando a ponte entre infraestrutura, execução e relatórios. Não crie novas camadas. Fixe a base.

## Passos da Missão (Critérios Verificáveis)

### 1. Corrigir Evidence Lifecycle (P-001)
- **Entrada:** `WorkerPort.execute_delegation()` e serialização de `Evidence`.
- **Problema Atual:** O sistema está gerando instâncias de `Evidence(validity=None)` no caminho de sucesso, violando o contrato tipado (causando crash na serialização).
- **Mudança Permitida:** Corrigir os builders e a resposta do `WorkerPort` real (não apenas mocks) para injetar validade concreta antes de instanciar a evidência.
- **Critério de Aceite:** Nenhuma instância de `Evidence` gerada pelo código em tempo de execução falha em `to_dict()` por falta de validade.

### 2. Corrigir WorkItem Policy Binding (P-002)
- **Entrada:** `SecurityAuditor.generate_work_items()` e `Orchestrator`.
- **Problema Atual:** A geração estática está criando itens com `effective_execution_policy = None` e `data_egress_policy = None`.
- **Mudança Permitida:** Fazer o binding real das políticas originadas no `AuditPlan` ou definidas pelo orquestrador injetando-as nos `WorkItems`.
- **Critério de Aceite:** O gate de egress valida políticas com objetos `ExecutionPolicy` reais, e não crasha acessando nulos.

### 3. Corrigir Snapshot Drift = Fail-Closed (Wipe & Re-run)
- **Entrada:** Módulo de orquestração (`execute_vertical_slice()` ou equivalente).
- **Problema Atual:** Falta a adoção da política da ADR-11.
- **Mudança Permitida:** Identificar alteração no snapshot entre passos -> Setar o estado como `failure_state = SNAPSHOT_DRIFT` -> Status final `STALE`. (Não implementar grafos incrementais).
- **Critério de Aceite:** Qualquer mutação no repositório auditado durante o fluxo estagna a execução com segurança e não publica.

### 4. Remover Mocks do Caminho Real
- **Entrada:** Suíte de testes (ex: `test_delegation.py`).
- **Problema Atual:** 100% dos testes que mascaravam P-001 e P-002 dependiam fortemente de `Mock(spec=WorkerPort)`.
- **Mudança Permitida:** Refatorar ou criar testes de integração E2E com `WorkerPort` e orquestrador rodando implementações de fato, ainda que com dependências injetáveis que simulem apenas a resposta da rede (evite falsos positivos lógicos).
- **Critério de Aceite:** Teste roda a integração passando os estados válidos.

### 5. Executar E2E Real (O "Happy Path")
- **Entrada:** O repositório real ou um repositório *dummy*.
- **Mudança Permitida:** Instanciar o `project-audit` contra si mesmo ou um dummy, rodar o `Discovery` -> `Plan` -> `Engineering` -> `Security`.
- **Critério de Aceite:** As fases completam sem exceções fatais.

### 6. Validar Artefatos Markdown (Layer 1)
- **Entrada:** Resultados da fase 5.
- **Critério de Aceite:** Geração física de `00_inventory.md`, `01_coverage.md`, `02_analytical.md` e `03_audit_ledger.md` no diretório `.audit/` isolado. Os artefatos carregam os `findings`, separando a semântica da mecânica de orquestração (Evidence).

### 7. Executar Integração com audit-normalize
- **Entrada:** Artefatos Markdown gerados.
- **Critério de Aceite:** O comando local do `audit-normalize` ingere os Markdowns sem erros e produz o `report_data.json` com sucesso.

### 8. Executar Suíte Completa
- **Ação:** Executar `pytest` completo na branch.
- **Critério de Aceite:** 100% dos testes (antigos + novos) passam em ambiente local. (Garanta que rodou).

### 9. Atualizar Documentação de Estado
- **Ação:** SOMENTE APÓS as etapas 1-8 passarem, atualizar o `docs/architecture/project-audit-current-state.md` removendo a *flag* de BLOCKED e sinalizando que as P-001/P-002 foram mitigadas empiricamente.

### 10. Preparar Merge
- **Ação:** Deixar o código *commitado* com a flag de que a E2E pipeline Single-Agent MVP está estável e pronta para ser mesclada na `main`.

---
**Nota para o Revisor (Memória/Status):**
Acompanhe os logs da execução e assegure o uso correto do repositório `.audit/` isolado (mantendo-o listado no `.gitignore` da raiz) como o local para armazenar o snapshot de `ai-memory` nativo da auditoria. Se o agente desviar das etapas 1-3 para construir novas abstrações (ex: criar subagentes), interrompa.
