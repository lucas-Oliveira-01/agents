import os
import tempfile
import unittest

from run_audits import count_canonical_candidates


class CanonicalCandidateCountTest(unittest.TestCase):
    def test_counts_unique_verifier_candidates_only(self):
        ledger = """# AUDIT LEDGER

## Independent Verifier

| Candidate | Severity | Verdict | Evidence |
|---|---|---|---|
| VC-alpha | P1 | VERIFIED | evidence-a |
| VC-beta | P2 | NOT_DETERMINABLE | evidence-b |
| VC-alpha | P1 | VERIFIED | duplicate-row |

## SEMANTIC COVERAGE

### WorkItem one
"""
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as handle:
            handle.write(ledger)
            path = handle.name

        try:
            self.assertEqual(count_canonical_candidates(path), 2)
        finally:
            os.unlink(path)

    def test_missing_ledger_is_zero(self):
        self.assertEqual(count_canonical_candidates("/tmp/nonexistent-audit-ledger.md"), 0)


if __name__ == "__main__":
    unittest.main()
