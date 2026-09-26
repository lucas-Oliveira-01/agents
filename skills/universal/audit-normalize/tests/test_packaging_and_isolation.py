"""Packaging and isolation tests verifying clean environment install, entry points, and execution without v8/."""

import json
import os
import subprocess
import sys
import tempfile
import pytest


def test_clean_venv_install_and_cli_execution_without_v8():
    """Verify that audit-normalize installs cleanly in a fresh venv and runs CLI without v8/."""
    # Location of the audit-normalize package or built wheel
    candidate_roots = [
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "audit-normalize")),
    ]
    pkg_target = os.environ.get("AUDIT_NORMALIZE_WHEEL")
    if not pkg_target and os.path.isdir("/tmp/audit_build_dist"):
        whls = [os.path.join("/tmp/audit_build_dist", f) for f in sorted(os.listdir("/tmp/audit_build_dist")) if f.endswith(".whl")]
        if whls:
            pkg_target = whls[-1]
    if not pkg_target:
        for cr in candidate_roots:
            if os.path.isfile(os.path.join(cr, "pyproject.toml")):
                pkg_target = cr
                break
    assert pkg_target is not None, "Could not locate installable audit-normalize wheel or source package"

    with tempfile.TemporaryDirectory() as temp_env_dir:
        venv_dir = os.path.join(temp_env_dir, "clean_venv")

        # 1. Create a clean virtual environment
        sub_res = subprocess.run(
            [sys.executable, "-m", "venv", venv_dir],
            capture_output=True,
            text=True,
        )
        assert sub_res.returncode == 0, f"Failed to create venv: {sub_res.stderr}"

        venv_pip = os.path.join(venv_dir, "bin", "pip")
        venv_normalize = os.path.join(venv_dir, "bin", "audit-normalize")
        venv_validate = os.path.join(venv_dir, "bin", "audit-validate")

        # 2. Clean install via pip
        install_res = subprocess.run(
            [venv_pip, "install", pkg_target],
            capture_output=True,
            text=True,
        )
        assert install_res.returncode == 0, f"pip install failed: {install_res.stderr}"

        # 3. Verify package is installed
        show_res = subprocess.run(
            [venv_pip, "show", "audit-normalize"],
            capture_output=True,
            text=True,
        )
        assert show_res.returncode == 0
        assert "Name: audit-normalize" in show_res.stdout

        # 4. Verify CLI entry points exist and respond to --help
        help_norm_res = subprocess.run(
            [venv_normalize, "--help"],
            capture_output=True,
            text=True,
        )
        assert help_norm_res.returncode == 0
        assert "audit-normalize" in help_norm_res.stdout

        help_val_res = subprocess.run(
            [venv_validate, "--help"],
            capture_output=True,
            text=True,
        )
        assert help_val_res.returncode == 0
        assert "audit-validate" in help_val_res.stdout

        # 5. Execution in a separate directory without v8/
        work_dir = os.path.join(temp_env_dir, "isolated_work")
        os.makedirs(work_dir)

        # Confirm v8 does NOT exist in isolated_work
        assert not os.path.exists(os.path.join(work_dir, "v8"))

        input_dir = os.path.join(work_dir, "docs", "audit")
        output_dir = os.path.join(work_dir, "docs", "audit", "normalized")
        os.makedirs(input_dir)

        # Write test audit document
        with open(os.path.join(input_dir, "03_audit_ledger.md"), "w") as f:
            f.write("""# AUDIT LEDGER
## Findings
### SEC-001: Missing CSRF Protection
Category: SECURITY
Type: VULNERABILITY
Severity: P2
Status: CONFIRMED
Location: src/web/WebSecurity.java:24
Description: State changing POST requests do not require Anti-CSRF token.
""")

        # Execute audit-normalize CLI in isolated_work
        cli_run = subprocess.run(
            [venv_normalize, "-i", input_dir, "-o", output_dir],
            cwd=work_dir,
            capture_output=True,
            text=True,
        )
        assert cli_run.returncode == 0, f"audit-normalize failed in isolation: {cli_run.stderr}"
        assert "Schema validity: VALID" in cli_run.stdout

        # Verify all 4 required artifacts exist
        report_data_file = os.path.join(output_dir, "report_data.json")
        val_report_file = os.path.join(output_dir, "validation_report.json")
        manifest_file = os.path.join(output_dir, "source_manifest.json")
        schema_file = os.path.join(output_dir, "report_data.schema.json")

        assert os.path.isfile(report_data_file)
        assert os.path.isfile(val_report_file)
        assert os.path.isfile(manifest_file)
        assert os.path.isfile(schema_file)

        with open(val_report_file, "r") as f:
            val_data = json.load(f)
        assert val_data["schema_validity"] == "VALID"

        # 6. Execute audit-validate CLI on the generated artifact
        val_cli_run = subprocess.run(
            [venv_validate, report_data_file],
            cwd=work_dir,
            capture_output=True,
            text=True,
        )
        assert val_cli_run.returncode == 0, f"audit-validate failed: {val_cli_run.stderr}"
