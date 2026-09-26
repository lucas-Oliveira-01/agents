    assert "/.audit/" in (tmp_path / ".gitignore").read_text().splitlines()
    assert {Path(p).name for p in result.artifacts} == {
        "00_inventory.md", "01_coverage.md", "02_analytical.md", "03_audit_ledger.md",
        "audit_execution_state.json",
    }
    assert all(Path(p).parent == audit for p in result.artifacts)