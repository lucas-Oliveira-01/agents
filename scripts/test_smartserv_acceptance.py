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
