# Astra — autoauditoria absoluta da skill project-audit

**Data:** 2026-09-24/25  
**Alvo exclusivo:** skills/universal/project-audit  
**Auto-fix:** OFF. Nenhuma fonte, teste ou configuração foi alterada.

## Método e resultado consolidado

A diretiva Astra, SKILL.md, ADR-11, módulos de src/project_audit, schemas e testes diretamente relacionados foram lidos. As provas locais foram executadas sem rede, MCP ou worker externo:

- /tmp/astra-state/proof.py: 16 cenários/assertions, 17 defeitos de estado/orquestração; saída em /tmp/astra-state/proof-output.txt e manifesto SHA-256 em /tmp/astra-state/read-manifest.json.
- /tmp/astra-pipeline/prove.py: 10 cenários de discovery, classificação, plano e artefatos; resultados em /tmp/astra-pipeline/proofs.jsonl.
- /tmp/astra-semantic/prove.py: parser, contexto e egress, exit 0.
- /tmp/astra-root/prove.py: CLI, backend, normalização por symlink, lifecycle MCP e helpers.

Suíte consolidada: 246 passed, 4 failed. As quatro falhas são a divergência entre tests/test_omniroute_backend.py (métodos portugueses e delegar_tarefa) e o checkout atual de omniroute_backend.py (métodos ingleses e delegate_task). Não foram corrigidas.

## Achados adicionais da CLI, backend e integração

### R-01 — P1 — Egress externo sensível é habilitado implicitamente

**Tipo:** Bug de segurança. **Por quê:** --phase full cria o worker e passa APPROVED_EXTERNAL/allow_sensitive=True sem autorização explícita do operador, contrariando a escalada opt-in e ADR-05. A prova capturou os argumentos; nenhum servidor externo foi chamado.

**Evidência exata: skills/universal/project-audit/src/project_audit/__main__.py:99-117**

    backend, mcp_client = create_local_omniroute_backend()
    worker_port = WorkerPort(backend, "omniroute/project-audit")
    semantic_worker = SemanticAuditor(worker_port)
    semantic_egress_policy=EgressPolicy(destination=EgressDestination.APPROVED_EXTERNAL, allow_sensitive=True)

### R-02 — P2 — Auto-fix usa caminho relativo sem workspace_dir

**Tipo:** Bug de execução. **Por quê:** o dispatcher usa os.getcwd() por default. Com --target diferente do cwd, target_file=app.py pode ser aplicado em outro projeto. A prova capturou a chamada sem iniciar worker.

**Evidência exata: skills/universal/project-audit/src/project_audit/__main__.py:151-161**

    asyncio.run(dispatch_opencode_worker(task=task, target_file=loc, isolated_memory=True))

### R-03 — P2 — Auto-fix despacha candidato P1 não confirmado

**Tipo:** Gap de segurança. **Por quê:** o filtro verifica somente severity P0/P1, não status CONFIRMED, evidência ou recommendation. Candidate NOT_DETERMINABLE/P1 recebeu instrução Corrija. A prova usou dispatcher local capturador.

**Evidência exata: skills/universal/project-audit/src/project_audit/__main__.py:147-161**

    if cand.severity in ["P0", "P1"]:
        task = f"Corrija o P1: {cand.title}..."

### R-04 — P2 — Falha de dispatcher é anunciada como sucesso

**Tipo:** Bug de observabilidade. **Por quê:** retorno da coroutine é descartado e contador sobe antes de Popen. A prova retornou exit 0 e “Dispatched 1 workers” para falha simulada.

**Evidência exata: skills/universal/project-audit/src/project_audit/__main__.py:162-169**

    if p1_count > 0:
        print(f"Dispatched {p1_count} workers for P1 auto-fixing in background!")
    return 0

### R-05 — P2 — Auto-fix ignora findings de Engineering

**Tipo:** Logic gap. **Por quê:** FullAuditResult agrega as duas passagens, mas o loop só percorre security.semantic_reviews. A prova deixou P1 de Engineering sem despacho.

**Evidência exata: skills/universal/project-audit/src/project_audit/__main__.py:147-150; runtime.py:129-130**

    if hasattr(result, 'security') and hasattr(result.security, 'semantic_reviews'):
        for review in result.security.semantic_reviews:

### R-06 — P2 — Remoção de fences corrompe JSON válido

**Tipo:** Bug de transporte. **Por quê:** split("```") corta também bloco Markdown que esteja dentro de evidence/description. JSON válido foi rejeitado antes de json.loads.

**Evidência exata: skills/universal/project-audit/src/project_audit/omniroute_backend.py:126-146**

    if text_result.startswith("```json"):
        text_result = text_result.split("```json")[1]
    text_result = text_result.split("```")[0].strip()

### R-07 — P2 — structuredContent válido perde para texto explicativo

**Tipo:** Bug de precedência. **Por quê:** content textual é parseado e falha antes do fallback para structuredContent. A prova usou content=Audit complete. e structuredContent={findings: []}.

**Evidência exata: skills/universal/project-audit/src/project_audit/omniroute_backend.py:136-155**

    if text_result:
        payload = json.loads(text_result)
    nested = result.get("structuredContent")

### R-08 — P1 — Normalização atravessa symlink abaixo de .audit

**Tipo:** Falha de isolamento. **Por quê:** normalized_dir é concatenado sem validar o destino real. A prova colocou .audit/normalized apontando para outside e encontrou os quatro JSON fora do cofre.

**Evidência exata: skills/universal/project-audit/src/project_audit/runtime.py:35-51,145-173**

    normalized_dir = resolved_output_dir / "normalized"
    normalization = run_audit_normalize(..., str(normalized_dir), ...)

### R-09 — P3 — Cliente MCP não é fechado em falha de inicialização ou no caminho normal

**Tipo:** Bug de lifecycle. **Por quê:** não há finally em create_local_omniroute_backend; main descarta mcp_client. Prova local: MCP_CLIENT_NOT_CLOSED_ON_INITIALIZE_FAILURE.

**Evidência exata: skills/universal/project-audit/src/project_audit/omniroute_backend.py:198-208; __main__.py:99-105**

    client = MCPClient(mcp_url=mcp_url, timeout=timeout)
    client.initialize()
    client.discover_tools()
    return create_backend_from_mcp_client(client), client

### R-10 — P2 — Quatro testes backend quebram por contrato divergente

**Tipo:** Falha de infraestrutura de testes. **Por quê:** FakeBuilder só possui objetivo/restricoes/contexto/formato/criterios, mas o backend chama objective/constraints/context/format/criteria; outro teste espera delegar_tarefa. Resultado fresco: 4 failed, 246 passed. Não foi feita correção.

**Evidência exata: skills/universal/project-audit/tests/test_omniroute_backend.py:6-30,69-76,121-127; src/project_audit/omniroute_backend.py:80-96,207-210**

    class FakeBuilder:
        def objetivo(self, value): ...
    builder = TaskBuilder().objective(...).constraints(...).context(...)
    client.call_tool("delegate_task", filtered)

### R-11 — P3 — Helpers de patch locais geram fonte inválida

**Tipo:** Falha de manutenção. **Por quê:** em cópias descartáveis, fix_backend.py, patch_backend_schema_fix.py e patch_main.py produziram respectivamente string não terminada, parêntese não fechado e indentação inválida; patch_main2.py importa .worker_port inexistente. São artefatos não rastreados, não runtime instalado.

**Evidência:** /tmp/astra-root/prove.py reportou HELPER_BREAKS_PARSE para os três primeiros e HELPER_INVALID_IMPORT para patch_main2.py. Nenhum helper foi aplicado.

### R-12 — P2 — Falha semântica não aparece nos artefatos

**Tipo:** Bug de publicação. **Por quê:** backend indisponível deixa PARTIAL/INFRA_ERROR no run, mas writer escreve quatro Markdown dizendo que não houve findings; main retorna 0 se normalização não falhar. Prova: REPORT_OMITS_SEMANTIC_FAILURE.

**Evidência exata: skills/universal/project-audit/src/project_audit/runtime.py:139-145; report_writer.py:298-305; __main__.py:128-138**

    staged = write_audit_artifacts(...)
    if result.normalization.status == "FAILED":
        return 3

## Vetores obrigatórios

- Async/blocking: asyncio.run(dispatch_opencode_worker(...)) é síncrono; o Popen retorna sem wait, ID persistido ou reconciliação. R-02–R-05.
- Despacho e schemas: enums atuais coincidem; as falhas demonstradas são o TypeError do parser, extração de JSON/fences e egress. Não foi inventado mismatch de enum.
- Falsos positivos/gaps: o arquivo disparador pode ser omitido do contexto, templates HTML/Vue/Svelte são excluídos e o limite por arquivo mede caracteres. Não se alegou falso positivo IDOR específico sem worker real.
- Typo traps: o atributo correto é semantic_reviews; o defeito é a coleção de Engineering ignorada, não security.reviews.

## Inventário e limites

Os inventários completos e hashes estão nos relatórios de frente abaixo. Não foram elevados a defeito: ausência da V3 por si só; ausência de findings em Evidence; enums atuais; UNKNOWN no default LOCAL_ONLY (fail-closed); observação determinística promovida automaticamente; prompt injection universal; perda de energia sem prova; path traversal sem cadeia; ou dependências externas ausentes. A prova de egress foi consolidada uma vez no relatório final.

Nenhuma correção, worker, chamada MCP externa ou rede foi executada. Aguardar análise humana.

---

## Apêndice I — estado e orquestração

# Auditoria state/orchestrator — somente leitura

Data: 2026-09-24. Alvo exclusivo: `skills/universal/project-audit`. Nenhum fonte ou teste existente foi editado. Provas em `/tmp/astra-state`, sem rede, processos workers ou backend externo; `Mock` executa funções locais no mesmo processo. Severidades são propostas de triagem.

## Reprodução

```sh
cd /home/oliveira/Projects/SKILLS
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=skills/universal/project-audit/src python /tmp/astra-state/proof.py
```

Resultado: 16 cenários/assertions passam e confirmam 17 defeitos (S14 e S17 compartilham cenário de trilha). Saída integral: `/tmp/astra-state/proof-output.txt`.

## Achados

### S01 — COMPLETE declarado permite publicar auditoria não executada

**Tipo:** Bug lógico / gate de publicação. **Severidade:** HIGH. **Prova:** `S01` em `proof.py`.

A validação de COMPLETE só procura RUNNING, deixando PLANNED passar. can_publish bloqueia apenas cobertura NONE, não PARTIAL/PENDING, e usa o enum COMPLETE sem validar os itens. A prova persiste por commit_run um run COMPLETE/PARTIAL cujo único item está PLANNED; can_publish retorna PASS com evidence_list vazia. Afeta a API de publicação inclusive após o gate de persistência; não foi demonstrado que run_full_audit produz sozinho esse estado.


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:276-294`

```python
276: def validate_run_not_complete_with_running_items(
277:     run: AuditRun,
278:     work_items: List[AuditWorkItem],
279: ) -> ValidationResult:
280:     """
281:     An AuditRun cannot be COMPLETE if any referenced WorkItem is still RUNNING.
282:     (semantic-validators.md §3)
283:     """
284:     if run.execution_completeness != RunExecutionCompleteness.COMPLETE:
285:         return _pass("RUN_COMPLETION_NOT_CLAIMED", "Run is not claiming COMPLETE status.")
286: 
287:     running = [wi for wi in work_items if wi.execution_state == ExecutionState.RUNNING]
288:     if running:
289:         return _error(
290:             "RUN_COMPLETE_WITH_RUNNING_ITEMS",
291:             f"AuditRun {run.run_id} claims COMPLETE but {len(running)} WorkItem(s) are still RUNNING.",
292:             {"running_item_ids": [wi.work_item_id for wi in running]},
293:         )
294:     return _pass("RUN_COMPLETION_CONSISTENT", "Run COMPLETE status is consistent with WorkItem states.")
```


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:649-677`

```python
649:         results.append(_error("PUBLISH_EMPTY_COVERAGE", "Cannot publish an audit with NONE coverage."))
650: 
651:     # 1. Snapshot integrity
652:     drift = validate_snapshot_drift(run, current_snapshot_fingerprint)
653:     results.append(drift)
654: 
655:     # 2. Execution completeness
656:     if run.execution_completeness not in (
657:         RunExecutionCompleteness.COMPLETE,
658:     ):
659:         results.append(
660:             _error(
661:                 "PUBLISH_EXECUTION_INCOMPLETE",
662:                 f"Run {run.run_id}: cannot publish. "
663:                 f"execution_completeness={run.execution_completeness.value} (must be COMPLETE).",
664:             )
665:         )
666:     else:
667:         results.append(_pass("PUBLISH_EXECUTION_COMPLETE", "Execution is COMPLETE."))
668: 
669:     # 3. No FAILED items
670:     failed_items = [
671:         wi for wi in work_items
672:         if wi.failure_state not in (WorkItemFailureState.NONE,)
673:         and wi.execution_state == ExecutionState.TERMINATED
674:     ]
675:     if failed_items:
676:         results.append(
677:             _error(
```

### S02 — Cobertura FULL ignora itens planejados que faltam na lista recebida

**Tipo:** Logic Gap / cobertura e integridade referencial. **Severidade:** HIGH. **Prova:** `S02` em `proof.py`.

applicable_domains e resolved_domains são calculados e nunca utilizados. O denominador é apenas work_items recebido; não há confronto com plan.work_items ou run.work_item_refs. A prova planeja dois itens, executa um e passa só esse ao commit_run/can_publish: FULL/PASS apesar do segundo item ainda PLANNED. Gate público vulnerável a lista incompleta; não alego omissão espontânea pelo fluxo CLI.


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:423-459`

```python
423: def validate_coverage_completeness_derivable(
424:     run: AuditRun,
425:     plan: AuditPlan,
426:     work_items: List[AuditWorkItem],
427: ) -> ValidationResult:
428:     """
429:     Coverage completeness must be mathematically derivable, not arbitrarily declared.
430:     requested_scope -> applicability -> selected_scope -> completed/reused WorkItems.
431:     (semantic-validators.md §6)
432:     """
433:     # Derive expected coverage from applicability decisions
434:     applicable_domains = {
435:         d.domain for d in plan.applicability_decisions if d.applicable
436:     }
437:     resolved_domains = set(plan.resolved_scope)
438: 
439:     # Completed or reused items
440:     terminal_ok_states = {ExecutionState.TERMINATED}
441:     completed_items = [
442:         wi for wi in work_items
443:         if wi.execution_state in terminal_ok_states
444:         and wi.failure_state == WorkItemFailureState.NONE
445:     ]
446:     blocked_items = [
447:         wi for wi in work_items
448:         if wi.failure_state == WorkItemFailureState.SAFETY_BLOCK
449:     ]
450:     failed_items = [
451:         wi for wi in work_items
452:         if wi.failure_state != WorkItemFailureState.NONE
453:         and wi.failure_state != WorkItemFailureState.SAFETY_BLOCK
454:     ]
455: 
456:     all_blocked = len(blocked_items) == len(work_items) and bool(work_items)
457: 
458:     if all_blocked:
459:         # ALL items were blocked — nothing was audited
```


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:742-758`

```python
742: 
743: 
744: def validate_run(
745:     run: AuditRun,
746:     plan: AuditPlan,
747:     work_items: List[AuditWorkItem],
748:     known_run_ids: Optional[List[str]] = None,
749:     interrupted_run_ids: Optional[List[str]] = None,
750: ) -> ValidationReport:
751:     """Run all semantic validators applicable to an AuditRun."""
752:     known_run_ids = known_run_ids or []
753:     interrupted_run_ids = interrupted_run_ids or []
754:     results = [
755:         validate_run_not_complete_with_running_items(run, work_items),
756:         validate_coverage_not_full_with_blocked_items(run, work_items),
757:         validate_coverage_completeness_derivable(run, plan, work_items),
758:         validate_run_recovery_ref(run, known_run_ids, interrupted_run_ids),
```

### S03 — commit_work_item persiste estados rejeitados pelo validador semântico

**Tipo:** Bug / gate semântico ausente. **Severidade:** MEDIUM. **Prova:** `S03` em `proof.py`.

A função chama apenas o schema. validate_work_item está importado mas nunca chamado no orquestrador. A prova cria item RUNNING sem tentativas e plan_ref inexistente: validate_work_item retorna ERROR, porém commit_work_item salva e reload conserva o estado inválido. Enfraquece o single-writer que promete validar antes de commit.


Evidência exata: `skills/universal/project-audit/src/project_audit/orchestrator.py:152-161`

```python
152:     def commit_work_item(self, work_item: AuditWorkItem) -> None:
153:         """Validate and persist a single AuditWorkItem."""
154:         errors = validate_audit_work_item(work_item.to_dict())
155:         if errors:
156:             raise SchemaValidationError(
157:                 f"AuditWorkItem {work_item.work_item_id} schema validation failed:\n"
158:                 + "\n".join(errors)
159:             )
160:         self.store.save_work_item(work_item)
161:         logger.debug("WorkItem committed: %s (%s)", work_item.work_item_id, work_item.execution_state.value)
```

### S04 — Evidence VALID de outro snapshot é aceita e persistida

**Tipo:** Logic Gap / binding de evidência. **Severidade:** HIGH. **Prova:** `S04` em `proof.py`.

Após validar forma, apenas work_item_ref é comparado. target_snapshot_ref não é vinculado ao snapshot do plano/item/run. A prova salva snapshot/plano/item A, depois commit_evidence aceita Evidence VALID com fingerprint de snapshot B inexistente. Schema valida só formato SHA-256. Afeta API canônica e respostas de auditor; nenhuma execução externa foi usada.


Evidência exata: `skills/universal/project-audit/src/project_audit/orchestrator.py:176-190`

```python
176:     def commit_evidence(self, evidence: Evidence, work_item: AuditWorkItem) -> None:
177:         """Validate evidence structural + semantic consistency, then persist."""
178:         errors = validate_evidence(evidence.to_dict())
179:         if errors:
180:             raise SchemaValidationError(
181:                 f"Evidence {evidence.evidence_id} schema validation failed:\n"
182:                 + "\n".join(errors)
183:             )
184:         # Evidence work_item_ref must match
185:         if evidence.work_item_ref != work_item.work_item_id:
186:             raise OrchestratorError(
187:                 f"Evidence {evidence.evidence_id} work_item_ref mismatch: "
188:                 f"{evidence.work_item_ref} != {work_item.work_item_id}"
189:             )
190:         self.store.save_evidence(evidence)
```

### S05 — freeze não congela declaração do plano nem impede regravação

**Tipo:** Bug / imutabilidade. **Severidade:** MEDIUM. **Prova:** `S05` em `proof.py`.

Somente coleções externas viram tuple e add_work_item consulta _assert_mutable. Reassignment de atributos, ApplicabilityDecision e BudgetEnvelope continuam mutáveis. A prova troca escopo, applicability e network policy após freeze e freeze_and_commit_plan sobrescreve o mesmo ID congelado. Isso altera o contrato já aceito sem nova versão.


Evidência exata: `skills/universal/project-audit/src/project_audit/models.py:691-716`

```python
691:     def freeze(self, at: Optional[datetime] = None) -> None:
692:         """Freeze the plan. Raises if already frozen."""
693:         if self.is_frozen:
694:             raise ImmutablePlanError(
695:                 f"AuditPlan {self.plan_id} is already frozen at {self.frozen_at.isoformat()}."
696:             )
697:         self.frozen_at = at or datetime.now(timezone.utc)
698:         # Deep immutability: convert mutable collections to tuples
699:         if hasattr(self, "requested_scope"):
700:             self.requested_scope = tuple(self.requested_scope)  # type: ignore
701:         if hasattr(self, "applicability_decisions"):
702:             self.applicability_decisions = tuple(self.applicability_decisions)  # type: ignore
703:         if hasattr(self, "resolved_scope"):
704:             self.resolved_scope = tuple(self.resolved_scope)  # type: ignore
705:         if hasattr(self, "work_items"):
706:             self.work_items = tuple(self.work_items)  # type: ignore
707: 
708:     def _assert_mutable(self, operation: str) -> None:
709:         if self.is_frozen:
710:             raise ImmutablePlanError(
711:                 f"Cannot {operation}: AuditPlan {self.plan_id} is frozen since {self.frozen_at.isoformat()}."
712:             )
713: 
714:     def add_work_item(self, item: AuditWorkItem) -> None:
715:         self._assert_mutable("add_work_item")
716:         self.work_items.append(item)
```


Evidência exata: `skills/universal/project-audit/src/project_audit/orchestrator.py:134-144`

```python
134:     def freeze_and_commit_plan(self, plan: AuditPlan) -> AuditPlan:
135:         """Freeze the plan (if not already frozen), validate, persist."""
136:         if not plan.is_frozen:
137:             plan.freeze()
138:         # Structural gate (plan_id + work_items refs only)
139:         errors = validate_audit_plan(plan.to_dict())
140:         if errors:
141:             raise SchemaValidationError(
142:                 f"AuditPlan schema validation failed:\n" + "\n".join(errors)
143:             )
144:         self.store.save_plan(plan)
```

### S06 — load_plan perde os WorkItem refs persistidos e reabre listas congeladas

**Tipo:** Bug / roundtrip e recovery. **Severidade:** MEDIUM. **Prova:** `S06` em `proof.py`.

O JSON possui work_items com IDs, mas load_plan ignora esses IDs e usa work_items or []. Depois de save/load sem argumento opcional, to_dict perde todos os refs mesmo com itens presentes no store. requested_scope/resolved_scope voltam a list embora frozen_at permaneça preenchido; append volta a funcionar. Não é apenas representação: save posterior elimina os refs.


Evidência exata: `skills/universal/project-audit/src/project_audit/state_store.py:254-266`

```python
254:         plan = AuditPlan(
255:             plan_id=d["plan_id"],
256:             target_snapshot_ref=d["target_snapshot_ref"],
257:             requested_scope=list(d.get("requested_scope", [])),
258:             applicability_decisions=applicability,
259:             resolved_scope=list(d.get("resolved_scope", [])),
260:             work_items=work_items or [],
261:             execution_policy=_load_execution_policy(d["execution_policy"]),
262:             egress_policy=_load_egress_policy(d["egress_policy"]),
263:             budget_envelope=budget,
264:             frozen_at=_dt(d.get("frozen_at")),
265:         )
266:         return plan
```

### S07 — Vertical slice não persiste AuditRun antes da execução, inviabilizando recovery de crash

**Tipo:** Bug / persistência de execução. **Severidade:** HIGH. **Prova:** `S07` em `proof.py`.

O run é criado em memória e salvo somente no final. A prova usa Mock.execute que levanta RuntimeError; após a exceção há work item RUNNING persistido mas list_run_ids == []. recover_run requer run existente e não pode reconstruir essa execução. Limitado ao execute_vertical_slice: outros runners podem ter persistência própria.


Evidência exata: `skills/universal/project-audit/src/project_audit/orchestrator.py:347-362`

```python
347:         # 3. Create AuditRun
348:         run = AuditRun(
349:             run_id=str(uuid.uuid4()),
350:             target_snapshot_ref=snapshot.snapshot_fingerprint,
351:             plan_ref=plan.plan_id,
352:             work_item_refs=[wi.work_item_id for wi in work_items],
353:             execution_completeness=RunExecutionCompleteness.RUNNING,
354:             coverage_completeness=RunCoverageCompleteness.PENDING,
355:             failure_state=RunFailureState.NONE,
356:             budget_state=RunBudgetState.HEALTHY,
357:             publication_state=RunPublicationState.NOT_PUBLISHED,
358:             previous_run_ref=previous_run_ref,
359:             recovery_from_ref=recovery_from_ref,
360:         )
361: 
362:         collected_evidence: List[Evidence] = []
```


Evidência exata: `skills/universal/project-audit/src/project_audit/orchestrator.py:374-386`

```python
374:             # Commit initial planned state
375:             self.commit_work_item(work_item)
376: 
377:             now = datetime.now(timezone.utc)
378:             attempt = work_item.start_attempt(started_at=now)
379:             self.commit_work_item(work_item)
380: 
381:             # Worker executes (isolated output — not yet committed to canonical state)
382:             receipt, evidence = auditor.execute(work_item, started_at=now)
383: 
384:             check_snapshot()
385:             # Commit receipt (evidence of execution)
386:             self.commit_receipt(receipt)
```


Evidência exata: `skills/universal/project-audit/src/project_audit/orchestrator.py:459-462`

```python
459:         check_snapshot()
460:         # 6. Commit the run
461:         known_run_ids = self.store.list_run_ids()
462:         self.commit_run(run, plan, work_items, known_run_ids=known_run_ids)
```

### S08 — recovery_from_ref válido sempre falha no commit final do vertical slice

**Tipo:** Bug / recovery. **Severidade:** MEDIUM. **Prova:** `S08` em `proof.py`.

O método aceita recovery_from_ref e entrega ao run, mas commit_run final só recebe known_run_ids; interrupted_run_ids fica []. Assim validate_run_recovery_ref rejeita toda referência não nula até quando o run anterior persistido está RUNNING e recover_run aceitou. A prova mostra falha depois de conclusão do mock local, deixando execução sem run final.


Evidência exata: `skills/universal/project-audit/src/project_audit/orchestrator.py:459-462`

```python
459:         check_snapshot()
460:         # 6. Commit the run
461:         known_run_ids = self.store.list_run_ids()
462:         self.commit_run(run, plan, work_items, known_run_ids=known_run_ids)
```


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:197-219`

```python
197: def validate_run_recovery_ref(
198:     run: AuditRun,
199:     known_run_ids: List[str],
200:     interrupted_run_ids: List[str],
201: ) -> ValidationResult:
202:     """
203:     AuditRun.recovery_from_ref must point to an interrupted/failed run.
204:     It cannot point to a successful run. (semantic-validators.md §2)
205:     """
206:     if run.recovery_from_ref is None:
207:         return _pass("RUN_NO_RECOVERY_REF", "No recovery_from_ref — not a recovery run.")
208:     if run.recovery_from_ref not in known_run_ids:
209:         return _error(
210:             "RUN_DANGLING_RECOVERY_REF",
211:             f"Run {run.run_id} recovery_from_ref {run.recovery_from_ref} does not exist.",
212:         )
213:     if run.recovery_from_ref not in interrupted_run_ids:
214:         return _error(
215:             "RUN_RECOVERY_REF_NOT_INTERRUPTED",
216:             f"Run {run.run_id} recovery_from_ref {run.recovery_from_ref} must point to "
217:             "an interrupted/failed run, not a successful one.",
218:         )
219:     return _pass("RUN_RECOVERY_REF_VALID", "recovery_from_ref points to a valid interrupted run.")
```


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:750-758`

```python
750: ) -> ValidationReport:
751:     """Run all semantic validators applicable to an AuditRun."""
752:     known_run_ids = known_run_ids or []
753:     interrupted_run_ids = interrupted_run_ids or []
754:     results = [
755:         validate_run_not_complete_with_running_items(run, work_items),
756:         validate_coverage_not_full_with_blocked_items(run, work_items),
757:         validate_coverage_completeness_derivable(run, plan, work_items),
758:         validate_run_recovery_ref(run, known_run_ids, interrupted_run_ids),
```

### S09 — Destino externo aprovado ignora allow_sensitive=False

**Tipo:** Bug / fail-open de egress. **Severidade:** HIGH. **Prova:** `S09` em `proof.py`.

A condição de bloqueio exige LOCAL_ONLY junto com dado sensível. Logo APPROVED_EXTERNAL e allow_sensitive=False retorna PASS para data_is_sensitive=True e None. WorkerPort usa diretamente esse resultado antes de backend.delegate, portanto flag que proíbe sensíveis não é aplicada. Prova apenas função pura, sem enviar conteúdo. Há defesa adicional em alguns backends: não alego vazamento real.


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:555-570`

```python
555:     # UNKNOWN (None) is treated as True (fail closed)
556:     is_sensitive = data_is_sensitive if data_is_sensitive is not None else True
557:     
558:     if (
559:         policy.destination == EgressDestination.LOCAL_ONLY
560:         and not policy.allow_sensitive
561:         and is_sensitive
562:     ):
563:         return _error(
564:             "EGRESS_SENSITIVE_DATA_DENIED",
565:             f"WorkItem {work_item.work_item_id}: data_egress_policy denies external egress "
566:             f"but sensitive data was detected (or sensitivity is UNKNOWN). DO NOT SEND. (ADR-05)",
567:         )
568:     return _pass("EGRESS_POLICY_CONSISTENT", "Egress policy is consistent with data classification.")
569: 
570: 
```


Evidência exata: `skills/universal/project-audit/src/project_audit/delegation.py:115-134`

```python
115:         # Security Egress Check
116:         # Unknown sensitivity fails closed before any delegation.
117:         egress_check = validate_egress_policy(work_item, data_is_sensitive=data_is_sensitive)
118:         if egress_check.is_error:
119:             finished_at = datetime.now(timezone.utc)
120:             receipt = ExecutionReceipt(
121:                 receipt_id=str(uuid.uuid4()),
122:                 work_item_ref=work_item.work_item_id,
123:                 command="omniroute-delegation",
124:                 arguments=[request.request_id],
125:                 policy_snapshot=work_item.effective_execution_policy,
126:                 started_at=started_at,
127:                 finished_at=finished_at,
128:                 exit_code=126,
129:                 artifact_refs=[],
130:                 environment_summary=f"WorkerPort: {self.actor_identity} | error: {egress_check.message}",
131:             )
132:             return WorkerExecution(receipt, None, None)
133: 
134:         result = self.backend.delegate(request)
```

### S10 — Evidência STALE é aceita como válida para REUSE

**Tipo:** Bug / validade de reuso. **Severidade:** MEDIUM. **Prova:** `S10` em `proof.py`.

Validador exige VALID em docstring, mas só recusa INVALID/NOT_DETERMINABLE e deixa STALE passar. can_publish só recusa INVALID em itens REUSE. Prova STALE => PASS nos dois. ADR-11 determina rerun integral após drift; não há reuso seguro de STALE. API/incremental latente: V1 planner pode não escolher REUSE.


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:313-336`

```python
313:     if not evidence_for_item:
314:         return _error(
315:             "REUSE_NO_PRIOR_EVIDENCE",
316:             f"WorkItem {work_item.work_item_id} action=REUSE but no prior evidence found.",
317:         )
318: 
319:     invalid_evidence = [e for e in evidence_for_item if e.validity == EvidenceValidity.INVALID]
320:     if invalid_evidence:
321:         return _error(
322:             "REUSE_INVALID_EVIDENCE",
323:             f"WorkItem {work_item.work_item_id} action=REUSE but evidence is INVALID. "
324:             "INVALID evidence cannot be reused. (ADR-04)",
325:             {"invalid_evidence_ids": [e.evidence_id for e in invalid_evidence]},
326:         )
327: 
328:     not_determinable = [e for e in evidence_for_item if e.validity == EvidenceValidity.NOT_DETERMINABLE]
329:     if not_determinable:
330:         return _error(
331:             "REUSE_UNDETERMINABLE_EVIDENCE",
332:             f"WorkItem {work_item.work_item_id} action=REUSE but evidence validity is NOT_DETERMINABLE. "
333:             "Fail-safe: treat as REAUDIT required. (ADR-04)",
334:         )
335: 
336:     return _pass("REUSE_EVIDENCE_VALID", f"WorkItem REUSE action has valid prior evidence.")
```


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:690-705`

```python
690:         e for e in evidence_list
691:         if e.work_item_ref in reuse_items and e.validity == EvidenceValidity.INVALID
692:     ]
693:     if invalid_reuse_evidence:
694:         results.append(
695:             _error(
696:                 "PUBLISH_INVALID_REUSE_EVIDENCE",
697:                 f"Run {run.run_id}: {len(invalid_reuse_evidence)} INVALID evidence item(s) "
698:                 "referenced by REUSE WorkItems. (ADR-04)",
699:             )
700:         )
701:     else:
702:         results.append(_pass("PUBLISH_EVIDENCE_VALID", "No INVALID evidence in REUSE items."))
703: 
704:     # 5. Required audit artifacts
705:     results.append(validate_publication_artifacts_registered(run))
```

### S11 — Retry rejeitado apaga falha e deixa item RUNNING sem tentativa ativa

**Tipo:** Bug / atomicidade de transição. **Severidade:** MEDIUM. **Prova:** `S11` em `proof.py`.

retry_attempt altera estado para RUNNING/NONE antes de start_attempt validar ordenação. Prova um retry com timestamp anterior ao término: IllegalAttemptOrderError ocorre, mas o item original TERMINATED/INFRA_ERROR fica RUNNING/NONE e sem nova tentativa. O validador passa a rejeitar o próprio objeto depois de operação recusada.


Evidência exata: `skills/universal/project-audit/src/project_audit/models.py:589-599`

```python
589:         # Check budget
590:         max_retries = self.effective_execution_policy.max_retries
591:         if len(self.attempts) > max_retries:
592:             raise IllegalStateTransitionError(
593:                 f"Retry budget exhausted: maximum {max_retries} retries allowed."
594:             )
595: 
596:         # Transition back to RUNNING for retry
597:         self.execution_state = ExecutionState.RUNNING
598:         self.failure_state = WorkItemFailureState.NONE
599:         return self.start_attempt(started_at=started_at)
```

### S12 — Tentativa aberta ou com duração negativa pode sustentar item TERMINATED

**Tipo:** Bug / lifecycle de tentativa. **Severidade:** MEDIUM. **Prova:** `S12` em `proof.py`.

terminate não exige encerrar a tentativa e o validador TERMINATED só exige que exista ao menos uma. Attempt.finish aceita finished_at anterior ao started_at; validate_attempt_ordering só compara tentativas adjacentes. Prova persiste item TERMINATED com tentativa aberta e run COMPLETE/FULL; depois termina essa tentativa dez segundos antes do início e composite validator continua PASS.


Evidência exata: `skills/universal/project-audit/src/project_audit/models.py:415-425`

```python
415:     def finish(self, finished_at: datetime, exit_code: int, receipt_ref: Optional[str] = None) -> None:
416:         if self.finished_at is not None:
417:             raise ValueError(f"Attempt {self.attempt_id} is already finished.")
418:         self.finished_at = finished_at
419:         self.receipt_ref = receipt_ref
420: 
421:     def fail(self, finished_at: datetime, reason: str, receipt_ref: Optional[str] = None) -> None:
422:         if self.finished_at is not None:
423:             raise ValueError(f"Attempt {self.attempt_id} is already finished.")
424:         self.finished_at = finished_at
425:         self.failure_reason = reason
```


Evidência exata: `skills/universal/project-audit/src/project_audit/models.py:601-607`

```python
601:     def terminate(
602:         self,
603:         failure_state: WorkItemFailureState = WorkItemFailureState.NONE,
604:     ) -> None:
605:         """Terminate this WorkItem with the given failure state."""
606:         self.transition(ExecutionState.TERMINATED)
607:         self.failure_state = failure_state
```


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:267-273`

```python
267:     if state == ExecutionState.TERMINATED:
268:         if not attempts:
269:             return _error(
270:                 "WORK_ITEM_TERMINATED_NO_ATTEMPTS",
271:                 f"WorkItem {work_item.work_item_id} is TERMINATED but has no attempts.",
272:             )
273:     return _pass("WORK_ITEM_STATE_MACHINE_VALID", f"WorkItem state machine is consistent.")
```


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:495-514`

```python
495: def validate_attempt_ordering(work_item: AuditWorkItem) -> ValidationResult:
496:     """
497:     Attempt #N cannot exist without Attempt #N-1.
498:     Temporal ordering: attempt[i].started_at >= attempt[i-1].finished_at
499:     (semantic-validators.md §7)
500:     """
501:     attempts = work_item.attempts
502:     for i in range(1, len(attempts)):
503:         prev = attempts[i - 1]
504:         curr = attempts[i]
505:         if not prev.is_finished:
506:             return _error(
507:                 "ATTEMPT_ORDERING_PREV_NOT_FINISHED",
508:                 f"WorkItem {work_item.work_item_id}: Attempt #{i} started before "
509:                 f"Attempt #{i - 1} ({prev.attempt_id}) was finished.",
510:             )
511:         if prev.finished_at and curr.started_at < prev.finished_at:
512:             return _error(
513:                 "ATTEMPT_ORDERING_TEMPORAL_VIOLATION",
514:                 f"WorkItem {work_item.work_item_id}: Attempt #{i + 1} started at "
```

### S13 — commit_evidence sobrescreve observação imutável com o mesmo ID

**Tipo:** Bug / histórico de evidência. **Severidade:** MEDIUM. **Prova:** `S13` em `proof.py`.

Evidence é frozen apenas em memória. Persistência faz rename por evidence_id sem conferir entrada existente, então uma nova instância com mesmo ID e fingerprint/source_refs diferentes apaga a observação anterior. A prova grava via commit_evidence duas observações conflitantes sob mesmo ID; só a segunda resta. Distinguir invalidação de validity (esperada no drift) de alteração do conteúdo observado (provada aqui).


Evidência exata: `skills/universal/project-audit/src/project_audit/state_store.py:295-297`

```python
295:     def save_evidence(self, evidence: Evidence) -> None:
296:         path = self._dirs["evidences"] / f"{evidence.evidence_id}.json"
297:         _atomic_write(path, evidence.to_dict())
```


Evidência exata: `skills/universal/project-audit/src/project_audit/state_store.py:84-88`

```python
84:     try:
85:         with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
86:             json.dump(data, f, indent=2, ensure_ascii=False)
87:             f.write("\n")
88:         os.rename(tmp_path, str(path))
```

### S14 — Vertical slice registra duração zero mesmo quando receipt registra duração real

**Tipo:** Bug / trilha temporal. **Severidade:** LOW. **Prova:** `S14` em `proof.py`.

A variável now é capturada antes do auditor e reutilizada em attempt.finish/fail. Prova receipt sintético com finished_at = started_at + 10s produz attempt.finished_at = started_at. A trilha de tentativas perde duração e contradiz o receipt. Limitado ao vertical slice; runners próprios usam finished_at do receipt.


Evidência exata: `skills/universal/project-audit/src/project_audit/orchestrator.py:377-399`

```python
377:             now = datetime.now(timezone.utc)
378:             attempt = work_item.start_attempt(started_at=now)
379:             self.commit_work_item(work_item)
380: 
381:             # Worker executes (isolated output — not yet committed to canonical state)
382:             receipt, evidence = auditor.execute(work_item, started_at=now)
383: 
384:             check_snapshot()
385:             # Commit receipt (evidence of execution)
386:             self.commit_receipt(receipt)
387: 
388:             if receipt.exit_code == 126:
389:                 # BLOCKED by safety gate
390:                 attempt.fail(finished_at=now, reason="SAFETY_BLOCK", receipt_ref=receipt.receipt_id)
391:                 work_item.terminate(failure_state=WorkItemFailureState.SAFETY_BLOCK)
392:             elif receipt.exit_code != 0 or evidence is None:
393:                 # FAILED
394:                 attempt.fail(finished_at=now, reason="INFRA_ERROR", receipt_ref=receipt.receipt_id)
395:                 work_item.terminate(failure_state=WorkItemFailureState.INFRA_ERROR)
396:             else:
397:                 # SUCCESS: validate and commit evidence
398:                 attempt.finish(finished_at=now, exit_code=0, receipt_ref=receipt.receipt_id)
399:                 self.commit_evidence(evidence, work_item)
```

### S15 — PERSISTING -> REGRESSED passa sem predecessor FIXED

**Tipo:** Logic Gap / finding lifecycle. **Severidade:** LOW. **Prova:** `S15` em `proof.py`.

A função declara REGRESSED exige FIXED, mas rejeita apenas NEW -> REGRESSED. PERSISTING -> REGRESSED retorna PASS. Validador público latente: não identifiquei chamada no pipeline normal; prova de contrato local, não de achado incorreto emitido em relatório.


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:365-380`

```python
365: 
366: def validate_finding_lifecycle_transition(
367:     previous_lifecycle: FindingLifecycle,
368:     new_lifecycle: FindingLifecycle,
369: ) -> ValidationResult:
370:     """
371:     NEW -> REGRESSED is a semantic error.
372:     REGRESSED requires a prior FIXED state.
373:     (semantic-validators.md §5)
374:     """
375:     if new_lifecycle == FindingLifecycle.REGRESSED and previous_lifecycle == FindingLifecycle.NEW:
376:         return _error(
377:             "FINDING_LIFECYCLE_INVALID_REGRESSION",
378:             f"Finding cannot transition NEW -> REGRESSED. REGRESSED requires a prior FIXED state.",
379:         )
380:     return _pass("FINDING_LIFECYCLE_TRANSITION_VALID", f"Lifecycle transition {previous_lifecycle} -> {new_lifecycle} is valid.")
```

### S16 — UNDETERMINABLE vira overall PASS

**Tipo:** Bug / agregação de validação. **Severidade:** LOW. **Prova:** `S16` em `proof.py`.

ValidationReport.overall só verifica ERROR e WARNING, descartando o quarto nível UNDETERMINABLE. Um relatório com única resposta desconhecida agrega PASS, violando distinção epistemológica declarada no módulo. Atualmente helper _undeterminable não tem uso no fluxo inspecionado: defeito latente de API, sem falha de publicação demonstrada por esse mecanismo isolado.


Evidência exata: `skills/universal/project-audit/src/project_audit/validators.py:80-86`

```python
80:     @property
81:     def overall(self) -> ValidationLevel:
82:         if self.has_errors:
83:             return ValidationLevel.ERROR
84:         if self.has_warnings:
85:             return ValidationLevel.WARNING
86:         return ValidationLevel.PASS
```

### S17 — Vertical slice registra evidence/ mas store grava evidences/

**Tipo:** Bug / referência de artefato. **Severidade:** LOW. **Prova:** `S14` em `proof.py`.

Após salvar Evidence, WorkItem.artifact_refs recebe evidence/<id>.json; StateStore escreve evidences/<id>.json. Prova verifica referência relativa ao store_root inexistente enquanto o arquivo real existe em evidences/. Afeta rastreabilidade do vertical slice.


Evidência exata: `skills/universal/project-audit/src/project_audit/orchestrator.py:398-401`

```python
398:                 attempt.finish(finished_at=now, exit_code=0, receipt_ref=receipt.receipt_id)
399:                 self.commit_evidence(evidence, work_item)
400:                 work_item.artifact_refs.append(f"evidence/{evidence.evidence_id}.json")
401:                 work_item.terminate(failure_state=WorkItemFailureState.NONE)
```


Evidência exata: `skills/universal/project-audit/src/project_audit/state_store.py:178-184`

```python
178:         self._dirs = {
179:             "snapshots": self.root / "target_snapshots",
180:             "plans": self.root / "audit_plans",
181:             "work_items": self.root / "audit_work_items",
182:             "evidences": self.root / "evidences",
183:             "runs": self.root / "audit_runs",
184:             "receipts": self.root / "execution_receipts",
```

## Hipóteses descartadas / limites

- Schemas vs serialização normal: os cinco tipos raiz possuem campos compatíveis com to_dict; AuditRun.audit_status está definido no schema atual. Não há achado de additionalProperties por esse campo.
- JSON Schema format checking está ativo com Draft202012Validator.FORMAT_CHECKER; não alego que UUIDs/datas inválidos passam pelo gate normal.
- Referencing é dependência obrigatória (`referencing>=0.35`); o fallback sem registry não foi classificado como defeito do ambiente suportado.
- Falta de findings[] em Evidence NÃO é bug: ADR-11 separa Layer 2 dos artefatos Markdown.
- Imutabilidade normal de TargetSnapshot/MethodologyState está protegida por frozen dataclass e cópia MappingProxyType; não alego bypass com object.__setattr__ como vulnerabilidade real.
- Limiar de max_retries (`len(attempts) > max_retries`) não é off-by-one: a tentativa inicial não é retry.
- Snapshot drift compara fingerprint, marca STALE/NOT_PUBLISHED e invalida evidências; fluxos normais cobertos pelos testes são coerentes. Não foram executados workers de drift.
- Ausência de fsync pode afetar perda de energia, mas não há prova executável de perda real neste escopo; não classificada como achado.
- Caminhos de estado aceitam identificadores como strings sem sanitização, mas identificadores normais são UUID/SHA validados/gerados; sem cadeia de entrada hostil demonstrada, não foi reportado path traversal.
- Não alego que artifacts registrados por basename existam fisicamente: o gate é denominado registered, e registro ≠ validação física. S17 demonstra referência interna efetivamente incorreta no produtor.
- Egress não foi testado em rede. Falha do gate é provada, eventual rejeição adicional por backend concreto deve ser considerada.
- API publica aceita estados inválidos; isso não prova que o happy path do runtime crie tais estados sozinho. Distinção registrada em S01/S02.
- S15/S16 são APIs latentes: severidade LOW; não há chamada normal identificada para produzir os estados de prova.

## Inventário de leitura

Arquivos abaixo lidos integralmente; nenhum modificado:

- `skills/universal/project-audit/docs/directives/astra_audit_directive.md` (27 linhas; SHA-256 `394c91a83574b5fb7b54addc356826f53f8f581cc99f98868474d2a5de6a9bee`)

- `docs/decisions/ADR-11-v1-single-agent-deterministic-first.md` (42 linhas; SHA-256 `affccc40dbfc6ef5f5598e5e26e1d4f4ca754c8c0c01a1b8a1d122c30f33b597`)

- `skills/universal/project-audit/src/project_audit/models.py` (799 linhas; SHA-256 `84c1a5ec9d4b5426901c5cfd59a64492de001f1a2d5c2d0a1da12f0282a43eca`)

- `skills/universal/project-audit/src/project_audit/validators.py` (770 linhas; SHA-256 `7f41a72017595499e0396854a1e0c09ed8d4a38595ac2fd073cfe6474da9cd17`)

- `skills/universal/project-audit/src/project_audit/schema_validator.py` (129 linhas; SHA-256 `669e142eb010a4761cf7906617ce63d1f10f592634c871ab374e73db1b43a7ec`)

- `skills/universal/project-audit/src/project_audit/state_store.py` (372 linhas; SHA-256 `7283f80bd5314a6a72c152bd2c1c62044bdb1fd75c32a9bdafb52e8d8232c639`)

- `skills/universal/project-audit/src/project_audit/orchestrator.py` (488 linhas; SHA-256 `d15476a6dcf2d7c0ed8c9320a33b202744bd1aa4d4409e9d61efba4152acd49f`)

- `skills/universal/project-audit/src/project_audit/schemas/audit-plan.schema.json` (65 linhas; SHA-256 `b84711cf373f1e23ee5a0bf4f0e0ecc99a6ee740d0dadefdeeac7de9d632d753`)

- `skills/universal/project-audit/src/project_audit/schemas/audit-run.schema.json` (58 linhas; SHA-256 `721408ec2961d32614997acdaa7a38479830da608e3b9f3da89a9b0df504016d`)

- `skills/universal/project-audit/src/project_audit/schemas/audit-work-item.schema.json` (53 linhas; SHA-256 `529129ebe63d9cd54e26ecc33b4a7a1033eb4d266402e8da25990caf2a60353c`)

- `skills/universal/project-audit/src/project_audit/schemas/evidence.schema.json` (31 linhas; SHA-256 `c367b1956ed1d1fd025a3a42a18f52186be054e02ee5107a9e3bec5f363c707a`)

- `skills/universal/project-audit/src/project_audit/schemas/shared.schema.json` (68 linhas; SHA-256 `0776067d26e2db3dfc11ef19d270d4d6d412bfcaaa63a21ebcdecac2c39c2e31`)

- `skills/universal/project-audit/src/project_audit/schemas/target-snapshot.schema.json` (63 linhas; SHA-256 `16fa4d2cb1cf709e19e2cec3a4f4ab89aa8d5ce76a0dfb90c6c2368b3b1e226c`)

- `skills/universal/project-audit/tests/conftest.py` (201 linhas; SHA-256 `90ae196ce908ebfe19552911c8ca1f3394a63e03ef7928975f8e8bbac9487d8b`)

- `skills/universal/project-audit/tests/test_models.py` (315 linhas; SHA-256 `53fac4af8c9df92522c5d6ab5dc6cbd33312d146a43c6c13d96c034499892bcc`)

- `skills/universal/project-audit/tests/test_validators.py` (497 linhas; SHA-256 `7368d947447a9af74a14af29d956ae146d7b01e7df34b1e1a9c4b45918ce4410`)

- `skills/universal/project-audit/tests/test_state_store.py` (188 linhas; SHA-256 `3eb2779715fbe82dc74861315bb4d6d59e31574b2f817b7eb40334e82fb82515`)

- `skills/universal/project-audit/tests/test_hardening.py` (879 linhas; SHA-256 `65e350e70c4658e26583020895bde9487a6c97932114e8125593ea058069c0d5`)

- `skills/universal/project-audit/tests/test_integration.py` (372 linhas; SHA-256 `0580851f85d37e846a23a57367b939a6b0be0df7c3616e8e564e951678853166`)

- `skills/universal/project-audit/tests/test_snapshot_drift.py` (219 linhas; SHA-256 `4d207da3a5ae6d11c8e38aff5b9ec7bc1763e331395af5c4bd63a45382259b79`)

- `skills/universal/project-audit/pyproject.toml` (36 linhas; SHA-256 `de700a706ca401d4f1b706ae8a43dcafa8fceda56b333db7cbf17aaf72e52eb5`)


Leitura parcial de evidência de contrato:

- `skills/universal/project-audit/src/project_audit/delegation.py:75-150`: uso do gate egress antes de delegate.
- Resultados de `rg -n` para `commit_run|can_publish|load_plan|load_evidence|validate_egress_policy|validate_work_item|execute_vertical_slice|start_attempt|finish` nos `.py` de src/project_audit: localizar chamadas, não auditoria integral dos demais módulos.
- `/home/oliveira/.codex/plugins/cache/openai-curated-remote/superpowers/6.4.1/skills/using-superpowers/SKILL.md`: lido como instrução; exclusão explícita para subagente.
- `git status --short skills/universal/project-audit`: alterações locais existentes em __main__.py/omniroute_backend.py e arquivos não rastreados foram preservados.

Leituras parciais adicionais para checar contrato de S17:

- `docs/references/canonical-data-model.md:64,97` via rg: artifact_refs são pointers para Markdown/Evidence; não foi auditado como alvo.
- `docs/references/semantic-validators.md` pesquisado via rg sem correspondência para os termos.
- `src/project_audit/security_runner.py:78` e `engineering_runner.py:107` via rg: receipts iniciam artifact_refs vazios.


---

## Apêndice II — discovery, classificação, pipeline e artefatos

# Auditoria parcial Astra — discovery, classificação, plano, engenharia e artefatos

Data: 2026-09-24. Somente leitura do alvo. Auto-fix OFF. Scripts, fixtures e evidências apenas em `/tmp/astra-pipeline/`. Sem rede e sem worker semântico. Dependência audit-normalize lida/usada apenas como contrato; nenhum achado atribuído a ela.

## Reexecução

```sh
PYTHONDONTWRITEBYTECODE=1 python3 /tmp/astra-pipeline/prove.py
```

Saída capturada: `/tmp/astra-pipeline/proofs.jsonl`. Dez cenários reproduzidos. A prova usa apenas bibliotecas locais instaladas (jsonschema, markdown). Tentativa pytest nos quatro arquivos diretamente relacionados falhou antes da coleta porque `/usr/bin/python3` não tem pytest. O agente principal executou a suíte completa usando `/tmp/astra-audit-env/bin/python`; não houve repetição desta frente. As dez provas diretas rodaram com sucesso.

## PIPE-01 — P1 — Plano FULL omite três categorias de engenharia implementadas

**Tipo:** Logic Gap.

**Por quê:** classify_applicability só gera seis superfícies de engenharia; BUILD, CONFIGURATION e DOCUMENTATION nunca entram nas decisões. build_plan deriva todos os work items exclusivamente dessas decisões, embora EngineeringAuditor já tenha handlers das três categorias e render_report possua seções próprias. O runtime termina com coverage FULL mesmo quando package.json, config.yaml e README.md são classificados e nenhuma dessas superfícies é inspecionada. Não se exige análise semântica completa: o defeito é perder até a inspeção determinística já implementada.

**Código exato:**

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/classifiers.py:175-196`

```python
def classify_applicability(snapshot: DiscoverySnapshot, stack: Iterable[str]) -> Tuple[ApplicabilityDecision, ...]:
    stack_set = set(stack)
    classifications = classify_files(snapshot)
    paths = {item.path.lower() for item in snapshot.files}
    source_paths = tuple(item.path for item in classifications if item.kind in {FileKind.SOURCE, FileKind.TEST})
    decisions = []

    def add(category: str, subcategory: str, state: ApplicabilityState, reason: str, evidence: Tuple[str, ...] = ()) -> None:
        decisions.append(ApplicabilityDecision(category, subcategory, state, reason, evidence))

    add("ARCHITECTURE", "STRUCTURE", ApplicabilityState.APPLICABLE if source_paths else ApplicabilityState.NOT_DETERMINABLE, "Source files provide an architecture surface" if source_paths else "No source files identified", source_paths[:8])
    add("CODE_QUALITY", "STATIC_REVIEW", ApplicabilityState.APPLICABLE if source_paths else ApplicabilityState.NOT_DETERMINABLE, "Source/test files identified" if source_paths else "No source files identified", source_paths[:8])
    tests = tuple(item.path for item in classifications if item.kind == FileKind.TEST)
    add("TESTING", "TEST_SUITE", ApplicabilityState.APPLICABLE if tests else ApplicabilityState.NOT_DETERMINABLE, "Test files identified" if tests else "No test files identified; absence is not proof of no test mechanism", tests[:8])
    db_evidence = tuple(p for p in paths if p.endswith(".sql"))
    db_present = "JDBC" in stack_set or "JPA_HIBERNATE" in stack_set or bool(db_evidence) or "POSTGRESQL" in stack_set or "MYSQL" in stack_set
    add("DATABASE", "PERSISTENCE", ApplicabilityState.APPLICABLE if db_present else ApplicabilityState.NOT_DETERMINABLE, "Database/persistence indicators found" if db_present else "No decisive persistence evidence", db_evidence[:8])
    ci_evidence = tuple(p for p in paths if p.startswith(".github/workflows/"))
    ci_present = bool(ci_evidence) or ".gitlab-ci.yml" in paths
    add("CI_CD", "PIPELINE", ApplicabilityState.APPLICABLE if ci_present else ApplicabilityState.NOT_DETERMINABLE, "CI configuration discovered" if ci_present else "No CI pipeline identified; absence is not proof of impossibility", ci_evidence[:8])
    infra_evidence = tuple(p for p in paths if Path(p).name in {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"})
    add("INFRASTRUCTURE", "CONTAINERS", ApplicabilityState.APPLICABLE if "DOCKER" in stack_set else ApplicabilityState.NOT_DETERMINABLE, "Docker artifacts discovered" if "DOCKER" in stack_set else "No deterministic container indicator", infra_evidence[:8])
```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/classifiers.py:213-223`

```python
    auth_signal = any(token in " ".join(stack_set).lower() for token in ("spring", "jwt", "oauth"))
    add("SECURITY", "AUTHENTICATION", ApplicabilityState.APPLICABLE if auth_signal else ApplicabilityState.NOT_DETERMINABLE, "Authentication-related stack signal found" if auth_signal else "No deterministic authentication mechanism identified")
    add("SECURITY", "AUTHORIZATION", ApplicabilityState.APPLICABLE if source_paths else ApplicabilityState.NOT_DETERMINABLE, "Authorization semantics require source inspection" if source_paths else "No source evidence")
    sql_present = "JDBC" in stack_set or "JPA_HIBERNATE" in stack_set or bool(db_evidence)
    add("SECURITY", "SQL_INJECTION", ApplicabilityState.APPLICABLE if sql_present else ApplicabilityState.NOT_DETERMINABLE, "SQL/persistence surface identified" if sql_present else "No decisive SQL surface evidence")
    file_surface = any(token in " ".join(paths) for token in ("upload", "download", "multipart", "attachment"))
    add("SECURITY", "FILE_SECURITY", ApplicabilityState.APPLICABLE if file_surface else ApplicabilityState.NOT_DETERMINABLE, "File-transfer surface indicated by paths" if file_surface else "No decisive file-transfer evidence")

    return tuple(decisions)


```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/planner.py:111-127`

```python
def build_plan(snapshot: TargetSnapshot, applicability: Iterable[ClassifiedApplicability]) -> Tuple[AuditPlan, Tuple[AuditWorkItem, ...]]:
    execution_policy, egress_policy = _default_policies()
    plan_id = str(uuid.uuid4())
    decisions = tuple(applicability)
    applicable = [d for d in decisions if d.state == ApplicabilityState.APPLICABLE]
    uncertain = [d for d in decisions if d.state == ApplicabilityState.NOT_DETERMINABLE]
    resolved = sorted({d.category for d in applicable} | {d.category for d in uncertain})
    requested_scope = ["FULL"]

    work_items = []
    for decision in sorted(decisions, key=lambda item: (item.category, item.subcategory)):
        if decision.state == ApplicabilityState.NOT_APPLICABLE:
            continue
        task = f"Audit {decision.category}/{decision.subcategory}"
        task_class = classify_task(task)
        evidence = ", ".join(decision.evidence_paths[:3]) or "no direct path evidence"
        work_items.append(
```

**Reprodução observada:**

```json
{
  "requested": [
    "FULL"
  ],
  "classes": [
    [
      ".gitignore",
      "GIT"
    ],
    [
      "README.md",
      "DOCUMENTATION"
    ],
    [
      "config.yaml",
      "CONFIG"
    ],
    [
      "package.json",
      "BUILD"
    ],
    [
      "src/app.py",
      "SOURCE"
    ]
  ],
  "inspections": [
    "ARCHITECTURE/STRUCTURE",
    "CI_CD/PIPELINE",
    "CODE_QUALITY/STATIC_REVIEW",
    "DATABASE/PERSISTENCE",
    "INFRASTRUCTURE/CONTAINERS",
    "TESTING/TEST_SUITE"
  ],
  "coverage": "FULL"
}
```

**Direção de correção (não aplicada):** Pedir cobertura de BUILD/CONFIGURATION/DOCUMENTATION na matriz e no plano e derivar cobertura do escopo esperado, não apenas de work items criados.

## PIPE-02 — P1 — Discovery segue symlink de arquivo para fora do alvo

**Tipo:** Architecture Flaw.

**Por quê:** followlinks=False só impede descer em diretórios symlink. path.stat(), path.open() e path.read_bytes() seguem symlinks de arquivos. Assim linked.py dentro do alvo importa bytes de outside.py fora dele, registra-os sob identidade relativa enganosa e os auditores os tratam como fonte do projeto. A prova confirma observação TODO originada exclusivamente fora do alvo. Não foi feito acesso a dados reais externos nem chamada semântica; a extrapolação para egress depende das políticas posteriores.

**Código exato:**

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/discovery.py:81-99`

```python
def _discover_files(root: Path) -> Tuple[FileRecord, ...]:
    records = []
    for current_root, dirs, filenames in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        for filename in sorted(filenames):
            path = Path(current_root) / filename
            try:
                size = path.stat().st_size
            except OSError:
                continue
            relative = path.relative_to(root).as_posix()
            records.append(
                FileRecord(
                    path=relative,
                    size=size,
                    sha256=_sha256(path),
                    binary=_is_binary(path),
                )
            )
```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/discovery.py:70-78`

```python
def _sha256(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None
```

**Reprodução observada:**

```json
{
  "target": "/tmp/astra-pipeline/case-r1yz5g73/link",
  "files": [
    "linked.py"
  ],
  "todo": [
    [
      "linked.py"
    ]
  ],
  "outside": "/tmp/astra-pipeline/case-r1yz5g73/outside.py"
}
```

**Direção de correção (não aplicada):** Validar tipo e destino real antes de ler; definir explicitamente se symlinks internos são permitidos e representar a identidade do link no snapshot.

## PIPE-03 — P1 — FIFO bloqueia discovery sem deadline

**Tipo:** Bug.

**Por quê:** os.walk entrega FIFO em filenames, stat funciona, mas abrir FIFO para leitura bloqueia aguardando escritor. Não existe verificação stat.S_ISREG nem timeout do hashing. A execução trava antes de criar run e as políticas de timeout dos work items não a limitam. A prova cria apenas FIFO temporário; subprocesso foi encerrado após um segundo.

**Código exato:**

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/discovery.py:81-97`

```python
def _discover_files(root: Path) -> Tuple[FileRecord, ...]:
    records = []
    for current_root, dirs, filenames in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP_DIRS)
        for filename in sorted(filenames):
            path = Path(current_root) / filename
            try:
                size = path.stat().st_size
            except OSError:
                continue
            relative = path.relative_to(root).as_posix()
            records.append(
                FileRecord(
                    path=relative,
                    size=size,
                    sha256=_sha256(path),
                    binary=_is_binary(path),
```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/discovery.py:70-78`

```python
def _sha256(path: Path) -> Optional[str]:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None
```

**Reprodução observada:**

```json
"discovery blocks on FIFO open; child killed after 1 second"
```

**Direção de correção (não aplicada):** Rejeitar/excluir explicitamente entradas que não sejam arquivos regulares, registrando a exclusão ou erro.

## PIPE-04 — P1 — COMMIT aceita e audita conteúdo ausente do commit

**Tipo:** Bug.

**Por quê:** git status limpo não garante igualdade do filesystem com HEAD: arquivos ignorados não aparecem no status. prepare_audit aceita esse estado e _input_fingerprints inclui todos os arquivos descobertos independentemente de target_mode. A prova produz TargetMode.COMMIT com ignored.py não existente na árvore HEAD. Isso viola o binding do relatório ao commit anunciado. As mesmas premissas não cobrem assume-unchanged/skip-worktree, mas esses casos não foram necessários à prova.

**Código exato:**

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/planner.py:169-186`

```python
def prepare_audit(
    discovery: DiscoverySnapshot,
    files: Tuple[FileClassification, ...],
    applicability: Tuple[ClassifiedApplicability, ...],
    target_mode: TargetMode = TargetMode.WORKTREE,
) -> PreparedAudit:
    if target_mode == TargetMode.COMMIT:
        if not discovery.git.is_repository:
            raise ValueError("COMMIT target mode requires a Git repository.")
        if discovery.git.working_tree_dirty:
            raise ValueError(
                "COMMIT target mode requires a clean working tree; "
                "the current filesystem does not provably equal HEAD."
            )

    snapshot = build_target_snapshot(discovery, target_mode=target_mode)
    plan, work_items = build_plan(snapshot, applicability)
    return PreparedAudit(snapshot, plan, work_items, files, applicability)
```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/planner.py:70-79`

```python

def _input_fingerprints(snapshot: DiscoverySnapshot, target_mode: TargetMode) -> Tuple[TrackedInputFingerprint, ...]:
    # V1 re-runs the entire audit: fingerprint every discovered input, including
    # untracked and binary files, instead of a dependency/configuration subset.
    rows = []
    for item in snapshot.files:
        if item.sha256 is None:
            raise ValueError(f"Cannot fingerprint audit input: {item.path}")
        rows.append(TrackedInputFingerprint(item.path, item.sha256))
    return tuple(sorted(rows, key=lambda item: item.path))
```

**Reprodução observada:**

```json
{
  "git_status": "",
  "head_files": [
    ".gitignore",
    "app.py"
  ],
  "snapshot_files": [
    ".gitignore",
    "app.py",
    "ignored.py"
  ],
  "mode": "COMMIT"
}
```

**Direção de correção (não aplicada):** Materializar a árvore do commit ou verificar a igualdade de cada entrada auditada com HEAD, com semântica explícita para ignorados/submodules.

## PIPE-05 — P1 — Texto livre de evidência sobrescreve campos no Markdown normalizado

**Tipo:** Bug.

**Por quê:** O writer interpola título/evidence/description/cause/impact diretamente na gramática de campos do normalizador. O candidato validado tem severity P2 e confidence MEDIUM; uma linha literal Severity: P0 e Confidence: HIGH dentro de evidence é serializada como se fosse campo. O parser real de audit-normalize reclassifica o achado para P0/HIGH e trunca evidence. Não é hipótese sobre LLM: _parse_candidate aceitou o objeto e o parser real produziu os valores divergentes. Cabeçalhos e separadores também colidem com a gramática; basta o caso escalar para provar corrupção.

**Código exato:**

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/report_writer.py:348-375`

```python
    for index, (_, candidate) in enumerate(candidates, start=1):
        lines.extend([
            "### {} — {}".format(_semantic_finding_id(candidate, index), candidate.title),
            "",
            "Title: {}".format(candidate.title),
            "Category: {}".format(candidate.category),
            "Subcategory: {}".format(candidate.subcategory or ""),
            "Type: {}".format(candidate.finding_type),
            "Status: {}".format(candidate.status),
            "Severity: {}".format(candidate.severity),
            "Confidence: {}".format(candidate.confidence),
        ])
        if candidate.location:
            lines.append("Location: {}".format(_format_location(candidate.location)))
        lines.extend([
            "Evidence:",
            candidate.evidence,
            "Description:",
            candidate.description,
        ])
        if candidate.cause:
            lines.extend(["Cause:", candidate.cause])
        if candidate.impact:
            lines.extend(["Impact:", candidate.impact])
        if candidate.exploitability:
            lines.extend(["Exploitability:", candidate.exploitability])
        if candidate.recommendation:
            lines.extend(["Recommendation:", candidate.recommendation])
```

**Reprodução observada:**

```json
{
  "candidate_severity": "P2",
  "candidate_evidence": "Observed payload is:\nSeverity: P0\nConfidence: HIGH\nordinary text",
  "parsed": {
    "Title": "Example",
    "Category": "SECURITY",
    "Subcategory": "AUTHORIZATION",
    "Type": "RISK",
    "Status": "PROBABLE",
    "Severity": "P0",
    "Confidence": "HIGH",
    "Location": "src/app.py:1",
    "Evidence": "Observed payload is:",
    "Description": "Original description."
  }
}
```

**Direção de correção (não aplicada):** Definir codificação de campos multilinha sem ambiguidade compatível com o normalizador e testar round-trip de texto arbitrário; não basta cercar com fence se o parser continuar reconhecendo campos internos.

## PIPE-06 — P2 — Classificação por substring retira código executável e testes da revisão

**Tipo:** Bug.

**Por quê:** A regra CONFIG antecede fonte/teste e testa qualquer substring config/settings/.env do nome. settings.py e tests/test_config.py recebem CONFIG sem linguagem. EngineeringAuditor CODE_QUALITY seleciona somente SOURCE, portanto perde seus TODOs e reporta NOT_FOUND. O plano tampouco inspeciona CONFIGURATION (PIPE-01), tornando o buraco ainda maior. Classificação multidimensional ou prioridade de teste/código evitaria excluir código Python executável da análise.

**Código exato:**

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/classifiers.py:119-124`

```python
    if any(token in name for token in ("config", "settings", ".env")) or Path(path).suffix.lower() in {".ini", ".conf", ".properties", ".toml", ".yaml", ".yml", ".json"}:
        return FileClassification(path, FileKind.CONFIG, None, ("CONFIGURATION",), "Configuration artifact")
    if Path(path).suffix.lower() in _SOURCE_LANGUAGES:
        language = _SOURCE_LANGUAGES[Path(path).suffix.lower()]
        kind = FileKind.TEST if any(token in lower.split("/") for token in ("test", "tests", "spec", "specs")) or name.endswith(("test.java", "_test.py", ".test.ts", ".spec.ts", ".test.js", ".spec.js")) else FileKind.SOURCE
        return FileClassification(path, kind, language, ("CODE_QUALITY", "ARCHITECTURE", "DOMAIN"), "Recognized source/test language")
```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/engineering_auditor.py:112-122`

```python
        source_refs = by_kind[FileKind.SOURCE]
        todo_refs = []
        broad_exception_refs = []
        for path in source_refs:
            text = _read_text(snapshot, path)
            if "TODO" in text or "FIXME" in text:
                todo_refs.append(path)
            if "except Exception:" in text or "catch (Exception" in text:
                broad_exception_refs.append(path)
        observations.extend(
            [
```

**Reprodução observada:**

```json
{
  "classes": [
    [
      "settings.py",
      "CONFIG"
    ],
    [
      "test_app.py",
      "SOURCE"
    ],
    [
      "tests/test_config.py",
      "CONFIG"
    ]
  ],
  "observations": [
    {
      "code": "CODE-INV-001",
      "category": "CODE_QUALITY",
      "subcategory": "STATIC_REVIEW",
      "state": "OBSERVED",
      "summary": "1 source file(s) classified for engineering review.",
      "source_refs": [
        "test_app.py"
      ]
    },
    {
      "code": "CODE-INV-002",
      "category": "CODE_QUALITY",
      "subcategory": "STATIC_REVIEW",
      "state": "NOT_FOUND",
      "summary": "No TODO/FIXME markers were found in the inspected source files.",
      "source_refs": []
    },
    {
      "code": "CODE-INV-003",
      "category": "CODE_QUALITY",
      "subcategory": "STATIC_REVIEW",
      "state": "NOT_FOUND",
      "summary": "No broad exception handlers matched the deterministic patterns.",
      "source_refs": []
    }
  ]
}
```

**Direção de correção (não aplicada):** Preservar SOURCE/TEST e linguagem para extensões de código, usando domínio de configuração adicional quando aplicável.

## PIPE-07 — P2 — Probe binário lê arquivo inteiro apesar do limite de 8192

**Tipo:** Bug.

**Por quê:** read_bytes() aloca todo o arquivo antes do slice. O probe supostamente limitado a 8192 bytes consumiu mais de 8 MiB para arquivo de 8 MiB; crescimento é linear ao maior arquivo. Arquivos binários/grandes são descobertos normalmente e repetidos nos checks de drift. O mesmo padrão ocorre nas leituras limitadas de classificadores/engenharia; limites de conteúdo não limitam I/O ou memória. A prova usa tracemalloc e 8 MiB, sem provocar OOM.

**Código exato:**

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/discovery.py:62-67`

```python
def _is_binary(path: Path) -> bool:
    try:
        data = path.read_bytes()[:_BINARY_PROBE]
    except OSError:
        return False
    return b"\x00" in data
```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/classifiers.py:133-138`

```python
def _read_text(snapshot: DiscoverySnapshot, path: str, limit: int = 128_000) -> str:
    try:
        data = (snapshot.root / path).read_bytes()[:limit]
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")
```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/engineering_auditor.py:43-48`

```python
def _read_text(snapshot: DiscoverySnapshot, path: str, limit: int = 128_000) -> str:
    try:
        raw = (snapshot.root / path).read_bytes()[:limit]
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace")
```

**Reprodução observada:**

```json
{
  "file_bytes": 8388608,
  "advertised_probe": 8192,
  "peak_allocated_bytes": 8396866
}
```

**Direção de correção (não aplicada):** Abrir stream binário e read(limit); usar hashing em chunks como já feito por _sha256.

## PIPE-08 — P2 — Evidências de aplicabilidade perdem case de caminhos

**Tipo:** Bug.

**Por quê:** paths é um set de strings lowercased, depois reutilizado como evidence_paths em DATABASE, CI_CD e INFRASTRUCTURE. Em Linux DB/Schema.SQL existe, mas a referência emitida db/schema.sql não existe. A referência inválida ainda vai para decision_basis canônico do plano. Iteração do set também não preserva ordenação determinística, embora esta prova focalize o erro de identidade.

**Código exato:**

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/classifiers.py:175-195`

```python
def classify_applicability(snapshot: DiscoverySnapshot, stack: Iterable[str]) -> Tuple[ApplicabilityDecision, ...]:
    stack_set = set(stack)
    classifications = classify_files(snapshot)
    paths = {item.path.lower() for item in snapshot.files}
    source_paths = tuple(item.path for item in classifications if item.kind in {FileKind.SOURCE, FileKind.TEST})
    decisions = []

    def add(category: str, subcategory: str, state: ApplicabilityState, reason: str, evidence: Tuple[str, ...] = ()) -> None:
        decisions.append(ApplicabilityDecision(category, subcategory, state, reason, evidence))

    add("ARCHITECTURE", "STRUCTURE", ApplicabilityState.APPLICABLE if source_paths else ApplicabilityState.NOT_DETERMINABLE, "Source files provide an architecture surface" if source_paths else "No source files identified", source_paths[:8])
    add("CODE_QUALITY", "STATIC_REVIEW", ApplicabilityState.APPLICABLE if source_paths else ApplicabilityState.NOT_DETERMINABLE, "Source/test files identified" if source_paths else "No source files identified", source_paths[:8])
    tests = tuple(item.path for item in classifications if item.kind == FileKind.TEST)
    add("TESTING", "TEST_SUITE", ApplicabilityState.APPLICABLE if tests else ApplicabilityState.NOT_DETERMINABLE, "Test files identified" if tests else "No test files identified; absence is not proof of no test mechanism", tests[:8])
    db_evidence = tuple(p for p in paths if p.endswith(".sql"))
    db_present = "JDBC" in stack_set or "JPA_HIBERNATE" in stack_set or bool(db_evidence) or "POSTGRESQL" in stack_set or "MYSQL" in stack_set
    add("DATABASE", "PERSISTENCE", ApplicabilityState.APPLICABLE if db_present else ApplicabilityState.NOT_DETERMINABLE, "Database/persistence indicators found" if db_present else "No decisive persistence evidence", db_evidence[:8])
    ci_evidence = tuple(p for p in paths if p.startswith(".github/workflows/"))
    ci_present = bool(ci_evidence) or ".gitlab-ci.yml" in paths
    add("CI_CD", "PIPELINE", ApplicabilityState.APPLICABLE if ci_present else ApplicabilityState.NOT_DETERMINABLE, "CI configuration discovered" if ci_present else "No CI pipeline identified; absence is not proof of impossibility", ci_evidence[:8])
    infra_evidence = tuple(p for p in paths if Path(p).name in {"dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"})
```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/planner.py:125-136`

```python
        task_class = classify_task(task)
        evidence = ", ".join(decision.evidence_paths[:3]) or "no direct path evidence"
        work_items.append(
            AuditWorkItem(
                work_item_id=str(uuid.uuid4()),
                plan_ref=plan_id,
                auditor="project-audit/single-agent",
                target_surface=f"{decision.category}/{decision.subcategory}",
                action=WorkItemAction.REAUDIT,
                decision_basis=(
                    f"Applicability={decision.state.value}; {decision.reason}; "
                    f"task_kind={task_class.kind.value}; deterministic_first=true; evidence={evidence}"
```

**Reprodução observada:**

```json
{
  "actual": [
    "DB/Schema.SQL"
  ],
  "evidence": [
    "db/schema.sql"
  ],
  "exists": [
    false
  ]
}
```

**Direção de correção (não aplicada):** Preservar paths originais e usar lower apenas para matching; ordenar a coleção antes de cortar os limites de evidência.

## PIPE-09 — P3 — Iterable de revisões é consumido antes de escrever ledger

**Tipo:** Bug.

**Por quê:** write_audit_artifacts aceita Iterable, incluindo generators; render_report o consome e render_ledger recebe o mesmo iterator já esgotado. Uma revisão produz SEM-001 no analytical, mas não no ledger. O runtime atual passa tuple e não sofre este caso; é defeito confirmado na API pública reutilizável do writer.

**Código exato:**

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/report_writer.py:414-423`

```python
        "- Semantic confirmation is required before creating CONFIRMED findings.",
        "",
    ])
    return "\n".join(lines)


def write_audit_artifacts(
    output_dir: str,
    prepared: PreparedAudit,
    discovery: DiscoverySnapshot,
```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/report_writer.py:444-452`

```python
    rendered = {
        "inventory": render_inventory(prepared, discovery),
        "coverage": render_coverage(prepared, engineering, security),
        "report": render_report(prepared, discovery, engineering, security, semantic_reviews),
        "ledger": render_ledger(engineering, security, semantic_reviews),
    }
    for key in ("inventory", "coverage", "report", "ledger"):
        _write(Path(paths[key]), rendered[key], overwrite)
    return paths
```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/report_writer.py:327-333`

```python
def render_semantic_findings(
    reviews: Iterable[SemanticReviewResult],
) -> str:
    candidates = []
    for review in reviews:
        for candidate in review.candidates:
            candidates.append((review.work_item_ref, candidate))
```

**Reprodução observada:**

```json
{
  "report_has_semantic": true,
  "ledger_has_semantic": false
}
```

**Direção de correção (não aplicada):** Materializar semantic_reviews uma vez no início antes dos dois renders.

## PIPE-10 — P3 — Timeout devolve stdout bytes em contrato str

**Tipo:** Bug.

**Por quê:** TimeoutExpired.stdout pode conter bytes mesmo com subprocess.run(text=True). O handler copia exc.stdout diretamente ao campo anotado str. Processo local que imprime started e excede 0,1s produz FAILED com stdout bytes; json.dumps(dataclasses.asdict(result)) falha TypeError. Não é demonstrada falha no CLI atual: o impacto provado é quebra do contrato do resultado e de consumidores JSON.

**Código exato:**

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/normalization_runner.py:9-16`

```python
@dataclass(frozen=True)
class NormalizationResult:
    status: str
    command: Tuple[str, ...]
    return_code: Optional[int]
    output_dir: str
    stdout: str
    stderr: str
```

`/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/normalization_runner.py:48-56`

```python
    except subprocess.TimeoutExpired as exc:
        return NormalizationResult(
            status="FAILED",
            command=tuple(argv),
            return_code=None,
            output_dir=output_dir,
            stdout=exc.stdout or "",
            stderr="audit-normalize timed out after {} seconds".format(timeout_seconds),
        )
```

**Reprodução observada:**

```json
{
  "status": "FAILED",
  "stdout_type": "bytes",
  "serialization_error": "Object of type bytes is not JSON serializable"
}
```

**Direção de correção (não aplicada):** Decodificar stdout/stderr capturados no caminho de timeout antes de construir NormalizationResult.

## Observação adicional comprovada, menor prioridade

`classifiers.py:123` reconhece `*_test.py` mas não o padrão Python/pytest `test_*.py` fora de diretórios test/tests. A mesma prova PIPE-06 contém `test_app.py` na raiz, classificado SOURCE. Não misturar com substring CONFIG: é outra condição da mesma classificação. Pode ser achado P2/P3 conforme suporte esperado à convenção Python.

## Hipóteses descartadas / delimitações

- fake_auditor.py usa placeholder explícito de target_snapshot_ref; FakeAuditorWithSnapshot corrige o binding. Não reportado como bug de produção porque o módulo é fake de teste e wrapper existe.
- IDs SEM baseados em sequence são declarados estáveis dentro de um conjunto de artefatos, não entre runs. UUID aleatório de work item no sort não viola essa garantia restrita.
- _inspection_result retorna NOT_DETERMINABLE para OBSERVED; condiz com não promover observações determinísticas a achados conclusivos.
- NOT_DETERMINABLE ainda gera work item no plano: não existe exclusão silenciosa dos domínios incertos nesta função.
- Normalização com return code 2 é tratada como COMPLETED_WITH_WARNINGS intencionalmente; faltarem os quatro arquivos torna FAILED. Não atribuída falha por não reinspecionar schema da ferramenta dependente.
- Escrita normal de artifacts preflighta todos os destinos quando overwrite=False, evitando sobrepor parcialmente um conjunto já existente. Atomicidade do conjunto sob falha de disco e restauração runtime pertencem à frente runtime.
- Campos HTML/Vue/Svelte UNKNOWN excluídos de security/context foram confirmados e serão reportados pela frente semantic, evitando duplicação.
- Limitações declaradas de análise semântica e detectores de tokens não foram promovidas automaticamente a bugs; só estão acima gaps específicos com saída falsa/incompleta demonstrada.
- Exceções não tratadas de EngineeringAuditor e estados persistidos são cobertos pelas frentes runtime/state; nenhuma inferência de recuperação foi adicionada aqui.

## Inventário de leitura

Todos os nove módulos atribuídos foram lidos integralmente (1.915 linhas).

- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/discovery.py` (132 linhas, SHA256 `52ca2b926903d4ced36109edc2e641ded7f6a717335a4be88fb13ee1bd059d59`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/classifiers.py` (232 linhas, SHA256 `194ed9dca43ae19a09399c415422f5877af43591ecfbfa7c6210e1072024a8e1`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/planner.py` (186 linhas, SHA256 `7db81cab94307f8e4f32c8a10da6f7c2fb54288abd0409249b229fd4043dc574`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/engineering_auditor.py` (379 linhas, SHA256 `6c26a188c6a38eba0d6d152642524b9c9532bbc277471ec94c1187e0aa72bff0`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/engineering_runner.py` (206 linhas, SHA256 `43091a9abfdb32dde057366c7b3e297496b29f718632aa89fdc87d7e13283630`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/report_writer.py` (452 linhas, SHA256 `cc0b3e860aba3741f41f35bdaf0349f42066dbe408553adc2ccfa11ca0584964`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/normalization_runner.py` (88 linhas, SHA256 `4c68dedac9f209b6146ef438394ec392517fa7a347184e757138635c03f69555`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/fake_auditor.py` (183 linhas, SHA256 `2e4bf99e35e2f0bfe4a97ead5f373567dd1a0debb7911015255fa83b33460468`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/__init__.py` (57 linhas, SHA256 `efcbcc15a2c5d0cd163f8c623e40afc8b7663e30245f52ae58f00faa3e78485d`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/tests/test_runtime_preparation.py` (102 linhas, SHA256 `5d46213d99cca5b85d839f34f3c8ff70d3ba87709c7a8542cbfcd7c059ad12d7`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/tests/test_engineering_pass.py` (61 linhas, SHA256 `97aa6813be94212a8fb93c3c59b747fe52dbc19b12ac0badd860ab3f8bcee215`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/tests/test_normalization_runner.py` (73 linhas, SHA256 `c8a6210f2efa109d0f7075f0fce182845dd566946774dd93eecfdca580789a7f`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/tests/test_report_writer.py` (141 linhas, SHA256 `12d3cdc1ebcb1b0d304a9f9371908864c03ac8e294499b855aaaa7c3b5d3df87`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/tests/test_runtime_e2e.py` (135 linhas, SHA256 `eec04834654b9bf3ada3a673fb8ff653cb15a6138c60a48551a2c720cd358bb9`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/docs/directives/astra_audit_directive.md` (27 linhas, SHA256 `394c91a83574b5fb7b54addc356826f53f8f581cc99f98868474d2a5de6a9bee`).
- Integral: `/home/oliveira/Projects/SKILLS/docs/decisions/ADR-11-v1-single-agent-deterministic-first.md` (42 linhas, SHA256 `affccc40dbfc6ef5f5598e5e26e1d4f4ca754c8c0c01a1b8a1d122c30f33b597`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/pyproject.toml` (36 linhas, SHA256 `de700a706ca401d4f1b706ae8a43dcafa8fceda56b333db7cbf17aaf72e52eb5`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/runtime.py` (188 linhas, SHA256 `7b655aa3aee7fd8680f5662e1ccf03937f320030e5502d3dc8164dc2eae08548`).
- Integral: `/home/oliveira/Projects/SKILLS/skills/universal/project-audit/src/project_audit/context_builder.py` (135 linhas, SHA256 `42b73e01467c140f30c71c2e57e0671888895fea22202d1c4575c3a6ba512071`).
- Parcial: `tests/test_hardening.py` (primeira leitura teve truncamento; não contado como leitura integral); buscas textuais em demais testes/docs e snapshot_drift.
- Parcial como contrato: `src/project_audit/semantic_auditor.py:1-140`; `_parse_candidate`, dataclasses e validação de campos.
- Parcial como contrato externo: `skills/universal/audit-normalize/src/audit_normalize/parser.py:612-785` e símbolos encontrados via rg; executado extract_raw_entities real para prova PIPE-05.
- Skill de processo lida: `/home/oliveira/.codex/plugins/cache/openai-curated-remote/superpowers/6.4.1/skills/using-superpowers/SKILL.md`; cláusula SUBAGENT-STOP aplicável.


---

## Apêndice III — semântica, contexto e segurança

# Revisão factual — frente semântica e segurança

Data: 2026-09-24. Alvo: `skills/universal/project-audit`. Auditoria somente leitura; nenhuma fonte ou teste existente foi alterado. Nenhum worker externo/modelo/rede foi usado. Backend de prova é uma classe local que captura o request e devolve JSON fixo.

## Artefatos

- `/tmp/astra-semantic/prove.py`: reprodução determinística executada com êxito.
- `/tmp/astra-semantic/review.md`: este relatório.

Comando executado a partir da raiz do repositório:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=skills/universal/project-audit/src python /tmp/astra-semantic/prove.py
```

Resultado: exit code 0. Os fixtures foram criados em diretórios temporários e removidos automaticamente. `discover` executou consultas locais de metadados Git; não houve comandos recebidos de projetos nem acesso remoto. Não executei pytest nesta frente; a execução consolidada da suíte pertence ao agente principal.

## S-01 — P2 — Campos de localização nulos provocam TypeError fora da barreira de validação

**Tipo:** Bug de parser/lifecycle. **Confiança:** alta.

**Arquivo:** `src/project_audit/semantic_auditor.py:73–79`.

```python
    for key in ("line", "line_start", "line_end"):
        if key in value and value[key] is not None and (
            not isinstance(value[key], int) or value[key] < 1
        ):
            raise SemanticOutputError("location line fields must be positive integers")
    if "line_start" in value and "line_end" in value and value["line_end"] < value["line_start"]:
        raise SemanticOutputError("location.line_end cannot precede line_start")
```

O primeiro teste aceita explicitamente `None`; o segundo compara os valores mesmo quando nulos. JSON com `location={"file":"app.py","line":1,"line_start":null,"line_end":null}` tem uma localização válida pelo campo `line` e os campos opcionais nulos passam pela verificação individual, mas gera `TypeError`. Mesmo que se decidisse proibir essa representação, a saída deveria virar `INVALID_OUTPUT`, não derrubar o runner.

**Propagação:** `semantic_auditor.py:281–286` captura somente `SemanticOutputError`; `semantic_runner.py:34–40` persiste o attempt iniciado, chama `worker.review` e só depois persiste o receipt. Resultado comprovado:

```text
NULL_LOCATION {"exception": "'<' not supported between instances of 'NoneType' and 'NoneType'", "persisted_execution_state": "RUNNING", "attempt_finished_at": "None", "receipt_count": 0}
```

**Impacto:** uma resposta JSON do backend aborta a revisão, deixa attempt RUNNING e perde o registro durável do receipt da chamada já concluída. A prova usa o runner, Orchestrator e StateStore reais.

## S-02 — P3 — Limite de linha pode ser contornado por endpoint isolado de intervalo

**Tipo:** Bug de validação. **Confiança:** alta.

**Arquivo:** `src/project_audit/semantic_auditor.py:169–175`.

```python
        if isinstance(candidate.location.get("line_start"), int) and isinstance(
            candidate.location.get("line_end"), int
        ):
            if candidate.location["line_start"] > len(content_lines) or candidate.location["line_end"] > len(content_lines):
                raise SemanticOutputError(
                    "finding location range exceeds the supplied context for " + file_path
                )
```

`_validate_location` aceita `line_start` ou `line_end` isolado, porém a checagem do contexto exige os dois. Um candidate com `{"file":"app.py","line_start":99999}` para arquivo de uma linha é aceito pelo parser e pelo validador de contexto.

```text
OUT_OF_BOUNDS_START_ACCEPTED {'file': 'app.py', 'line_start': 99999}
```

**Impacto limitado:** a garantia de rejeitar linhas inexistentes é incompleta; metadado inventado passa pela validação. `report_writer._format_location` exibe somente o arquivo quando o intervalo está incompleto, reduzindo a visibilidade do dado inválido. Não demonstra uma vulnerabilidade real na aplicação auditada, nem se deve alegar que a evidência textual está semanticamente validada.

## S-03 — P3 — Limite por arquivo usa caracteres, embora o contrato seja bytes

**Tipo:** Bug de contabilização do contexto. **Confiança:** alta.

**Arquivo:** `src/project_audit/context_builder.py:28–30` e `:77–79,101`.

```python
def _read(snapshot: DiscoverySnapshot, path: str, limit: int) -> str:
    try:
        return (snapshot.root / path).read_text(encoding="utf-8", errors="replace")[:limit]
```

```python
    max_files: int = 12,
    max_bytes_per_file: int = 24_000,
    max_total_bytes: int = 96_000,
```

```python
        content = _read(snapshot, classification.path, max_bytes_per_file)
```

O slicing é feito em `str` decodificada, portanto conta caracteres Unicode. A prova usa 24.000 caracteres `á` em `app.py`:

```text
CONTEXT_BUDGET {"per_file_limit": 24000, "actual_file_bytes": 48000}
```

**Impacto:** viola o limite solicitado por arquivo e pode consumir o orçamento global com menos arquivos. O limite global usa encode e continua respeitado; não se provou e não se afirma egress de tamanho ilimitado. Há ainda leitura completa antes do slice, mas não medi memória nem executei arquivo enorme; isso não é registrado como outro achado.

## S-04 — P2 — Escalação semântica não preserva o arquivo que motivou a revisão

**Tipo:** Lacuna lógica na passagem de evidência. **Confiança:** alta para omissão de contexto; nenhum resultado de LLM presumido.

**Arquivos:** `src/project_audit/security_runner.py:103–116`, `semantic_runner.py:37–38`, `context_builder.py:90–101`.

```python
        needs_semantic = any(
            getattr(observation, "state", None) in {"OBSERVED", "NOT_DETERMINABLE"}
            for observation in result.observations
        )
        if semantic_worker is not None and needs_semantic:
            semantic_result = execute_semantic_review(
                orchestrator,
                discovery,
                run,
                item,
                semantic_worker,
                plan=plan,
                work_items=work_items,
            )
```

```python
    context = build_context(discovery, work_item.target_surface)
    result = worker.review(work_item, run, context)
```

```python
    ranked = sorted(
        candidates,
        key=lambda item: (-_score(item.path, item, category, subcategory), item.path),
    )

    items: List[ContextItem] = []
    total_bytes = 0
    for classification in ranked[:max_files]:
```

As `result.source_refs` que contêm a observação não são passadas ao construtor. O builder ordena por score de caminho e seleciona os 12 primeiros, independentemente da ocorrência encontrada. Fixture: 12 arquivos `a00.py` a `a11.py` contendo `x = 1`, mais `z.py` com `requests.get(user_url)`. Todos têm o mesmo score para SSRF; o único arquivo relevante fica fora:

```text
TRIGGER_EVIDENCE {"observed": ["z.py"], "supplied": ["a00.py", "a01.py", "a02.py", "a03.py", "a04.py", "a05.py", "a06.py", "a07.py", "a08.py", "a09.py", "a10.py", "a11.py"]}
```

**Impacto provado:** o modelo não recebe a ocorrência que disparou a escalação e não pode confirmar ou refutar esse sinal com a evidência enviada. Não é pedido de árvore de dependência V3: o achado é a perda de uma referência concreta já produzida na passagem determinística. Não afirmei que um worker real retornaria falso negativo, nem executei revisão externa. Também não afirmei que o indicador FULL sozinho equivale a completude semântica, pois o relatório distingue essas coisas.

## S-05 — P2 — Templates frontend reconhecidos como superfície XSS são excluídos da inspeção

**Tipo:** Bug de integração classificação/segurança. **Confiança:** alta.

**Arquivos:** `src/project_audit/classifiers.py` (`_SOURCE_LANGUAGES`, `classify_file`, `frontend_evidence`); `security_pass.py:57–64`; `context_builder.py:83–87`.

```python
    for item in classifications:
        if item.kind in {FileKind.GENERATED, FileKind.UNKNOWN}:
            continue
```

```python
    candidates = [
        item
        for item in classifications
        if item.kind not in {FileKind.GENERATED, FileKind.UNKNOWN}
        and not item.path.startswith(".git/")
    ]
```

`classify_applicability` reconhece extensões `.html`, `.vue` e `.svelte` como frontend, mas `classify_file` não tem regra para classificá-las e retorna UNKNOWN quando não há outra regra de nome/pasta. Assim os dois consumidores excluem essas superfícies.

A prova usa `index.html` contendo `<script>document.body.innerHTML = location.hash.slice(1);</script>`:

```text
TEMPLATE {"classification": "UNKNOWN", "xss": "NOT_FOUND", "context_files": 0}
```

**Impacto:** o scanner não encontra sequer o padrão literal `innerHTML =` em arquivo suportado pela decisão de aplicabilidade, e o contexto semântico não inclui o arquivo. A ausência da implementação V3 não explica essa contradição. O agente pipeline foi avisado e deixou a propriedade deste achado nesta frente para evitar duplicação.

## S-06 — P1 — Política nega conteúdo sensível, mas backend recebe segredo (duplicado da frente state)

Este achado deve ser consolidado com a prova de validators da frente state, não contado duas vezes.

**Arquivo:** `src/project_audit/validators.py:559–563`; encadeamento `semantic_auditor.py:225–250` → `delegation.py:117–134`.

```python
    if (
        policy.destination == EgressDestination.LOCAL_ONLY
        and not policy.allow_sensitive
        and is_sensitive
    ):
```

A negação é uma conjunção que só bloqueia uma combinação; `APPROVED_EXTERNAL, allow_sensitive=False` não bloqueia sequer dado classificado SECRET. A prova integrada envia apenas um segredo sintético a um backend local capturador:

```text
EGRESS {"destination": "APPROVED_EXTERNAL", "allow_sensitive": false, "detected": "SECRET", "status": "COMPLETED", "sent_secret": true}
EGRESS {"destination": "LOCAL_ONLY", "allow_sensitive": true, "detected": "SECRET", "status": "COMPLETED", "sent_secret": true}
EGRESS {"destination": "LOCAL_ONLY", "allow_sensitive": false, "detected": "SECRET", "status": "BLOCKED", "sent_secret": false}
```

**Impacto:** o caminho real SemanticAuditor/WorkerPort atravessa a política apesar da proibição `allow_sensitive=False`. Com backend externo configurado, o mesmo request transportaria o segredo. Não houve exfiltração real na prova. ADR-05 exige autorização explícita de WHAT/WHERE e `docs/architecture/single-agent-runtime.md:100` documenta o bloqueio quando `allow_sensitive=false`.

## Inventário de leitura

Leitura integral dos módulos atribuídos (prefixo `skills/universal/project-audit/src/project_audit/`):

- `semantic_auditor.py`
- `semantic_runner.py`
- `security_auditor.py`
- `security_runner.py`
- `security_pass.py`
- `context_builder.py`
- `sensitivity.py`
- `delegation.py`

Leitura integral adicional:

- `src/project_audit/discovery.py`
- `src/project_audit/classifiers.py`
- `src/project_audit/omniroute_backend.py`
- `tests/test_semantic_gate.py`
- `tests/test_security_pass.py`
- `tests/test_security_auditor.py`
- `tests/test_security_auditor_contract.py`
- `tests/test_delegation.py`
- `pyproject.toml`
- `SKILL.md`
- `docs/directives/astra_audit_directive.md`
- `docs/decisions/0001-v3-semantic-adjudication-architecture.md`
- Repositório: `docs/decisions/execution-safety-trust-boundary.md`

Leitura parcial para contratos (não declarar auditoria integral desses arquivos):

- `src/project_audit/validators.py`: cobertura/reuse/evidence e `validate_egress_policy`.
- `src/project_audit/models.py`: declaração de AuditRun; símbolos de Attempt/start_attempt localizados por busca.
- `src/project_audit/state_store.py`: cabeçalho/layout e funções iniciais de persistência.
- `src/project_audit/runtime.py`: início até persistência/retorno do full audit, com foco em binding da política e chamadas dos passes.
- `src/project_audit/report_writer.py`: resultados de busca e blocos relevantes de formatação de localização/semântica.
- `tests/conftest.py`: fixtures de policy/plan/work_item.
- `tests/test_hardening.py`: busca dos testes e descrições de egress; não lido integralmente.
- Repositório: `docs/architecture/single-agent-runtime.md`: fronteiras atuais/semânticas.
- `src/project_audit/schemas/shared.schema.json`: linhas da definição de EgressPolicy via busca.

## Hipóteses descartadas ou não elevadas a achado

1. **Enums incompatíveis entre semantic_auditor e OmniRoute:** as listas atuais de category/type/status/severity/confidence no prompt do backend coincidem com os conjuntos do parser. Sem bug demonstrado nesse vetor específico.
2. **`security.reviews` inexistente:** SecurityPassResult declara `semantic_reviews`; não apareceu erro desse nome nos módulos atribuídos.
3. **Default UNKNOWN libera contexto:** `assess_text` retorna UNKNOWN e `is_sensitive` o trata como sensível; default LOCAL_ONLY/false bloqueou de fato. O achado egress é a combinação de políticas, não uma classificação permissiva.
4. **Caller pode rebaixar SECRET via declared_sensitivity=PUBLIC:** `aggregate_assessments` escolhe a classificação mais restritiva; não há rebaixamento nessa operação.
5. **Observação determinística equivale automaticamente a vulnerabilidade:** security_pass emite OBSERVED/NOT_FOUND/NOT_DETERMINABLE e explicita limitações; não há promoção automática nesse módulo.
6. **Ausência do gate V3 prova bug atual:** ADR descreve evolução futura. Não contabilizei gate adversarial nem análise holística de fluxo ausentes como defeitos automaticamente.
7. **Contexto reduzido prova falso positivo IDOR/textContent específico:** sem worker e sem fixture histórica completa, só é demonstrável a omissão concreta de evidência em S-04. Não reexecutei a comparação histórica citada no ADR.
8. **JSON markers garantem imunidade semântica universal a prompt injection:** os testes demonstram separação estrutural/round-trip, não comportamento universal de modelo. Não aleguei ataque operacional bem-sucedido.
9. **SecurityAuditor legado tem prompt só com path:** confirmado por leitura, mas a limitação da API antiga não foi elevada a outro achado sem demonstrar seu uso efetivo no fluxo de produção atual. O runtime usa DeterministicSecurityAuditor + SemanticAuditor.
10. **Token/bytes global ilimitado:** limite total mede UTF-8; o bug demonstrado limita-se ao teto por arquivo.
11. **`bool` como linha inteira:** `isinstance(True,int)` aceitaria boolean; não executei prova separada nem elevei a novo achado (mesma família de validação de localização).
12. **Tipagem/rejeição de payload MCP:** backend lido para comparar contratos; os casos de extração de JSON/fences são propriedade do agente principal e não duplicados aqui.

## Limitações

Não há prova de comportamento de modelo, chamadas MCP reais, vazamento real ou exploração em projeto de terceiros. Severidades se referem ao motor e seus contratos observáveis. As provas usam retornos locais controlados e código real de parser, contexto, scanner, políticas, orquestrador e armazenamento. A numeração das linhas corresponde ao código lido durante esta revisão; o consolidado deve verificar eventuais edições concorrentes. Nenhuma correção foi aplicada. O agente principal consolidará documentação e persistência solicitadas pelo usuário.

## Adendo documental — grounding de candidates sem localização

Revisão adicional solicitada pelo agente principal, sem nova execução. Por inspeção de `semantic_auditor.py:87–90`, `evidence` só precisa ser string não vazia; `status=CONFIRMED` é permitido. Em `:152–154`:

```python
    for candidate in candidates:
        if candidate.location is None:
            continue
```

Logo um candidate estruturalmente completo com `location=None`, `evidence="unsupported"` e `status="CONFIRMED"` não tem a evidência comparada ao conteúdo fornecido (por exemplo, `print(1)`). Essa aceitação estrutural é uma propriedade do código; não depende de comportamento de modelo. A revisão não executou esse caso nem alegou falso positivo emitido por worker real.

**Classificação desta frente:** limitação de grounding, não achado independente. A localização opcional é deliberadamente aceita e pode ser legítima para achados transversais; evidência pode ser paráfrase em vez de substring literal. Não identifiquei contrato implementado que exija match literal. A exigência de um segundo gate semântico é evolução explícita do ADR V3 e não deve ser contada automaticamente como bug atual. O agente principal pode manter esse fato na seção de limitações e falsos positivos, distinguindo-o de S-02 (bounds prometidos mas contornáveis) e S-04 (evidência conhecida excluída antes da análise).
