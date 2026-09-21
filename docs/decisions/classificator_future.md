# Arquitetura de Classificadores no Pipeline de Auditoria Multi-Agente

## Sumário Executivo e Contexto

Este documento estabelece o referencial arquitetural canônico para a incorporação de **classificadores especializados** no ecossistema de auditoria técnica multi-agente. O objetivo central é a **otimização de custo computacional e de tokens (LLM)** sem degradação da precisão analítica.

A premissa fundamental da arquitetura baseia-se na separação estrita de responsabilidades ao longo do ciclo de vida da análise:

> **Classificadores decidem escopo, pertencimento e relevância ("o que é / onde pertence / o que merece atenção").**  
> **Auditores avaliam conformidade e comportamento do sistema ("o que está acontecendo / isso é um defeito?").**  
> **Verificadores validam hipóteses de forma adversarial e independente ("esta conclusão é factualmente correta?").**  
> **Normalizadores consolidam a saída de forma determinística ("como estruturar os dados canonicamente?").**

Essa segregação viabiliza o posicionamento estratégico de camadas de inteligência de baixo custo (algoritmos determinísticos e modelos locais/leves) antes do acionamento de etapas de raciocínio semântico de alto custo (modelos de linguagem de fronteira).

---

## Estratégia de Camadas de Processamento (Tiers de Execução)

O processamento é estratificado em quatro níveis com custos computacionais progressivos:

```text
                 VOLUME DE ENTRADA
                         │
                         ▼
             ┌───────────────────────┐
             │  Tier 1: Determinístico │  ← Custo ~0 (código/regras)
             └───────────┬───────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │  Tier 2: Modelos Leves │  ← Baixo custo (SLM/local)
             └───────────┬───────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │  Tier 3: Modelo Forte │  ← Custo elevado (LLM frontier)
             └───────────┬───────────┘
                         │
                         ▼
             ┌───────────────────────┐
             │  Tier 4: Verificação  │  ← Seletivo / Adversarial
             └───────────────────────┘
```

### 1. Tier 1: Classificadores Determinísticos
Operam exclusivamente via heurísticas estruturadas, regras estáticas, expressões regulares, análise de sintaxe (AST) e verificação de hashes criptográficos. Não utilizam LLMs.
* **Escopo:** Tipagem de arquivos, detecção de stack tecnológica, aplicabilidade básica, checagem de segurança de comandos, classificação de diffs Git, detecção de código gerado e condições de invalidação de cache.
* **Custo computacional:** Desprezível (~0 tokens).

### 2. Tier 2: Classificadores Baratos (SLM / Heurísticas Semânticas)
Utilizam modelos locais compactos ou instâncias otimizadas para classificação semântica rápida.
* **Escopo:** Scoring de relevância contextual de arquivos e trechos, agrupamento semântico preliminar, triagem de candidatos a achados (*finding candidates*) e similaridade estrutural.
* **Tolerância a falha:** Alta. Falsos positivos são filtrados nas etapas subsequentes; o classificador apenas prioriza o direcionamento de recursos analíticos.

### 3. Tier 3: Raciocínio Profundo (Auditores Especializados)
Empregam modelos de alta capacidade dedicados à análise dedutiva e correlação técnica.
* **Escopo:** Confirmação de vulnerabilidades, reconstrução de caminhos de ataque (*attack paths*), determinação de causa raiz, análise cruzada de múltiplos módulos e resolução de ambiguidades.

### 4. Tier 4: Verificação Independente e Normalização
Etapas de contraprova lógica e formalização de dados.
* **Escopo:** Verificação adversarial de hipóteses e consolidação determinística via `audit-normalize` (sem permissão para alucinação ou supressão arbitrária de achados).

---

## Visão Geral da Arquitetura do Pipeline

```text
                                PROJETO
                                   │
                                   ▼
                         ┌───────────────────┐
                         │  project-context  │
                         └─────────┬─────────┘
                                   │
                                   ▼
                         ┌───────────────────┐
                         │  PROJECT PROFILE  │
                         │    CLASSIFIERS    │
                         └─────────┬─────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              Applicability    Relevance    Change Impact
               Classifier     Classifier     Classifier
                    │              │              │
                    └──────────────┼──────────────┘
                                   ▼
                            AUDIT PLANNER
                                   │
                     ┌─────────────┼─────────────┐
                     ▼             ▼             ▼
                 code-audit  security-audit   db-audit
                     │             │             │
                     ▼             ▼             ▼
                 Candidate     Candidate     Candidate
                Classifier    Classifier    Classifier
                     │             │             │
                     └─────────────┼─────────────┘
                                   ▼
                              VERIFIERS
                                   │
                                   ▼
                          project-audit-core
                             (correlation)
                                   │
                                   ▼
                           Audit Output Set
                                   │
                                   ▼
                            audit-normalize
```

---

## Catálogo de Classificadores por Fase do Ciclo de Vida

### Fase I: Perfilamento e Descoberta de Contexto

#### 1. Classificador de Perfil do Projeto (`Project Profile Classifier`)
* **Momento:** Bootstrap da execução.
* **Tipo:** Predominantemente determinístico com agregação sintética.
* **Função:** Produz uma fotografia das dimensões operacionais do projeto para alimentar o planejador de auditoria (`Audit Planner`).
* **Estrutura de Saída:**
  ```yaml
  COMPLEXITY: LOW | MEDIUM | HIGH
  APPLICATION: CLI | WEB_BACKEND | WEB_FRONTEND | LIBRARY | FULLSTACK
  PERSISTENCE: NONE | SQLITE | POSTGRESQL | MONGO | REDIS
  NETWORK: NONE | INBOUND_HTTP | OUTBOUND_REST | WEBSOCKET
  AUTH: NONE | SESSION | JWT | OAUTH2
  FRONTEND: NONE | REACT | VUE | SSR
  CONTAINER: NONE | DOCKER | KUBERNETES
  CI: NONE | GITHUB_ACTIONS | GITLAB_CI
  RISK_SURFACES:
    - DATABASE
    - FILESYSTEM
    - PROCESS_EXECUTION
  ```

#### 2. Classificador de Superfície Tecnológica (`Technology Surface Classifier`)
* **Momento:** Fase de coleta de contexto.
* **Tipo:** Determinístico (inspeção mecânica de manifestos, dependências e assinaturas).
* **Função:** Mapeia a presença de subsistemas tecnológicos através de artefatos concretos (`pom.xml`, `package.json`, `build.gradle`, `Dockerfile`, anotações de código como `@Entity`, `ProcessBuilder`, `fetch()`).
* **Categorias de Superfície:**
  * `HTTP`, `DATABASE`, `FILESYSTEM`, `NETWORK`, `AUTH`, `CRYPTO`, `SERIALIZATION`, `PROCESS_EXECUTION`, `CONTAINERS`, `EXTERNAL_SERVICES`.

#### 3. Classificador de Aplicabilidade (`Applicability Classifier`)
* **Momento:** Imediatamente anterior ao agendamento de auditores especializados.
* **Tipo:** Determinístico baseado na superfície tecnológica.
* **Função:** Determina quais domínios de auditoria devem ser acionados, desativando módulos irrelevantes para a stack em questão.
* **Fluxo Operacional:**
  ```text
  Contexto do Projeto
         ↓
  Applicability Classifier
         ↓
  ┌───────────────┬─────────────────┬───────────────┐
  │  APPLICABLE   │ NOT_APPLICABLE  │   UNCERTAIN   │
  └───────────────┴─────────────────┴───────────────┘
  ```
* **Exemplo de Decisão:**
  ```text
  Entrada: Projeto Java CLI, Gradle, SQLite, sem HTTP/Web/Auth
  Saída:
    CODE_AUDIT           → APPLICABLE
    DATABASE_AUDIT       → APPLICABLE
    TESTING_AUDIT        → APPLICABLE
    SECURITY_GENERAL     → PARTIALLY_APPLICABLE
    SECURITY_WEB_XSS     → NOT_APPLICABLE
    SECURITY_SSRF        → NOT_APPLICABLE
    AUTHENTICATION_AUDIT → NOT_APPLICABLE
  ```

---

### Fase II: Mapeamento de Escopo e Filtragem de Contexto

#### 4. Classificador de Arquivos (`File Classifier`)
* **Momento:** Indexação do repositório.
* **Tipo:** Determinístico (baseado em extensões, paths e regras de convenção).
* **Função:** Classifica cada arquivo do projeto em categorias de escopo técnico, alimentando diretamente o *coverage manifest*.
* **Taxonomia de Classes:**
  * `SOURCE`, `TEST`, `CONFIG`, `BUILD`, `DATABASE`, `DOCUMENTATION`, `INFRASTRUCTURE`, `GENERATED`, `DEPENDENCY`, `OUT_OF_SCOPE`, `UNKNOWN`.
* **Exemplos de Classificação:**
  * `src/main/java/.../UserService.java` → `SOURCE / DOMAIN`
  * `src/test/java/.../UserServiceTest.java` → `TEST`
  * `docker-compose.yml` → `INFRASTRUCTURE / CONFIG`
  * `schema.sql` → `DATABASE`
  * `README.md` → `DOCUMENTATION`
  * `target/...` → `GENERATED / OUT_OF_SCOPE`

#### 5. Classificador de Relevância Contextual (`Relevance Classifier`)
* **Momento:** Distribuição de arquivos para os auditores.
* **Tipo:** Modelo Leve / Heurística Semântica (Tier 2).
* **Função:** Calcula um score de relevância ponderada por auditor/módulo, garantindo que cada agente receba estritamente o contexto de maior interesse.
* **Princípio:** *Aplicabilidade do módulo difere da relevância do arquivo individual.*
* **Exemplo Comparativo:**
  ```text
  Arquivo: UserService.java
    security-audit: HIGH (0.92)
    code-audit:     HIGH (0.88)
    database-audit: LOW  (0.20)

  Arquivo: UserRepository.java
    database-audit: HIGH   (0.95)
    security-audit: MEDIUM (0.55)
    code-audit:     MEDIUM (0.50)
  ```

#### 6. Classificador de Superfícies de Entrada Externa (`Input Surface Classifier`)
* **Momento:** Pré-processamento do `security-audit`.
* **Tipo:** Híbrido (AST determinístico + análise semântica leve).
* **Função:** Identifica pontos de contato com dados externos não confiáveis antes do raciocínio analítico de segurança.
* **Fontes Inspecionadas:** Parâmetros HTTP, argumentos de CLI, variáveis de ambiente, manipuladores de arquivos, canais de mensageria, webhooks, cabeçalhos, cookies, payloads JSON/XML/CSV.
* **Estrutura de Saída:**
  ```yaml
  input_element: "request.path.id"
  origin: "EXTERNAL"
  trust_level: "UNTRUSTED"
  consumers:
    - "OrderController"
    - "OrderService"
    - "OrderRepository"
  ```

#### 7. Classificador de Fronteiras de Confiança (`Trust Boundary Classifier`)
* **Momento:** Análise de fluxo de dados no `security-audit`.
* **Tipo:** Híbrido.
* **Função:** Classifica o nível de confiança intrínseco de cada entidade produtora de dados no pipeline de execução.
* **Taxonomia:**
  * `UNTRUSTED`: Entradas de rede públicas, payloads de usuários.
  * `USER_CONTROLLED`: Headers, parâmetros de sessão, tokens de cliente.
  * `EXTERNAL_SERVICE`: Respostas de APIs externas integradas.
  * `DATA_STORE`: Registros recuperados do banco de dados relacional/NoSQL.
  * `INTERNAL`: Comunicações entre processos confiáveis.
  * `CONFIGURATION`: Variáveis de ambiente e parâmetros de inicialização.
  * `SYSTEM`: Recursos do sistema operacional local.
* **Aplicações:** Detecção estruturada de SQL Injection, SSRF, IDOR, Deserialização Insegura, Execução de Comandos e Quebra de Autorização.

---

### Fase III: Auditoria Incremental e Reaudit

#### 8. Classificador de Impacto de Mudança (`Change Impact Classifier`)
* **Momento:** Análise diferencial de repositórios (*incremental audit*).
* **Tipo:** Determinístico via `git diff` e mapeamento de dependências internas.
* **Função:** Analisa o conjunto de alterações entre dois commits e mapeia quais subsistemas foram impactados, minimizando o escopo de execução.
* **Exemplo de Regra de Impacto:**
  ```text
  Diff git A..B
  ├── src/auth/JwtService.java → SECURITY / AUTHENTICATION (HIGH IMPACT)
  ├── schema.sql               → DATABASE (HIGH IMPACT)
  ├── pom.xml                  → BUILD / DEPENDENCY (HIGH IMPACT)
  └── README.md                → DOCUMENTATION (LOW IMPACT)
  ```

#### 9. Classificador de Necessidade de Reauditoria (`Reaudit Necessity Classifier`)
* **Momento:** Avaliação de achados (*findings*) pré-existentes em execuções sucessivas.
* **Tipo:** Determinístico / Regras de Correlação.
* **Função:** Classifica a situação de achados anteriores diante de um novo diff de código, evitando a reanálise redundante de problemas não afetados.
* **Taxonomia de Ações:**
  * `REUSE`: O achado permanece válido sem necessidade de nova inspeção.
  * `RECHECK`: O contexto foi alterado; exige reavaliação pelo auditor.
  * `INVALIDATE`: A alteração removeu ou reestruturou o componente afetado.
* **Matriz de Decisão Operacional:**
  | Achado Anterior | Relação com a Modificação | Ação do Classificador |
  | :--- | :--- | :--- |
  | SQL Injection em `OrderDao.java` | Arquivo inalterado e dependências estáveis | `REUSE` |
  | Autorização falha em `UserService` | `UserService.java` modificado | `RECHECK` |
  | Dependência vulnerável no build | `pom.xml` modificado | `RECHECK` |
  | Vulnerabilidade em arquivo deletado | Arquivo removido no commit | `INVALIDATE` |

#### 10. Classificador de Reutilização de Evidência (`Evidence Reuse Classifier`)
* **Momento:** Pré-execução incremental de auditores.
* **Tipo:** Determinístico estrito (comparação de hashes e árvores sintáticas).
* **Função:** Valida se uma evidência colhida em sessões anteriores mantém integridade factual baseando-se no hash do arquivo, toolchain e configurações relacionadas.
* **Status Possíveis:** `VALID_TO_REUSE`, `REQUIRES_RECHECK`, `INVALIDATED`, `UNKNOWN`.

---

### Fase IV: Governança e Execução Segura

#### 11. Classificador de Segurança de Execução (`Execution Safety Classifier / Gate`)
* **Momento:** Imediatamente antes do despacho de qualquer comando no ambiente operacional.
* **Tipo:** Determinístico estrito (Allowlist, Denylist, Regras de Sandbox). **Nunca delegar a decisão final a um LLM.**
* **Função:** Intercepta comandos de inspeção e ferramentas para evitar mutações destrutivas, vazamento de dados ou efeitos colaterais imprevistos.
* **Taxonomia de Comandos:**
  * `READ_ONLY`: Seguro para execução imediata (`git status`, `git log`, `find`).
  * `SAFE_MUTATION`: Modificações estritamente controladas em ambiente isolado.
  * `POSSIBLE_SIDE_EFFECT`: Comandos que realizam compilação ou testes locais (`mvn test`, `cargo check`).
  * `EXTERNAL_EFFECT`: Comandos com conectividade externa ou criação de contêineres (`docker compose up`, `curl`).
  * `DANGEROUS`: Bloqueio compulsório (`git reset --hard`, `rm -rf`, deleções estruturais).
* **Fluxo de Decisão:**
  ```text
  Comando Candidato
         ↓
  Execution Safety Classifier
         ↓
       Seguro?
      ┌───┴───┐
     Sim     Não
      ↓       ↓
   Executar  Bloquear e Reportar Erro
  ```

---

### Fase V: Triagem de Sinais e Refinamento de Achados

#### 12. Classificador de Evidência (`Evidence Classifier`)
* **Momento:** Avaliação de suporte probatório durante a auditoria.
* **Tipo:** Modelo Leve ou Regra Semântica.
* **Função:** Categoriza a força probatória de uma evidência com base na máxima operacional: **`evidence > narrative`**.
* **Taxonomia de Evidência:**
  * `DIRECT`: Evidência factual inequívoca no código (ex: chamada explícita de API segura ou insegura).
  * `INDIRECT`: Menção descritiva em documentação ou comentários (ex: declaração em README).
  * `WEAK`: Inferência probabilística sem prova material concreta.
  * `CONTRADICTORY`: Conflito entre fontes (ex: documentação indica PostgreSQL, manifesto de container define MySQL).
  * `MISSING`: Ausência de verificação observável.

#### 13. Classificador de Candidatos a Finding (`Finding Candidate Classifier`)
* **Momento:** Pós-análise estática / Pré-modelo forte.
* **Tipo:** Modelo Leve / Classificador Barato (Tier 2).
* **Função:** Reduz o volume massivo de sinais estáticos brutos, selecionando apenas ocorrências com densidade suficiente para merecer raciocínio analítico profundo.
* **Funil de Redução:**
  ```text
  1000 sinais brutos (AST, regex, linters)
         ↓
  Finding Candidate Classifier
         ↓
  73 candidatos relevantes (REVIEW / HIGH_PRIORITY_REVIEW)
         ↓
  Auditor com Modelo Forte (Tier 3)
         ↓
  12 findings validados
  ```
* **Guardrail:** O classificador de candidatos **não declara** nem confirma vulnerabilidades; atua exclusivamente como filtro de relevância econômica.

#### 14. Classificador de Confiança Preliminar (`Preliminary Signal Classifier`)
* **Momento:** Triagem de candidatos.
* **Tipo:** Modelo Leve.
* **Função:** Avalia a intensidade do sinal (`HIGH_SIGNAL`, `MEDIUM_SIGNAL`, `LOW_SIGNAL`).
* **Guardrail:** Sob nenhuma hipótese um resultado de alta confiança do classificador é convertido diretamente em `CONFIRMED`. Todo candidato de alto sinal deve ser submetido à verificação profunda (`Verifiers`).

#### 15. Classificador de Duplicidade Preliminar (`Duplicity Classifier`)
* **Momento:** Pré-normalização.
* **Tipo:** Modelo Leve / Similaridade Vetorial.
* **Função:** Sinaliza quando múltiplos candidatos a achados compartilham provável causa raiz (`LIKELY_SAME`, `POSSIBLY_RELATED`, `DISTINCT`).
* **Guardrail:** **Não realiza merges definitivos.** O merge e a deduplicação formal cabem exclusivamente ao módulo determinístico `audit-normalize`.

#### 16. Classificador de Severidade Preliminar (`Preliminary Severity Classifier`)
* **Momento:** Triagem contextual de impacto.
* **Tipo:** Modelo Leve / Heurística Estruturada.
* **Função:** Extrai atributos objetivos de risco (exposição pública à internet, bypass de autenticação, vazamento de credenciais vs. escopo restrito a ambiente local).
* **Guardrail:** Classifica apenas o perfil de risco (`STRONG`, `MODERATE`, `LOW`). A atribuição formal de severidade (`P0`, `P1`, `P2`, `P3`, `INFO`) permanece como juízo exclusivo do auditor de Tier 3.

---

### Fase VI: Consolidação e Pós-Auditoria

#### 17. Classificador de Maturidade do Projeto (`Project Maturity Classifier`)
* **Momento:** Fase final de síntese (pós-execução dos auditores e verificadores).
* **Tipo:** Agregação ponderada baseada exclusivamente em fatos e evidências consolidadas.
* **Função:** Avalia eixos específicos da engenharia do projeto com suporte probatório:
  * `TESTING`: `ABSENT` | `BASIC` | `MODERATE` | `STRONG`
  * `CI_CD`: `ABSENT` | `BASIC` | `MATURE`
  * `DOCUMENTATION`: `MINIMAL` | `ADEQUATE` | `EXEMPLARY`
  * `SECURITY_POSTURE`: `DEFICIENT` | `BASE` | `HARDENED`
* **Guardrail:** Veda-se a atribuição arbitrária de níveis de maturidade sem o embasamento direto em achados e métricas verificadas no relatório consolidado.

---

## Matriz de Responsabilidades do Pipeline

Para garantir governança estrita e previsibilidade arquitetural, cada componente opera dentro de fronteiras intransponíveis:

| Componente | Pergunta Essencial | Escopo de Ação | O que é expressamente VEDADO |
| :--- | :--- | :--- | :--- |
| **Classificador** | *"Onde vale alocar esforço de análise?"* | Filtragem, roteamento, scoring de relevância, agrupamento inicial | Emitir julgamento final de conformidade ou declarar bugs/vulnerabilidades confirmadas |
| **Auditor** | *"O que está acontecendo tecnicamente?"* | Análise semântica profunda, correlação de código, dedução de impacto | Executar deduplicação destrutiva ou rodar comandos não validados |
| **Verificador** | *"Esta conclusão resiste à contestação?"* | Refutação adversarial, checagem de premissas factuais | Criar achados fora do escopo sob validação |
| **Normalizador** (`audit-normalize`) | *"Como estruturar estes dados canonicamente?"* | Validação de schema, deduplicação conservadora, ledger imutável | Julgar mérito técnico sem evidência ou inventar achados |

---

## Diretrizes de Implementação para Agentes

1. **Priorizar Sempre Soluções Determinísticas:** Se uma classificação puder ser resolvida via regex, AST, checagem de extensão de arquivo ou hash de conteúdo, o uso de LLM é estritamente proibido.
2. **Filosofia de Falha Segura (Fail-Safe Scope):** Diante de ambiguidade ou classificação `UNCERTAIN` quanto à aplicabilidade de um arquivo ou módulo, o classificador deve optar pela inclusão segura para revisão posterior por Tier superior.
3. **Imutabilidade de Achados sem Verificação:** Nenhum classificador tem autoridade para descartar silenciosamente achados existentes sem registro rastreável de causa (`INVALIDATED` com justificativa técnica).
4. **Isolamento de Estado:** Os classificadores devem operar como funções puras ou com dependência restrita ao `project-context` indexado, prevenindo acoplamento indevido entre auditores concorrentes.
