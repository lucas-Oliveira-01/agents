from __future__ import annotations

import argparse
from pathlib import Path

from .classifiers import classify_applicability, classify_files, classify_stack
from .discovery import discover
from .models import TargetMode
from .normalization_runner import run_audit_normalize
from .orchestrator import Orchestrator
from .planner import prepare_audit
from .runtime import run_full_audit, audit_paths, initialize_audit_repository
from .state_store import StateStore
from .omniroute_backend import create_local_omniroute_backend
from .semantic_auditor import SemanticAuditor
from .models import EgressPolicy, EgressDestination
from .delegation import WorkerPort
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Run or prepare a project-audit swarm-aware audit")
    parser.add_argument("--target", default=".", help="Repository/worktree to inspect")
    parser.add_argument(
        "--state-dir",
        default=None,
        help="Audit state directory (default: <target>/.audit/runs)",
    )
    parser.add_argument(
        "--phase",
        choices=("prepare", "engineering", "full", "fix"),
        default="prepare",
        help="Prepare the plan, execute Engineering PASS 1, execute full audit, or fix findings",
    )
    parser.add_argument("--run-id", default=None, help="Run ID to use for 'fix' phase")
    parser.add_argument("--no-persist", action="store_true", help="Do not persist state during prepare phase")
    parser.add_argument("--output-dir", default=None, help="Audit Markdown output directory (default: <target>/.audit)")
    parser.add_argument("--overwrite-audit", action="store_true", help="Explicitly allow replacing existing audit artifacts")
    parser.add_argument("--normalize", action="store_true", help="Invoke audit-normalize after Markdown generation")
    parser.add_argument("--normalize-command", default="audit-normalize", help="Downstream audit-normalize executable")
    parser.add_argument("--allow-external", action="store_true", help="Explicitly allow external egress")
    parser.add_argument("--target-mode", choices=("WORKTREE", "COMMIT"), default="WORKTREE", help="Define whether the audit target is the current worktree or the Git commit state")
    args = parser.parse_args()

    root, vault, state_dir, output_dir = audit_paths(args.target, args.state_dir, args.output_dir)
    if not (args.phase == "prepare" and args.no_persist):
        initialize_audit_repository(root, vault)
    discovery = discover(str(root))
    files = classify_files(discovery)
    stack = classify_stack(discovery)
    applicability = classify_applicability(discovery, stack)
    prepared = prepare_audit(
        discovery,
        files,
        applicability,
        target_mode=TargetMode(args.target_mode),
    )

    if args.phase == "prepare":
        if not args.no_persist:
            state_dir = Path(args.state_dir) if args.state_dir else discovery.root / ".audit" / "runs"
            orchestrator = Orchestrator(StateStore(state_dir))
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
        print(f"target_mode={args.target_mode}")
        print(f"persisted={not args.no_persist}")
        return 0

    if args.phase == "engineering":
        from .engineering_runner import execute_engineering_pass

        state_dir = Path(args.state_dir) if args.state_dir else discovery.root / ".audit" / "runs"
        engineering = execute_engineering_pass(
            Orchestrator(StateStore(state_dir)),
            discovery,
            prepared.plan,
            list(prepared.work_items),
            target_snapshot=prepared.snapshot,
        )
        print("phase=engineering")
        print(f"execution={engineering.run.execution_completeness.value}")
        print(f"coverage={engineering.run.coverage_completeness.value}")
        print(f"inspections={len(engineering.inspections)}")
        print(f"evidence={len(engineering.evidence)}")
        print(f"run={engineering.run.run_id}")
        print(f"snapshot={engineering.run.target_snapshot_ref}")
        return 0

    semantic_worker = None
    mcp_client = None
    try:
        try:
            backend, mcp_client = create_local_omniroute_backend()
            worker_port = WorkerPort(backend, "omniroute/project-audit")
            semantic_worker = SemanticAuditor(worker_port)
        except Exception as e:
            print(f"Semantic delegation disabled: {e}", file=sys.stderr)

        if args.phase == "fix":
            if not args.run_id:
                print("Error: --run-id is required for the 'fix' phase", file=sys.stderr)
                return 1

            findings_path = Path(args.output_dir or (discovery.root / ".audit")) / "report_data.json"
            if not findings_path.exists():
                print(f"Error: {findings_path} not found. Please run full audit with --normalize first to produce JSON findings.", file=sys.stderr)
                return 1

            import json
            try:
                data = json.loads(findings_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Error reading JSON findings: {e}", file=sys.stderr)
                return 1

            print("Scanning for P0/P1 findings to auto-fix...")
            import asyncio
            try:
                from omniroute_delegation.local_worker_mcp import dispatch_opencode_worker
            except ImportError:
                print("Auto-fix unavailable. Install omniroute-delegation locally.", file=sys.stderr)
                return 1

            p1_count = 0
            for cand in data.get("findings", []):
                if cand.get("severity") in ["P0", "P1"] and cand.get("status", "CONFIRMED") == "CONFIRMED":
                    p1_count += 1
                    title = cand.get("title", "")
                    print(f"Auto-fixing {cand.get('severity')}: {title}")
                    loc_dict = cand.get("location", {}) or {}
                    loc = loc_dict.get("file", "") if isinstance(loc_dict, dict) else ""
                    task = (
                        f"Fix the confirmed finding: {title}. "
                        f"Description: {cand.get('description', '')}. "
                        f"Recommendation: {cand.get('recommendation', '')}"
                    )

                    async def run_dispatch():
                        res = await dispatch_opencode_worker(
                            task=task,
                            target_file=loc,
                            workspace_dir=str(discovery.root),
                            isolated_memory=True
                        )
                        print(f"L3W worker dispatched for {title}")
                    asyncio.run(run_dispatch())

            if p1_count > 0:
                print(f"Dispatched {p1_count} L3W workers for confirmed P0/P1 auto-fixes.")
            else:
                print("No P0/P1 confirmed findings required auto-fix.")
            return 0

        # -- Full Audit Execution --
        result = run_full_audit(
            args.target,
            state_dir=args.state_dir,
            output_dir=args.output_dir,
            target_mode=TargetMode(args.target_mode),
            overwrite_artifacts=args.overwrite_audit,
            normalize=args.normalize,
            normalize_command=args.normalize_command,
            semantic_worker=semantic_worker,
            semantic_egress_policy=EgressPolicy(destination=EgressDestination.APPROVED_EXTERNAL if getattr(args, "allow_external", False) else EgressDestination.LOCAL_ONLY, allow_sensitive=True),
        )
        final_run = result.security.run

        print("phase=full")
        print(f"status={final_run.audit_status}")
        print(f"execution={final_run.execution_completeness.value}")
        print(f"coverage={final_run.coverage_completeness.value}")
        print(f"run={final_run.run_id}")
        print(f"snapshot={final_run.target_snapshot_ref}")
        print(f"artifacts={len(result.artifacts)}")
        print(f"output_dir={args.output_dir or str(result.discovery.root / '.audit')}")
        
        if final_run.failure_state.value == "SEMANTIC_COVERAGE_FAILED":
            print("failure_state=SEMANTIC_COVERAGE_FAILED")
            return 4

        if result.normalization is not None:
            print(f"normalization={result.normalization.status}")
            print(f"normalization_return_code={result.normalization.return_code}")
            if result.normalization.stdout:
                print(result.normalization.stdout.rstrip())
            if result.normalization.stderr:
                print(result.normalization.stderr.rstrip())
            if result.normalization.status == "FAILED":
                return 3
            if result.normalization.status == "NOT_EXECUTED":
                return 4


    finally:
        # Release the MCP transport owned by the Gateway-backed backend.
        if mcp_client is not None:
            import asyncio
            try:
                # the MCP client usually has a close or terminate
                if hasattr(mcp_client, "close"):
                    if asyncio.iscoroutinefunction(mcp_client.close):
                        asyncio.run(mcp_client.close())
                    else:
                        mcp_client.close()
            except Exception:
                pass

    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
