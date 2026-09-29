"""Packaging and isolation tests verifying clean environment install, entry points, and execution without v8/."""

import json
import os
import subprocess
import sys
import tempfile
import pytest


def test_clean_venv_install_and_cli_execution_without_v8():
    """Verify that audit-normalize installs cleanly in a fresh venv and runs CLI without v8/."""
    from pathlib import Path
    import email
    import importlib.metadata
    import shutil
    import zipfile
    from packaging.requirements import Requirement

    package = Path(__file__).resolve().parents[1]
    # Build this checkout, never an arbitrary stale wheel from /tmp.
    with tempfile.TemporaryDirectory() as temp_env_dir:
        temp_root = Path(temp_env_dir)
        wheel_dir = temp_root / "dist"
        wheel_dir.mkdir()
        clean_env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        clean_env.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
        build = subprocess.run(
            [sys.executable, "-m", "pip", "wheel", "--no-build-isolation", "--no-deps",
             "--no-index", "--wheel-dir", str(wheel_dir), str(package)],
            capture_output=True, text=True, env=clean_env,
        )
        assert build.returncode == 0, build.stderr
        wheels = list(wheel_dir.glob("*.whl"))
        assert len(wheels) == 1
        pkg_target = str(wheels[0])
        with zipfile.ZipFile(pkg_target) as wheel:
            schema_name = "audit_normalize/references/validation_report.schema.json"
            assert wheel.read(schema_name) == (package / "references/validation_report.schema.json").read_bytes()
            metadata_name = next(n for n in wheel.namelist() if n.endswith(".dist-info/METADATA"))
            metadata = email.message_from_bytes(wheel.read(metadata_name))
        venv_dir = str(temp_root / "clean_venv")

        # 1. Create a clean virtual environment
        sub_res = subprocess.run(
            [sys.executable, "-m", "venv", venv_dir],
            capture_output=True,
            text=True,
            env=clean_env,
        )
        assert sub_res.returncode == 0, f"Failed to create venv: {sub_res.stderr}"

        venv_pip = os.path.join(venv_dir, "bin", "pip")
        venv_normalize = os.path.join(venv_dir, "bin", "audit-normalize")
        venv_validate = os.path.join(venv_dir, "bin", "audit-validate")

        # Seed only declared runtime dependencies from the test environment.
        # This fresh venv has no access to the checkout or parent site-packages.
        venv_python = os.path.join(venv_dir, "bin", "python")
        site = Path(subprocess.check_output(
            [venv_python, "-c", "import sysconfig; print(sysconfig.get_path('purelib'))"],
            text=True, env=clean_env).strip())
        pending = list(metadata.get_all("Requires-Dist", []))
        seeded = set()
        while pending:
            requirement = Requirement(pending.pop())
            if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
                continue
            dependency = importlib.metadata.distribution(requirement.name)
            assert dependency.version in requirement.specifier, str(requirement)
            name = dependency.metadata["Name"].lower()
            if name in seeded:
                continue
            seeded.add(name)
            for entry in dependency.files or ():
                if ".." in entry.parts or entry.is_absolute():
                    continue
                source = Path(dependency.locate_file(entry))
                if source.is_file():
                    dest = site / entry
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)
            pending.extend(dependency.requires or ())

        # 2. Install the freshly built artifact without index/build downloads.
        install_res = subprocess.run(
            [venv_pip, "install", "--no-index", "--no-deps", pkg_target],
            capture_output=True,
            text=True,
            env=clean_env,
        )
        assert install_res.returncode == 0, f"pip install failed: {install_res.stderr}"

        check = subprocess.run([venv_pip, "check"], capture_output=True, text=True, env=clean_env)
        assert check.returncode == 0, check.stdout + check.stderr
        origin = subprocess.check_output(
            [venv_python, "-I", "-c", "import audit_normalize; print(audit_normalize.__file__)"],
            text=True, env=clean_env).strip()
        assert Path(origin).is_relative_to(site)

        # 3. Verify package is installed
        show_res = subprocess.run(
            [venv_pip, "show", "audit-normalize"],
            capture_output=True,
            text=True,
            env=clean_env,
        )
        assert show_res.returncode == 0
        assert "Name: audit-normalize" in show_res.stdout

        # 4. Verify CLI entry points exist and respond to --help
        help_norm_res = subprocess.run(
            [venv_normalize, "--help"],
            capture_output=True,
            text=True,
            env=clean_env,
        )
        assert help_norm_res.returncode == 0
        assert "audit-normalize" in help_norm_res.stdout

        help_val_res = subprocess.run(
            [venv_validate, "--help"],
            capture_output=True,
            text=True,
            env=clean_env,
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
            env=clean_env,
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
            env=clean_env,
        )
        # Without an execution-state sidecar, the CLI must preserve UNKNOWN
        # execution and INCOMPLETE security even though the schema is valid.
        assert val_cli_run.returncode == 3, f"unexpected audit-validate result: {val_cli_run.stderr}"
        validation = json.loads(val_cli_run.stdout)
        assert validation["schema_validity"] == "VALID"
        assert validation["execution_validity"] == "UNKNOWN"
        assert validation["security_verdict"] == "INCOMPLETE"


def test_validation_report_schema_is_packaged_and_canonical():
    from pathlib import Path
    import audit_normalize
    from audit_normalize.normalize import get_default_validation_report_schema_path
    package = Path(audit_normalize.__file__).parent
    packaged = package / 'references' / 'validation_report.schema.json'
    assert packaged.is_file()
    assert Path(get_default_validation_report_schema_path()) == packaged
    canonical = Path(__file__).parents[1] / 'references' / 'validation_report.schema.json'
    assert packaged.read_bytes() == canonical.read_bytes()
