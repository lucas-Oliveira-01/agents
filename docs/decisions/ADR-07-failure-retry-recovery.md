# ADR-07: Failure, Retry, Recovery and Single-Writer State

## Status
Aceito — Fase 6

## Contexto

O estado do Orchestrator é persistido em JSON dentro do vault .audit. Atomicidade de
arquivo isolado não é suficiente para impedir duas execuções concorrentes de intercalarem
leituras, transições e commits. Além disso, uma queda de processo antes do primeiro commit
do AuditRun podia deixar uma execução sem âncora durável para recovery.

## Decisão

1. Cada namespace de auditoria possui um lock físico audit-writer.lock, protegido por
   POSIX flock(LOCK_EX | LOCK_NB). O kernel libera o lock quando o processo termina;
   o conteúdo do arquivo é apenas diagnóstico e nunca é usado para decidir que um lock
   antigo está "stale".
2. run_full_audit() mantém o lock durante toda a execução/publicação da execução.
   Uma segunda execução concorrente falha fechada com StateStoreBusyError.
3. Persistências de estado usam escrita temporária + fsync do arquivo + os.replace +
   fsync do diretório quando suportado.
4. O AuditRun é persistido como RUNNING antes da primeira execução de WorkItem.
   Assim, interrupções abruptas deixam um ponto de recuperação durável.
5. Recovery nunca reutiliza um AuditRun interrompido como estado mutável. O Orchestrator
   cria uma nova tríade AuditPlan → AuditWorkItem → AuditRun, liga o novo run por
   recovery_from_ref e preserva o histórico do run original.
6. WorkItems concluídos com sucesso são preservados no recovery; itens pendentes, falhos,
   bloqueados ou afetados por drift são recriados como PLANNED.
7. Execuções de WorkItems já terminados são idempotentes: um replay não reexecuta o item
   terminado sem uma nova decisão explícita de retry.

## Consequências

A autoridade de escrita deixa de ser apenas lógica: passa a existir uma barreira física
por processo. O estado intermediário de uma execução fica recuperável, e recovery passa
a ser uma nova execução com identidade própria, em vez de uma mutação retroativa.
flock é deliberadamente POSIX; ambientes não-POSIX devem usar uma implementação
equivalente antes de habilitar execução concorrente.
