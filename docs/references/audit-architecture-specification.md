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

## 3. Contratos Canônicos (Entidades Lógicas)

Estes contratos representam estruturas de dados que necessitam de serialização/interoperabilidade (JSON Schemas persistidos), e não dezenas de DTOs internos efêmeros:

- **`TargetSnapshot`**: Identidade exata e determinística do alvo auditado (commit + working tree status + dependências ativas + versões metodológicas).
- **`AuditPlan`**: Estrutura gerada pelo Orchestrator contendo escopo, aplicabilidade, budget global, políticas e itens de trabalho.
- **`AuditWorkItem`**: A unidade operacional atômica do incrementalismo (contém `work_id`, `auditor`, `target_snapshot`, `inputs`, `data_egress_policy`, etc).
- **`AuditRun`**: Estado persistente da execução em andamento (`PLANNED`, `RUNNING`, `COMPLETED`, `PARTIAL`, `FAILED`).
- **`Evidence` / `EvidenceValidity`**: Objeto imutável contendo a prova, e a determinação de se a prova material ainda se sustenta.
- **`FindingFingerprint`**: Identidade lógica e estável de um problema (baseada no domínio, controle afetado, semântica do ativo), não estritamente acoplada a números de linha.

---

## 4. Invariantes Arquiteturais a Preservar

- **Single-Writer State:** O Orchestrator é a única *autoridade* capaz de publicar/mutacionar o estado canônico do *run*. O mecanismo concreto (file lock, atomic rename) é detalhe, mas a propriedade de um único publicador é arquitetural.
- **Evidence > Narrative:** A severidade ou confiança de um *finding* deve ser justificada por evidência atribuível (código fonte, metadados, execução). Narrativa do LLM sozinha não pode elevar o status epistêmico.
- **Determinismo do Normalizer:** O `audit-normalize` nunca usa LLM e nunca "inventa" categorias.
- **Auditoria Incompleta ≠ Ausência de Problemas:** Se o *Budget* acabar, o estado do módulo é `PARTIAL`.
- **Sem Delegação Recursiva no Provider:** Agente chama OmniRoute. OmniRoute chama LLM. Sem loop no provider.

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
