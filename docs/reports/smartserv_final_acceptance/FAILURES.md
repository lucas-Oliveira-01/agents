# Falhas

## F-001 — Transporte full indisponível no sandbox

- severity: P1
- confidence: HIGH
- component: MCP client / sandbox network
- problem: full worktree não conseguiu abrir `http://127.0.0.1:20131/mcp` (`Operation not permitted`); retry escalado foi rejeitado pelo limite automático.
- evidence: `executions/001_full_worktree_final/`; smoke real anterior passou com acesso ao daemon.
- impact: impede semantic worker, normalização e prova de findings/publication para a matriz.
- reproduction: comando e stderr em `command.txt`, `stderr.log`, `metadata.json`.
- correction: nenhuma correção de código; bloqueador é autorização/rede externa ao pipeline.
- verification: health + smoke real MCP separado PASS.

## F-002 — `.git/index` do checkout somente leitura

- severity: P1
- confidence: HIGH
- component: repository provenance
- problem: `git add`/commit final falhou em `.git/index.lock: Read-only file system` após a revisão automática.
- evidence: status em `FULL_EXECUTION_LOG.md`; alterações permanecem no working tree.
- impact: o checkout principal não possui SHA final único; matriz usa candidato `/tmp` explicitamente identificado.
- correction: snapshot candidato commitado em `aa1eff1`/`3fc557c`; requer restauração da capacidade de escrita para integrar ao branch.
- verification: `git status` e SHA foram registrados antes da matriz.

## F-003 — Defeitos determinísticos corrigidos durante aceitação

- severity: P1/P2
- confidence: HIGH
- component: gateway, verifier, runtime, packaging
- problem: aliases com `NameError`, JSON/usage não robustos, cache de respostas incompletas, consolidação sem vínculo WorkItem, transporte fail-open, schema ausente no pacote e import ausente no drift.
- evidence: red/green logs e regressões em `tests/`.
- impact: cada defeito podia produzir crash, cache incorreto, publicação indevida, falso COMPLETE ou falha em controle adversarial.
- correction: patches documentados em `CHANGES.md` e commits candidatos `7f26173`, `5213a1c`, `3fc557c`.
- verification: project-audit 400, delegation 219, gateway 33, normalize 57+1 skip, drift 6 passed.
