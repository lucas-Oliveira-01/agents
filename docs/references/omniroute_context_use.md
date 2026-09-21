# CONTEXTO DE TRANSFERÊNCIA — OMNIROUTE + AGENTES + AUDITORIA

## 1. OBJETIVO DESTE CHAT

Estou desenvolvendo uma arquitetura pessoal de agentes/skills para desenvolvimento de software, auditoria técnica e gerenciamento persistente de contexto.

Um dos objetivos centrais é maximizar:

```text
QUALIDADE
+
RELIABILIDADE
+
TRACEABILITY
----------------
com o menor custo possível de tokens/créditos
```

Quero investigar como usar o **OmniRoute** como uma infraestrutura local de roteamento e offloading de LLMs.

Não quero simplesmente "usar modelos menores".

Quero descobrir:

> Como executar cada tarefa com o mecanismo/modelo mais barato que consiga manter a qualidade exigida?

Quero explorar profundamente os limites técnicos do OmniRoute antes de definir a arquitetura final.

---

# 2. CONTEXTO DO USUÁRIO

Sou estudante de Engenharia de Software e escrevo meu próprio código.

Não quero que IA gere ou modifique código por mim por causa das regras acadêmicas da minha faculdade.

Uso IA principalmente para:

```text
análise
revisão
auditoria
explicação
documentação
planejamento
pesquisa
diagnóstico
```

Portanto, o objetivo desta infraestrutura não é criar um agente que programe autonomamente tudo.

É criar uma infraestrutura de apoio, análise e delegação controlada.

---

# 3. PROTÓTIPO ATUAL DO OMNIROUTE

Já construí um protótipo local de integração entre um agente Antigravity e o OmniRoute via MCP.

Arquitetura atual:

```text
Antigravity
    ↓
MCP
    ↓
Python wrapper
    ↓
HTTP
    ↓
localhost:20128
    ↓
OmniRoute
```

O protótipo possui:

```text
omniroute_mcp.py
```

que cria um servidor MCP e expõe:

```python
delegar_tarefa(
    prompt: str,
    modelo_ou_rota: str = "auto/coding"
) -> str
```

O wrapper atualmente:

1. lê `OMNIROUTE_API_KEY`;
2. faz POST para:

```text
http://localhost:20128/v1/chat/completions
```

3. utiliza payload OpenAI-compatible:

```json
{
  "model": "auto/coding",
  "messages": [
    {
      "role": "user",
      "content": "..."
    }
  ]
}
```

4. retorna:

```text
choices[0].message.content
```

5. trata erros HTTP/rede de forma simples.

Dependências atuais do protótipo:

```text
Python >= 3.10
mcp
requests
```

### Problema conhecido

A API key chegou a ficar hardcoded no `mcp_config.json`.

Isso é apenas estado do protótipo e deve ser corrigido antes de qualquer versão séria.

---

# 4. O QUE O PROTÓTIPO QUER RESOLVER

O modelo principal do agente é relativamente caro/capaz.

Grande parte das tarefas, porém, não precisa dessa capacidade.

Exemplos de tarefas potencialmente delegáveis:

```text
tradução
sumarização
parsing
extração
classificação
triagem
formatação
normalização
preparação de contexto
análise simples
categorização de arquivos
transformações mecânicas
```

A ideia é:

```text
modelo principal
      ↓
decide se vale delegar
      ↓
OmniRoute
      ↓
modelo adequado
```

O modelo principal continua responsável pelo raciocínio complexo.

---

# 5. ARQUITETURA DE AUDITORIA QUE ESTOU DESENVOLVENDO

Existe uma arquitetura modular de auditoria:

```text
project-audit
code-audit
security-audit
database-audit
test-audit
git-audit
documentation-audit
...
```

Os auditores seguem o mesmo contrato de saída.

Depois:

```text
audit-normalize
       ↓
report_data.json
       ├── report-publish
       └── issue-forge
```

O `audit-normalize` é deliberadamente determinístico/conservador.

Ele não deve virar um segundo auditor LLM.

---

# 6. PROBLEMA DE CUSTO DA AUDITORIA

Uma auditoria completa pode consumir muitos tokens.

Quero que o `project-audit` seja adaptativo.

### Applicability

Primeiro descobrir o que faz sentido para o projeto.

Exemplo:

```text
Java
CLI
sem banco
sem frontend
sem HTTP
JUnit
Maven
Git
```

Não faz sentido executar:

```text
database-audit
frontend-audit
web-specific checks
```

apenas porque são módulos existentes.

### User scope

Também quero permitir:

```text
FULL
FULL EXCEPT X
ONLY X,Y,Z
```

Exemplo:

```text
"Faça uma auditoria completa exceto arquitetura e banco."
```

O PA deverá rodar apenas os módulos aplicáveis restantes.

---

# 7. AUDITORIA INCREMENTAL

Cada auditoria possui um target Git commit.

Exemplo:

```text
Audit A
commit = abc123
```

Depois:

```text
abc123 → def456
```

Quero descobrir automaticamente:

```text
o que mudou?
quais superfícies foram afetadas?
quais findings podem ser reutilizados?
quais precisam ser revalidados?
quais precisam de nova auditoria?
```

Estados conceituais:

```text
REUSE
REVALIDATE
RUN / REAUDIT
INVALIDATE
```

Não quero considerar um finding resolvido simplesmente porque o arquivo mudou.

Idealmente:

```text
Git diff
   ↓
file impact
   ↓
symbol impact
   ↓
dependency impact
   ↓
finding impact
```

Exemplo:

```text
SEC-001
↓
AuthService#validateToken()
```

Se outra função do mesmo arquivo mudou, isso não implica automaticamente que SEC-001 foi afetado.

---

# 8. HISTÓRICO DOS FINDINGS

Quero manter continuidade entre auditorias.

Exemplo:

```text
Audit A

SEC-001
SEC-002
SEC-003
```

Depois:

```text
Audit B
```

O sistema deveria conseguir determinar:

```text
SEC-001 → RESOLVED
SEC-002 → PERSISTS
SEC-003 → MODIFIED
```

mas somente quando houver evidência suficiente.

Nunca transformar ausência atual em "resolvido" sem verificar.

---

# 9. `.audit/` COMO REPOSITÓRIO INDEPENDENTE

Não quero nenhum artefato produzido pela IA entrando no Git do projeto acadêmico.

O projeto deverá ignorar:

```gitignore
.audit/
```

E `.audit/` terá seu próprio Git:

```text
project/
├── src/
├── .git/
├── .gitignore
└── .audit/
    └── .git/
```

Assim:

```text
project.git
      ≠
audit.git
```

O `.audit/` poderá armazenar:

```text
histórico
cache
contexto
runs
resultados
proveniência
metadados
delegações
relatórios
```

Mas secrets não devem ser versionados nem mesmo no audit repository.

A independência do Git é importante porque permite ao sistema manter memória operacional sem contaminar o projeto acadêmico.

---

# 10. POSSÍVEL ESTRUTURA DE `.audit/`

Ainda não está congelada.

Uma hipótese:

```text
.audit/
├── .git/
├── state/
├── runs/
├── cache/
├── reports/
```

Podem existir conceitos adicionais:

```text
context
history
provenance
delegation
```

mas não quero overengineering prematuro.

---

# 11. HIPÓTESE ARQUITETURAL SOBRE OMNIROUTE

A análise especializada que fizemos indica que o OmniRoute pode ser muito mais do que um simples proxy.

A documentação pesquisada aponta capacidades como:

```text
routing
model selection
provider selection
Auto-Combo
fallback
retry
health
quota
rate limiting
load balancing
circuit breakers
cache
prompt-cache affinity
session affinity
streaming
observability
budgets
MCP
A2A
```

Também foram mencionadas estratégias como:

```text
auto
auto/coding
auto/fast
auto/cheap
auto/offline
auto/smart
cost-optimized
context-optimized
cache-optimized
p2c
fusion
pipeline
```

IMPORTANTE:

Essas capacidades foram obtidas em pesquisa anterior sobre o projeto OmniRoute e devem ser tratadas como **hipóteses/fatos externos provisórios até serem verificadas contra a versão real do OmniRoute instalado localmente**.

Não assumir que minha instalação possui exatamente a versão ou os recursos citados.

---

# 12. DESCOBERTA IMPORTANTE DA PESQUISA ANTERIOR

A análise especializada indicou que:

```text
auto/coding
```

não é simplesmente:

```text
"usar modelo X"
```

mas uma política de seleção.

O OmniRoute aparentemente considera múltiplos sinais para Auto-Combo, incluindo coisas relacionadas a:

```text
cost
latency
quota
health
task fit
quality
reliability
context affinity
cache affinity
session availability
```

Portanto não quero criar prematuramente um router próprio do tipo:

```text
coding → model A
security → model B
translation → model C
```

Prefiro investigar se o desenho correto é:

```text
task
↓
policy
↓
OmniRoute
↓
concrete model/provider
```

---

# 13. NOVO MODELO MENTAL DE TASK ROUTER

O Task Router do meu sistema não deveria necessariamente decidir:

```text
qual modelo usar?
```

Ele deveria decidir:

```text
qual política de execução usar?
```

Exemplo:

```text
translation
→ cheap

simple extraction
→ fast

coding
→ coding

large-context analysis
→ context-optimized

critical reasoning
→ quality-first
```

Depois:

```text
policy
↓
OmniRoute
↓
modelo concreto
```

Assim o meu sistema fica desacoplado dos providers/modelos atuais.

---

# 14. O QUE DEVE FICAR FORA DO OMNIROUTE

Minha arquitetura pretende deixar no meu próprio sistema:

```text
audit applicability
audit planning
project profile
dependency graph
git impact analysis
progressive disclosure
finding identity
finding lifecycle
REUSE / REVALIDATE / RUN
audit completeness
semantic validation
quality gates
global audit budget
cross-audit correlation
project-specific provenance
trust boundaries
```

Essas coisas dependem do domínio do meu sistema.

---

# 15. O QUE OMNIROUTE DEVE ASSUMIR

Idealmente o OmniRoute continua responsável por coisas de infraestrutura:

```text
model/provider selection
routing
fallback
provider health
retry
circuit breaker
quota
rate limiting
load balancing
prompt-cache affinity
transport
telemetry
provider-specific execution
```

Não quero duplicar essas funções no meu wrapper.

---

# 16. O WRAPPER MCP

Hoje ele é apenas:

```text
MCP
↓
HTTP request
↓
texto
```

No futuro poderia virar uma camada fina chamada conceitualmente:

```text
Delegation Gateway
```

Ela poderia controlar:

```text
capability restrictions
task policy
deterministic cache
global budget
provenance
validation
structured result
```

Mas NÃO deveria recriar:

```text
retry
provider health
fallback
load balancing
circuit breaker
provider routing
```

porque isso duplicaria OmniRoute.

---

# 17. MCP COMO CAPABILITY FIREWALL

Não quero dar ao agente acesso indiscriminado ao MCP administrativo completo do OmniRoute.

Idealmente o agente teria algo próximo de:

```text
delegate_task(...)
```

e talvez:

```text
inspect_route(...)
get_usage(...)
```

somente se necessário.

Não quero que o agente possa arbitrariamente:

```text
alterar providers
alterar routing
mudar budgets
limpar cache
alterar resilience
```

sem uma razão explícita.

A camada MCP deve funcionar como uma capability boundary.

---

# 18. NÃO QUERO DELEGAÇÃO RECURSIVA

O desenho desejado é:

```text
main agent
    ↓
OmniRoute
    ↓
leaf model
```

e não:

```text
main agent
    ↓
model A
    ↓
OmniRoute
    ↓
model B
    ↓
OmniRoute
    ↓
...
```

Não assumir que o OmniRoute consegue garantir isso sozinho.

A capability de delegação deve ser controlada pelo agente/wrapper.

---

# 19. MODELOS FRACOS SEM PERDER QUALIDADE

Quero explorar:

```text
cheap model
        ↓
triage / simple task
        ↓
quality gate
        ↓
accept
ou
escalate
```

Modelo forte deve ser reservado para:

```text
complex reasoning
security
authorization
business logic
cross-module analysis
ambiguous cases
critical findings
conflicts
```

A qualidade final não deve depender de confiar cegamente no modelo barato.

---

# 20. POSSÍVEL ESCALATION

Arquitetura conceitual:

```text
TASK
 ↓
cheap model
 ↓
validation
 ├── PASS → RESULT
 └── FAIL/UNCERTAIN → strong model
```

O modelo barato não deve simplesmente decidir sozinho se sua própria resposta é suficiente.

O sistema deve possuir critérios de validação objetivos sempre que possível.

Exemplos:

```text
schema
required fields
provenance
deterministic checks
contradictions
format
evidence references
```

---

# 21. CACHE

Quero distinguir dois tipos:

### Cache de infraestrutura

Pode existir dentro do OmniRoute:

```text
semantic cache
prompt cache
cache affinity
```

Isso é otimização de execução.

### Cache do meu sistema

Deve servir para:

```text
reprodutibilidade
histórico
auditoria incremental
reuse
```

Uma possível chave:

```text
task
+
normalized input
+
context hash
+
prompt version
+
tool version
+
policy version
+
output contract
```

→ SHA-256

O cache do meu sistema não deve depender cegamente do semantic cache do OmniRoute.

---

# 22. CACHE DE DELEGAÇÃO

Exemplo:

```text
"Extraia todos os endpoints deste controller."
```

Se:

```text
arquivo não mudou
+
contexto não mudou
+
prompt não mudou
+
ferramenta não mudou
+
policy não mudou
```

poderíamos ter:

```text
CACHE HIT
```

sem chamar outro LLM.

Quero investigar se o OmniRoute já oferece mecanismos que podem ajudar e qual parte deve ser implementada externamente.

---

# 23. PROVENANCE

Quero registrar internamente algo próximo de:

```text
task_id
project_id
audit_run_id
task_type
policy_id
input_hash
context_hash
prompt_version
tool_version
resolved_model
resolved_provider
route
omniroute_version
latency_ms
tokens_in
tokens_out
cost
fallback_attempts
cache_hit
output_hash
validation_result
```

O OmniRoute pode fornecer parte disso.

Meu sistema deve acrescentar:

```text
por que a tarefa existiu
qual auditor
qual finding
qual política
qual run
qual versão da skill
```

---

# 24. OBSERVABILIDADE

Quero medir:

```text
tasks
model selected
provider
latency
tokens
cost
errors
fallbacks
cache hit rate
cache miss rate
quality signals
```

Idealmente por:

```text
project
run
skill
task
model
route
```

Quero separar:

```text
telemetry de infraestrutura
```

de:

```text
telemetry semântica do meu sistema
```

---

# 25. BUDGET

Quero potencialmente ter:

```text
global audit budget
run budget
task budget
request budget
```

Minha camada deveria controlar:

```text
budget global
```

Enquanto OmniRoute controla:

```text
budget específico da request
provider quota
routing economics
```

Exemplo:

```text
audit budget = X
```

↓

```text
task budget = Y
```

↓

```text
OmniRoute request budget = Z
```

Nunca quero degradar silenciosamente uma auditoria por falta de orçamento.

Estados explícitos são preferíveis:

```text
COMPLETE
PARTIAL
INCOMPLETE
FAILED
BLOCKED
```

---

# 26. PROGRESSIVE DISCLOSURE

Outro mecanismo que quero investigar no meu sistema:

```text
level 0
project profile

level 1
relevant files

level 2
relevant symbols

level 3
surrounding code

level 4
dependency chain

level 5
full source
```

A intenção é nunca enviar todo o projeto ao modelo sem necessidade.

O OmniRoute provavelmente não deve ser responsável por isso.

O Orchestrator seleciona o contexto.

OmniRoute executa a chamada.

---

# 27. SCRIPT + LLM

Princípio central:

```text
script → deterministic evidence
LLM → interpretation
```

Exemplos de tarefas determinísticas:

```text
SHA-256
git diff
file inventory
AST extraction
dependency graph
test execution
schema validation
JSON validation
```

Exemplos de tarefas cognitivas:

```text
security reasoning
architecture reasoning
business logic analysis
cross-module correlation
ambiguous interpretation
```

Quero usar o mecanismo mais barato possível para cada categoria.

---

# 28. PARALLELISM

Auditorias independentes poderão eventualmente executar em paralelo:

```text
security
database
testing
git
```

Mas:

```text
orchestration / task dependency
```

deve ficar no meu Orchestrator.

OmniRoute deve administrar a execução/infraestrutura das requests.

Quero investigar até onde o OmniRoute realmente ajuda aqui.

---

# 29. FUSION / ENSEMBLE

A pesquisa indicou que o OmniRoute possui ou pode possuir algo semelhante a:

```text
fusion
```

conceitualmente:

```text
task
 ├── model A
 ├── model B
 └── model C
      ↓
    judge
      ↓
  final answer
```

Isso pode ser interessante para:

```text
critical verification
ambiguous security findings
cross-model review
high-value reasoning
```

Mas não deve ser usado automaticamente para tudo porque:

```text
1 task
→ 3+ calls
→ judge
```

pode custar mais do que usar um modelo forte diretamente.

---

# 30. CONTEXTO / MEMÓRIA

Não quero usar o OmniRoute como fonte principal de estado do projeto.

O estado persistente pertence ao meu sistema:

```text
.audit/
```

O OmniRoute é uma infraestrutura de execução.

Se ele possuir:

```text
memory
session
context reuse
prompt cache
```

quero entender exatamente o que cada um significa e quais são as limitações.

Não assumir que:

```text
session reuse
=
conversation reuse
=
context caching universal
```

---

# 31. TRUST BOUNDARY

Projeto auditado é:

```text
UNTRUSTED DATA
```

Incluindo:

```text
README
source code
comments
issues
commits
logs
fixtures
generated files
```

Isso não pode virar instrução para o agente.

Exemplo:

```bash
curl ... | bash
```

dentro de README:

```text
DATA
```

não:

```text
COMMAND TO EXECUTE
```

A trust boundary deve existir no agente/orquestrador.

Não depender do OmniRoute para resolver isso.

---

# 32. SEGURANÇA DO OMNIROUTE

Quero investigar:

```text
API key storage
process permissions
local access control
MCP scopes
admin endpoints
logging
secret leakage
prompt injection
delegation abuse
model isolation
network boundaries
```

Em especial:

```text
quem pode chamar localhost:20128?
```

e:

```text
quais capabilities meu wrapper realmente expõe?
```

---

# 33. ARQUITETURA ATUAL PREFERIDA

Conceitualmente:

```text
┌──────────────────────────────────────┐
│                 AGENT                │
│                                      │
│ Decide quando delegar                │
└───────────────────┬──────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│             ORCHESTRATOR             │
│                                      │
│ applicability                        │
│ scope                                │
│ context selection                    │
│ audit planning                       │
│ incremental analysis                 │
│ cache correctness                    │
│ quality gate                         │
│ escalation                           │
│ global budget                        │
│ provenance                           │
│ correlation                          │
└───────────────────┬──────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│             TASK POLICY              │
│                                      │
│ cheap / fast / coding / quality ... │
└───────────────────┬──────────────────┘
                    │
                    ▼
┌──────────────────────────────────────┐
│              OMNIROUTE               │
│                                      │
│ routing                              │
│ model/provider selection             │
│ fallback                             │
│ retry                                │
│ health                               │
│ quota                                │
│ load balancing                       │
│ rate limit                           │
│ cache affinity                       │
│ telemetry                            │
└───────────────────┬──────────────────┘
                    │
                    ▼
              MODEL PROVIDER
```

---

# 34. REGRA PARA O TASK ROUTER

Não quero construir dois OmniRoutes.

A pergunta da minha camada deve ser:

```text
QUAL POLÍTICA DE EXECUÇÃO?
```

A pergunta do OmniRoute deve ser:

```text
QUAL CANDIDATO CONCRETO E COMO EXECUTAR?
```

Se as duas camadas começarem a decidir a mesma coisa, revisar a arquitetura.

---

# 35. PRINCÍPIO DE EFICIÊNCIA

A regra desejada para todo o ecossistema:

> Use o mecanismo mais barato capaz de produzir evidência suficiente para aquela decisão.

Hierarquia ideal:

```text
deterministic tool
        ↓
cheap model
        ↓
medium model
        ↓
strong model
        ↓
ensemble / verification
```

Não usar modelo forte quando uma operação determinística resolve o problema.

Não usar modelo barato quando a tarefa exige raciocínio de alto risco.

---

# 36. O QUE QUERO INVESTIGAR AGORA

Quero que você continue a partir deste contexto e seja um **especialista crítico em OmniRoute**, não apenas um assistente que concorda comigo.

Primeiro:

1. Determine exatamente qual versão do OmniRoute está instalada.
2. Compare a versão real com a documentação atual.
3. Diferencie:

   * capacidade realmente presente;
   * capacidade documentada;
   * capacidade experimental;
   * capacidade ausente;
   * capacidade que exige wrapper externo.
4. Verifique as possibilidades reais de:

   * Auto-Combo;
   * routing;
   * cost optimization;
   * latency optimization;
   * quality signals;
   * fallback;
   * retries;
   * cache;
   * prompt-cache affinity;
   * context handling;
   * session;
   * fusion;
   * pipelines;
   * concurrency;
   * MCP;
   * observability;
   * budgets.
5. Identifique funcionalidades que eu ainda não considerei.
6. Identifique ideias minhas que seriam desnecessárias porque o OmniRoute já resolve.
7. Identifique ideias que o OmniRoute não deveria assumir.
8. Identifique pontos em que um wrapper externo é realmente necessário.
9. Investigue limites, trade-offs e riscos.
10. Considere custo, qualidade, latência e confiabilidade simultaneamente.

---

# 37. NÃO IMPLEMENTE A ARQUITETURA AINDA

Neste estágio quero:

```text
pesquisa
crítica
arquitetura
limites
trade-offs
validação de hipóteses
```

Não comece criando dezenas de arquivos ou skills.

Primeiro determine a arquitetura correta.

Depois poderemos especificar:

```text
delegation-mcp
task policies
cache
provenance
orchestrator
OmniRoute configuration
```

---

# 38. NÃO ASSUMA QUE MINHAS IDEIAS ESTÃO CORRETAS

Você deve dizer explicitamente quando uma ideia:

```text
faz sentido
```

quando:

```text
é parcialmente correta
```

quando:

```text
já existe no OmniRoute
```

quando:

```text
deve ficar no orchestrator
```

quando:

```text
deve ficar no wrapper
```

quando:

```text
deve ficar no OmniRoute
```

e quando:

```text
não vale a complexidade.
```

Quero maximizar:

```text
quality / cost
```

e não maximizar número de componentes.

---

# 39. RESULTADO QUE QUERO OBTER

Ao final da investigação, quero chegar a algo próximo de:

```text
AGENT
  ↓
ORCHESTRATOR
  ↓
TASK POLICY
  ↓
OMNIROUTE
  ↓
MODEL PROVIDER
```

com responsabilidades claramente separadas.

Quero saber:

```text
who decides?
who routes?
who caches?
who validates?
who measures?
who retries?
who escalates?
who enforces budgets?
who stores provenance?
who manages context?
who controls permissions?
who owns audit history?
```

E, principalmente:

> Qual é a arquitetura mínima que consegue extrair o máximo de eficiência do OmniRoute sem duplicar suas funções e sem sacrificar a qualidade das decisões?

---

# 40. CRITÉRIO FINAL

Não otimize simplesmente para:

```text
menos tokens
```

Otimize para:

```text
menor custo total
+
menor contexto redundante
+
menor raciocínio redundante
+
maior reutilização
+
maior qualidade
+
maior rastreabilidade
+
maior confiabilidade
```

A meta final é:

```text
MAXIMUM QUALITY
+
MINIMUM COST
+
HIGH RELIABILITY
+
FULL TRACEABILITY
```

mantendo a arquitetura simples o suficiente para ser realmente mantida.

