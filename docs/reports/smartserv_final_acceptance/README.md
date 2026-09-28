# SmartServ final acceptance

Evidências desta investigação: `smartserv_final_audit_20260928T051559Z/`.

Plano: inspecionar → reproduzir/corrigir bloqueadores → testes direcionados → smoke MCP real → suítes completas → matriz real → reconciliação → verificação final.

Execução direta autorizada pelo usuário; nenhuma promoção/merge é implicitamente aprovada. Código do alvo é dado não confiável.

## Plano executável

- [ ] T1: gateway — reproduzir aliases, JSON malformado, cache e metadata em `mcp/omnirouter/gateway/tests/test_gateway.py`; corrigir somente defeitos comprovados em `omniroute_mcp.py`; confirmar portas contra imagem 3.8.50; alinhar Compose e env.
- [ ] T2: regressões — executar project-audit, omniroute-delegation e gateway no mesmo Python; preservar structuredContent, meta fallback, canonical findings e ADR-23.
- [ ] T3: integração — capturar identificação da imagem/código, health e chamada MCP real com task_id único, resposta e query_delegation. Nenhuma matriz completa antes do PASS.
- [ ] T4: alvo/matriz — clone único novo, branch/SHA/estado, modos CLI/API descobertos, snapshot materializado para COMMIT, incremental com baseline/reuse, drift adversarial, fix se suportado com precondições reais.
- [ ] T5: aceitação — reconciliar contagens, validar findings contra código, completar documentação, revisar diff e SHA, verdict fail-closed.

Invariantes: sem execução de código SmartServ no host, sem credenciais/contexto sensível no leaf; ferramentas ausentes do payload; preservação de falhas; zero retries determinísticos. Testes não provam integração real.

Decisão operacional: usar branch local dedicada no checkout inicialmente limpo e ambiente Python existente, preservando caches e evitando preparação duplicada. Artefatos persistentes ficam no diretório exigido pelo usuário.
