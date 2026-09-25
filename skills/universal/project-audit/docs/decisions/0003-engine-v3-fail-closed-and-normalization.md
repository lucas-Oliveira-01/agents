# ADR 0003: Engine V3 - Fail-Closed Orchestration e Contrato Semântico Explícito

## 1. Contexto
Após o diagnóstico do benchmark `test3` (ADR 0002), o plano de ação para a Engine V3 foi refinado para garantir que a resiliência do parser não se transforme em permissividade perigosa, e que o auditor jamais emita um "falso limpo".

## 2. Decisões Arquiteturais (Invariantes da V3)

### 2.1 Orquestração Fail-Closed (Tolerância Zero a Falsos Limpos)
* **Problema:** Um `SCHEMA_VIOLATION` ou `TIMEOUT` na LLM resultava em 0 findings.
* **Decisão:** Falhas na camada semântica devem transitar o status da auditoria para `SEMANTIC_COVERAGE_FAILED` e o status geral para `INCOMPLETE`.
* **Exit Codes:** O CLI deve retornar códigos de erro específicos (ex: `4` para falha de cobertura semântica), bloqueando pipelines de CI/CD.

### 2.2 Normalização Semântica Explícita (Provenance)
* **Problema:** Coagir valores (ex: `CRITICAL` -> `P0`) silenciosamente destrói a trilha de auditoria.
* **Decisão:** O parser aceitará pequenas variações de shape (ex: array direto vs envelopado em `{"findings": []}`), mas a normalização de campos será registrada explicitamente no Ledger.
* **Exemplo de Provenance:**
  ```json
  {
    "severity": "P0",
    "raw_severity": "CRITICAL",
    "normalization": {"applied": true, "rule": "severity_alias"}
  }
  ```
* **Rejeição Estrita:** Formatos bizarros ou severidades desconhecidas (ex: `VERY_BAD`) resultarão em `VALIDATION_ERROR`, ativando o Fail-Closed.

### 2.3 Applicability Tri-State
* **Problema:** Tratar `NOT_DETERMINABLE` automaticamente como `APPLICABLE = false` oculta lacunas de análise.
* **Decisão:** A matriz de aplicabilidade passa a ser: `APPLICABLE`, `NOT_APPLICABLE`, e `UNKNOWN`. 
* Um domínio `UNKNOWN` sem evidências pode pular o gasto de tokens (DEFERRED), mas mantém a cobertura como `UNKNOWN` no relatório final.

### 2.4 Precisão Determinística baseada em Contexto de Execução
* **Problema:** A heurística baseada em caminhos (ex: ignorar `frontend/` para SSRF) é frágil.
* **Decisão:** A classificação de SSRF e similares exigirá a validação do *Execution Context* (ex: `Java + RestTemplate` = Server-side, `Browser JS + fetch` = Client-side), independentemente da pasta do arquivo.

### 2.5 Auto-Fix Desacoplado e Imutável
* **Problema:** O Auto-fix no meio da varredura polui o snapshot e impede a reprodutibilidade.
* **Decisão:** O comando de varredura (`project-audit --phase full`) será estritamente read-only.
* O Auto-fix será um comando separado (`project-audit fix <run_id>`) que:
  1. Cria um novo snapshot (Snapshot B).
  2. Aplica o patch sugerido para um finding confirmado.
  3. Re-audita o delta.
  4. Valida a ausência da vulnerabilidade (Before/After Ledger).

## 3. Ordem de Implementação

1. **Replay Harness (Passo 0):** Congelar os failures de JSON do `test3` em um suite de testes para validar o parser e o Fail-Closed.
2. **Parser & Normalizer:** Implementar a extração resiliente com registro de provenance.
3. **Fail-closed Orchestration:** Impedir `0 findings` sem cobertura semântica.
4. **Applicability Tri-State:** Introduzir os estados `TRUE/FALSE/UNKNOWN`.
5. **Contextos Determinísticos:** Refinar matchers (SSRF, XSS).
6. **Auto-fix (Fase Final):** Implementar o CLI isolado para patching e verificação.
