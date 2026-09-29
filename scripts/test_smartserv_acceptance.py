from smartserv_acceptance import count_canonical_candidates


def test_counts_unique_verifier_candidates_only(tmp_path):
    ledger = tmp_path / 'ledger.md'
    ledger.write_text('''# AUDIT LEDGER

## Independent Verifier

| Candidate | Severity | Verdict | Evidence |
|---|---|---|---|
| VC-alpha | P1 | VERIFIED | evidence-a |
| VC-beta | P2 | NOT_DETERMINABLE | evidence-b |
| VC-alpha | P1 | VERIFIED | duplicate-row |

## SEMANTIC COVERAGE

| VC-not-a-candidate | ignored |
''')
    assert count_canonical_candidates(ledger) == 2


def test_missing_ledger_is_zero(tmp_path):
    assert count_canonical_candidates(tmp_path / 'missing') == 0


def test_rendered_findings_ignore_raw_output_fences():
    from smartserv_acceptance import rendered_finding_titles
    text = '''## SEMANTIC COVERAGE
~~~text
## SEMANTIC FINDINGS
### SEM-999 — not published
~~~
## SEMANTIC FINDINGS
### SEM-001 — Actual candidate
Title: Actual candidate
## Next section
### SEM-002 — not a finding
'''
    assert rendered_finding_titles(text) == ['Actual candidate']


import ast
from pathlib import Path
import pytest


@pytest.mark.parametrize("raw,canonical,raw_unparseable", [(0, 1, 1), (1, 2, 0), (2, 1, 1)])
def test_raw_canonical_gate_fails_closed(raw, canonical, raw_unparseable):
    # Execute the production assertions directly, without a simulated semantic run.
    tree = ast.parse(Path(__file__).with_name("smartserv_acceptance.py").read_text())
    assertions = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)
        and any(isinstance(child, ast.Name) and child.id in {"raw", "raw_unparseable"}
                for child in ast.walk(node.test))]
    assert assertions, "Acceptance must enforce raw/parser invariants"
    code = compile(ast.Module(body=assertions, type_ignores=[]), "acceptance-gate", "exec")
    with pytest.raises(AssertionError):
        exec(code, {"raw": raw, "canonical": canonical, "raw_unparseable": raw_unparseable})
