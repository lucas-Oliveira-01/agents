# Arquitetura de Referência: Delegação, Roteamento e Auditoria Técnica com OmniRoute

## 1. Visão Geral e Contexto Operacional

### 1.1 Objetivo e Escopo da Arquitetura
Este documento estabelece a especificação arquitetural canônica para a integração entre o ecossistema de agentes/skills do Antigravity, o gateway local de roteamento de modelos de linguagem **OmniRoute** e os pipelines de auditoria técnica de software.

O sistema destina-se a atuar como uma infraestrutura de apoio analítico, revisão de código, auditoria de segurança/qualidade, diagnóstico arquitetural e gerenciamento persistente de contexto.

### 1.2 Restrições Operacionais e Integridade Acadêmica/Institucional
O sistema opera sob diretrizes estritas de não interferência autônoma no código-fonte do projeto auditado:
* **Geração Autônoma Proibida**: É vedada a geração ou modificação direta e autônoma de código de produção por parte dos agentes de IA, garantindo conformidade com regras acadêmicas e institucionais de autoria intelectual.
* **Foco Analítico e Consultivo**: A atuação das LLMs restringe-se exclusivamente a:
  * Análise estática e dinâmica;
  * Revisão e auditoria de vulnerabilidades/qualidade;
  * Diagnóstico e explicação arquitetural;
  * Documentação e sumarização técnica;
  * Planejamento e triagem de tarefas.

### 1.3 Princípio Fundamental de Otimização
A arquitetura é orientada pela equação de eficiência máxima:

$$\text{Eficiência} = \frac{\text{Qualidade} \times \text{Confiabilidade} \times \text{Rastreabilidade}}{\text{Custo de Tokens / Latência}}$$

O objetivo primário não é a mera substituição arbitrária por modelos compactos, mas a seleção determinística e dinâmica do mecanismo de menor custo financeiro e computacional capaz de satisfazer os requisitos de qualidade da tarefa.

---

## 2. Princípios de Engenharia e Modelo Mental

### 2.1 Separação Estrita: Script Determinístico vs. Cognição LLM
O sistema impõe distinção estrita entre operações determinísticas e operações cognitivas:

| Categoria | Mecanismo de Execução | Exemplos de Aplicação |
| :--- | :--- | :--- |
| **Evidência Determinística** | Scripts nativos, CLI, parsers AST | Cálculo de hashes (SHA-256), `git diff`, inventário de arquivos, AST parsing, extração de dependências, execução de testes unitários, validação sintática e de schemas JSON. |
| **Interpretação Cognitiva** | Modelos de Linguagem (LLMs via OmniRoute) | Raciocínio sobre segurança e fluxos de autenticação, análise arquitetural, correlação de regras de negócio entre módulos, interpretação de casos limítrofes e ambíguos. |

> **Regra de Ouro**: Nenhuma operação computacional determinística deve ser delegada a uma LLM.

### 2.2 Desacoplamento via Políticas de Execução (*Task Policies*)
O Orquestrador de Agentes não seleciona modelos concretos (ex: Claude 3.5 Sonnet, GPT-4o, Llama 3) nem provedores específicos (OpenAI, Anthropic, Ollama). Em vez disso, o sistema opera através de **Políticas de Execução Abstratas**:

```text
[Tarefa Cognitiva]
       ↓
[Política Abstrata] (fast, cheap, coding, context-optimized, quality-first)
       ↓
[OmniRoute]
       ↓ (Avaliação de custo, latência, quotas, saúde e cache affinity)
[Modelo / Provedor Concreto]
```

Dessa forma, alterações em disponibilidade, preços ou modelos de mercado afetam unicamente as tabelas de roteamento do OmniRoute, mantendo a camada de agentes completamente desacoplada.

### 2.3 Hierarquia de Execução e Portões de Escalonamento (*Escalation Gates*)
A delegação cognitiva segue uma progressão de menor custo para maior capacidade, controlada por validações determinísticas:

```text
               ┌───────────────────────────────┐
               │    Tarefa Identificada        │
               └──────────────┬────────────────┘
                              │
                              ▼
               ┌───────────────────────────────┐
               │ Ferramenta Determinística /   │
               │ Script Nativo                 │
               └──────────────┬────────────────┘
                              │ Sucesso
                              ▼
               ┌───────────────────────────────┐
               │ Modelo Econômico (cheap/fast) │
               └──────────────┬────────────────┘
                              │
                              ▼
               ┌───────────────────────────────┐
               │ Validação Objetiva do Schema  │
               └──────┬─────────────────┬──────┘
                      │ Aprovado        │ Reprovado / Ambíguo
                      ▼                 ▼
          ┌─────────────────────┐ ┌───────────────────────────┐
          │ Consumo do          │ │ Escalonamento para Modelo │
          │ Resultado           │ │ de Alta Capacidade        │
          └─────────────────────┘ └───────────────────────────┘
```

Critérios objetivos de validação:
1. Conformidade com JSON Schema estrito;
2. Presença de todos os campos mandatórios e referências de evidência;
3. Ausência de contradições lógicas em relação a dados determinísticos prévios;
4. Formatação e integridade de citações de código/símbolo.

> **Diretriz**: Modelos econômicos nunca validam autonomamente a qualidade de suas próprias respostas.

### 2.4 Isolamento de Contexto e Divulgação Progressiva (*Progressive Disclosure*)
Para evitar saturação de janelas de contexto e desperdício de tokens, o envio de contexto aos modelos segue uma estrutura hierárquica por níveis de granularidade:

* **Nível 0 (Perfil do Projeto)**: Metadados globais, ecossistema tecnológico, dependências primárias (`pom.xml`, `package.json`).
* **Nível 1 (Arquivos Relevantes)**: Lista de caminhos afetados e seus propósitos imediatos.
* **Nível 2 (Símbolos Relevantes)**: Assinaturas de classes, métodos, interfaces e anotações.
* **Nível 3 (Código Circunvizinho)**: Implementação do bloco/função sob auditoria direta.
* **Nível 4 (Cadeia de Dependências)**: Fluxos de chamada diretos e indiretos (call-graph relevante).
* **Nível 5 (Fonte Integral)**: Código-fonte integral, restrito a auditorias de segurança críticas onde a cadeia completa é mandatória.

### 2.5 Limite de Confiança (*Trust Boundary*) e Sanitização de Entradas
Todos os artefatos provenientes do repositório auditado são classificados como **Dados Não Confiáveis** (*Untrusted Data*):
* Arquivos-fonte, comentários de código, documentações (`README.md`), mensagens de commit, issues e fixtures de teste são processados exclusivamente como **dados passivos de entrada**.
* Sob nenhuma hipótese conteúdos extraídos do código auditado devem ser concatenados em prompts como instruções de sistema ou comandos executáveis, eliminando o vetor de ataque por *Indirect Prompt Injection*.

---

## 3. Topologia e Fluxo de Execução da Arquitetura

### 3.1 Diagrama de Camadas da Arquitetura

```text
┌────────────────────────────────────────────────────────────────────────┐
│                        AGENTE ANTIGRAVITY                              │
│  - Recebe comandos do usuário e gerencia objetivos de alto nível        │
│  - Decide pontos de delegação cognitiva vs. execução local             │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  ORQUESTRADOR DE DOMÍNIO (AUDITORIA)                   │
│  - Matriz de aplicabilidade e escopo (FULL, ONLY, EXCEPT)              │
│  - Análise incremental Git Diff (arquivo -> símbolo -> finding)        │
│  - Gestão de estado e histórico de findings (.audit/state/)            │
│  - Divulgação progressiva de contexto (Nível 0 a 5)                    │
│  - Controle de orçamento global de tokens por auditoria                │
│  - Portões de qualidade e políticas de escalonamento                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│              DELEGATION GATEWAY (WRAPPER MCP / FIREWALL)               │
│  - Interface MCP restrita: delegar_tarefa(), consultar_status()        │
│  - Capability Firewall: bloqueio de acessos administrativos            │
│  - Prevenção de delegação recursiva (profundidade estrita = 1)         │
│  - Cache determinístico de aplicação (SHA-256)                         │
│  - Normalização de entrada e validação de schema de saída              │
│  - Registro de proveniência semântica e custos por tarefa              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP (localhost:20128/v1)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        OMNIROUTE (INFRAESTRUTURA)                      │
│  - Roteamento dinâmico via políticas (auto/coding, auto/fast, etc.)    │
│  - Resiliência: fallback, retry com backoff, circuit breakers          │
│  - Gestão de tráfego: quotas, rate limiting, balanceamento P2C         │
│  - Cache de infraestrutura: prompt-cache affinity, semantic cache      │
│  - Observabilidade de rede: latência, tokens, telemetria por provedor  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     PROVEDORES / MODELOS FOLHA                         │
│  - OpenAI / Anthropic / Groq / Provedores Locais (Ollama, vLLM)        │
│  - Execução estrita do payload (sem capacidades de sub-delegação)      │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Agente Orquestrador (*Orchestrator*)
Camada responsável pelas decisões de negócio e integridade analítica:
* Não executa roteamento de rede nem seleção de endpoints de LLM.
* Formula os objetivos da tarefa, define o escopo de arquivos aplicáveis e valida a consistência conceitual dos resultados.

### 3.3 Gateway de Delegação MCP (*Delegation Gateway & Capability Firewall*)
Componente de mediação entre os agentes e o OmniRoute:
* Expõe ferramentas estritamente controladas através do protocolo MCP (`omniroute_mcp.py` / `omniroute`).
* Funciona como barreira de segurança (*Capability Firewall*), impedindo que modelos externos alterem rotas, quotas, provedores ou configurações internas do OmniRoute.
* Aplica o cache determinístico da aplicação antes de despachar a requisição para a rede.
* Inibe loops e chamadas recursivas.

### 3.4 Gateway OmniRoute (`localhost:20128`)
Servidor local de infraestrutura de inferência:
* Expõe endpoints compatíveis com a especificação OpenAI (`/v1/chat/completions`, `/v1/models`).
* Aplica lógica de Auto-Combo, balanceamento P2C (*Power of Two Choices*), rate-limiting preventivo e monitoramento contínuo da saúde dos provedores configurados.

### 3.5 Provedores e Modelos Folha (*Leaf Models*)
* Instâncias terminais de computação cognitiva.
* Recebem prompts fechados e retornam saídas estruturadas. Não possuem acesso a ferramentas de delegação recursiva.

---

## 4. O Sistema de Auditoria Modular e Incremental

### 4.1 Módulos Especializados e Contrato de Normalização
A arquitetura de auditoria é composta por módulos analíticos independentes, onde cada módulo é especialista em uma dimensão do sistema:

```text
├── project-audit       (perfil global, governança e conformidade)
├── code-audit          (qualidade, acoplamento, complexidade e code smells)
├── security-audit      (vulnerabilidades OWASP, sanitização, autenticação)
├── database-audit      (modelagem relacional, queries, migrações, índices)
├── test-audit          (cobertura de testes, asserções, testes ausentes)
├── git-audit           (histórico de commits, integridade de branches, churn)
└── documentation-audit (aderência a specs, completude técnica)
```

#### Contrato Canônico de Normalização (`audit-normalize`)
* Cada auditor produz suas descobertas em formato estruturado.
* O componente determinístico `audit-normalize` agrega, desduplica, valida schemas e gera o dataset canônico `report_data.json`.
* `audit-normalize` é rigorosamente determinístico (não utiliza LLMs) para assegurar neutralidade e rastreabilidade dos dados auditados.

### 4.2 Matriz de Aplicabilidade e Escopo do Usuário
A execução de auditorias não deve ser exaustiva por padrão, mas orientada por aplicabilidade técnica e filtros de escopo:

#### 1. Verificação de Aplicabilidade (*Applicability*)
O orquestrador inspeciona o projeto antes de instanciar auditores:
* *Exemplo*: Um utilitário de terminal em Java puro (CLI, sem frontend, sem HTTP, sem banco de dados relacional) desativa automaticamente `database-audit` e verificações web, executando apenas `code-audit`, `security-audit` (cli/io), `test-audit` e `git-audit`.

#### 2. Escopos de Execução (*User Scopes*)
O sistema aceita comandos determinísticos de escopo:
* `FULL`: Todos os módulos aplicáveis são executados.
* `FULL EXCEPT <Módulos>`: Executa todos os módulos aplicáveis exceto os especificados.
* `ONLY <Módulos>`: Executa estritamente o subconjunto de auditores solicitado.

### 4.3 Auditoria Incremental Orientada a Git Diff e Grafo de Impacto
Em vez de reauditar todo o repositório a cada ciclo, a auditoria rastreia alterações entre commits de referência:

```text
Commit Base (A: abc123) ──▶ Commit Alvo (B: def456)
                                   │
                                   ▼
                            git diff --name-status
                                   │
                                   ▼
                      Grafo de Impacto de Arquivos
                                   │
                                   ▼
                     Análise de Impacto por Símbolo
                                   │
                                   ▼
                     Mapeamento de Dependências
                                   │
                                   ▼
                  Classificação de Impacto no Finding
```

#### Regra de Isolamento por Símbolo
A modificação de um arquivo não invalida automaticamente todas as descobertas daquele arquivo. Se o finding `SEC-001` reside em `AuthService#validateToken()`, e uma alteração subsequente ocorre apenas em `AuthService#formatUserName()`, a evidência de `SEC-001` permanece estável, dispensando reauditoria completa.

### 4.4 Ciclo de Vida e Continuidade dos Findings
Cada finding identificado é rastreado por um identificador estável e possui transições de estado controladas:

```text
                   ┌───────────────────────────────────────┐
                   │             NOVO FINDING              │
                   └──────────────────┬────────────────────┘
                                      │
                 ┌────────────────────┴────────────────────┐
                 │ Alteração em commit subsequente         │
                 ▼                                         ▼
   ┌───────────────────────────┐             ┌───────────────────────────┐
   │ Sem impacto detectado no  │             │ Impacto detectado no      │
   │ símbolo ou contexto       │             │ símbolo ou contexto       │
   └─────────────┬─────────────┘             └─────────────┬─────────────┘
                 │                                         │
                 ▼                                         ▼
          [ REUSE / PERSISTS ]                     [ REVALIDATE ]
                 │                                         │
                 │                         ┌───────────────┴───────────────┐
                 │                         ▼                               ▼
                 │                 Evidência mantida             Solução comprovada
                 │                         │                               │
                 │                         ▼                               ▼
                 │                   [ MODIFIED ]                    [ RESOLVED ]
                 │
                 ▼
         [ INVALIDATE ] (Caso arquivo ou trecho seja removido sem contrapartida)
```

* **REUSE (Reaproveitamento)**: Contexto e código permanecem inalterados; o finding é replicado para o novo relatório sem nova chamada de LLM.
* **REVALIDATE (Revalidação)**: O código associado sofreu modificação; uma tarefa focada (escopo restrito) é despachada para verificar a procedência do finding.
* **RESOLVED (Resolvido)**: Apenas é atribuído quando há verificação explícita e positiva de que a falha deixou de existir. **Nunca classificar como resolvido por mera ausência do finding em um diff raso.**
* **PERSISTS (Persistente)**: O finding continua reproduzível e inalterado.
* **MODIFIED (Modificado)**: O finding persiste, porém suas linhas, contexto ou severidade foram alterados.

---

## 5. Estratégia de Cache e Persistência de Estado

### 5.1 Dualidade de Cache: Infraestrutura vs. Aplicação Determinística
Para maximizar desempenho e reprodutibilidade, a arquitetura divide a responsabilidade de cache em duas camadas ortogonais:

```text
┌────────────────────────────────────────────────────────────────────────┐
│               CAMADA 1: CACHE DETERMINÍSTICO DA APLICAÇÃO              │
│  - Reside no Delegation Gateway / Orquestrador                         │
│  - Escopo: Tarefas de domínio, idempotência semântica e auditoria      │
│  - Chave: Hash SHA-256 exato de parâmetros de entrada normalizados     │
│  - Armazenamento: Persistido em disco dentro de .audit/cache/          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Cache Miss
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               CAMADA 2: CACHE DE INFRAESTRUTURA (OMNIROUTE)            │
│  - Reside no motor local do OmniRoute                                  │
│  - Escopo: Prompt caching em provedores (Anthropic/OpenAI), afinidade  │
│  - Chave: Similaridade semântica, prefixos idênticos de prompt         │
│  - Armazenamento: Gerenciado pelo OmniRoute / Memória volátil          │
└────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Especificação da Chave de Cache Determinístico da Aplicação
O Delegation Gateway calcula a chave de cache determinístico através do hash SHA-256 de uma estrutura canônica serializada:

$$\text{CacheKey} = \text{SHA-256}\Big(\text{task\_type} \parallel \text{normalized\_input} \parallel \text{context\_hash} \parallel \text{prompt\_version} \parallel \text{tool\_version} \parallel \text{policy\_id} \parallel \text{output\_schema\_version}\Big)$$

Campos componentes da chave:
1. `task_type`: Identificador do tipo de tarefa (ex: `endpoint_extraction`, `triage_vulnerability`).
2. `normalized_input`: Dados de entrada sem variações de formatação irrelevantes.
3. `context_hash`: Hash SHA-256 dos arquivos de código-fonte fornecidos como contexto.
4. `prompt_version`: Versão do template de prompt utilizado.
5. `tool_version`: Versão do script/orquestrador que originou a chamada.
6. `policy_id`: Identificador da política aplicada (ex: `auto/coding`, `auto/cheap`).
7. `output_schema_version`: Versão do schema de saída esperado.

Caso os arquivos e o prompt não tenham mudado, o Delegation Gateway retorna o resultado persistido imediatamente (`CACHE HIT`), sem acionar a rede ou o OmniRoute.

### 5.3 Repositório Independente de Auditoria (`.audit/`) e Isolamento do Git
Para garantir que nenhum artefato gerado pela IA seja versionado no repositório de código do projeto auditado, a arquitetura institui uma fronteira estrita de repositórios:

```text
meu-projeto/
├── .git/               ──▶ Repositório Git Primário do Projeto de Engenharia
├── .gitignore          ──▶ Deve conter obrigatoriamente a linha: .audit/
├── src/
├── pom.xml
└── .audit/             ──▶ Diretório de Trabalho do Sistema de Auditoria
    └── .git/           ──▶ Repositório Git Independente da Auditoria
```

#### Vantagens do Isolamento
1. **Conformidade e Limpeza**: O código acadêmico/profissional não é contaminado por arquivos temporários, logs ou relatórios de IA.
2. **Versionamento Próprio**: A auditoria ganha versionamento independente, permitindo rastrear o histórico de análises, mudanças de findings e métricas ao longo do tempo.
3. **Isolamento de Segredos**: Arquivos de estado e cache não correm risco de submissão acidental a repositórios públicos de código.

### 5.4 Estrutura de Diretórios Recomendada para `.audit/`

```text
.audit/
├── .git/                  # Controle de versão independente da auditoria
├── config.json            # Configuração local da auditoria e políticas de escopo
├── state/                 # Estado persistente atual do projeto
│   ├── profile.json       # Perfil tecnológico identificado (Nível 0)
│   ├── active_findings.json # Registro canônico de findings ativos
│   └── baseline_commit    # Commit SHA da última auditoria consolidada
├── runs/                  # Execuções históricas
│   └── 20260921_143000/
│       ├── run_manifest.json # Metadados, escopo, commit alvo e estatísticas
│       ├── raw/           # Respostas brutas por auditor
│       └── report_data.json # Dataset normalizado gerado pelo audit-normalize
├── cache/                 # Armazenamento persistente do cache determinístico
│   └── tasks/             # Arquivos indexados por CacheKey (SHA-256)
└── reports/               # Relatórios técnicos formatados (Markdown, HTML, etc.)
```

---

## 6. Governança de Execução, Resiliência e Recursos

### 6.1 Envelopes de Políticas do OmniRoute
O sistema mapeia categorias operacionais em políticas de roteamento gerenciadas pelo OmniRoute:

| Política | Perfil de Otimização | Cenários Típicos de Aplicação |
| :--- | :--- | :--- |
| `auto/cheap` | Custo mínimo absoluto | Tradução de termos, formatação, extração mecânica de strings, categorização sintática. |
| `auto/fast` | Menor latência (TTFT) | Triagem inicial de arquivos, verificação de consistência rápida, resumos superficiais. |
| `auto/coding` | Capacidade intermediária | Análise de métodos isolados, identificação de code smells, parsing de lógica estruturada. |
| `auto/smart` / `quality-first` | Raciocínio de alta capacidade | Auditoria de segurança profunda, análise de autorização, correlação arquitetural cross-module. |
| `fusion` | Consenso multi-modelo | Desempate em findings críticos ambíguos, verificação de falsos positivos de alta gravidade. |

> **Nota sobre Auto-Combo**: As rotas automáticas do OmniRoute consideram sinais dinâmicos de latência, cota restante, custo por milhão de tokens e taxas de erro em tempo de execução para selecionar o melhor provedor a cada chamada.

### 6.2 Prevenção Rigorosa de Delegação Recursiva
A arquitetura proíbe terminantemente chamadas recursivas entre modelos:

$$\text{Agente Principal} \xrightarrow{\text{delegação}} \text{OmniRoute} \xrightarrow{\text{inferência}} \text{Modelo Folha}$$

$$\text{Modelo Folha} \centernot\xrightarrow{\text{delegação}} \text{OmniRoute}$$

* O modelo de linguagem executado via OmniRoute não recebe credenciais de API, tokens MCP ou ferramentas de sub-delegação.
* Toda decomposição de subtarefas deve ser gerenciada no nível do Agente Orquestrador em TypeScript/Python.

### 6.3 Modelo de Orçamentação Hierárquica (*Budget Governance*)
O consumo financeiro e de tokens é regulado em múltiplos níveis de contenção:

```text
[Orçamento Global da Auditoria (ex: $2.00 / 500k tokens)]
                         │
                         ▼
      [Orçamento por Run de Módulo (ex: $0.30)]
                         │
                         ▼
      [Orçamento por Tarefa Individual (ex: $0.02)]
                         │
                         ▼
      [Orçamento por Request HTTP (Timeout / Max Tokens)]
```

#### Regra de Degradação Explícita
Caso o orçamento atinja o limite estipulado, o sistema **não deve degradar silenciosamente** a profundidade das verificações. A execução é interrompida com status determinístico:
* `COMPLETE`: Auditoria concluída dentro do orçamento.
* `PARTIAL`: Conclusão parcial com lista explícita de módulos não executados por estouro de cota.
* `BLOCKED / FAILED`: Execução bloqueada antes de atingir evidência mínima suficiente.

### 6.4 Fusão e Ensembles (*Fusion*) em Casos Críticos
O modo `fusion` dispara requisições concorrentes para múltiplos modelos distintos e consolida as respostas através de um modelo juiz:
* **Uso Restrito**: Devido ao custo multiplicado ($N \text{ chamadas} + \text{juiz}$), o modo `fusion` deve ser acionado exclusivamente para validação de vulnerabilidades críticas de segurança onde a evidência é ambígua ou divergente.
* Não deve ser empregado em tarefas mecânicas ou triagens rotineiras.

---

## 7. Observabilidade, Rastreabilidade e Proveniência

### 7.1 Schema Canônico de Proveniência Semântica
Cada tarefa executada através do Delegation Gateway produz um registro de proveniência imutável indexado em `run_manifest.json`:

```json
{
  "task_id": "task_audit_sec_0084_abc123",
  "project_id": "core-banking-service",
  "audit_run_id": "run_20260921_143000",
  "task_type": "security_vulnerability_triage",
  "policy_requested": "auto/coding",
  "input_context": {
    "target_file": "src/main/java/com/bank/auth/TokenValidator.java",
    "git_commit": "def456789abcdef",
    "context_hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "prompt_version": "v1.4.0",
    "disclosure_level": 3
  },
  "execution_telemetry": {
    "resolved_model": "deepseek-coder-v2:latest",
    "resolved_provider": "local_ollama",
    "effective_route": "auto/coding",
    "latency_ms": 1420,
    "tokens_prompt": 845,
    "tokens_completion": 210,
    "cost_estimated_usd": 0.0000,
    "fallback_triggered": false,
    "application_cache_hit": false,
    "infrastructure_cache_hit": true
  },
  "validation": {
    "schema_validation_passed": true,
    "escalation_triggered": false,
    "output_hash_sha256": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a"
  }
}
```

### 7.2 Telemetria de Infraestrutura vs. Telemetria Semântica
A observabilidade é dividida segundo os domínios:
* **Telemetria de Infraestrutura (OmniRoute)**: Latência de rede, tempo até o primeiro token (TTFT), códigos de status HTTP, falhas de conectividade com provedores, taxas de chave de API saturada.
* **Telemetria Semântica (Delegation Gateway / Orquestrador)**: Relação entre findings gerados por token consumido, taxa de reprovação em validações de schema, frequência de escalonamento para modelos superiores e taxa de acerto do cache da aplicação.

---

## 8. Segurança e Limites de Acesso

### 8.1 Capability Firewall e Restrição de Escopo MCP
O wrapper MCP que expõe o OmniRoute aos agentes implementa o princípio do menor privilégio (*Least Privilege*):

```text
Ferramentas Expostas ao Agente:
  ✔ delegar_tarefa(prompt, politica, schema_esperado)
  ✔ consultar_status_delegacao(tarefa_id)
  ✔ invalidar_cache_local(filtro)

Ferramentas e Rotas Bloqueadas (Acesso Administrativo Restrito):
  ✖ Adicionar/remover provedores de modelo
  ✖ Alterar chaves de API do sistema OmniRoute
  ✖ Alterar rotas globais e pesos de Auto-Combo
  ✖ Modificar limites de quotas e circuit breakers
```

### 8.2 Isolamento de Rede Local e Gerenciamento de Credenciais
* O gateway OmniRoute escuta estritamente na interface local de loopback (`localhost:20128` / `127.0.0.1:20128`), sendo expressamente vedada a exposição em interfaces públicas (`0.0.0.0`) sem camada de autenticação TLS/mTLS.
* A comunicação entre o Delegation Gateway e o OmniRoute utiliza tokens de autenticação transmitidos exclusivamente por variáveis de ambiente (`OMNIROUTE_API_KEY`).
* É vedada a inserção de chaves de API em arquivos de configuração estáticos (`mcp_config.json`, repositórios Git ou arquivos de documentação).

### 8.3 Defesa Contra Prompt Injection Indireto
Para prevenir que instruções maliciosas contidas em códigos auditados influenciem o julgamento das LLMs:
1. **Delimitação Estruturada**: Todo conteúdo proveniente do repositório é encapsulado em delimitadores seguros (ex: blocos Markdown com marcadores únicos e tags XML fechadas como `<untrusted_code_block>`).
2. **Instruções Metacognitivas**: Os templates de sistema contêm diretrizes imutáveis que explicitam que conteúdos contidos nas tags de dados nunca devem ser executados, avaliados como ordens de sistema ou interpretados como alteração de comportamento do auditor.

---

## 9. Matriz Canônica de Responsabilidades (RACI / Separação de Papéis)

A tabela a seguir estabelece a divisão definitiva de responsabilidades no ecossistema:

| Responsabilidade Arquitetural | Orquestrador de Domínio | Delegation Gateway (MCP) | OmniRoute (Infra) | Modelo Folha |
| :--- | :---: | :---: | :---: | :---: |
| **Decisão de Auditoria & Aplicabilidade** | **R / A** | I | N/A | N/A |
| **Seleção do Nível de Contexto (0 a 5)** | **R / A** | C | N/A | N/A |
| **Definição da Política de Execução** | **R / A** | C | I | N/A |
| **Cache Determinístico da Aplicação** | C | **R / A** | N/A | N/A |
| **Seleção do Modelo e Provedor Concreto** | N/A | I | **R / A** | N/A |
| **Resiliência (Fallback, Retries, Circuit Breaker)**| N/A | I | **R / A** | N/A |
| **Cache de Prompt / Afinidade de Infraestrutura** | N/A | I | **R / A** | N/A |
| **Execução da Inferência Cognitiva** | N/A | N/A | I | **R / A** |
| **Validação Sintática e de Schemas** | C | **R / A** | N/A | N/A |
| **Decisão de Escalonamento (*Escalation*)** | **R / A** | C | N/A | N/A |
| **Governança do Orçamento Global da Run** | **R / A** | C | I | N/A |
| **Gestão de Quota e Taxa por Provedor** | N/A | I | **R / A** | N/A |
| **Controle de Acesso e Prevenção de Recursão** | I | **R / A** | C | N/A |
| **Proveniência Semântica do Finding** | **R / A** | C | I | N/A |
| **Versionamento e Histórico (`.audit/`)** | **R / A** | N/A | N/A | N/A |

*Legenda: **R** = Responsável pela Execução; **A** = Aprovador/Dono do Domínio; **C** = Consultado; **I** = Informado; **N/A** = Não Aplicável.*

---

## 10. Roteiro de Validação e Verificação Técnica do OmniRoute Local

Antes da consolidação final de novas integrações, os seguintes passos técnicos de verificação devem ser executados contra a instância local do OmniRoute:

1. **Determinação de Versão e Capacidades Reais**:
   * Efetuar requisição a `http://localhost:20128/v1/models` e analisar endpoints administrativos disponíveis.
   * Confrontar os modelos e rotas retornados com as políticas esperadas (`auto/coding`, `auto/fast`, `auto/cheap`).
2. **Validação de Políticas Auto-Combo**:
   * Enviar cargas de teste com a rota `auto/coding` e verificar nos headers ou na telemetria qual provedor foi selecionado e sob quais critérios.
3. **Auditoria da Fronteira de Segurança do MCP**:
   * Verificar se `omniroute_mcp.py` possui apenas as funções de interface necessárias (`delegar_tarefa`), sem vazar ferramentas de configuração administrativa.
   * Assegurar que a variável `OMNIROUTE_API_KEY` é consumida via ambiente seguro e que nenhuma chave está em código estático.
4. **Teste de Carga e Comportamento de Resiliência**:
   * Simular indisponibilidade forçada de um provedor upstream para testar o chaveamento automático de *fallback* e a ativação de *circuit breakers* sem falha abrupta para o agente.
5. **Aferição da Afinidade de Prompt Cache**:
   * Despachar requisições sequenciais com prefixos de sistema volumosos idênticos e medir latência/consumo de tokens para confirmar se o cache de infraestrutura do OmniRoute está ativo.
6. **Validação do Cache Determinístico da Aplicação**:
   * Despachar a mesma requisição via Delegation Gateway duas vezes consecutivas e validar que a segunda requisição é resolvida via arquivo em `.audit/cache/tasks/` com latência inferior a 10ms.
7. **Verificação de Isolamento do Git**:
   * Confirmar a existência de `.audit/.git/` e validar que `git status` no repositório do projeto principal não exibe referências aos arquivos de `.audit/`.
