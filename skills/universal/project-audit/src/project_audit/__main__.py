from __future__ import annotations

import argparse
from pathlib import Path

from .classifiers import classify_applicability, classify_files, classify_stack
from .discovery import discover
from .engineering_runner import execute_engineering_pass
from .security_runner import execute_security_pass
from .report_writer import write_audit_artifacts
from .normalization_runner import run_audit_normalize
from .orchestrator import Orchestrator
from .planner import prepare_audit
from .state_store import StateStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or prepare a project-audit single-agent audit")
    parser.add_argument("--target", default=".", help="Repository/worktree to inspect")
    parser.add_argument(
        "--state-dir",
        default=None,
        help="Audit state directory (default: <target>/.audit/runs)",
    )
    parser.add_argument(
        "--phase",
        choices=("prepare", "engineering", "full"),
        default="prepare",
        help="Prepare the plan, execute Engineering PASS 1, or execute the full two-pass audit",
    )
    parser.add_argument("--no-persist", action="store_true", help="Do not persist state during prepare phase")
    parser.add_argument("--output-dir", default=None, help="Audit Markdown output directory (default: <target>/docs/audit)")
    parser.add_argument("--overwrite-audit", action="store_true", help="Explicitly allow replacing existing audit artifacts")
    parser.add_argument("--normalize", action="store_true", help="Invoke audit-normalize after Markdown generation")
    parser.add_argument("--normalize-command", default="audit-normalize", help="Downstream audit-normalize executable")
    args = parser.parse_args()

    discovery = discover(args.target)
    files = classify_files(discovery)
    stack = classify_stack(discovery)
    applicability = classify_applicability(discovery, stack)
    prepared = prepare_audit(discovery, files, applicability)

    state_dir = Path(args.state_dir) if args.state_dir else discovery.root / ".audit" / "runs"
    orchestrator = Orchestrator(StateStore(state_dir))

    if args.phase in ("engineering", "full"):
        result = execute_engineering_pass(
            orchestrator,
            discovery,
            prepared.plan,
            list(prepared.work_items),
        )
        print(f"phase=engineering")
        print(f"execution={result.run.execution_completeness.value}")
        print(f"coverage={result.run.coverage_completeness.value}")
        print(f"inspections={len(result.inspections)}")
        print(f"evidence={len(result.evidence)}")
        print(f"run={result.run.run_id}")
        print(f"snapshot={result.run.target_snapshot_ref}")
        if args.phase == "full":
            security = execute_security_pass(
                orchestrator,
                discovery,
                prepared.plan,
                list(prepared.work_items),
                result.run,
            )
            final_run = security.run
            output_dir = args.output_dir or str(discovery.root / "docs" / "audit")
            artifacts = write_audit_artifacts(output_dir, prepared, discovery, result, security, overwrite=args.overwrite_audit)
            result.run.artifact_refs = list(artifacts.values())
            orchestrator.commit_run(
                result.run,
                prepared.plan,
                list(prepared.work_items),
                known_run_ids=orchestrator.store.list_run_ids(),
            )
            print("security_pass=complete")
            print(f"execution={final_run.execution_completeness.value}")
            print(f"coverage={final_run.coverage_completeness.value}")
            print(f"run={final_run.run_id}")
            print(f"artifacts={len(artifacts)}")
            print(f"output_dir={output_dir}")
            if args.normalize:
                normalized_dir = str(Path(output_dir) / "normalized")
                normalization = run_audit_normalize(
                    output_dir,
                    normalized_dir,
                    base_dir=str(discovery.root),
                    command=args.normalize_command,
                )
                print(f"normalization={normalization.status}")
                print(f"normalization_return_code={normalization.return_code}")
                if normalization.stdout:
                    print(normalization.stdout.rstrip())
                if normalization.stderr:
                    print(normalization.stderr.rstrip())
                if normalization.status == "FAILED":
                    return 3
                if normalization.status == "NOT_EXECUTED":
                    return 4
        return 0

    if not args.no_persist:
        orchestrator.commit_snapshot(prepared.snapshot)
        orchestrator.freeze_and_commit_plan(prepared.plan)
        for work_item in prepared.work_items:
            orchestrator.commit_work_item(work_item)

    print(f"target={discovery.root}")
    print(f"files={len(files)}")
    print(f"git_repository={discovery.git.is_repository}")
    print(f"revision={discovery.git.revision or 'NOT_AVAILABLE'}")
    print(f"stack={','.join(stack) if stack else 'UNKNOWN'}")
    print(f"work_items={len(prepared.work_items)}")
    print(f"snapshot={prepared.snapshot.snapshot_fingerprint}")
    print("phase=prepare")
    print(f"persisted={not args.no_persist}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
