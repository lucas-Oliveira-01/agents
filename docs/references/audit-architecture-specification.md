# Audit System Architectural Specification

*Status: DRAFT (Pre-implementation phase)*

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

- **Algoritmo Exato do "Evidence Dependency Graph":** A semântica existe (mudança em X invalida Y), mas o mecanismo de descoberta (heurística vs AST) ainda não foi congelado.
- **Mecanismo de Lock do `.audit/`:** Como garantir o Single-Writer fisicamente.

---

## 6. O Caminho para `Architecture Frozen`

A implementação física do agente `project-audit` **NÃO DEVE** iniciar até que a seguinte esteira termine:

1. [x] **ADR-06** (Target Identity)
2. [x] **ADR-04** (Evidence/Incremental Semantics)
3. [x] **ADR-05** (Trust/Execution Semantics)
4. [x] **ADR-07** (Failure/Retry/Recovery Semantics)
5. [x] **Canonical Data Model** (Modelagem Semântica dos Contratos Internos da Camada 2)
6. [ ] **Semantic Validators** (Regras de negócio que o schema não pode codificar sozinho)
7. [ ] **JSON Schemas Físicos** (A representação final do modelo)
8. [ ] **Architecture Frozen**
