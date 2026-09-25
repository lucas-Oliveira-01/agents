# Diretriz de Auditoria Absoluta: Astra Mode

## 1. Contexto e Alvo
**Alvo da Auditoria:** `/home/oliveira/Projects/SKILLS/skills/universal/project-audit` (Exclusivamente a skill project-audit).
**Agente Executante:** Astra (Modo de varredura profunda e exaustiva).
**Objetivo Primário:** Encontrar todo e qualquer erro, bug lógico, falha de infraestrutura, código quebradiço e propensão a falsos positivos dentro do próprio motor de auditoria.

## 2. Instruções de Execução (Strict Rules)
Você deve varrer o código-fonte da skill `project-audit` arquivo por arquivo (focando no diretório `src/project_audit/` e subarquivos). 

Para CADA problema encontrado, você DEVE fornecer:
1. **Nome do Problema / Tipo (Bug, Architecture Flaw, Logic Gap)**
2. **O Porquê:** Explicação detalhada de por que isso quebra o código ou gera resultados ruins (ex: falsos positivos no LLM, quebras de async/await, schemas JSON não correspondentes).
3. **Evidência Irrefutável:** Trecho exato do código que causa o erro (file path + source code).
4. **Inventário Completo:** Não invente falhas. Se a lógica estiver sólida, passe para a próxima. Apenas documente o que puder ser matematicamente ou logicamente provado pelo código atual.

## 3. Vetores de Inspeção Obrigatórios
- **Orquestração Assíncrona e Blocking Calls:** O auto-fix usa `asyncio.run(dispatch_opencode_worker(...))` em um loop síncrono. Isso trava a thread? Os workers sobrevivem se o orquestrador morre?
- **Despache Semântico e Modelos de Schema:** A comunicação do `semantic_auditor.py` com o `omniroute_backend.py` está blindada contra falhas de tipagem?
- **Falsos Positivos e Gaps de Regra:** O parser `_parse_candidate` rejeita dados válidos? O construtor de contexto (`context_builder.py`) fornece evidências insuficientes para a LLM, causando a cegueira de IDOR documentada na V2?
- **Hardcodings e Typo Traps:** Existência de atributos chamados incorretamente (como vimos com `security.reviews` vs `security.semantic_reviews`).

## 4. Output e Persistência
Ao concluir a varredura, você deve:
1. Gravar um relatório detalhado e estruturado em `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/docs/audit_results/astra_self_audit.md`.
2. Registrar um sumário dos defeitos estruturais críticos na base global do `ai-memory` (usando `ai-memory write-page` ou correspondente).
3. Aguardar a análise humana antes de aplicar qualquer correção (`Auto-fix = OFF` para esta fase).
