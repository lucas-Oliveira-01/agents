# ADR 11: Project-Audit V1 Core Architecture (Single-Agent, Deterministic-First)

## Status
Accepted (Supersedes conflicting clauses in ADR-04, ADR-08, ADR-09, and Swarm Architecture for V1 Runtime)

## Context
O desenvolvimento do `project-audit` sofreu *front-loading* arquitetural, misturando a metodologia de desenvolvimento multi-agente (Swarm) com os requisitos de execução do produto. Além disso, a complexidade teórica de grafos de invalidação incrementais e classificadores LLM em cascata estava bloqueando a entrega do "Caminho Feliz" (Happy Path) funcional de ponta a ponta.

Precisamos de uma espinha dorsal simples, testável e barata computacionalmente para a V1, preservando o isolamento do estado da auditoria.

## Decision

Estabelecemos as seguintes regras como a **Autoridade Arquitetural Suprema** para a V1 do `project-audit`:

### 1. Modelo de Execução: Single-Agent
O runtime do produto na V1 é estritamente **One Agent**. Não haverá federação de agentes, *Security Agents* independentes ou *Code Agents* atuando em paralelo no runtime. O ecossistema Swarm fica restrito à metodologia de *desenvolvimento* do repositório.

### 2. Deterministic-First & Semantic Escalation
A lógica de LLM não é o motor de execução padrão; é um **mecanismo de escalada**.
- **Tarefas Determinísticas** (Discovery, Hash, Classificação de arquivos, Deteção de Stack) rodam nativamente, sem LLM.
- **Escalada Semântica**: Quando a lógica determinística se esgota, o orquestrador decide se o raciocínio semântico é estritamente necessário.
- **OmniRoute como Gateway Opcional**: Se a escalada for aprovada, a tarefa é enviada via `Task Policy` para o `OmniRoute`, que abstrai a escolha do modelo, provider, fallback e quotas. O OmniRoute atua como infraestrutura, não como uma camada obrigatória de "subagentes".

### 3. Falha Fechada para Snapshot Drift (Wipe & Re-run)
A V1 não implementará grafos de invalidação granulares.
Se houver mutação no repositório auditado durante a execução (Snapshot Drift):
- O sistema sinaliza internamente `failure_state = SNAPSHOT_DRIFT`.
- A semântica operacional deriva para `audit status = STALE`.
- A auditoria não é publicada. Uma nova execução completa deve ser solicitada.

### 4. Fronteira de Contratos Estrita (Evidence vs Markdown)
- **Layer 2 (Estado/Orquestração)**: A entidade `Evidence` registra *o que foi observado/validado*, preservando as políticas de execução (`effective_execution_policy`, `data_egress_policy`) e o binding de ciclo de vida perfeito. Não necessita de array de `findings[]` no payload canônico de estado.
- **Layer 1 (Artefatos de Saída)**: Os achados, análises e controles vão para os 4 artefatos Markdown canônicos.
- **Integração Layer 3**: Os artefatos Markdown são então processados pelo `audit-normalize` para gerar o `report_data.json`.

### 5. Repositório `.audit/` Isolado e Memória Persistente
O diretório `.audit/` (ignorado via `.gitignore` no projeto alvo) é o cofre da auditoria. Ele operará como um repositório Git isolado para preservar o histórico de execuções (`TargetSnapshot`), armazenar os relatórios Markdown e conter o `ai-memory` específico daquela auditoria, permitindo que o modelo rastreie histórico inteligente entre re-runs.

## Consequences
- **Desbloqueio Imediato**: Foco absoluto em resolver os bugs de implementação (`validity=None`) em vez de construir grafos teóricos.
- **Queda de Custos**: O *parser* determinístico faz 80% do trabalho; o LLM só é chamado com contexto reduzido.
- **Clareza de Testes**: Um único fluxo linear (Discovery -> Classification -> Applicability -> PASS 1 -> PASS 2 -> Correlation -> Markdown -> Normalize) a ser testado de ponta a ponta.
