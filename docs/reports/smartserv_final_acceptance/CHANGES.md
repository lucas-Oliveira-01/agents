# Correções

## Gateway (candidate ainda não commitado)

- Alias `delegar_tarefa` usava `profile` inexistente; corrigido para `perfil`.
- `invalidate_cache` usava `limpar_expirados` inexistente; corrigido para `clear_expired`.
- Aliases eram registrados depois de `mcp.run()`; entrada do servidor movida ao final.
- JSON válido com raiz não objeto causava AttributeError; agora gera INVALID_UPSTREAM_RESPONSE e telemetria terminal.
- `usage` não objeto causava AttributeError; agora degrada somente telemetria opcional.
- CACHE_KEY_CONFLICT deixava registro running; agora persiste estado error e finished_at.
- Respostas truncadas/filtradas/desconhecidas eram cacheadas como resultados reutilizáveis; cache determinístico agora exige finish_reason=stop.
- Compose usa API_HOST=0.0.0.0 dentro do container e gateway usa API_PORT interpolado (20129 padrão); host continua 127.0.0.1. `.env.example` alinhado.

Prova: tests/gateway_red — 14 failed, 19 passed; tests/gateway_green — 33 passed. Logs em diretório de execução.

## Porta: hipótese histórica refinada

Imagem 3.8.50 implementa apiBridgeServer.ts: API_PORT faz proxy de rotas OpenAI para DASHBOARD_PORT no mesmo container. Logo 20128 também serve /v1; não era necessariamente endpoint inválido. Ambas /v1/models retornaram 200 a partir do gateway. Defeito confirmado é incoerência do padrão versionado (API_HOST loopback) e configuração que ignora API_PORT. Runtime existente já tinha API_HOST=0.0.0.0.

## Regressões históricas

PR #34 foi preservado na história, mas run_audits.py removido por a53f391 e test_run_audits.py por f4be09d. Não há contador canônico ativo no HEAD inicial. A regra de candidatos VC únicos da tabela Independent Verifier será preservada no executor de aceitação. A regressão structuredContent existe e passou na suíte 394. Meta fallback está corrigido no código; adicionada regressão explícita ausente no HEAD inicial.

## Runtime / fronteiras de aceitação

- Exclusion Git externa já efetiva agora impede edição desnecessária de .gitignore; teste COMMIT antes falhava por dirty tree, depois passa.
- Consolidação exige VERIFIED para todas as severidades; anteriormente P2 rejeitado era conservado.
- `--no-persist` fora de prepare agora é erro de uso antes de tocar alvo. Full transient não é suportado, em vez de afirmar persistência inexistente.
- Inicialização de transporte MCP com falha no CLI full agora retorna exit 4/TRANSPORT_FAILURE; anteriormente desabilitava semântica e imprimia COMPLETE/FULL.
- Executor de aceitação registra SHA dinâmico, compara todos os arquivos descobertos com blobs de HEAD e preserva regra VC única do PR #34.

Evidência: runtime_acceptance_red (2 falhas), cli_red e cli_transport_red; runtime_targeted_green (37 pass), cli_transport_green (2 pass), canonical_green (2 pass).
