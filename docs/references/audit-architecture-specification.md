# Audit System Architectural Specification

*Status: DRAFT (Pre-implementation phase)*

Esta especificação consolida as diretrizes para o ecossistema de auditoria baseada em agentes, unificando a orquestração (`project-audit`), infraestrutura de execução (`OmniRoute`), normalização determinística (`audit-normalize`) e estado incremental (`.audit/`).

---

## 1. Decisões a serem adicionadas às ADRs Existentes

- **Em `audit-pipeline-modularity.md`:** 
  - *Fail-Open vs Fail-Closed:* Definir que classificadores incertos não podem eliminar silenciosamente superfícies de risco. Classificadores reduzem trabalho, mas a incerteza exige retenção de escopo.
  - *Independent Verifier:* Inserir explicitamente o papel de "Verifier" que atua após o "Strong Auditor", avaliando evidências de forma isolada (evitando viés de confirmação) antes da consolidação de findings graves (P0/P1).

- **Em `isolated-audit-repository.md`:**
  - *Retenção de Dados:* Diferenciar artefatos versionados (manifestos, ledgers, relatórios canônicos) de artefatos transitórios não versionados (caches do provider, transcrições brutas de LLM, binários pesados), para evitar o vazamento de segredos e inchaço do repositório.

- **Em `omniroute-policy-gateway.md`:**
  - *Data Egress Policy:* O Orchestrator deve classificar a sensibilidade dos dados antes de invocar o gateway. O OmniRoute só pode executar tarefas dentro das restrições de *Trust* passadas pela política (ex: `LOCAL_ONLY`, `APPROVED_EXTERNAL`).

---

## 2. Novas ADRs Realmente Necessárias

Para evitar *overengineering* (a criação de "managers" para tudo), as preocupações restantes serão agrupadas em apenas 3 novas ADRs essenciais que definem o comportamento do sistema:

1. **`ADR-04: Incremental State & Evidence Validity`**
   - **Foco:** Reuso de conclusões depende estritamente da validade da evidência subjacente, não apenas de um `git diff` de arquivo.
   - **Decisão:** Separar o ciclo de vida do Finding (ex: `PERSISTING`, `FIXED`) do ciclo de vida da Evidência (`VALID`, `STALE`). Requer o mapeamento de dependências da evidência (código + config + schema).

2. **`ADR-05: Execution Safety & Trust Boundary`**
   - **Foco:** Isolamento contra dados não-confiáveis do repositório (ex: README com injeção de prompt ou comandos destrutivos).
   - **Decisão:** Implementação de um *Execution Safety Gate* determinístico. Comandos de leitura executam, comandos com efeito colateral exigem sandbox, comandos destrutivos são bloqueados. O projeto auditado é tratado sempre como `UNTRUSTED DATA`.

3. **`ADR-06: Reproducibility & Audit Target Snapshot`**
   - **Foco:** Um *commit hash* sozinho não garante o mesmo ambiente ou metodologia de auditoria.
   - **Decisão:** Toda auditoria opera sobre um `TargetSnapshot` (estado do git, dependências geradas) e inclui as versões da metodologia (`policy_version`, `auditor_version`, `schema_version`).

---

## 3. Contratos Canônicos (Entidades Lógicas)

Estes não são "microserviços" nem "managers independentes", mas sim **estruturas de dados estritas (schemas)** que trafegam entre as fases:

- **`TargetSnapshot`**: Identidade exata e determinística do alvo auditado (commit + working tree status + dependências ativas).
- **`AuditPlan`**: Estrutura gerada pelo Orchestrator contendo escopo, aplicabilidade, budget global, políticas e itens de trabalho (`AuditWorkItems`).
- **`AuditWorkItem`**: A menor unidade de execução (ex: "verificar autorização no arquivo X"). Permite paralelismo e retry isolado.
- **`AuditRun`**: Estado persistente da execução em andamento (`PLANNED`, `RUNNING`, `COMPLETED`, `PARTIAL`, `FAILED`), gerido por um mecanismo *Single-Writer* (o Orchestrator).
- **`Evidence` / `EvidenceValidity`**: Objeto imutável contendo a prova. Inclui *fingerprint* determinístico e estado de validade em auditorias incrementais.
- **`FindingFingerprint`**: Identidade estável do problema através do tempo, não acoplada estritamente a números de linha.

---

## 4. Invariantes Arquiteturais a Preservar

- **Single-Writer de Estado:** Trabalhadores (Specialized Auditors) produzem *outputs imutáveis*. Apenas o Orchestrator atualiza o estado canônico do `.audit/` para evitar corrupção por concorrência.
- **Evidence > Narrative:** Nenhuma hipótese deve ser promovida a finding `CONFIRMED` sem evidência extraída (ex: AST, diff ou comportamento reproduzido).
- **Determinismo do Normalizer:** O `audit-normalize` nunca usa LLM e nunca "inventa" ou tenta inferir categorias ausentes; ele apenas compila o que já está provado no contrato.
- **Auditoria Incompleta ≠ Ausência de Problemas:** Se o *Budget* acabar, o estado do módulo é `PARTIAL`, nunca `COMPLETE` com "nenhum problema encontrado".
- **Sem Delegação Recursiva no Provider:** Agente chama OmniRoute. OmniRoute chama LLM. O LLM folha não invoca novas instâncias do OmniRoute autonomamente.

---

## 5. Indefinições (Requerem Decisão Futura)

- **Algoritmo Exato do "Evidence Dependency Graph":** Como rastrear matematicamente que uma mudança no `pom.xml` invalida a evidência em `UserService.java` (Heurística simples ou AST profundo?).
- **Algoritmo do "Finding Fingerprint":** Como gerar um hash estável para um problema que sobrevive a refatorações que mudam as linhas de código.
- **Layout Físico do `.audit/`:** A estrutura de diretórios (`runs/`, `state/`, `cache/`) ainda precisa ser congelada.
- **Single-Writer Lock Protocol:** Como garantir que execuções assíncronas abortem graciosamente ou enfileirem escritas.

---

## 6. Critério Objetivo para `Architecture Frozen`

A implementação física do agente `project-audit` **NÃO DEVE** iniciar até que todos os itens abaixo estejam *checados*:

- [ ] ADRs 04, 05 e 06 documentadas e aprovadas.
- [ ] Estrutura JSON/Schema canônica para `AuditPlan` e `AuditWorkItem` formalizada.
- [ ] Estrutura JSON/Schema para `TargetSnapshot` e `AuditRun` formalizada.
- [ ] Definição objetiva do Lifecycle de Evidência vs Lifecycle de Finding mapeada.
- [ ] Semântica de falhas e *budgets* (quando abortar, quando considerar PARTIAL) formalizada.
- [ ] Estrutura inicial do repositório `.audit/` acordada.
