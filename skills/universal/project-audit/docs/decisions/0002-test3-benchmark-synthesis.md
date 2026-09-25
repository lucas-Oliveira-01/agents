# ADR 0002: Test3 Benchmark Synthesis & Engine V3 Roadmap

## 1. Contexto do Experimento

A bateria de testes `test3` foi executada como um experimento controlado em três fases (`case1_discovery`, `case2_full_no_fix`, `case3_full_autofix`) utilizando exatamente o mesmo snapshot e commit base do `smartserv`.

O objetivo era medir a eficácia da **Engine V2** com a recém-implementada delegação via OmniRoute, e verificar a funcionalidade de auto-fix.

## 2. Resultados da Execução

* **Descoberta Determinística (Sucesso):** O motor identificou perfeitamente 168 arquivos, stack tecnológica, e levantou corretamente as "superfícies de evidência" (ex: 34 pontos de autenticação, 10 potenciais sinks de XSS, 14 manipulações de arquivo).
* **Filtro de Evidência (Sucesso):** O motor agiu corretamente ao NÃO classificar assinaturas isoladas (ex: presença de `fetch` ou classes de JWT) imediatamente como vulnerabilidades.
* **Adjudicação Semântica (Falha Crítica):** 5 das 7 categorias críticas de segurança (Autenticação, Autorização, XSS, SSRF e File Security) terminaram em `SCHEMA_VIOLATION`. 
* **Auto-fix (Não atingido):** Devido à quebra de schema da LLM, nenhum finding crítico foi formalmente confirmado. Logo, o `case3_full_autofix` não despachou correções no código, revelando que a falha bloqueia o ciclo completo.

## 3. Síntese Comparativa (O "Cérebro" vs. A "Plataforma")

| Dimensão | Vencedor | Justificativa |
|---|---|---|
| **Plataforma / Arquitetura** | **Engine V2 (test3)** | Melhor separação de conceitos (Snapshot imutável, Evidências, Recibos, Work Items). Garante governança total. |
| **Raciocínio Semântico** | **GPT-V1** | Melhor compreensão de fluxos de negócio, autorização cruzada (IDOR) e modelagem de ameaças. |
| **Exploração e Discovery** | **Claude v3** | Maior amplitude exploratória (mas gera alto ruído e falsos positivos se não for filtrado). |

**Conclusão Central:**
O gargalo atual do `project-audit` **não é mais a descoberta determinística**; é o **Contrato de Saída Semântica**. O sistema atual confunde uma falha de parsing/tipagem (SCHEMA_VIOLATION) da LLM com a inexistência de vulnerabilidades, mascarando falhas reais no relatório final.

## 4. Decisões Arquiteturais para a Engine V3

Para transformar a excelente plataforma da V2 em um auditor plenamente funcional:

1. **Gate de Validação Tolerante a Falhas:**
   - Erros no contrato JSON do worker delegado (`SCHEMA_VIOLATION`) **nunca** devem ser convertidos em "0 findings". Eles devem gerar o estado explícito `SEMANTIC_COVERAGE_FAILED` ou `AUDIT_INCOMPLETE`.
2. **Correção do Contrato OmniRoute:**
   - Ajustar o prompt sistêmico no `semantic_auditor.py` e o parser para aceitar respostas semânticas puras ou listas flexíveis, garantindo que a LLM se alinhe ao schema Pydantic.
3. **Pipeline do Auto-fix:**
   - O auto-fix exigirá um plano de execução isolado, com diffs e verificações pós-fix ("Before/After Ledger").
4. **Refinamento de Determinismos (SSRF vs Fetch):**
   - Corrigir heurísticas determinísticas, como diferenciar `fetch()` no navegador (Client-side) de requisições de backend (Server-side SSRF).
