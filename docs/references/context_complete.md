# Especificação Arquitetural Canônica — Sistema Modular de Auditoria Técnica de Software

## Sumário Executivo e Contexto do Sistema

Este documento estabelece a referência arquitetural canônica, formal e prescritiva para o Sistema Modular de Auditoria Técnica de Software. O propósito do sistema não é gerar relatórios puramente retóricos ou maximizar quantitativamente apontamentos superficiais, mas produzir diagnósticos técnicos de alta fidelidade epistêmica, reprodutíveis, rastreáveis e baseados estritamente em evidências empíricas.

O sistema opera sob o seguinte pipeline conceitual fundamental:

```text
Investigação ──► Evidência ──► Auditoria Especializada ──► Consolidação ──► Dataset Canônico ──► Publicação / Operação
```

A arquitetura orienta-se pelos seguintes atributos de qualidade:
* **Baseada em Evidências (*Evidence-First*):** Nenhuma asserção técnica é aceita sem prova observável.
* **Reprodutível:** As conclusões e execuções de testes/scripts devem ser determinísticas.
* **Rastreável:** Cadeia de proveniência íntegra desde a linha de código até o dataset final.
* **Persistente:** Estado desacoplado de sessões de chat, armazenado em artefatos versionáveis.
* **Modular e Incremental:** Execução segregada por domínios semânticos e reaproveitamento de análises via diff de commits.
* **Conservadora:** Na dúvida epistêmica, preserva-se a incerteza (`NOT_DETERMINABLE`) em vez de inferir certezas.
* **Epistemicamente Explícita:** Separação estrita entre Fato Observado, Inferência, Hipótese e Limitação.

---

## 1. Princípios e Restrições Operacionais

### 1.1 Restrição de Autoria e Fronteira de Isolamento (*Human-in-the-Loop*)
Em ambientes onde o código-fonte funcional do software auditado é desenvolvido manualmente (ex.: contexto acadêmico de Engenharia de Software), estabelece-se a regra de não modificação:
* **Proibição Estrita:** Modelos de Linguagem (LLMs) e agentes automatizados são estritamente proibidos de gerar, alterar ou sobrescrever arquivos de código-fonte funcional do projeto-alvo.
* **Escopo Permitido para Agentes/IA:** Análise estática, auditoria, revisão arquitetural, explicação técnica, documentação analítica, planejamento, pesquisa de vulnerabilidades e diagnóstico de defeitos.
* **Isolamento de Estado:** O sistema de auditoria reside em estrutura completamente segregada do repositório de produção do projeto (diretório `.audit/` com controle de versão independente), garantindo que nenhum artefato funcional seja impactado.

### 1.2 O Axioma Arquitetural de Eficiência e Rigor
A arquitetura é regida pelo axioma de otimização de esforço:

> **Executar a menor quantidade de trabalho necessária para obter evidência empírica suficiente, atual e válida, sem degradar o rigor epistemológico do diagnóstico.**

Eficiência deriva de aplicabilidade assertiva, delimitação precisa de escopo, reutilização conservadora de evidências, ferramentas determinísticas e fatiamento contextual — nunca da redução do rigor analítico.

---

## 2. Topologia do Pipeline e Arquitetura de Camadas

### 2.1 Visão Global do Pipeline

A arquitetura organiza-se em camadas funcionais especializadas e desacopladas:

```text
                     PROJETO-ALVO (Target Project)
                                  │
                                  ▼
                     PROJECT-CONTEXT (Descoberta)
                                  │
                                  ▼
                     PROJECT-AUDIT (Orquestração)
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
    CODE-AUDIT             SECURITY-AUDIT           DATABASE-AUDIT
         │                        │                        │
         ▼                        ▼                        ▼
    TEST-AUDIT               GIT-AUDIT                 DOC-AUDIT
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  ▼
                     CORRELAÇÃO & CONSOLIDAÇÃO
                                  │
                                  ▼
                          AUDIT OUTPUT SET
                                  │
                                  ▼
                    AUDIT-NORMALIZE (Compilador)
                                  │
                                  ▼
                          report_data.json
                                  │
                     ┌────────────┴────────────┐
                     ▼                         ▼
               REPORT-PUBLISH             ISSUE-FORGE
```

### 2.2 Camada `project-context` (Reconhecimento Neutro)
Responsável pelo levantamento factual e mapeamento estrutural do projeto-alvo. Não atua como auditor e não emite julgamentos técnicos de valor.
* **Atividades:** Identificação de stack tecnológica, dependências declaradas e transitivas, entrypoints, estrutura de módulos, sistemas de build, suites de teste, esquemas de banco de dados, topologia de rede/infraestrutura e configurações de deploy.
* **Escopo Epistêmico:** Responde estritamente à pergunta *"O que existe no projeto?"*, abstendo-se de responder *"Isso está correto?"*.
* **Saída:** Perfil descritivo estruturado e persistente do projeto.

### 2.3 Camada `project-audit` (Orquestração, Seleção e Correlação)
Evoluído a partir de uma abordagem monolítica original para atuar como coordenador de auditorias modulares, evitando consumo desnecessário de contexto (ex.: auditar banco em aplicações CLI sem persistência).
* **Atividades:** Resolução de escopo com o usuário, avaliação de aplicabilidade técnica, seleção e acionamento de auditores especializados, verificação de cobertura, correlação causal de achados interdomínio e consolidação final do *Audit Output Set*.

### 2.4 Camada de Auditores Especializados (Domínios Semânticos Coesos)
Módulos dedicados à análise aprofundada de verticais técnicas específicas:
* `code-audit`: Qualidade estrutural, princípios de design (SOLID), padrões arquiteturais, manutenibilidade, acoplamento e coesão.
* `security-audit`: Superfície de ataque, controles criptográficos, autenticação, autorização, modelagem de ameaças e vulnerabilidades.
* `database-audit`: Esquema relacional, integridade referencial, normalização, indexação, transações, concorrência, migrações e mapeamento objeto-relacional (ORM).
* `test-audit`: Pirâmide de testes, cobertura efetiva, assertividade, qualidade de fixtures e determinismo.
* `git-audit`: Higiene de versionamento, histórico de commits, branches, integridade e busca delimitada de segredos vazados.
* `documentation-audit`: Consistência entre documentação (README, arquitetura, contratos de API) e a implementação real.

> **Princípio de Granularidade:** Cada auditor especializado deve possuir uma fronteira semântica ampla o suficiente para produzir valor de forma autônoma. Micro-skills especializadas (ex.: `solid-audit` ou `pattern-audit`) são proibidas; tais matérias integram organicamente o `code-audit`.

### 2.5 Camada `audit-normalize` (Compilação Canônica)
Compilador conservador, determinístico e não-destrutivo que processa os artefatos Markdown do *Audit Output Set* e gera a estrutura JSON unificada e validada por esquema (`report_data.json`).
* **Invariante:** Não audita código-fonte, não infere achados, não corrige julgamentos técnicos e não mascara incertezas.

### 2.6 Camadas Downstream: `report-publish` e `issue-forge`
* `report-publish`: Renderiza dashboards, páginas estáticas, relatórios executivos em PDF ou portais de documentação a partir do `report_data.json`.
* `issue-forge`: Consome o dataset canônico e gera artefatos operacionais granulares (tarefas no Jira, GitHub Issues, itens de backlog).

---

## 3. Contrato Canônico de Saída: O *Audit Output Set*

### 3.1 Unificação Contratual
Todo processo de auditoria — seja a execução de um auditor especializado individual ou uma auditoria completa orquestrada — deve produzir rigorosamente o mesmo conjunto de quatro artefatos no diretório `docs/audit/`. Não existem contratos proprietários ou formatos ad-hoc por domínio.

```text
docs/audit/
├── 00_inventory_and_threat_model.md
├── 01_coverage_manifest.md
├── 02_analytical_report.md
└── 03_audit_ledger.md
```

### 3.2 Artefato 00 — Inventário e Modelo de Ameaças (`00_inventory_and_threat_model.md`)
Registra as fronteiras operacionais, perfil do sistema e modelagem estruturada de segurança:
* **Identidade do Alvo:** Repositório, Target Commit (distinguindo formalmente `TARGET_COMMIT` do `CURRENT_HEAD` do ambiente de execução), branch e versão de release.
* **Ambiente de Execução:** Ferramental de runtime, SO, variáveis de ambiente e dependências locais.
* **Componentes de Ameaça:** Ativos protegidos (*Assets*), Atores (*Actors*), Superfícies de Ataque (*Attack Surfaces*), Fronteiras de Confiança (*Trust Boundaries*), Dados Sensíveis manipulados e Limitações Globais da análise.

### 3.3 Artefato 01 — Manifesto de Cobertura (`01_coverage_manifest.md`)
Garante transparência epistemológica e demarcação precisa do escopo avaliado através de quatro dimensões obrigatórias:

#### Dimensão 1: Aplicabilidade (Applicability)
Classifica se categorias técnicas aplicam-se à realidade do projeto analisado.
* **Estados Canônicos:**
  * `APPLICABLE`: A categoria incide tecnicamente sobre o projeto (ex.: Autenticação em API REST).
  * `NOT_APPLICABLE`: O recurso inexiste por desenho arquitetural (ex.: Migrações SQL em utilitário CLI sem banco de dados).
  * `NOT_DETERMINABLE`: Impossível determinar aplicabilidade com a documentação e código disponíveis.

> **Regra:** A ausência de defeitos encontrados nunca deve ser usada para classificar uma categoria como `NOT_APPLICABLE`.

#### Dimensão 2: Cobertura de Inspeção (Inspection Coverage)
Registra o status da inspeção analítica e seu resultado:
* **Estados de Inspeção:** `INSPECTED`, `PARTIALLY_INSPECTED`, `NOT_INSPECTED`, `NOT_DETERMINABLE`.
* **Resultados de Inspeção:**
  * `FINDINGS_PRESENT`: Falhas ou observações foram catalogadas na categoria.
  * `NOT_FOUND`: A categoria foi efetivamente analisada e nenhuma inconformidade foi observada dentro do escopo disponível. *(Nota: Não equivale a declarar o sistema imune ou matematicamente seguro).*
  * `NOT_DETERMINABLE`: Ambiguidade ou limitações impediram conclusão analítica.

#### Dimensão 3: Cobertura de Arquivos (File Coverage)
Mapeia o nível de exame dos artefatos físicos do projeto.
* **Estados Canônicos:** `AUDITED`, `PARTIALLY_AUDITED`, `NOT_AUDITED`.
* **Distinção Fundamental:** Arquivos catalogados no inventário (`MAPPED`) não são considerados auditados (`AUDITED`). A listagem de 100 arquivos no inventário onde 30 foram inspecionados reflete exatamente 30 arquivos com status `AUDITED` e 70 como `NOT_AUDITED`.

#### Dimensão 4: Log de Execução (Execution Log)
Rastreabilidade estrita de cada comando executado no ambiente de auditoria:
* **Campos:** Comando exato executado, Propósito técnico e Status (`EXECUTED` ou `NOT_EXECUTED` acompanhado de justificativa).
* **Invariante:** Proibido registrar comandos que não foram efetivamente disparados no shell do auditor.

### 3.4 Artefato 02 — Relatório Analítico (`02_analytical_report.md`)
Documento narrativo que fornece o raciocínio aprofundado, visão sistêmica, justificativas contextuais, trade-offs técnicos, avaliação de manutenibilidade e recomendações arquiteturais estruturadas.

### 3.5 Artefato 03 — Ledger de Auditoria (`03_audit_ledger.md`)
Repositório tabular e estruturado de achados técnicos (*findings*) e controles verificados (*controls*). Constitui a principal fonte de dados primária para o compilador `audit-normalize`.

---

## 4. Epistemologia, Evidências e Modelo de Dados

### 4.1 O Princípio *Evidence-First* e Separação Epistêmica
A auditoria fundamenta-se na verificação ativa de asserções:

```text
Afirmação (Claim) ──► Requisito de Evidência ──► Evidência Verificada ──► Veredito Técnico
```

Documentações, arquivos README, comentários em código e mensagens de commit são classificados como **alegações não confiáveis (Untrusted Claims)** até que sua validação empírica ou lógica ocorra no código executável ou no ambiente de runtime.

Na descrição de qualquer diagnóstico, deve ser mantida a distinção epistemológica:
* **[Observation]:** Fato empírico diretamente observado no código, logs ou execução de ferramentas.
* **[Inference]:** Conclusão lógica derivada diretamente das observações documentadas.
* **[Hypothesis]:** Explicação plausível ou potencial causa-raiz ainda pendente de prova definitiva.
* **[Limitation]:** Barreira técnica concreta que impossibilitou aprofundar ou confirmar a análise.

### 4.2 Status Epistêmico dos Achados
* `CONFIRMED`: A falha é sustentada por evidência incontestável (código, teste que reproduz, log de erro).
* `PROBABLE`: Fortes indícios lógicos e padrões suspeitos, mas com ausência de execução comprobatória.
* `NOT_DETERMINABLE`: Impossível determinar o comportamento real devido a dependências externas ou restrições contextuais.

> **Regra:** É terminantemente vedado promover um estado de `Hypothesis` para `CONFIRMED` sem a apresentação de nova evidência empírica.

### 4.3 Taxonomia Tipológica de Achados (*Finding Types*)
O sistema reconhece dez tipos padronizados:
1. `BUG`: Erro funcional demonstrável que viola a especificação explícita do software.
2. `TECHNICAL_DEFECT`: Desvio de padrão técnico aceito, má gestão de recursos ou falha não-funcional.
3. `VULNERABILITY`: Brecha de segurança suscetível a exploração de ameaças externas ou internas.
4. `RISK`: Situação com probabilidade adversa não materializada de imediato, mas latente.
5. `INCONSISTENCY`: Divergência entre camadas (ex.: domínio aceita nulo, banco declara `NOT NULL`).
6. `TECH_DEBT`: Débito técnico consciente ou acúmulo de soluções improvisadas que dificultam evolução.
7. `OPERATIONAL_PROBLEM`: Falhas em deploy, empacotamento, monitoramento, configuração de portas ou logs.
8. `ARCHITECTURAL_DEFECT`: Violação concreta de limites arquiteturais, dependências circulares ou quebra de coesão.
9. `ARCHITECTURAL_IMPROVEMENT`: Oportunidade identificada de otimização estrutural sem falha presente.
10. `REQUIREMENT_DEPENDENT`: Comportamento ambíguo cuja avaliação depende de definição explícita do negócio.

### 4.4 Severidade (*Severity*) vs Confiança (*Confidence*)
Severidade e Confiança são grandezas ortogonais e independentes:

* **Escala de Severidade:** `P0` (Crítico/Blocante), `P1` (Alto), `P2` (Médio), `P3` (Baixo), `INFO` (Informativo).
  * A determinação da severidade baseia-se em: impacto no negócio/sistema, explorabilidade, contexto de exposição, pré-condições exigidas e criticidade operacional. A gravidade de uma falha nunca é julgada apenas pela sua "aparência" sintática.
* **Escala de Confiança:** `HIGH` (Alta), `MEDIUM` (Média), `LOW` (Baixa).
  * Expressa a certeza epistêmica da equipe de auditoria sobre a existência e escopo do achado. Um achado de severidade `P2` com confiança `HIGH` é uma classificação perfeitamente válida.

### 4.5 Esquema Canônico de um Achado (*Finding Schema*)
No ledger e no dataset canônico, cada achado é composto pelos seguintes atributos:

| Campo | Tipo | Descrição |
|---|---|---|
| `id` | String | Identificador estável por domínio (ex.: `SEC-001`, `ARCH-002`, `DB-001`). |
| `title` | String | Título técnico, conciso e autoexplicativo (obrigatório). |
| `category` | String | Grande vertical de auditoria (ex.: `SECURITY`, `DATABASE`, `ARCHITECTURE`). |
| `subcategory` | String | Tópico específico (ex.: `SQL_INJECTION`, `TRANSACTION_BOUNDARY`). |
| `type` | Enum | Um dos 10 tipos taxonômicos canônicos. |
| `status` | Enum | `CONFIRMED`, `PROBABLE`, ou `NOT_DETERMINABLE`. |
| `severity` | Enum | `P0`, `P1`, `P2`, `P3`, ou `INFO`. |
| `confidence` | Enum | `HIGH`, `MEDIUM`, ou `LOW`. |
| `location` | Array/String | Arquivo e linhas correspondentes (ex.: `src/auth.py:45-52`). Suporta múltiplos locais para mesma causa raiz. |
| `evidence` | String | Trecho de código, comando executado, log ou demonstração irrefutável. |
| `description` | String | Detalhamento técnico estruturado utilizando os marcadores epistêmicos. |
| `cause` | String | Causa-raiz subjacente do defeito. |
| `impact` | String | Consequência tangível para estabilidade, integridade ou segurança. |
| `exploitability` | String | Avaliação das barreiras para materialização do risco. |
| `recommendation` | String | Plano de correção técnico, prescritivo e acionável. |

### 4.6 Registro de Controles Positivos (*Controls*)
A auditoria audita conformidades verificadas, registrando controles de segurança e integridade efetivamente presentes no sistema (ex.: uso consistente de `PreparedStatement`, verificação estrita de autorização, hashing seguro de senhas com sal).

* **Regra de Inclusão:** Um controle só pode ser catalogado se sua eficácia foi testada ou validada no código. A ausência de SQL Injection não autoriza a criação do controle "SQL 100% Protegido".
* **Esquema:** `id` (ex.: `CONTROL-001`), `title`, `category`, `subcategory`, `status` (`VERIFIED`), `description` (contendo a prova da verificação, contexto e eventuais limitações) e `provenance`.

---

## 5. Diretrizes Especializadas por Domínio Técnico

### 5.1 Engenharia de Segurança
* **Inspeção em Duas Passadas (Two-Pass Inspection):** A segurança não deve ser uma subseção superficial da análise de código. O desenho original prescreve:
  ```text
  PASSADA 1: Engenharia e Estrutura ──► PASSADA 2: Ataque e Segurança ──► Correlação Cruzada
  ```
* **Modelagem de Ameaças:** Mapeamento explícito de Ativos, Atores, Vetores de Exposição, Trust Boundaries e Proteção de Dados Sensíveis. Proibido assumir existência de controles não demonstrados em código.
* **Cadeias de Ataque (*Attack Chains*):** Vulnerabilidades relevantes devem descrever a trajetória completa da ameaça:
  ```text
  Ator Malicioso ──► Pré-condição ──► Entrada Controlável ──► Ponto Vulnerável ──► Bypass de Controle ──► Impacto
  ```
* **Catálogo Canônico:** Inspeção orientada por tópicos aplicáveis: `SQL_INJECTION`, `XSS`, `CSRF`, `SSRF`, `IDOR`, `AUTHENTICATION`, `AUTHORIZATION`, `BRUTE_FORCE`, `SESSION`, `COOKIE`, `JWT`, `PASSWORD_STORAGE`, `SECRET_EXPOSURE`, `CORS`, `HTTPS`, `SECURITY_HEADERS`, `CSP`, `OPEN_REDIRECT`, `MASS_ASSIGNMENT`, `DESERIALIZATION`, `RACE_CONDITION`, `TOCTOU`, `RESOURCE_EXHAUSTION`, `BUSINESS_LOGIC`, `DEBUG_EXPOSURE`, `DEPENDENCY`, `SUPPLY_CHAIN`.
* **Varredura Histórica de Segredos:** A análise do histórico Git para busca de credenciais deve ser estritamente delimitada (padrão sugerido: últimos 50 commits), utilizando comandos estruturados (ex.: `git log --all --full-history -- ".env"`). Jamais afirmar ausência de segredos históricos sem inspeção que sustente tal garantia.

### 5.2 Controle de Versão e Higiene do Git
Diferenciação clara entre arquivos ignorados (`.gitignore`), não rastreados (*untracked*) e rastreados (*tracked*). Análise de convenções de branch, rastreabilidade de commits, tags de release e presença de artefatos temporários indevidamente commitados.

### 5.3 Testabilidade, Execução e Cobertura de Testes
Estabelece-se a distinção rigorosa dos seguintes estados da esteira de qualidade:
```text
Framework Configurado  ≠  Testes Existentes  ≠  Testes Executados  ≠  Testes Aprovados  ≠  Cobertura Medida
```
* A aprovação de uma build (`BUILD SUCCESSFUL`) não atesta a cobertura de regras de negócio.
* O valor de cobertura (ex.: `84%`) só pode ser declarado caso uma ferramenta confiável de medição tenha sido efetivamente executada. Na ausência de testes, deve-se declarar `No test suite detected`, evitando o registro leviano de `0%` medido.

### 5.4 Toolchain, Sistema de Build e Dependências
Avaliação de reprodutibilidade da compilação, wrappers (`gradlew`, `mvnw`), lockfiles (`package-lock.json`, `poetry.lock`), bibliotecas locais avulsas (ex.: JARs sem gestão de dependências), dependências transitivas e detecção de versões vulneráveis ou conflitantes.

### 5.5 Persistência de Dados e Banco de Dados
Inspeção de conformidade de esquemas DDL, integridade referencial (PK, FK, UK), índices adequados, regras de nulidade, normalização, demarcação explícita de transações (`@Transactional`, commits, rollbacks em falha), ciclo de vida e pool de conexões, consultas parametrizadas, potenciais problemas de N+1 queries e versionamento via migrações estruturadas.

### 5.6 Domínio e Modelagem de Negócio
Avaliação de invariantes de entidades, integridade de Value Objects, delimitação de Agregados, transições válidas de estados e encapsulamento.
* **Distinção Fundamental:** Uma regra implementada incorretamente no código difere formalmente de um comportamento indefinido por ausência de especificação externa do negócio (`REQUIREMENT_DEPENDENT`).

### 5.7 Arquitetura, Acoplamento e SOLID
Avaliação de acoplamento eferente/aferente, coesão de módulos, direcionalidade de dependências e fronteiras de domínio.
* **Modelos Arquiteturais:** Padrões (Clean Architecture, Hexagonal, Onion, Layered) são identificados pelo comportamento e fluxo de contratos entre camadas, nunca apenas pelo nome de diretórios ou pacotes.
* **Aplicação de SOLID:** Violações de princípios SOLID só configuram defeitos técnicos quando geram efeitos adversos tangíveis e observáveis (complexidade desnecessária, rigidez, fragilidade, impossibilidade de testes). Não se criam interfaces vazias apenas para satisfazer formalmente o DIP.

### 5.8 Padrões de Projeto (*Design Patterns*) e Avaliação de Trade-Offs
Identificação de padrões com base em intenção, adequação técnica, custos e benefícios reais. Padrões de design não são recomendados compulsoriamente apenas porque existem em catálogos. A escolha por implementações pragmáticas (ex.: injeção manual de dependências em aplicações reduzidas) deve ser compreendida no seu contexto antes de ser rotulada como não-conformidade.

### 5.9 Contratos *Cross-Layer* e Consistência Interimplementações
Auditoria vertical da propagação de contratos:
```text
Entidade de Domínio ──► Modelo de Mapeamento (DTO/ORM) ──► Persistência ──► Sentença SQL ──► Esquema DDL
```
Detecção de incompatibilidades entre validações de domínio (ex.: campo obrigatório com tamanho máximo) e definições do banco (ex.: coluna permitindo nulo com tamanho ilimitado). Quando existirem implementações paralelas ou alternativas de uma mesma operação, inspeciona-se a consistência de tratamento de exceções, regras e persistência.

### 5.10 Configuração, Infraestrutura e Operações
Segregação estrita entre Código, Configuração, Segredos e Infraestrutura. Classificação clara do ambiente alvo (`development`, `test`, `ci`, `staging`, `production`, `unknown`). Arquivos Docker, Docker Compose, permissões de usuário (root vs non-root), limites de recursos e logs são avaliados conforme a proporção real do projeto. A ausência de ferramentas enterprise em sistemas de escopo reduzido não deve ser classificada automaticamente como defeito de alta severidade.

### 5.11 Migrações e Evolução de Esquema
Investigação de inicialização de base, idempotência de seeds e scripts de migração (Flyway, Liquibase ou ferramentas nativas do ecossistema). Ferramentas de migração somente devem ser receitadas caso haja benefício concreto e problema real a ser solucionado.

### 5.12 Avaliação de Maturidade e Detecção de *Overengineering*
* **Estágios de Maturidade:** Inferidos objetivamente a partir das evidências: `LABORATORY`, `ACADEMIC`, `INTERMEDIATE`, `PROFESSIONAL`, `PRODUCTION_READY`. Proibido atribuir pontuações arbitrárias desprovidas de critérios empíricos.
* **Prevenção de Complexidade Acidental (*Overengineering*):** O auditor deve alertar formalmente contra a adoção prematura de microsserviços, Kubernetes, CQRS, Event Sourcing ou camadas artificiais de abstração desproporcionais aos requisitos operacionais do sistema.

### 5.13 Heurísticas de Auxílio de IA na Autoria do Código
Avaliação analítica não-forense com objetivo pedagógico e diagnóstico:
* **Graus de Indício:** `Baixo`, `Moderado`, `Forte`, sempre associados a um nível de Confiança (`Baixa`, `Média`, `Alta`).
* **Sinais Indicativos:** Volume atípico de código padronizado/boilerplate, comentários explicativos genéricos, abstrações perfeitas porém redundantes, assimetrias comportamentais e uniformidade excessiva de sintaxe. Essas heurísticas jamais constituem comprovação forense definitiva.

---

## 6. Orquestração, Escopo e Otimização de Recursos

### 6.1 Resolução Precoce de Escopo (*Scope Resolution*)
A definição de escopo deve ocorrer antes do consumo desnecessário de contexto e execução de análises:

```text
Solicitação do Usuário ──► Matriz de Aplicabilidade ──► Escopo Filtrado ──► Plano de Auditoria Otimizado
```

Modalidades aceitas:
* `FULL`: Execução de todas as verticais aplicáveis.
* `FULL EXCEPT [domínios]`: Execução completa excluindo domínios específicos (ex.: "auditoria completa exceto banco de dados"). As verticais excluídas devem ser registradas expressamente no manifesto de cobertura como ignoradas a pedido do usuário.
* `ONLY [domínios]`: Execução isolada de auditores determinados (ex.: somente `security-audit`).

### 6.2 Execução Autônoma vs Orquestrada
Qualquer auditor especializado possui completude semântica para rodar isoladamente, produzindo o *Audit Output Set* padronizado e encaminhando-o diretamente para o `audit-normalize`. O papel do `project-audit` é adicionar inteligência de orquestração, correlação interdomínio e unificação quando múltiplas disciplinas são mobilizadas.

### 6.3 Ciclo de Vida da Orquestração no `project-audit`
Quando opera como orquestrador, o `project-audit` executa nove etapas sequenciais:
1. Compreensão inicial do projeto (consumindo o perfil do `project-context`).
2. Delimitação estrita do escopo de trabalho.
3. Determinação e seleção dos auditores especializados aplicáveis.
4. Coordenação da execução dos auditores selecionados.
5. Coleta e validação dos artefatos produzidos.
6. Verificação de integridade e preenchimento da cobertura analítica.
7. Correlação causal entre apontamentos de múltiplos domínios.
8. Resolução de inconsistências textuais e consolidação dos achados.
9. Emissão do *Audit Output Set* consolidado.

### 6.4 Correlação Causal Interdomínio
O orquestrador mapeia como defeitos estruturais propagam falhas em outras dimensões técnicas.
* **Exemplo de Encadeamento Causal:**
  ```text
  Alto Acoplamento (ARCH-001) ──► Dificuldade de Testes Unitários ──► Lógica de Autorização Dispersa ──► Falha de Autorização (SEC-004)
  ```
* **Regra:** Não converter problemas arquiteturais em achados de segurança sem nexo de causalidade comprovado.

### 6.5 Deduplicação e Análise de Divergências
* **Deduplicação Causal:** Múltiplas ocorrências com idêntica causa-raiz originadas em diferentes arquivos devem ser agrupadas sob um único identificador no ledger (apontando as múltiplas localizações), evitando inflar artificialmente o volume de achados.
* **Conservadorismo:** Na incerteza sobre se duas falhas compartilham a mesma causa-raiz, preservam-se entidades separadas.
* **Divergência Analítica (*Divergence*):** Registra-se divergência somente quando duas passadas de auditoria discordam semanticamente sobre a gravidade ou status de uma evidência (ex.: Passada 1 indica `P1` e Passada 2 indica `P2`). Convergência de julgamentos não gera divergência.

### 6.6 Fatiamento de Contexto (*Context Slicing*) e Divulgação Progressiva
Para conter o consumo de tokens e preservar precisão diagnóstica, os auditores operam sob divulgação progressiva de contexto:
* **Nível 0:** Perfil consolidado e sumário arquitetural do projeto.
* **Nível 1:** Árvore de arquivos relevantes para o domínio da auditoria.
* **Nível 2:** Assinaturas de interfaces, classes e símbolos de interesse.
* **Nível 3:** Código-fonte das rotinas centrais inspecionadas.
* **Nível 4:** Cadeia de chamadas e dependências diretas.
* **Nível 5:** Código-fonte integral e fixtures de suporte (apenas se justificado).

---

## 7. Análise Incremental e Evolução Temporal da Auditoria

### 7.1 Auditoria Incremental Baseada em Commits
O histórico de auditorias é atrelado a commits específicos do Git (`TARGET_COMMIT`). Ao atualizar o projeto (`abc123` ──► `def456`), o sistema realiza a inspeção diferencial (`git diff abc123..def456`) para identificar as superfícies modificadas.

### 7.2 Taxonomia de Tratamento de Achados Anteriores
Frente a alterações de código, achados e evidências de auditorias anteriores recebem uma de quatro classificações:
* `REUSE`: A evidência permanece válida por critérios objetivos (código, dependências e contexto do achado mantiveram-se intocados).
* `REVALIDATE`: Alterações menores ocorreram no módulo; exige inspeção rápida focada, sem necessidade de reauditoria total.
* `REAUDIT`: A superfície do componente sofreu refatoração substancial; auditoria completa do módulo é disparada.
* `INVALIDATE`: A evidência anterior perdeu aderência ao código atual e deve ser descartada do conjunto ativo.

### 7.3 Propagação de Impacto Multinível
A análise incremental não deve restringir-se à detecção superficial de arquivos alterados:
```text
Arquivo Modificado ──► Símbolos Alterados ──► Dependências Afetadas ──► Achados Impactados
```
Uma alteração de documentação ou a adição de um método não relacionado dentro de uma classe extensa não invalida automaticamente os achados existentes referentes a outros métodos da mesma classe.

### 7.4 Rastreamento do Ciclo de Vida dos Achados
Na comparação entre auditorias sucessivas, cada achado histórico assume um estado evolutivo:
* `RESOLVED`: A causa-raiz foi comprovadamente eliminada mediante verificação de nova evidência.
* `PERSISTS`: O defeito permanece presente e inalterado na versão auditada.
* `MODIFIED`: A localização, impacto ou expressão sintática da falha foi alterada pelas mudanças de código.
* `NEW`: Novo apontamento identificado nas superfícies adicionadas ou alteradas.
* `NOT_DETERMINABLE`: Impossível atestar resolução ou persistência sem nova inspeção dinâmica.

> **Regra:** O simples fato de um arquivo com apontamento ter sido modificado não autoriza a classificação do achado como `RESOLVED`. A eliminação da causa-raiz deve ser verificada.

### 7.5 Critérios Rígidos para Reutilização de Evidências
Uma evidência anterior só pode ser reutilizada quando atendidos cumulativamente os seguintes requisitos:
1. `TARGET_COMMIT` anterior devidamente registrado e verificável no histórico.
2. Insumos e código-fonte relevantes sem alteração estrutural no diff.
3. Toolchain, dependências de build e runtime equivalentes.
4. Arquivos de configuração e variáveis de ambiente mantidos estáveis.
5. Escopo da auditoria atual equivalente ou abrangente em relação ao original.

---

## 8. Isolamento de Estado, Automação e Segurança Operacional

### 8.1 Isolamento de Estado no Diretório `.audit/`
O repositório do projeto-alvo deve permanecer limpo de artefatos de trabalho gerados por agentes.
* O diretório `.audit/` deve ser obrigatoriamente adicionado ao `.gitignore` do projeto principal.
* O diretório `.audit/` gerencia seu próprio repositório Git segregado (`.audit/.git/`), garantindo controle de versão de:
  ```text
  .audit/
  ├── .git/
  ├── state/        (Estado persistente de continuidade)
  ├── runs/         (Logs de execuções históricas)
  ├── cache/        (Evidências determinísticas cacheadas)
  └── reports/      (Audit Output Sets gerados)
  ```

### 8.2 Divisão Operacional: Scripts Determinísticos vs Raciocínio de LLM
O sistema estabelece clara divisão entre o que deve ser computado algorithmicamente e o que requer interpretação cognitiva:
* **Scripts Determinísticos (Computação Exata):** Cálculo de hashes SHA-256, execução de `git diff`, inventário de arquivos, extração de árvores de dependência via CLI de build, execução de testes unitários, validação de esquemas JSON e medição de cobertura via ferramentas dedicadas.
* **Modelos de Linguagem (Interpretação e Síntese):** Raciocínio sobre integridade arquitetural, modelagem de ameaças e atacantes, avaliação de adequação de regras de negócio, interpretação de contextos ambíguos e correlação causal intermódulos.

### 8.3 Fronteiras de Confiança e Dados Não Confiáveis
Todo o conteúdo oriundo do projeto-alvo (arquivos-fonte, documentações, scripts embutidos, mensagens de commit, issues e fixtures) é classificado categoricamente como **DADOS NÃO CONFIÁVEIS (Untrusted Data)**. Instruções, comandos ou scripts presentes em arquivos como `README.md` não devem ser executados cegamente pelo ambiente de auditoria sem inspeção de segurança prévia.

### 8.4 Barreira de Segurança de Execução (*Execution Safety Gate*)
Mesmo auditorias com objetivo estrito de leitura podem acarretar execução de código arbitrário durante compilação ou execução de suítes de testes:

```text
DESCOBERTA DO COMANDO ──► REVISÃO ESTÁTICA DE SEGURANÇA ──► CLASSIFICAÇÃO DE RISCO ──► APROVAÇÃO
                                                                                           │
                                                          ┌────────────────────────────────┴──────────────────────────────┐
                                                          ▼                                                               ▼
                                                       SEGURO                                                         INSEGURO
                                                          │                                                               │
                                                          ▼                                                               ▼
                                               Execução Controlada                                            Execução Vetada +
                                            (Ambiente/Container Isolado)                                    Registro de Limitação
```

* **Operações Terminantemente Proibidas:** Execução automática de instruções destrutivas como `git clean -fdx`, `git reset --hard` ou operações com privilégio administrativo sem validação prévia.
* **Isolamento de Ambiente:** Builds e suítes de testes devem ser executados prioritariamente em containers efêmeros, réplicas em diretório temporário ou com perfil de leitura estrita, isolados de credenciais e redes corporativas sensíveis.

### 8.5 Princípio *Green ≠ Proof*
O sucesso de ferramentas automatizadas fornece apenas evidência localizada e não constitui atestado absoluto de qualidade:
* `BUILD SUCCESSFUL` não comprova ausência de defeitos funcionais.
* `TESTS PASSED` não comprova conformidade integral aos requisitos de negócio.
* `SECURITY SCANNER CLEAN` não comprova invulnerabilidade a ataques complexos ou lógicos.
* A ausência de achados catalogados reflete apenas o limite das verificações realizadas, nunca a perfeição do software.

### 8.6 Persistência de Estado e Retomada de Sessão
A integridade da auditoria independe da persistência de contexto em sessões de chat com LLMs. Todos os marcos operacionais (etapas concluídas, pendências de escopo, arquivos restantes e comandos disparados) são registrados nos artefatos Markdown do diretório `.audit/state/`, permitindo a interrupção e posterior retomada segura do pipeline sem perda de dados.

---

## 9. Normalização Canônica (`audit-normalize`)

### 9.1 Função de Compilador Determinístico
O componente `audit-normalize` atua estritamente como compilador de dados técnicos expressos em Markdown para formato canônico estruturado (`report_data.json`).
* **Invariantes:**
  * Não adiciona novos achados técnicos nem inventa informações inexistentes nos relatórios de origem.
  * Não altera a severidade ou confiança de apontamentos com base em julgamentos próprios.
  * Preserva incertezas técnicas e anotações epistêmicas registradas pelos auditores.

### 9.2 O Pipeline Canônico de Normalização
O processamento do `audit-normalize` obedece rigorosamente a oito estágios sequenciais:

```text
1. Discovery ──► 2. Classification ──► 3. Extraction ──► 4. Normalization ──►
──► 5. Deduplication ──► 6. Conflict Resolution ──► 7. Metrics Recalculation ──► 8. Integrity Validation
```

### 9.3 Rastreamento de Fontes e Snapshot Criptográfico
Cada documento lido pelo normalizador é catalogado com metadados de procedência:
* Atributos: `source_id`, `path`, `filename`, hash criptográfico `sha256` e papel canônico (`source_role`).
* **Papéis Canônicos de Origem:** `AUDIT_LEDGER`, `ANALYTICAL_REPORT`, `INVENTORY`, `THREAT_MODEL`, `COVERAGE_MANIFEST`, `EXTERNAL_REVIEW`, `UNKNOWN`.
* **Identificador de Snapshot (`audit_snapshot_id`):** O conjunto de hashes das fontes compõe uma árvore de verificação determinística que valida a imutabilidade dos artefatos durante todo o processamento de compilação.

### 9.4 Deduplicação e Precedência em Conflitos
Quando dados divergentes sobre a mesma entidade são fornecidos por múltiplas fontes, aplica-se a seguinte ordem de precedência decrescente:
1. `AUDIT_LEDGER` (Posto 1 — Fonte primária de achados estruturados)
2. `ANALYTICAL_REPORT` (Posto 2 — Contextualização analítica)
3. `INVENTORY` / `THREAT_MODEL` / `COVERAGE_MANIFEST` (Posto 3 — Coberturas e escopo)
4. `EXTERNAL_REVIEW` (Posto 4 — Auditorias complementares)
5. `UNKNOWN` (Posto 0 — Origem não qualificada)

> **Resolução de Empates:** Divergências entre fontes de mesmo ranking que não possam ser resolvidas por critério estrito de compatibilidade permanecem formalmente registradas como `UNRESOLVED` no manifesto de conflitos (`validation_report.json`), sendo vetada a escolha arbitrária de valores.

### 9.5 Fusão Não Destrutiva (*Non-Destructive Merge*) e Anomalias
* **Fusão Não Destrutiva:** Se uma fonte reporta uma informação complementar (ex.: trecho de código como evidência) que esteja ausente em outra fonte de maior posto, o dado complementar é incorporado ao registro canônico sem que os dados já consolidados sejam sobrescritos.
* **Conflito vs Anomalia:**
  * *Conflito:* Fontes apresentando representações mutuamente exclusivas para a mesma propriedade de um achado (ex.: severidade `P1` vs `P2`).
  * *Anomalia:* Dados tecnicamente incoerentes no contexto geral do projeto (ex.: configuração de MySQL em sistema que declarou uso exclusivo de PostgreSQL).

### 9.6 Recálculo Estrito de Métricas
O normalizador recalcula autonomamente todas as métricas consolidadas diretamente a partir dos arrays canônicos de dados (`findings[]`, `controls[]`, `inspections[]`). É terminantemente proibido extrair totais ou estatísticas a partir de textos corridos contidos em sumários executivos ou introduções narrativas.

### 9.7 Garantias de Idempotência e Determinismo
O arquivo `report_data.json` deve ser estritamente reprodutível byte a byte para o mesmo conjunto de arquivos de entrada:
* Codificação compulsória em UTF-8 com terminação de linha LF (`\n`).
* Ordenação canônica obrigatória de chaves de dicionários JSON.
* Ordenação determinística de coleções (fontes por `source_id`, achados por `finding.id`, controles por `control.id`).
* O resultado da validação final deve ser explicitamente classificado em: `VALID`, `VALID_WITH_WARNINGS` ou `INVALID`.

---

## 10. Matriz de Decisões Arquiteturais

### 10.1 Decisões Consolidadas e Inegociáveis
A arquitetura do sistema considera congeladas as seguintes diretrizes:
* Adoção de auditores especializados cobrindo verticais semânticas amplas.
* Unificação irrevogável do contrato de saída através do *Audit Output Set* padronizado.
* Posicionamento do `project-audit` como orquestrador, correlacionador e consolidador, e não como reexecutor redundante.
* Função do `project-context` limitada estritamente ao reconhecimento neutro ("o que existe").
* Papel do `audit-normalize` restrito a compilador conservador e determinístico sem heurística diagnóstica.
* Gestão explícita de aplicabilidade (`APPLICABLE`, `NOT_APPLICABLE`, `NOT_DETERMINABLE`).
* Resolução prévia de escopo (`FULL`, `FULL EXCEPT`, `ONLY`) antes do consumo computacional.
* Abordagem incremental ancorada no diff de commits e rastreamento histórico de achados.
* Rigor epistemológico com anotação explícita de Observações, Inferências, Hipóteses e Limitações.
* Isolamento físico e de versionamento do sistema de auditoria através do diretório `.audit/`.
* Classificação de dados do projeto-alvo como não confiáveis e imposição de barreiras de segurança de execução.
* Independência total entre Severidade e Confiança diagnóstica.

### 10.2 Questões em Aberto e Roadmap Futuro
Os seguintes tópicos permanecem como hipóteses funcionais ou arquiteturas a serem detalhadas conforme a maturação do ecossistema:
* Estrutura interna definitiva e ciclo de retenção dos subdiretórios em `.audit/` (`state/`, `runs/`, `cache/`).
* Algoritmo formal de propagação de impacto para auditoria incremental ciente de árvore de dependências (AST e grafos de símbolos).
* Especificação formal do algoritmo de fingerprinting estrutural para identidade temporal de achados além do ID textual.
* Política formal para execução paralela de auditores especializados em ambientes multithreading/multiprocesso.
* Heurística refinada para seleção autônoma de auditores especializados diretamente a partir do perfil do `project-context`.

---

## 11. Sumário de Diretrizes para Agentes Executores

Ao atuar no ecossistema deste sistema de auditoria, qualquer agente deve pautar suas decisões pelas seguintes regras:

1. **Nunca modifique código do projeto-alvo:** Toda a sua inteligência destina-se a analisar, diagnosticar e documentar, mantendo os arquivos funcionais do repositório principal inalterados.
2. **Respeite o contrato de saída único:** Seja trabalhando em auditoria individual ou orquestrada, produza exclusivamente os quatro artefatos canônicos (`00`, `01`, `02`, `03`) em conformidade com o *Audit Output Set*.
3. **Mantenha rigor epistemológico:** Separe claramente o que foi visto do que foi deduzido. Jamais apresente hipóteses como certezas consolidadas sem prova cabal.
4. **Trabalhe sob demanda de escopo:** Resolva a aplicabilidade e escopo antes de carregar volumes extensos de código no contexto cognitivo.
5. **Opere de forma conservadora:** Em caso de dúvida sobre um defeito ou risco, registre `NOT_DETERMINABLE` e documente a limitação técnica que motivou a decisão.
