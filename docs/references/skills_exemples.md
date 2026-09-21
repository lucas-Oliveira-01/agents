# Arquitetura de Referência para Engenharia e Governança de Agent Skills

## 1. Visão Geral e Modelo Conceitual

### 1.1 Contexto e Propósito
Este documento estabelece o padrão canônico de arquitetura, estruturação, ciclo de vida e governança para *Agent Skills*. O objetivo é fornecer uma referência prescritiva para agentes autônomos e desenvolvedores de sistemas agênticos, consolidando padrões avançados de engenharia de software aplicados a fluxos baseados em Modelos de Linguagem (LLMs).

A proliferação de assistentes inteligentes evidenciou a insuficiência de abordagens baseadas exclusivamente em prompts monolíticos não estruturados. Sistemas confiáveis exigem determinismo operacional, separação rigorosa de responsabilidades, gestão explícita de estado e verificação independente.

### 1.2 A Distinção Fundamental: Skill vs. Ferramenta vs. Domínio
A concepção adequada de um ecossistema agêntico exige diferenciar claramente três camadas operacionais:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ DOMÍNIO (Base de Conhecimento)                                        │
│ Taxonomias, especificações, normas e heurísticas estáticas            │
│ Exemplos: OWASP Top 10, especificações RFC, gramáticas de linguagens   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ alimenta
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ SKILL (Instruções e Fluxo de Trabalho)                                 │
│ Roteamento, decomposição de tarefas, políticas e critérios de decisão  │
│ Exemplo: Pipeline de auditoria de código, gerador de migrações SQL     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ orquestra
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ FERRAMENTA (Mecanismo de Execução)                                     │
│ Ações com efeitos colaterais ou interfaces com o sistema operacional  │
│ Exemplos: Bash, Git, APIs de busca, parsers AST, compiladores          │
└────────────────────────────────────────────────────────────────────────┘
```

* **Domínio**: Representa o *conhecimento factual*. Não define fluxos de execução nem possui efeitos colaterais.
* **Skill**: Representa o *procedimento prescritivo*. Define quando acionar ferramentas, como decompor problemas e como interpretar resultados intermediários.
* **Ferramenta**: Representa a *capacidade mecânica*. É a interface que lê arquivos, executa processos ou realiza chamadas de rede.

### 1.3 O Modelo Arquitetural em Quatro Camadas
A engenharia de skills robustas decompõe o sistema em quatro camadas desacopladas:

1. **Camada 1: Conhecimento de Domínio (*Domain Knowledge*)**: Taxonomias especializadas, regras de negócio e padrões técnicos isolados em arquivos de referência estáticos (`references/`).
2. **Camada 2: Diretrizes de Fluxo (*Skill & Routing*)**: Lógica de decisão, pontos de ramificação condicional e instruções de despacho operacional (`SKILL.md`).
3. **Camada 3: Execução Operacional (*Execution Machinery*)**: Agentes especializados, scripts determinísticos, isolamento em sandbox e ferramentas nativas/MCP (`scripts/`, `agents/`).
4. **Camada 4: Garantia de Qualidade e Estado (*Quality & State*)**: Esquemas estruturados de entrada/saída, validações determinísticas, ledger de cobertura, logs de auditoria e baterias de teste (`evals/`, schemas JSON).

```text
┌────────────────────────────────────────┐
│  1. DOMAIN KNOWLEDGE                   │
│  Taxonomias, referências e regras      │
└───────────────────┬────────────────────┘
                    │ consulta condicional
┌───────────────────▼────────────────────┐
│  2. SKILL & ROUTING                    │
│  Orquestração, triagem e decisões      │
└───────────────────┬────────────────────┘
                    │ despacha
┌───────────────────▼────────────────────┐
│  3. EXECUTION MACHINERY                │
│  Scripts determinísticos e subagentes  │
└───────────────────┬────────────────────┘
                    │ produz estado validado
┌───────────────────▼────────────────────┐
│  4. QUALITY & STATE                    │
│  Schemas JSON, validadores e evals     │
└────────────────────────────────────────┘
```

### 1.4 Panorama das Fontes de Referência
Os padrões consolidados neste documento derivam de implementações reais em produção:

| Projeto / Fonte | Natureza | Relevância Arquitetural |
| :--- | :--- | :--- |
| **`getsentry/skills`** | Repositório oficial de Agent Skills da Sentry | **Engenharia de Skill como Produto**: padronização de layout, roteamento compacto, ciclo de vida (`skill-writer`), avaliação sistemática (`evals`), otimização orientada a métricas (`prompt-optimizer`) e segurança de skills (`skill-scanner`). |
| **Cloudflare `security-audit-skill`** | Skill de auditoria de segurança multiagente | **Orquestração e Verificação Independente**: orquestrador com soberania de estado, isolamento entre `scratch/` e `artifacts/`, ledger de cobertura, independência epistemológica (*hunter* vs. *verifier*) e contratos JSON Schema rígidos. |
| **OWASP Top 10** | Padrão taxonômico de segurança de aplicações | **Camada de Conhecimento**: utilização como modelo de classificação modular inserido em `references/`, evitando a poluição do fluxo de trabalho procedural. |
| **CanIRunAI** | Aplicação de análise de hardware e compatibilidade | **Coleta Determinística**: padrão híbrido combinando comandos de SO com zero dependências externas, catálogo estático e lógica decisória sem alucinações. |
| **Sentry Platform** | Plataforma de observabilidade contínua | **Telemetria Operacional**: extração de métricas de execução agêntica (latência, decisões, erros, consumo de tokens) para rastreabilidade de runtime. |

---

## 2. Anatomia Canônica de uma Skill (Padrão Sentry)

### 2.1 Estrutura de Diretórios Padronizada
Um repositório de skills profissional adota uma árvore de arquivos previsível, separando instruções de runtime de contratos de manutenção:

```text
repository-root/
├── .claude-plugin/
│   ├── marketplace.json
│   └── plugin.json
├── .agents/
│   └── skills -> ../skills/               # Link simbólico para compatibilidade de tooling
├── agents/                                # Definições de subagentes reutilizáveis
│   ├── researcher.md
│   ├── security-critic.md
│   └── verifier.md
├── skills/
│   ├── <nome-da-skill>/
│   │   ├── SKILL.md                       # Roteador de execução em runtime (< 500 linhas)
│   │   ├── SPEC.md                        # Contrato de manutenção e especificações técnicas
│   │   ├── SOURCES.md                     # Proveniência, decisões arquiteturais e lacunas
│   │   ├── references/                    # Conhecimento factual sob demanda (Just-in-Time)
│   │   │   ├── architecture-model.md
│   │   │   └── evidence-requirements.md
│   │   ├── references/evidence/           # Exemplos canônicos de sucesso e anti-patterns
│   │   ├── scripts/                       # Operações determinísticas e validações
│   │   │   ├── validate-schema.cjs
│   │   │   └── collect-context.sh
│   │   ├── assets/                        # Templates estáticos, schemas JSON e diagramas
│   │   │   ├── schemas/
│   │   │   └── templates/
│   │   ├── EVAL.md                        # Critérios de avaliação da skill
│   │   └── evals/                         # Bateria de testes automatizados
│   │       ├── axis.config.json
│   │       ├── scenarios/
│   │       └── fixtures/
├── AGENTS.md                              # Guia global de agentes
├── CLAUDE.md                              # Instruções de contexto para runtime Claude
└── README.md
```

### 2.2 Contratos de Arquivo

#### `SKILL.md` (Runtime Behavior)
O arquivo `SKILL.md` destina-se exclusivamente à execução. Não deve conter histórico de decisões, changelogs extensos ou tratados teóricos.
* **Frontmatter obrigatório**: Declaração estrita com `name` (correspondendo ao nome da pasta) e `description` rica em termos realistas de disparo (*trigger matching*).
* **Tamanho compacto**: Deve idealmente conter menos de 500 linhas de texto.
* **Papel estruturante**: Funciona como um índice algorítmico, determinando qual fluxo seguir, quais arquivos carregar e quais scripts executar.

#### `SPEC.md` (Maintenance Contract)
Documento voltado a engenheiros e agentes responsáveis por modificar a própria skill. Define:
* Intenção primária e escopo delimitado (*non-goals* explícitos).
* Heurísticas de ativação e condições de descarte.
* Modelo de evidência exigido.
* Hipóteses arquiteturais, limitações conhecidas e vetores de manutenção futura.

#### `SOURCES.md` (Provenance & History)
Registra o histórico de design da skill:
* Fontes primárias de documentação e referências externas utilizadas.
* Racional de decisões de design consolidadas.
* Lacunas conhecidas (*known gaps*) identificadas em produção ou testes.

### 2.3 Princípio da Descoberta Progressiva (*Progressive Disclosure*)
Um dos problemas fundamentais no design de agentes é a degradação de desempenho e a interferência de instruções decorrentes da saturação da janela de contexto. O modelo de Descoberta Progressiva resolve essa limitação estruturando o consumo de informações em etapas sequenciais:

```text
                [1. Descoberta de Skill]
                  name + description
                          │
                          ▼
                [2. Leitura do SKILL.md]
                  runtime router central
                          │
                          ▼
             [3. Classificação do Pedido]
             identifica parâmetros e modo
                          │
                          ▼
          [4. Carga Seletiva de Referências]
         apenas os arquivos estritamente úteis
                          │
                          ▼
           [5. Execução de Scripts / Ações]
          validação determinística no runtime
                          │
                          ▼
             [6. Delegação Especializada]
            subagentes acionados sob demanda
```

Ao carregar apenas o contexto estritamente necessário para a etapa corrente:
1. Minimiza-se o volume total de tokens transmitidos ao modelo.
2. Elimina-se a *interferência de instruções* (*instruction interference*), evitando que regras secundárias disputem atenção semântica com diretrizes fundamentais.

### 2.4 A Regra de Consulta Just-in-Time
Toda referência localizada em `references/` deve possuir uma justificativa operacional explícita para consulta:

> **Regra de Consulta Canônica**:
> * "Preciso decidir X, portanto devo consultar `references/Y.md`."
> * "Preciso executar X, portanto devo consultar `references/Y.md`."

Se um documento de referência apenas fornecer contexto genérico sem alterar diretamente uma bifurcação decisória, uma ação mecânica ou um critério de validação do agente, sua inclusão é desnecessária e deve ser eliminada.

---

## 3. Taxonomia de Padrões de Execução (Execution Shapes)

Toda tarefa executada por uma skill possui uma forma de fluxo ótima. O padrão Sentry formaliza dez formatos canônicos de execução:

```text
                        EXECUTION SHAPES
                                │
    ┌───────────────────────────┼───────────────────────────┐
    ▼                           ▼                           ▼
[Simples]                 [Intermediário]             [Avançado]
├── inline-guidance       ├── argument-driven         ├── router
├── reference-backed      └── script-backed           ├── parallelization
└── asset-template                                    ├── orchestrator-workers
                                                      ├── subagent-fork
                                                      └── hook-backed
```

### 3.1 `inline-guidance`
* **Estrutura**: Instruções sequenciais compactas contidas inteiramente dentro de `SKILL.md`.
* **Caso de uso**: Tarefas lineares, políticas operacionais simples ou checklists diretos que não demandam bases de conhecimento adicionais nem validações externas.

### 3.2 `reference-backed-expert`
* **Estrutura**: Um núcleo `SKILL.md` atuando como roteador, acompanhado por múltiplos arquivos modulares em `references/`.
* **Caso de uso**: Domínios técnicos densos (e.g., segurança de autenticação, migrações de bancos de dados legados) nos quais o conhecimento detalhado só deve ser carregado sob demanda.

### 3.3 `script-backed-workflow`
* **Estrutura**: A skill delega a computação lógica, transformações de dados ou checagens sintáticas a scripts determinísticos em `scripts/`.
* **Princípio**: *Nunca atribuir a um modelo de linguagem o que pode ser processado de forma determinística por código estruturado.*
* **Caso de uso**: Parsing de código, validação contra JSON Schema, diffing e cálculos estáticos.

### 3.4 `argument-driven`
* **Estrutura**: O fluxo de trabalho é parametrizado via argumentos explícitos recebidos pelo comando ou prompt (e.g., `--profile=deep`, `--target=src/api`).
* **Caso de uso**: Operações modulares com múltiplos níveis de profundidade, escopo delimitado ou formatos de saída diferenciados.

### 3.5 `router`
* **Estrutura**: A skill analisa a solicitação do usuário e a despacha para uma sub-rotina ou referência especializada com contratos isolados.
* **Requisitos arquiteturais**: Critérios explícitos de classificação, rota de fallback predefinida e estratégia de mitigação contra erros de roteamento (*misroute recovery*).

### 3.6 `parallelization`
* **Estrutura**: Divisão da carga de trabalho em unidades independentes atribuídas a agentes paralelos, sintetizadas por um agregador central.
* **Requisitos arquiteturais**: Definição rígida da unidade atômica de trabalho, algoritmo determinístico de merge/votação, reconciliação de conflitos e teto máximo de custo e latência.

### 3.7 `orchestrator-workers`
* **Estrutura**: O orquestrador decompõe dinamicamente a demanda em subunidades desconhecidas a priori, distribui tarefas a instâncias executoras (workers) e sintetiza o resultado final.
* **Requisitos arquiteturais**: Schema unificado de atribuição de tarefas, schema padronizado de resposta, limite estrito de ramificação (*fan-out cap*) e política de consolidação.

### 3.8 `subagent-fork`
* **Estrutura**: Execução de subtarefas em conversas ou processos isolados, podendo empregar modelos distintos ou conjuntos de ferramentas restritos.
* **Caso de uso**: Proteção de contexto do agente primário, execução de raciocínio de alta profundidade ou operação em ambientes com permissões segregadas.

### 3.9 `hook-backed`
* **Estrutura**: A execução é interceptada antes ou depois da invocação do agente por mecanismos em nível de plataforma (hooks nativos).
* **Caso de uso**: Imposição mandatória de segurança, auditoria compulsória de comandos Bash e sanitização de segredos antes do envio de mensagens.

### 3.10 `asset-template`
* **Estrutura**: O valor central da skill reside em matrizes estáticas, esqueletos de código, arquivos de configuração ou templates semânticos armazenados em `assets/`.
* **Caso de uso**: Scaffolding de projetos, geração de manifestos Kubernetes e aplicação de políticas de conformidade.

### 3.11 A Escada de Complexidade (Princípio da Parcimônia)
A introdução de complexidade estrutural deve ser rigorosamente justificada pela necessidade de reduzir a ambiguidade de execução:

```text
inline-guidance
       │
       ▼  (demanda conhecimento profundo modular)
reference-backed-expert
       │
       ▼  (demanda determinismo de parsing/validação)
script-backed-workflow
       │
       ▼  (demanda parametrização operacional)
argument-driven
       │
       ▼  (demanda coordenação e paralelismo dinâmico)
router / parallelization / orchestrator-workers
```

1. Adicionar uma nova **referência** exige uma decisão de consulta concreta.
2. Adicionar um novo **script** exige uma operação propensa a falhas em linguagem natural.
3. Adicionar uma nova **rota** exige entradas estruturalmente divergentes.
4. Adicionar um novo **subagente** exige isolamento de contexto ou modelo epistemológico diferenciado.

---

## 4. Ciclo de Vida e Avaliação de Skills (`skill-writer` e `prompt-optimizer`)

### 4.1 Engenharia de Skills como Produto
Uma skill deve ser gerenciada como software em produção, sujeita a versionamento, testes de regressão, contratos explícitos e manutenibilidade documentada.

```text
[1. Resolução] ──► [2. Síntese] ──► [3. Iteração] ──► [4. Redação] ──► [5. Otimização] ──► [6. Registro]
 Target/Shape         Hipóteses       Contratos         Authoring         Descrição          Evals/CI
```

Antes de realizar qualquer alteração em uma skill, o agente ou engenheiro deve responder formalmente a quatro perguntas:
1. **Qual comportamento observável do agente é alterado?**
2. **Qual regra ou instrução existente é substituída ou eliminada?**
3. **Qual parte do texto atual pode ser excluída para evitar acúmulo de contexto?**
4. **Por que um novo arquivo é estritamente necessário em vez de consolidar o atual?**

### 4.2 O "Precision Pass"
Após redigir ou alterar o `SKILL.md` ou arquivos auxiliares, aplica-se uma checagem de precisão (*precision pass*): cada linha adicionada deve corresponder a uma alteração direta em:
* Uma decisão tomada pelo agente.
* Uma ação externa executada (e.g., ferramenta, comando).
* Uma verificação de integridade antes da entrega.

Linhas explicativas, conselhos genéricos e redundâncias devem ser sumariamente purgados.

### 4.3 Avaliação Sistemática e Baterias de Teste (`evals/`)
Skills de produção exigem avaliação automatizada para prevenção de regressões comportamentais:

```text
skill-root/
├── EVAL.md
└── evals/
    ├── axis.config.json           # Definição das dimensões de qualidade e pesos
    ├── scenarios/                 # Cenários de teste em formato JSON
    └── fixtures/                  # Arquivos de código/dados para testes reproduzíveis
```

Estrutura canônica de um cenário de avaliação:
```json
{
  "name": "audit_jwt_none_algorithm",
  "prompt": "Audite o módulo de autenticação presente em src/auth/jwt.py",
  "setup": [
    { "action": "copy_fixture", "source": "fixtures/insecure_jwt.py", "target": "src/auth/jwt.py" }
  ],
  "judge": [
    { "check": "detects_algorithm_none_vulnerability", "weight": 0.4 },
    { "check": "produces_stable_finding_fingerprint", "weight": 0.3 },
    { "check": "proposes_safe_secret_verification", "weight": 0.3 }
  ],
  "artifacts": [
    "findings.json"
  ]
}
```

Tipos de validadores em evals:
1. **Determinísticos / Scripts**: Checagem de saída contra schemas JSON, saídas de compiladores e status de comandos.
2. **LLM Judges**: Avaliação semântica da explicação técnica e precisão das justificativas com critérios pontuados.
3. **Conjunto Holdout**: Manutenção de cenários isolados não consultados durante a elaboração de prompts para assegurar capacidade de generalização.

### 4.4 Otimização Metódica de Prompts (`prompt-optimizer`)
Prompts não são textos declarativos livres; são especificações operacionais de controle. A otimização deve seguir metodologia empírica:

1. **Definição de Fronteiras**: Delimitação clara de tipo de tarefa, família do modelo, superfície do prompt, entradas, ferramentas, saídas estruturadas, restrições duras (*hard constraints*) e objetivos negativos (*non-goals*).
2. **Coleta de Linha de Base (*Baseline*)**: Execução da bateria de testes na versão atual do prompt com catalogação estruturada de falhas.
3. **Agrupamento de Falhas e Causa Raiz**: Clusterização estatística dos erros observados.
4. **Geração e Teste de Candidatos**: Modificação incremental testada estritamente contra as mesmas métricas.
5. **Diagnóstico de Gargalos Externos**: O processo de refinamento de prompt deve ser interrompido quando a causa raiz do problema residir em:
   * Limitação intrínseca de capacidade do modelo escolhido.
   * Mecanismos falhos de recuperação de contexto (*retrieval*).
   * Deficiências no design ou validação de ferramentas (tool schemas).
   * Ausência de métricas objetivas de avaliação.

---

## 5. Segurança, Análise Estática e Vetores de Risco (`skill-scanner`)

### 5.1 A Skill como Superfície de Ataque
Instruções fornecidas a agentes autônomos operam como código executável em linguagem natural com acesso direto a ferramentas de sistema. O padrão `skill-scanner` estrutura a auditoria de skills em camadas estáticas e comportamentais:

```text
[Skill Submetida]
       │
       ▼
[Scanner Estático] ──► Gera JSON de evidências preliminares
       │
       ▼
[Auditoria Comportamental]
 ├── Frontmatter Integrity
 ├── Prompt Injection & Semântica
 ├── Behavioral Poisoning & Persistência
 ├── Script Security & Subprocessos
 └── Supply Chain & Dependências Externas
       │
       ▼
[Análise de Privilégios Mínimos]
```

### 5.2 Vetores de Verificação de Segurança

#### Integridade de Frontmatter
* Validação de alinhamento entre o campo `description` e as reais capacidades descritas no corpo do documento.
* Restrição estrita de ferramentas (`allowed-tools`) autorizadas para o agente.

#### Prompt Injection: Semântica vs. Ataque Real
A auditoria deve distinguir rigorosamente a *menção a padrões de ataque* da *tentativa de subversão do agente*:
* **Permitido**: Uma skill de segurança contendo assinaturas de payloads SQLi ou instruções sobre como identificar Prompt Injections em aplicações alvo.
* **Malicioso**: Instruções direcionadas ao agente que o forcem a ignorar diretrizes do sistema, omitir verificações de integridade ou exfiltrar dados sensíveis.

#### Envenenamento Comportamental (*Behavioral Poisoning*)
Identificação de instruções que visem persistir além da sessão de execução da skill, tais como comandos para:
* Modificar arquivos de memória persistente (`MEMORY.md`, `CLAUDE.md`, `AGENTS.md`).
* Adicionar padrões automáticos a listas de permissão (*allowlists*).
* Modificar configurações globais do sistema (`~/.claude/`, `~/.agents/`).
* Reduzir salvaguardas e níveis de privilégio da plataforma.

#### Segurança de Scripts e Subprocessos
Auditoria estrita de scripts utilitários em `scripts/`:
* Proibição de rotinas de exfiltração de dados e conexões reversas (*reverse shells*).
* Vedação de chamadas inseguras (`eval()`, `exec()`, `shell=True` sem sanitização).
* Verificação estrita de correspondência: as ações mecânicas do script devem cumprir rigorosamente o declarado na documentação.

#### Cadeia de Suprimentos (*Supply Chain*)
* Vetar download e execução de binários ou instruções remotas em tempo de execução.
* Validar hashes ou versões imutáveis de bibliotecas e dependências declaradas.

### 5.3 Hierarquia de Risco e Menor Privilégio
A atribuição de ferramentas deve obedecer ao princípio de privilégio mínimo:

| Nível de Risco | Conjunto de Ferramentas | Diretriz de Governança |
| :--- | :--- | :--- |
| **Baixo** | `Read`, `Grep`, `Glob` | Leitura passiva do repositório. Não apresenta risco de mutação ou exfiltração ativa. |
| **Médio** | `Read`, `Grep`, `Glob`, `Bash` (read-only) | Execução de comandos determinísticos com ambiente controlado e rede bloqueada. |
| **Alto** | `Read`, `Grep`, `Glob`, `Bash`, `Write`, `Edit` | Modificação de arquivos no repositório. Exige isolamento em diretórios temporários (`scratch/`). |
| **Crítico** | `... + WebFetch, Task, Subagents` | Acesso à rede externa, delegação encadeada e orquestração de terceiros. Demanda sandbox rígido. |

---

## 6. Orquestração Multiagente e Gerenciamento de Estado (Padrão Cloudflare)

### 6.1 O Pipeline em Seis Fases
Para fluxos analíticos ou transformações de alta complexidade, a arquitetura multiagente adota separação formal de estágios com artefatos estruturados intermediários:

```text
[Fase 1: RECONNAISSANCE] ──► Mapeamento independente de arquitetura (4 agentes passivos)
          │
          ▼
[Fase 2: COVERAGE HUNTING] ──► Exploração em ondas orientada pelo ledger de cobertura
          │
          ▼
[Fase 3: CANDIDATE VALIDATION] ──► Validação preliminar e triagem de hipóteses
          │
          ▼
[Fase 4: STRUCTURED OUTPUT] ──► Serialização em esquemas JSON rigorosamente tipados
          │
          ▼
[Fase 5: INDEPENDENT VERIFICATION] ──► Verificador limpo tenta refutar formalmente a hipótese
          │
          ▼
[Fase 6: REPORTING] ──► Síntese de relatórios executivos e técnicos
```

### 6.2 Soberania de Estado do Orquestrador
Os agentes executores (*workers*) não possuem permissão de escrita no estado global. O controle central é exclusivo do agente orquestrador (*parent*):

```text
                       PARENT AGENT
                    (Orquestrador Central)
               Dono Exclusivo do Estado Global
                             │
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
findings.json        coverage-ledger.json     run-metadata.json
     │                       │                       │
     └───────────────────────┼───────────────────────┘
                             │ distribui tarefas isoladas
            ┌────────────────┴────────────────┐
            ▼                                 ▼
      HUNTER WORKER                     VERIFIER WORKER
    agents/worker-1/                  agents/worker-2/
     ├── scratch/                      ├── scratch/
     └── artifacts/                    └── artifacts/
   (Sem acesso ao global)            (Sem acesso ao global)
```

### 6.3 Isolamento Operacional: `scratch/` vs. `artifacts/`
Qualquer arquivo produzido no ambiente do alvo ou por subagentes é classificado como potencialmente não confiável. Adota-se a política de promoção segura de artefatos:

```text
[Subagente / Ambiente Alvo]
           │
           ▼
   [agents/<id>/scratch/]   <── Escrita livre isolada
           │
           │  Validação Rígida pelo Orquestrador:
           │  ├── Ausência de path traversal ('..')
           │  ├── Rejeição de symlinks maliciosos
           │  ├── Verificação de tamanho e tipos de arquivo
           │  └── Prevenção de TOCTOU (Time-of-Check to Time-of-Use)
           ▼
  [agents/<id>/artifacts/]  <── Artefatos promovidos para síntese
```

### 6.4 Sandboxing Estrutural
Instruções em linguagem natural **não constituem fronteira de segurança**. A contenção do agente deve ser fornecida pela infraestrutura:
* Bloqueio total de tráfego de rede externa não autorizado.
* Sistema de arquivos do repositório/toolchain montado como somente-leitura (*read-only*).
* Escrita permitida exclusivamente em diretórios temporários (`scratch/`).
* Restrições rígidas de CPU, memória, número de processos filhos e tempo de execução (*wall-clock*).
* Caso o ambiente de sandbox não esteja disponível, operações de risco são suspensas e marcadas com status de pendência estruturada (`needs_validation`).

### 6.5 Reconhecimento Desacoplado da Exploração
Na Fase 1 de Reconhecimento, quatro agentes especializados operam de forma estritamente somente-leitura:
1. **1a**: Arquitetura de produto, stack tecnológica e mapeamento operacional.
2. **1b**: Entidades de segurança, limites de autoridade e controles de acesso.
3. **1c**: Superfícies de entrada, pontos de cópia e destinos de fluxo (*sinks*).
4. **1d**: Topologia de execução, modelos de deployment e observabilidade.

Cada agente reporta exclusivamente fatos objetivos referenciados com `file:line`. O orquestrador sintetiza os fatos em um modelo arquitetural unificado antes de instanciar qualquer agente de exploração (*hunter*).

### 6.6 O Ledger de Cobertura (*Coverage Ledger*)
Em sistemas corporativos, declarações genéricas de conclusão de tarefas são inaceitáveis. O estado da execução é mapeado em um ledger determinístico:

```json
{
  "coverage_id": "cov_auth_oauth2_callback",
  "canonical_refs": ["src/auth/oauth.py:84-120"],
  "surface": "api_rest",
  "boundary": "unauthenticated_to_internal",
  "subsystem": "authentication",
  "attack_class": "BrokenAccessControl",
  "starting_paths": ["src/auth/oauth.py"],
  "wave": 1,
  "status": "candidate",
  "agent_id": "hunter_04",
  "reviewed_paths": ["src/auth/oauth.py", "src/auth/token_store.py"],
  "local_checks": ["state_parameter_validation", "pkce_flow_enforcement"],
  "result_fingerprints": ["fp_oauth_state_missing_b7c2"],
  "unresolved": []
}
```

Estados formais de uma unidade de cobertura:
* `planned`: Programada para análise.
* `in_progress`: Sendo avaliada por um agente.
* `covered`: Coberta e validada sem inconformidades encontradas.
* `candidate`: Hipótese de inconformidade/vulnerabilidade gerada.
* `blocked`: Impossibilitada de prosseguir por falhas no ambiente ou dependências.
* `deferred`: Postergada deliberadamente devido a limites orçamentários.
* `out_of_scope` / `not_applicable`: Descartada com justificativa documentada.

#### Reexecução Incremental
O ledger de cobertura viabiliza execuções subsequentes sem retrabalho cego:
1. Compara-se o ledger anterior com as alterações git da base de código.
2. Unidades associadas a trechos de código inalterados permanecem com status preservado, dispensando nova fase de descoberta.
3. Trechos alterados têm suas unidades automaticamente resetadas para `planned`.

### 6.7 Perfis de Execução (*Profiles*) vs. Padrão de Evidência
A variação de perfis de execução regula a amplitude da exploração, mas **nunca flexibiliza o rigor da evidência exigida**:

```text
┌────────────────────────────────────────────────────────────────────────┐
│               BARRA DE EVIDÊNCIA (Constante Imutável)                 │
│ Todo apontamento exige prova causal, traço fático e linhas de código   │
└────────────────────────────────────────────────────────────────────────┘
                                    ▲
                                    │
       ┌────────────────────────────┼────────────────────────────┐
       │                            │                            │
[Perfil QUICK]             [Perfil STANDARD]             [Perfil DEEP]
1 onda de hunting          Múltiplas ondas               Análise exaustiva
1 crítico final            Críticos intermediários       Múltiplos críticos
1 verificador/candidato    1 verificador/candidato       Validação cruzada dupla
```

### 6.8 Gestão Formal de Orçamento (*Budgeting*)
O consumo de recursos (tempo, tokens, chamadas de modelo) deve ser tratado como variável arquitetural:
* O orquestrador reserva fatias de orçamento dedicadas para verificação independente e síntese de relatório.
* Ao atingir o limite orçamentário, a execução não finaliza falsamente com status de conclusão.
* Registra-se `run_status = incomplete`, sinaliza-se o motivo explícito (`budget_exhausted`) e as unidades pendentes passam para `deferred`.

### 6.9 Independência Epistemológica: Hunter vs. Verifier
O agente que formula uma hipótese é cognitivamente inclinado a confirmá-la (*viés de confirmação*). O padrão Cloudflare impõe segregação funcional obrigatória:

```text
                     [HUNTER AGENT]
              Localiza anomalia potencial
                          │
                          ▼
                  [Candidato JSON]
                          │
                          ▼
                 [NOVO VERIFICADOR]
       Instância independente sem histórico do agente anterior
       Recria o raciocínio a partir do código bruto original
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
    [CONFIRMED]   [NEEDS_VALIDATION]  [REJECTED]
```

Responsabilidades do verificador independente (*fresh verifier*):
1. Reler os arquivos-fonte de forma autônoma.
2. Auditar cada linha de código apontada na cadeia causal.
3. Reconstruir os fluxos de controle e checagens existentes.
4. Tentar reproduzir a falha ou refutar a hipótese.
5. Retornar exclusivamente JSON estruturado sem prosa livre.

### 6.10 Máquina de Estados de Apontamentos (*Findings*)
Os apontamentos transitam por uma máquina de estados formal, possuindo esquemas diferenciados por estado:

```text
                     [CANDIDATO]
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
    [CONFIRMED]   [NEEDS_VALIDATION] [REJECTED]
```

* **`confirmed`**: Hipótese formalmente comprovada com demonstração causal cabal.
  * *Campos obrigatórios*: `fingerprint`, `title`, `description`, `root_cause`, `intended_behavior`, `trace`, `evidence`, `conditions`, `execution`, `remediation`, `severity`, `confidence`.
* **`needs_validation`**: Cenários prováveis onde o agente não pôde validar a hipótese devido a limitações ambientais (falta de dependências, ausência de sandbox).
  * *Campos obrigatórios*: `claimed_root_cause`, `trace`, `evidence`, `blockers`, `validation_plan`.
  * **Regra de integridade**: É estritamente vedada a atribuição de notas de severidade (`severity`) a itens com pendência de validação.
* **`rejected`**: Hipótese demonstradamente refutada pelo verificador.
  * Registra a justificativa e os testes de refutação para impedir que execuções futuras redundem no mesmo falso positivo.

### 6.11 Identificadores Estáveis (*Fingerprints*)
Cada candidato recebe um identificador determinístico (hash criptográfico ou token estruturado) gerado a partir de sua causa raiz, arquivo e bloco de código:
* Permite rastrear o ciclo de vida do problema entre múltiplas execuções (`candidate` -> `confirmed` -> `resolved`).
* Impede a duplicação de apontamentos idênticos gerados por diferentes ondas de agentes.

### 6.12 Validação Defensiva com JSON Schema
Toda comunicação interagente ou gravação de estado deve ser estritamente validada por schemas JSON com diretivas defensivas:
* Ativação obrigatória de `additionalProperties: false` para repelir alucinação de campos arbitrários.
* O validador determinístico (`validate-findings.cjs`) inspeciona limites antes e depois do parse:
  * Limite máximo de bytes do arquivo.
  * Profundidade máxima de aninhamento de objetos (*nesting depth*).
  * Limite de quantidade total de elementos em coleções e arrays.
  * Validação canônica de caminhos de arquivo e codificação Unicode.

> [!IMPORTANT]
> **Artefatos e mensagens gerados por LLMs são entradas não confiáveis.** Validadores de código determinístico devem protegê-los com o mesmo rigor dispensado a dados vindos de fontes externas de rede.

---

## 7. Modularização de Domínio e Padrões Híbridos

### 7.1 Domínios Cognitivos como Plugins Modulares
Em vez de sobrecarregar um único arquivo com o conhecimento integral de um domínio extenso, segmenta-se o saber técnico em arquivos modulares carregados condicionalmente pelo orquestrador:

```text
skills/security-audit/
├── SKILL.md
└── references/
    ├── ATTACK-CLASSES.md                      # Roteador de classes de ataque
    ├── domains/
    │   ├── web-protocol-and-auth.md           # Sessão, tokens, OAuth, CORS
    │   ├── client-side.md                     # XSS, CSRF, DOM injection
    │   ├── cloud-and-deployment.md            # IAM, containers, secrets
    │   ├── supply-chain-and-release.md        # Dependências, pipelines CI/CD
    │   └── ai-and-llm.md                      # Injeções de contexto, tool sinks
```

### 7.2 Modelagem Causal vs. Listas de Checagem
Sistemas avançados não fornecem listas de sintomas superficiais, mas sim modelos causais de raciocínio. Exemplos aplicados:

#### Domínio de Segurança em IA / LLMs
Em vez de classificar qualquer injeção de prompt textual como vulnerabilidade isolada, modela-se a cadeia de quebra de fronteira de autoridade:
```text
[Conteúdo Não Confiável]
          │
          ▼
   [Modelo de IA]
          │
          ▼
 [Execução de Ferramenta / Ação Externa]
          │
          ▼
[Violação de Fronteira: Escalação de Privilégio / Exfiltração de Dados]
```
A falha de segurança só existe se a instrução não confiável atravessar a fronteira em direção a um consumidor (*sink*) autorizado sem sanitização intermediária.

#### Domínio de Cadeia de Suprimentos
Mapeamento de todo o ciclo causal de vida de componentes de software:
```text
Dependência ──► Resolução ──► Build ──► Artefato ──► Assinatura ──► Promoção ──► Execução
```
A verificação audita explicitamente a identidade do emissor, os limites de autoridade e a autenticidade criptográfica de cada etapa do pipeline.

### 7.3 Taxonomias Externas como Camada de Referência
Frameworks da indústria (como o **OWASP Top 10:2025**) devem ser integrados como conhecimento descritivo de taxonomia em `references/owasp-2025.md`, e **nunca como lógica procedural de workflow**.

A taxonomia define categorias padronizadas de risco (e.g., *A01 Broken Access Control*, *A03 Software Supply Chain Failures*). A lógica de como verificar o código, testar fluxos e confirmar a viabilidade de uma falha pertence estritamente ao workflow da skill e aos validadores determinísticos.

### 7.4 Padrão Coletor Determinístico + Catálogo Estático (Padrão CanIRunAI)
Para cenários que dependem do ambiente subjacente ou de especificações de hardware/infraestrutura, a arquitetura deve evitar a coleta via inferência livre do modelo:

```text
┌────────────────────────────────────────────────────────────────────────┐
│ 1. COLETOR DETERMINÍSTICO                                             │
│ Script nativo (Node.js built-ins / Shell) sem dependências externas    │
│ Executa comandos de SO e extrai dados brutos (CPU, GPU, RAM, Disco)   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ JSON de fatos brutos
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. CATÁLOGO ESTÁTICO DE CONHECIMENTO                                  │
│ Arquivo JSON/YAML versionado contendo a matriz de compatibilidade      │
│ Exemplo: modelos, requisitos mínimos e pesos matemáticos               │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ parâmetros consolidados
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. MOTOR DE DECISÃO DO AGENTE                                          │
│ O modelo de linguagem processa os fatos validados contra o catálogo    │
│ Produz recomendações sem risco de alucinação de especificações         │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Arquitetura Canônica Recomendada para Produção

Consolidando os padrões analíticos e operacionais analisados, a estrutura de referência canônica para engenharia de skills em sistemas corporativos de agentes é apresentada a seguir.

### 8.1 Layout Canônico de Diretórios

```text
enterprise-agent-skills/
├── .agents/
│   └── skills/                                # Espelho local de skills registradas
├── agents/                                    # Personas e subagentes formais
│   ├── orchestrator.md                        # Agente orquestrador de estado global
│   ├── researcher.md                          # Agente de reconhecimento estático
│   ├── hunter.md                              # Agente de exploração e teste de hipóteses
│   └── verifier.md                            # Verificador independente limpo
├── skills/
│   └── code-audit/                            # Instância canônica de skill
│       ├── SKILL.md                           # Roteador central de execução (< 500 linhas)
│       ├── SPEC.md                            # Contrato de manutenção e engenharia
│       ├── SOURCES.md                         # Registro de decisões e histórico
│       ├── references/                        # Bases de conhecimento Just-in-Time
│       │   ├── mode-selection.md              # Critérios de seleção de perfis e rotas
│       │   ├── architecture-model.md          # Modelagem de sistemas alvo
│       │   ├── evidence-model.md              # Critérios de admissibilidade de evidências
│       │   └── domains/                       # Domínios de auditoria especializados
│       │       ├── auth-and-identity.md
│       │       ├── injection-and-dataflow.md
│       │       └── supply-chain.md
│       ├── scripts/                           # Determinismo e garantias matemáticas
│       │   ├── validate-ledger.cjs            # Validador defensivo de cobertura
│       │   ├── validate-findings.cjs          # Validador defensivo de apontamentos
│       │   └── collect-git-diff.sh            # Coletor determinístico de alterações
│       ├── assets/                            # Artefatos reutilizáveis e contratos
│       │   ├── schemas/
│       │   │   ├── ledger-schema.json
│       │   │   └── findings-schema.json
│       │   └── templates/
│       │       └── executive-report.md
│       ├── EVAL.md                            # Documentação de critérios de validação
│       └── evals/                             # Bateria de testes de regressão
│           ├── axis.config.json
│           ├── scenarios/
│           └── fixtures/
└── README.md
```

### 8.2 Fluxo Unificado de Execução de Runtime

```text
                          SOLICITAÇÃO DO USUÁRIO
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │   ROTEADOR CENTRAL  │
                          │      (SKILL.md)     │
                          └──────────┬──────────┘
                                     │
                     Triagem e Seleção de Perfil/Modo
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │   PROGRESSIVE LOAD  │
                          │   Carga JIT apenas  │
                          │  das refs necessárias│
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │    ORQUESTRADOR     │
                          │ (Soberania de Estado)│
                          └──────────┬──────────┘
                                     │
                    Gera Plano e Ledger de Cobertura
                                     │
            ┌────────────────────────┼────────────────────────┐
            ▼                        ▼                        ▼
     [Hunter Wave 1]          [Hunter Wave 2]          [Hunter Wave N]
     (agents/*/scratch)       (agents/*/scratch)       (agents/*/scratch)
            │                        │                        │
            └────────────────────────┼────────────────────────┘
                                     ▼
                          ┌─────────────────────┐
                          │     AGREGAÇÃO &     │
                          │ PROMOÇÃO DE ARTEFATO│
                          │ (Checagens TOCTOU)  │
                          └──────────┬──────────┘
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │ VALIDADOR DE SCHEMA │
                          │ (JSON Schema Estrito│
                          │  additionalProp=F)  │
                          └──────────┬──────────┘
                                     │
                             Candidatos Válidos
                                     │
                                     ▼
                          ┌─────────────────────┐
                          │ VERIFICADOR INDEP.  │
                          │   (Fresh Instance)  │
                          │ Tenta refutar prova │
                          └──────────┬──────────┘
                                     │
             ┌───────────────────────┼───────────────────────┐
             ▼                       ▼                       ▼
        [CONFIRMED]         [NEEDS_VALIDATION]          [REJECTED]
             │                       │                       │
             └───────────────────────┼───────────────────────┘
                                     ▼
                          ┌─────────────────────┐
                          │ ATUALIZAÇÃO DO LEDGER│
                          │  E RELATÓRIO FINAL  │
                          └─────────────────────┘
```

### 8.3 Matriz de Responsabilidades por Componente

| Componente | Pergunta Fundamental Respondida | Natureza do Componente |
| :--- | :--- | :--- |
| **Router (`SKILL.md`)** | *"Qual tarefa deve ser realizada e sob qual política de despacho?"* | Decisório / Lógica de Roteamento |
| **Workflow** | *"Em qual ordem e dependência sequencial as etapas operam?"* | Procedural / Orquestração |
| **Agent / Worker** | *"Como aplicar inferência e raciocínio técnico sobre o contexto?"* | Cognitivo / Baseado em LLM |
| **Script** | *"O que deve ser executado de forma determinística sem intervenção de inferência?"* | Mecânico / Código Determinístico |
| **Reference** | *"Qual conhecimento especializado de domínio é necessário para a decisão corrente?"* | Declarativo / Just-in-Time |
| **JSON Schema** | *"Qual é o formato estrutural restrito e mandatório da saída?"* | Contratual / Validação Sintática |
| **Validator** | *"A saída entregue respeita integralmente as restrições sintáticas e de limites?"* | Defensivo / Sanitização de Dados |
| **Verifier** | *"Uma instância agêntica independente e sem histórico é capaz de refutar esta hipótese?"* | Epistemológico / Segregação de Função |
| **Ledger / State** | *"Quais unidades foram cobertas, quais falharam e quais permanecem pendentes?"* | Factual / Gestão de Estado |
| **Evals** | *"Esta skill mantém sua precisão e robustez após alterações de engenharia?"* | Qualidade / CI e Testes Contínuos |

---

## 9. Referências Canônicas

1. **Sentry Agent Skills Repository**: Diretrizes arquiteturais, especificações de plugins e padrões de engenharia para agentes.
   * [getsentry/skills](https://github.com/getsentry/skills)
2. **Sentry Skill Writer Reference**: Especificação formal do framework de criação e manutenção de skills.
   * [getsentry/skills - skill-writer](https://github.com/getsentry/skills/tree/main/skills/skill-writer)
3. **Sentry Prompt Optimizer**: Metodologia de mensuração empírica e otimização de prompts operacionais.
   * [getsentry/skills - prompt-optimizer](https://github.com/getsentry/skills/tree/main/skills/prompt-optimizer)
4. **Sentry Skill Scanner**: Padrão de análise estática e governança de segurança para Agent Skills.
   * [getsentry/skills - skill-scanner](https://github.com/getsentry/skills/tree/main/skills/skill-scanner)
5. **Cloudflare Security Audit Skill**: Arquitetura multiagente com orquestração central, ledger de cobertura e verificação independente.
   * [cloudflare/security-audit-skill](https://github.com/cloudflare/security-audit-skill)
6. **OWASP Top 10 (2025)**: Padrão taxonômico para classificação de riscos e vulnerabilidades em software.
   * [OWASP Foundation - Top 10:2025](https://top10.owasp.org/2025/)
7. **CanIRunAI**: Exemplo de pipeline combinando detecção determinística de sistema com catálogo estático de compatibilidade.
   * [CanIRunAI Project](https://canirunai.kc1t.com/en)
