# ADR 0001: V3 Semantic Adjudication Architecture

## Status
Aceito

## Contexto
O motor \`project-audit\` (Engine V2) atingiu maturidade arquitetural e operacional excepcional: implementou com sucesso um pipeline limpo baseado em \`TargetSnapshot\`, \`Inventory\`, \`AuditPlan\`, \`WorkItem\`, \`Evidence\`, e \`ExecutionReceipt\`. Ele não promove observações determinísticas automaticamente para vulnerabilidades, reduzindo achismos infundados de análise puramente estática.

Entretanto, as execuções de testes comparativos detalhados revelaram que o **Semantic Adjudicator** da Engine V2 atua abaixo da capacidade dos testes ad-hoc realizados com o modelo puro (GPT-v1). A análise semântica V2 demonstrou:
1. **Falsos Positivos em Sinks Seguros:** O modelo marcou como \`VULNERABILITY / CONFIRMED\` instâncias de \`textContent\` e \`confirm()\`, extrapolando erroneamente que alterações futuras constituíam vulnerabilidades atuais.
2. **Cegueira para IDOR e Fluxos de Negócio:** A Engine V2 atomizou os Work Items em escopos muito restritos (fragmentação method-by-method), privando a LLM da visão holística do fluxo (\`Role\` -> \`Endpoint\` -> \`Service\` -> \`Domain\`). Consequentemente, não encontrou falhas de autorização de negócios (IDORs) mapeadas por abordagens anteriores.
3. **Overfitting para XSS:** Praticamente 100% dos findings semânticos reportados foram derivados de XSS em frontend, ignorando completamente problemas sistêmicos provados anteriormente (CORS wildcard, concorrência, ausência de \`JdbcTransactionManager\`).

## Decisão
A arquitetura do \`project-audit\` evoluirá para a **V3 (Semantic Adjudication and Flow Analysis)**, combinando a robustez orquestral da V2 com as heurísticas semânticas avançadas que operavam no GPT-v1.

O novo pipeline formalizado deve ser:

1. **Engine V2 Deterministic (Surface Map):** Mapeamento do inventário e superfícies suspeitas.
2. **Semantic Reviewer (Business Flow):** A LLM receberá recortes expandidos que contenham a teia de invocação (Model + Controller + Service) e será instruída a verificar **Regras de Negócio e Autorização**, e não apenas injeções superficiais de sintaxe.
3. **Finding Validator / False-Positive Gate (NOVO):** Um novo módulo no pipeline que submete os Findings potenciais a uma segunda passagem destrutiva. O Gate receberá instruções explícitas para abater hipóteses futuras (ex: "é \`textContent\` agora, logo descarta a suspeita de XSS") e reclassificar severidades superdimensionadas.
4. **Evidence & Provenance:** Persistência determinística orquestrada e assinatura do relatório final.

## Consequências
* **Positivas:** Redução massiva de falsos positivos da camada semântica. Restauração da capacidade da engine de identificar IDORs e bypasses de permissão.
* **Negativas / Riscos:** Maior gasto de tokens (pois exige avaliação de fluxos inteiros e uma etapa adicional de validação - o Gate). Maior complexidade na montagem do Contexto (ContextBuilder precisará inferir a árvore de dependência para mandar recortes de fluxo coerentes).

## Anotações Adicionais
- Quantidade de Findings **não** deve ser contabilizada como indicador primário de qualidade do auditor. A métrica ouro passa a ser a densidade de \`True Positives\` em fluxos sistêmicos.
- Os modelos de subagente delegados pelo \`omniroute\` precisarão de schemas enriquecidos para classificar a validade das mitigações locais, retroalimentando o False-Positive Gate.
