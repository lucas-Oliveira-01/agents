"""Current-checkout SmartServ acceptance executor, never executes target code."""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from acceptance_capture import redact


def count_canonical_candidates(ledger_path):
    """PR #34 invariant: unique VC IDs in the verifier table, never raw strings."""
    path = Path(ledger_path)
    if not path.exists():
        return 0
    active = False
    ids = set()
    for line in path.read_text().splitlines():
        text = line.strip()
        if text == '## Independent Verifier':
            active = True
            continue
        if active and text.startswith('## '):
            break
        if active:
            match = re.match(r'^\|\s*(VC-[^|]+?)\s*\|', text)
            if match:
                ids.add(match.group(1).strip())
    return len(ids)


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


def prove_target(target):
    from project_audit.discovery import discover
    snapshot = discover(str(target))
    sha = git(target, 'rev-parse', 'HEAD')
    mismatches = []
    rows = []
    for item in snapshot.files:
        blob = subprocess.run(['git', '-C', str(target), 'show', f'{sha}:{item.path}'], capture_output=True)
        blob_hash = hashlib.sha256(blob.stdout).hexdigest() if blob.returncode == 0 else None
        rows.append({'path': item.path, 'worktree_sha256': item.sha256, 'commit_blob_sha256': blob_hash})
        if item.sha256 != blob_hash:
            mismatches.append(item.path)
    return {'repository': git(target, 'remote', 'get-url', 'origin'), 'branch': git(target, 'branch', '--show-current'),
            'target_commit': sha, 'working_tree': git(target, 'status', '--porcelain'),
            'timestamp': datetime.now(timezone.utc).isoformat(), 'mismatches': mismatches, 'files': rows}


def archive(vault, dest):
    """Sanitize text copies; record every changed hash instead of hiding redaction."""
    records = []
    if not vault.exists():
        return records
    for p in sorted(vault.rglob('*')):
        rel = p.relative_to(vault)
        if '.git' in rel.parts or not p.is_file():
            continue
        data = p.read_bytes()
        try:
            cleaned = redact(data.decode('utf-8')).encode()
        except UnicodeDecodeError:
            # Audit artifacts are text; do not blindly copy unknown binary stores.
            records.append({'path': str(rel), 'binary_not_copied': True})
            continue
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(cleaned)
        records.append({'path': str(rel), 'sha256_original': hashlib.sha256(data).hexdigest(),
                        'sha256_artifact': hashlib.sha256(cleaned).hexdigest(), 'redacted': data != cleaned})
    return records


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--target', type=Path, required=True)
    p.add_argument('--artifacts', type=Path, required=True)
    p.add_argument('--execution', required=True)
    p.add_argument('--mode', choices=['normalize', 'worktree', 'commit', 'incremental', 'drift', 'prepare', 'engineering', 'transient'], required=True)
    p.add_argument('--baseline')
    a = p.parse_args()
    dest = a.artifacts / 'executions' / a.execution
    dest.mkdir(parents=True, exist_ok=True)
    # External Git exclusion: no edit to the target's .git or tracked files.
    excludes = a.artifacts / 'analysis' / 'audit-excludes'
    excludes.write_text('/.audit/\n')
    os.environ.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='core.excludesFile', GIT_CONFIG_VALUE_0=str(excludes.resolve()))
    before = prove_target(a.target)
    (dest / 'target_before.json').write_text(json.dumps(before, indent=2))
    assert not before['mismatches'], 'Target materialization does not match commit'
    auditor = git(Path.cwd(), 'rev-parse', 'HEAD')
    info = {'execution': a.execution, 'mode': a.mode, 'auditor_commit': auditor, 'target_commit': before['target_commit'],
            'raw': None, 'canonical': None, 'verified': None, 'published': None, 'normalized': 'NOT_REQUESTED'}
    client = None
    drift_restore = None
    vault = a.target / '.audit'
    state = vault / 'runs'
    output = vault / a.execution
    exit_code = 1
    try:
        if a.mode in {'prepare', 'engineering', 'transient'}:
            from project_audit.__main__ import main as cli
            sys.argv = ['project-audit', '--target', str(a.target), '--phase', 'prepare' if a.mode == 'transient' else a.mode,
                        '--state-dir', str(vault / (a.execution + '-state')), '--output-dir', str(output)]
            before_vault = sorted(str(x.relative_to(vault)) for x in vault.rglob('*')) if vault.exists() else []
            if a.mode == 'transient':
                sys.argv.append('--no-persist')
            exit_code = cli()
            if a.mode == 'transient':
                after_vault = sorted(str(x.relative_to(vault)) for x in vault.rglob('*')) if vault.exists() else []
                assert before_vault == after_vault, 'Transient preparation persisted files'
            info['status'] = 'PASS' if exit_code == 0 else 'FAIL'
        else:
            from project_audit.runtime import run_full_audit
            from project_audit.models import EgressPolicy, EgressDestination, TargetMode
            from project_audit.omniroute_backend import create_local_omniroute_backend
            from project_audit.delegation import WorkerPort
            from project_audit.semantic_auditor import SemanticAuditor
            from project_audit.state_store import StateStore
            from project_audit.verifier import candidate_identity
            from omniroute_delegation.semantic_parser import extract_json
            worker = None
            if a.mode != 'drift':
                backend, client = create_local_omniroute_backend(timeout=210)
                class ObservedWorker(SemanticAuditor):
                    def review(self, item, run, context, **kwargs):
                        with (dest / 'progress.jsonl').open('a') as f:
                            f.write(json.dumps({'surface': item.target_surface, 'event': 'start', 'time': datetime.now(timezone.utc).isoformat()})+'\n')
                        result = super().review(item, run, context, **kwargs)
                        with (dest / 'progress.jsonl').open('a') as f:
                            f.write(json.dumps({'surface': item.target_surface, 'event': result.status, 'candidates': len(result.candidates)})+'\n')
                        return result
                worker = ObservedWorker(WorkerPort(backend, 'omniroute/project-audit'))
            else:
                # Controlled mutation after real deterministic inspection; no fake auditor/output.
                from project_audit.engineering_auditor import EngineeringAuditor
                source = a.target / 'README.md'
                original_bytes = source.read_bytes()
                original_inspect = EngineeringAuditor.inspect
                calls = []
                def inspect(*args, **kwargs):
                    result = original_inspect(*args, **kwargs)
                    if not calls:
                        source.write_bytes(original_bytes + b'\n<!-- acceptance drift probe -->\n')
                        calls.append(True)
                    return result
                EngineeringAuditor.inspect = inspect
                drift_restore = (source, original_bytes, EngineeringAuditor, original_inspect)
            result = run_full_audit(str(a.target), state_dir=str(state), output_dir=str(output),
                target_mode=TargetMode.COMMIT if a.mode == 'commit' else TargetMode.WORKTREE,
                normalize=a.mode == 'normalize', normalize_command=str(Path(sys.executable).parent / 'audit-normalize'),
                semantic_worker=worker,
                semantic_egress_policy=EgressPolicy(destination=EgressDestination.APPROVED_EXTERNAL, allow_sensitive=True) if worker else None,
                previous_run_ref=a.baseline if a.mode == 'incremental' else None)
            run = result.security.run
            raw = 0
            raw_unparseable = 0
            for review in result.semantic_reviews:
                if review.raw_output:
                    try:
                        data = extract_json(review.raw_output)
                        entries = data if isinstance(data, list) else data.get('findings')
                        if isinstance(entries, list):
                            raw += len(entries)
                        else:
                            raw_unparseable += 1
                    except Exception:
                        raw_unparseable += 1
            ids = {x.candidate_id for x in result.verification_results}
            verified = {x.candidate_id for x in result.verification_results if x.verdict.value == 'VERIFIED'}
            canonical = count_canonical_candidates(output / '03_audit_ledger.md')
            assert canonical == len(ids), 'Verifier ledger count disagrees with canonical identities'
            report = (output / '03_audit_ledger.md').read_text()
            # Count only rendered canonical sections, after the raw coverage section.
            rendered = report.split('## SEMANTIC FINDINGS\n', 1)[-1] if '## SEMANTIC FINDINGS\n' in report else ''
            rendered_count = len(re.findall(r'^### SEM-\d+ — ', rendered, re.M))
            publication = run.publication_state.value
            published = rendered_count if publication == 'PUBLISHED_COMPLETE' else 0
            info.update(status='PASS' if (run.execution_completeness.value, run.coverage_completeness.value, run.failure_state.value) == ('COMPLETE','FULL','NONE') else 'FAIL',
                run_id=run.run_id, snapshot=run.target_snapshot_ref, execution_state=run.execution_completeness.value,
                coverage=run.coverage_completeness.value, failure_state=run.failure_state.value, publication_state=publication,
                raw=raw, raw_unparseable=raw_unparseable, canonical=canonical, verified=len(verified), published=published,
                rendered_candidates=rendered_count, normalized=result.normalization.status if result.normalization else 'NOT_REQUESTED',
                actions=[{'surface': w.target_surface, 'action': w.action.value, 'decision': w.decision_basis} for w in result.prepared.work_items])
            candidates = []
            for review in result.semantic_reviews:
                for c in review.candidates:
                    candidates.append({'id': candidate_identity(c), 'surface': review.target_surface, **asdict(c)})
            (dest / 'candidates.json').write_text(redact(json.dumps(candidates, indent=2)))
            (dest / 'verification.json').write_text(json.dumps([asdict(v) for v in result.verification_results], indent=2))
            store = StateStore(state)
            missing = []
            for evidence in (*result.engineering.evidence, *result.security.evidence):
                try:
                    persisted = store.load_evidence(evidence.evidence_id)
                    assert persisted.work_item_ref == evidence.work_item_ref
                except Exception:
                    missing.append(evidence.evidence_id)
            info['missing_evidence'] = missing
            assert not missing
            if a.mode == 'drift':
                stale = [store.load_evidence(x) for x in store.list_evidence_ids() if store.load_evidence(x).validity.value == 'STALE']
                info['stale_evidence_count'] = len(stale)
                info['drift_detected'] = any(w.failure_state.value == 'SNAPSHOT_DRIFT' for w in result.prepared.work_items)
                assert info['drift_detected'] and stale and published == 0 and publication != 'PUBLISHED_COMPLETE'
                info['status'] = 'CONTROL PASSED'
            if a.mode == 'incremental':
                info['baseline_run'] = a.baseline
                assert a.baseline and any(w.action.value == 'REUSE' for w in result.prepared.work_items)
            if a.mode == 'normalize' and info['normalized'] != 'COMPLETED':
                info['status'] = 'FAIL'
            exit_code = 0 if info['status'] in {'PASS', 'CONTROL PASSED'} else 4
    except Exception as exc:
        info.update(status='FAIL', error_type=type(exc).__name__, error=redact(str(exc)))
        raise
    finally:
        if client:
            client.close()
        if drift_restore:
            source, data, cls, method = drift_restore
            source.write_bytes(data)
            cls.inspect = method
        after = prove_target(a.target)
        (dest / 'target_after.json').write_text(json.dumps(after, indent=2))
        info['target_unchanged'] = before['files'] == after['files'] and before['target_commit'] == after['target_commit']
        info['exit_code'] = exit_code
        info['artifact_manifest'] = archive(vault, dest / 'audit')
        (dest / 'result.json').write_text(redact(json.dumps(info, indent=2)))
        print(json.dumps({k:v for k,v in info.items() if k not in {'artifact_manifest','actions'}}, indent=2))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
