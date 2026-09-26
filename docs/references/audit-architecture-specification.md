# Audit System Architectural Specification

*Status: IMPLEMENTED — core architecture with Phase 3 incremental graph*

Esta especificação consolida as diretrizes para o ecossistema de auditoria baseada em agentes, unificando a orquestração (`project-audit`), infraestrutura de execução (`OmniRoute`), normalização determinística (`audit-normalize`) e estado incremental (`.audit/`).

---

## 1. Decisões a serem adicionadas às ADRs Existentes

- **Em `audit-pipeline-modularity.md`:** 
  - *Applicability Uncertainty vs Execution Safety:* Separar as duas políticas. 
    - Incerteza de Classificação (Applicability): Incerteza **não exclui** silenciosamente uma superfície. O escopo é ampliado ou mantido (`DO NOT EXCLUDE`).
    - Incerteza de Execução (Safety Gate): Aqui sim, **Fail-Closed**. Se a decisão de segurança não estiver disponível, o comando não é executado (`DO NOT EXECUTE`).
  - *Independent Verifier:* Inserir explicitamente o papel de "Verifier" que atua após o "Strong Auditor", avaliando evidências de forma isolada (evitando viés de confirmação) antes da consolidação de findings graves (P0/P1).

- **Em `isolated-audit-repository.md`:**
  - *Retenção de Dados:* Diferenciar artefatos versionados (manifestos, ledgers, relatórios canônicos) de artefatos transitórios não versionados (caches do provider, transcrições brutas de LLM, binários pesados), para evitar o vazamento de segredos e inchaço do repositório.

- **Em `omniroute-policy-gateway.md`:**
  - *Data Egress Policy:* O Orchestrator deve classificar a sensibilidade dos dados antes de invocar o gateway, operando no nível do `AuditWorkItem` (ex: `WI-01` pode ter política diferente de `WI-02`). O OmniRoute só pode executar tarefas dentro das restrições de *Trust* passadas.

---

## 2. Novas ADRs Realmente Necessárias

Para evitar *overengineering* (a criação de "managers" para tudo), as preocupações restantes serão agrupadas em apenas 3 novas ADRs essenciais. **A ordem de dependência rigorosa é 06 -> 04 -> 05**.

1. **`ADR-06: Reproducibility & Audit Target Snapshot`**
   - **Foco:** Um *commit hash* sozinho não garante o mesmo ambiente ou metodologia de auditoria. Define a identidade ontológica exata do que está sendo auditado.

2. **`ADR-04: Incremental State & Evidence Validity`**
   - **Foco:** Reuso de conclusões depende estritamente da validade da evidência subjacente. Separar a identidade da evidência da validade, e a identidade do finding do ciclo de vida.
   - **Requisito:** Depende da fundação construída pela ADR-06.

3. **`ADR-05: Execution Safety & Trust Boundary`**
   - **Foco:** Isolamento contra dados não-confiáveis do repositório e políticas de Egress.

---

## 3. Contratos Canônicos (As 3 Camadas)

Para não misturar responsabilidades, o sistema é dividido em três camadas estritas de contrato:

### Camada 1: Audit Output Contract (Especializado)
- **Formato:** Markdown (`00_inventory.md`, `01_coverage.md`, `02_analytical.md`, `03_ledger.md`).
- **Função:** Saída universal gerada pelos Specialized Auditors (`security-audit`, `code-audit`).
- Eles **não** devolvem JSON. Devolvem prosa técnica estruturada.

### Camada 2: Orchestrator Internal Contracts (Estado Persistido)
- **Formato:** Modelos Semânticos / JSON Interno (armazenado em `.audit/runs/`).
- **Função:** Controle do pipeline de orquestração.
- **Entidades:** 
  - `TargetSnapshot`: Identidade do alvo (commit + dependências metodológicas).
  - `AuditPlan`: Estrutura de escopo e budget.
  - `AuditWorkItem`: Unidade atômica com estado de execução.
  - `AuditRun`: O container persistente da execução global.
  - `Evidence / FindingFingerprint`: Identidades lógicas de problemas e suas provas.

### Camada 3: Normalizer Canonical Contract (A Fonte da Verdade)
- **Formato:** JSON rigoroso (`report_data.json` regido por `report_data.schema.json`).
- **Função:** Output 100% determinístico produzido exclusivamente pela ferramenta `audit-normalize`. Nenhuma outra entidade gera esse arquivo.

---

## 4. Invariantes Arquiteturais a Preservar

- **Single-Writer State:** O Orchestrator é a única *autoridade* capaz de publicar/mutacionar o estado canônico do *run*. O mecanismo concreto (file lock, atomic rename) é detalhe, mas a propriedade de um único publicador é arquitetural.
- **Evidence > Narrative:** A severidade ou confiança de um *finding* deve ser justificada por evidência atribuível (código fonte, metadados, execução). Narrativa do LLM sozinha não pode elevar o status epistêmico.
- **Determinismo do Normalizer:** O `audit-normalize` nunca usa LLM e nunca "inventa" categorias.
- **Sem Delegação Recursiva no Provider:** Agente chama OmniRoute. OmniRoute chama LLM. Sem loop no provider.
- **Diferenciação Estrita de Falha (ADR-07):** `BLOCKED` (restrição de segurança deliberada) ≠ `FAILED` (erro de infra) ≠ `PARTIAL` (budget esgotado, com resultados válidos).

---

## 5. Indefinições Estruturais

- **Mecanismo de Lock do `.audit/`:** Como garantir o Single-Writer fisicamente.

---


### Fase 3 — Evidence Dependency Graph

O algoritmo incremental agora é congelado em project_audit.incremental:

1. Evidence.source_refs são dependências fortes (SOURCE).
2. Evidence.dependencies são dependências semânticas desacopladas (SEMANTIC).
3. Cada aresta é resolvida contra os fingerprints dos inputs do TargetSnapshot que produziu a Evidence.
4. Fonte/dependência removida ou inexiste no snapshot anterior torna o contexto não determinável e exige REAUDIT; remoção no snapshot atual produz INVALIDATE.
5. Mudança de fonte exige REAUDIT; mudança de dependência semântica exige REVALIDATE.
6. Mudança de audit_contract_version ou policy_version exige REAUDIT.
7. Mudança da versão do auditor exige REVALIDATE.
8. Sem dependências factuais registradas, a decisão é REAUDIT por fail-safe.
9. A precedência decisória é fixa: INVALIDATE > REAUDIT > REVALIDATE > REUSE.

INVALIDATE permanece decisão de nível Evidence. Como o contrato canônico de AuditWorkItem
possui apenas ações executáveis REUSE, REVALIDATE e REAUDIT, uma decisão INVALIDATE
é vinculada a REAUDIT para impedir o reaproveitamento e forçar nova análise.


### Fase 4 — Independent Verifier

Após cada revisão semântica, o Core executa um Verifier independente antes da consolidação dos artifacts.
O Verifier não consome raw output, provider, model ou narrativa do auditor para decidir a passagem do gate;
ele verifica exclusivamente a aderência entre candidato, Evidence persistida, WorkItem e TargetSnapshot.

P0/P1 somente podem atravessar o gate quando já são CONFIRMED, HIGH e possuem localização de fonte ancorada
nas referências da Evidence. Falhas produzem VERIFIED, REJECTED ou NOT_DETERMINABLE; o Verifier jamais promove
um candidato para CONFIRMED. Candidatos P0/P1 não verificados são removidos do conjunto consolidado que alimenta
o normalizer, enquanto o resultado da verificação permanece registrado no execution state e no Ledger.

## 6. O Caminho para `Architecture Frozen`

A implementação física do agente `project-audit` **NÃO DEVE** iniciar até que a seguinte esteira termine:

1. [x] **ADR-04, 05, 06, 07** (Aprovadas)
2. [x] **Canonical Data Model** (Aprovado)
3. [x] **Semantic Validators** (Aprovado)
4. [x] **Cross-model consistency check** (Revisão final de consistência estrutural e autoridade)
5. [x] **JSON Schemas derivados do modelo** (Representação mecânica da estrutura)
6. [x] **Schema validation passou**
7. [x] **Schema ↔ Model consistency passou**
8. [x] **Architecture Frozen** (Nenhuma decisão arquitetural implícita)\n## Phase 5 — Immutable Auto-Fix Transaction\n\nAuto-fix is a transaction over immutable audit state, never an in-place mutation of an existing Run/Evidence/Finding record.\nThe transaction is valid only for one independently VERIFIED P0/P1 candidate from a clean COMMIT-target Snapshot A.\n\nThe worker operates in an isolated L3W workspace and may return a patch touching only the candidate's verified source file.\nThe Orchestrator applies the patch only after `git apply --check`, captures Snapshot B, and runs a dedicated post-fix audit.\nA Before/After Ledger records Snapshot A, Snapshot B, patch SHA-256, worker receipt, and post-fix finding presence.\nFindingLifecycle=FIXED is recorded only when the same logical finding identity is absent after the post-fix audit; otherwise\nthe transaction is NOT_FIXED/PERSISTING. The historical source run and its Evidence remain immutable.\n\n