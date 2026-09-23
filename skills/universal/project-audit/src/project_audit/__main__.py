from __future__ import annotations

import argparse
from pathlib import Path

from .classifiers import classify_applicability, classify_files, classify_stack
from .discovery import discover
from .engineering_runner import execute_engineering_pass
from .security_runner import execute_security_pass
from .report_writer import write_audit_artifacts
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
            artifacts = write_audit_artifacts(output_dir, prepared, discovery, result, security)
            print("security_pass=complete")
            print(f"execution={final_run.execution_completeness.value}")
            print(f"coverage={final_run.coverage_completeness.value}")
            print(f"run={final_run.run_id}")
            print(f"artifacts={len(artifacts)}")
            print(f"output_dir={output_dir}")
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
