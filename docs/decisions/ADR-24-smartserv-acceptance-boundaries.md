# ADR-24 — Fronteiras comprováveis na aceitação SmartServ

Status: Accepted
Date: 2026-09-28

## Contexto e decisão

A aceitação reproduziu três comportamentos incompatíveis com fail-closed: full continuava sem backend semântico após falha de transporte; --no-persist era ignorado fora de prepare; candidatos P2 rejeitados eram mantidos na consolidação. Corrigidos com regressões: transporte indisponível retorna 4, flag incompatível retorna 2 antes de escrever, e publicação de candidatos exige VERIFIED em qualquer severidade.

O verificador continua sendo determinístico e limitado à integridade/referências da Evidence. VERIFIED não prova a verdade da narrativa do LLM. A aceitação precisa conferir o fundamento no código do alvo; não se promove incerteza a vulnerabilidade.

Para alvo COMMIT/READ_ONLY, uma exclusão Git já efetiva via core.excludesFile é aceita como alternativa à alteração de .gitignore. Isso qualifica o item 2 de `isolated-audit-repository.md`: a fronteira de exclusão precisa existir, mas não exige mutação de arquivo rastreado quando uma configuração externa de execução já fornece a mesma exclusão. Estado/relatórios continuam em .audit com repositório próprio. Não se modifica .git do alvo.

COMMIT no runtime atual significa HEAD materializado e checkout limpo; não há parâmetro de revisão arbitrária nem checkout automático. A aceitação compara SHA-256 dos bytes de cada arquivo descoberto com o blob de HEAD, além de verificar Git limpo, antes e depois. Não se infere essa equivalência só de HEAD.

O modo transient histórico invocava full --no-persist, porém a flag nunca tinha efeito nesse caminho. O modo suportado é preparação transitória; o full transient fica explicitamente UNSUPPORTED. Incremental real usa previous_run_ref da API, não duas chamadas CLI full sem baseline.

Gateway 3.8.50: API_PORT é bridge para o dashboard; 20128 também serve /v1. Usar API_PORT na rede Docker e API_HOST=0.0.0.0, mantendo publicação do host em 127.0.0.1. Respostas cujo finish_reason difere de stop não entram no cache determinístico. Aliases devem ser registrados antes de iniciar o servidor.

## Evidência e consequência

Ver `docs/reports/smartserv_final_acceptance/`. Não há alteração dos schemas canônicos. ADR-23 permanece integralmente obrigatório. Nenhuma dessas correções prova por si só GREEN; matriz real, revisão semântica e proveniência continuam necessárias.
