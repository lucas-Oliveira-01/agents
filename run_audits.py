import os
import sys
import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
import threading
import re


def run_cmd(cmd, cwd=None):
    print(f"Running: {cmd} in {cwd}")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = proc.communicate()
    return proc.returncode, stdout, stderr


def run_with_drift(cmd, cwd, drift_file):
    print(f"Running with drift: {cmd} in {cwd}")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # wait a bit for it to start
    time.sleep(2)
    # create drift
    drift_path = os.path.join(cwd, drift_file)
    print(f"Applying drift to {drift_path}")
    with open(drift_path, "a") as f:
        f.write("\n// snapshot drift mutation\n")
    
    stdout, stderr = proc.communicate()
    return proc.returncode, stdout, stderr


SOURCE_PROJECT = "/home/oliveira/Projects/SKILLS/auditoring/test8/smartserv"
RESULTS_DIR = "/home/oliveira/Projects/SKILLS/smartserv_replay_final_pr33_fixed"


def get_git_info(repo_path):
    rc, branch, _ = run_cmd("git rev-parse --abbrev-ref HEAD", repo_path)
    rc, commit, _ = run_cmd("git rev-parse HEAD", repo_path)
    return {
        "repository": repo_path,
        "branch": branch.strip(),
        "commit": commit.strip()
    }


def count_canonical_candidates(ledger_path):
    """Count canonical verifier candidates from the ledger's dedicated table."""
    if not os.path.exists(ledger_path):
        return 0

    in_verifier_section = False
    candidate_ids = set()

    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()

            if stripped == "## Independent Verifier":
                in_verifier_section = True
                continue

            if in_verifier_section and stripped.startswith("## "):
                break

            if not in_verifier_section:
                continue

            match = re.match(r"^\|\s*(VC-[^|]+?)\s*\|", line)
            if match:
                candidate_ids.add(match.group(1).strip())

    return len(candidate_ids)


def collect_audit_artifacts(audit_dir, dest_audit_dir):
    if not os.path.exists(audit_dir):
        return {}
        
    shutil.copytree(audit_dir, dest_audit_dir, dirs_exist_ok=True)
    
    ledger_path = os.path.join(dest_audit_dir, "03_audit_ledger.md")
    findings_count = 0
    canonical_count = count_canonical_candidates(ledger_path)
    published_count = 0
    
    # try to count findings if ledger exists
    if os.path.exists(ledger_path):
        with open(ledger_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("## Finding:"):
                    published_count += 1
                    
    # try to read raw outputs if exist
    raw_dir = os.path.join(dest_audit_dir, "raw")
    if os.path.exists(raw_dir):
        for fname in os.listdir(raw_dir):
            if fname.endswith(".json"):
                try:
                    with open(os.path.join(raw_dir, fname), "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if "findings" in data:
                            findings_count += len(data["findings"])
                except Exception:
                    pass
                    
    return {
        "raw_findings": max(findings_count, published_count),
        "canonical_findings": canonical_count,
        "published_findings": published_count
    }


def main():
    if os.path.exists(RESULTS_DIR):
        shutil.rmtree(RESULTS_DIR)
    os.makedirs(RESULTS_DIR)

    git_info = get_git_info(SOURCE_PROJECT)

    executions = [
        {"id": "012_full_normalize", "cmd": "PYTHONPATH=../../skills/universal/project-audit/src:../../skills/universal/omnirouter-gateway/src:../../skills/universal/omniroute-delegation/src python3 -m project_audit --target project --phase full --target-mode WORKTREE --normalize --normalize-command audit-normalize", "type": "standard"},
        {"id": "001_full_worktree", "cmd": "PYTHONPATH=../../skills/universal/project-audit/src:../../skills/universal/omnirouter-gateway/src:../../skills/universal/omniroute-delegation/src python3 -m project_audit --target project --phase full --target-mode WORKTREE", "type": "standard"},
        {"id": "002_full_commit", "cmd": "PYTHONPATH=../../skills/universal/project-audit/src:../../skills/universal/omnirouter-gateway/src:../../skills/universal/omniroute-delegation/src python3 -m project_audit --target project --phase full --target-mode COMMIT", "type": "standard"},
        {"id": "003_transient", "cmd": "PYTHONPATH=../../skills/universal/project-audit/src:../../skills/universal/omnirouter-gateway/src:../../skills/universal/omniroute-delegation/src python3 -m project_audit --target project --phase full --target-mode WORKTREE --no-persist", "type": "standard"},
        {"id": "004_incremental", "cmd": "PYTHONPATH=../../skills/universal/project-audit/src:../../skills/universal/omnirouter-gateway/src:../../skills/universal/omniroute-delegation/src python3 -m project_audit --target project --phase full --target-mode WORKTREE", "type": "incremental"},
        {"id": "005_snapshot_drift", "cmd": "PYTHONPATH=../../skills/universal/project-audit/src:../../skills/universal/omnirouter-gateway/src:../../skills/universal/omniroute-delegation/src python3 -m project_audit --target project --phase full --target-mode WORKTREE", "type": "drift"},
        {"id": "006_prepare_only", "cmd": "PYTHONPATH=../../skills/universal/project-audit/src:../../skills/universal/omnirouter-gateway/src:../../skills/universal/omniroute-delegation/src python3 -m project_audit --target project --phase prepare --target-mode WORKTREE", "type": "standard"},
        {"id": "007_engineering_only", "cmd": "PYTHONPATH=../../skills/universal/project-audit/src:../../skills/universal/omnirouter-gateway/src:../../skills/universal/omniroute-delegation/src python3 -m project_audit --target project --phase engineering --target-mode WORKTREE", "type": "standard"},
    ]

    results = []

    for exe in executions:
        print(f"--- Starting {exe['id']} ---")
        run_dir = os.path.join(RESULTS_DIR, exe["id"])
        project_dir = os.path.join(run_dir, "project")
        audit_dest_dir = os.path.join(run_dir, "audit")
        logs_dir = os.path.join(run_dir, "logs")
        
        os.makedirs(run_dir)
        os.makedirs(logs_dir)
        
        # Clone isolated copy
        run_cmd(f"cp -r {SOURCE_PROJECT} {project_dir}")
        
        start_time = datetime.now(timezone.utc).isoformat()
        
        if exe["type"] == "incremental":
            # Run baseline first
            print("Running baseline for incremental...")
            baseline_cmd = "PYTHONPATH=../../skills/universal/project-audit/src:../../skills/universal/omnirouter-gateway/src:../../skills/universal/omniroute-delegation/src python3 -m project_audit --target project --phase full --target-mode WORKTREE"
            b_rc, b_out, b_err = run_cmd(baseline_cmd, cwd=run_dir)
            with open(os.path.join(logs_dir, "baseline_stdout.log"), "w") as f: f.write(b_out)
            with open(os.path.join(logs_dir, "baseline_stderr.log"), "w") as f: f.write(b_err)
            
            # Now run incremental
            print("Running incremental...")
            rc, stdout, stderr = run_cmd(exe["cmd"], cwd=run_dir)
            
        elif exe["type"] == "drift":
            rc, stdout, stderr = run_with_drift(exe["cmd"], cwd=run_dir, drift_file="project/README.md")
        else:
            rc, stdout, stderr = run_cmd(exe["cmd"], cwd=run_dir)
            
        end_time = datetime.now(timezone.utc).isoformat()
        
        with open(os.path.join(logs_dir, "command.txt"), "w") as f:
            f.write(exe["cmd"] + "\n")
        with open(os.path.join(logs_dir, "stdout.log"), "w") as f:
            f.write(stdout)
        with open(os.path.join(logs_dir, "stderr.log"), "w") as f:
            f.write(stderr)
            
        # Collect artifacts
        source_audit_dir = os.path.join(project_dir, ".audit")
        artifacts_stats = collect_audit_artifacts(source_audit_dir, audit_dest_dir)
        
        status = "EXECUTION_SUCCESS" if rc == 0 else "EXECUTION_FAILURE"
        if exe["type"] == "drift" and rc != 0:
            status = "SNAPSHOT_DRIFT"
            
        metadata = {
            "execution_id": exe["id"],
            "execution_mode": exe["cmd"],
            "target": "smartserv",
            "source_path": SOURCE_PROJECT,
            "clone_path": project_dir,
            "repository": git_info["repository"],
            "branch": git_info["branch"],
            "commit": git_info["commit"],
            "auditor_commit": get_git_info(os.path.join(os.getcwd(), "skills", "universal", "project-audit"))["commit"],
            "started_at": start_time,
            "finished_at": end_time,
            "status": status,
            "exit_code": rc,
            "raw_findings": artifacts_stats.get("raw_findings", 0),
            "canonical_findings": artifacts_stats.get("canonical_findings", 0),
            "published_findings": artifacts_stats.get("published_findings", 0)
        }
        
        with open(os.path.join(run_dir, "metadata.json"), "w") as f:
            json.dump(metadata, f, indent=2)
            
        results.append(metadata)

    # Generate ALL_RUNS_SUMMARY.json
    summary_json = {
        "project": "smartserv",
        "executions": results,
        "summary": {
            "total_executions": len(results),
            "successful": sum(1 for r in results if r["status"] == "EXECUTION_SUCCESS"),
            "failed": sum(1 for r in results if r["status"] == "EXECUTION_FAILURE"),
            "partial": sum(1 for r in results if r["status"] not in ("EXECUTION_SUCCESS", "EXECUTION_FAILURE")),
            "raw_findings": sum(r["raw_findings"] for r in results),
            "canonical_findings": sum(r.get("canonical_findings", 0) for r in results),
            "published_findings": sum(r["published_findings"] for r in results)
        }
    }
    
    with open(os.path.join(RESULTS_DIR, "ALL_RUNS_SUMMARY.json"), "w") as f:
        json.dump(summary_json, f, indent=2)
        
    # Generate ALL_RUNS_SUMMARY.md
    with open(os.path.join(RESULTS_DIR, "ALL_RUNS_SUMMARY.md"), "w") as f:
        f.write("# ALL RUNS SUMMARY\n\n")
        f.write("## Execution Matrix\n")
        f.write("| Execution | Mode | Status | Raw Findings | Canonical | Published |\n")
        f.write("|---|---|---|---|---|---|\n")
        for r in results:
            f.write(f"| {r['execution_id']} | {r['execution_mode']} | {r['status']} | {r['raw_findings']} | {r.get('canonical_findings', 0)} | {r['published_findings']} |\n")

if __name__ == "__main__":
    main()
