"""Testy jednostkowe audit_decision (mock row)."""
import unittest

from audit_decision import (
    decide_tier,
    normalize_letter,
    skip_reason,
    structural_issues,
)


def mock_row(**kwargs):
    base = {
        "pytanie": "Test pytanie?",
        "typ_pytania": "testowe",
        "odp_a": "a1",
        "odp_b": "b1",
        "odp_c": None,
        "odp_d": None,
        "poprawna_odpowiedz": "A",
        "poprawna_odpowiedz_tekst": None,
    }
    base.update(kwargs)
    return base


class TestAuditDecision(unittest.TestCase):
    def test_audit_ok_triple_match(self):
        votes = [{"letter": "B"}, {"letter": "B"}, {"letter": "B"}]
        tier, _, letters, cons = decide_tier("B", "B", votes, [])
        self.assertEqual(tier, "AUDIT_OK")
        self.assertEqual(cons, "B")

    def test_mismatch_db_vs_pdf(self):
        votes = [{"letter": "B"}, {"letter": "B"}, {"letter": "B"}]
        tier, detail, _, _ = decide_tier("B", "C", votes, [])
        self.assertEqual(tier, "AUDIT_REVIEW_MISMATCH")
        self.assertIn("db", detail)

    def test_no_consensus_split(self):
        votes = [{"letter": "A"}, {"letter": "B"}, {"letter": "A"}]
        tier, _, _, _ = decide_tier("A", "A", votes, [])
        self.assertEqual(tier, "AUDIT_REVIEW_NO_CONSENSUS")

    def test_no_pdf(self):
        tier, _, _, _ = decide_tier(None, "A", [], [])
        self.assertEqual(tier, "AUDIT_REVIEW_NO_PDF")

    def test_struct_blocks(self):
        row = mock_row(pytanie="")
        self.assertIn("empty_pytanie", structural_issues(row))

    def test_skip_otwarte(self):
        row = mock_row(typ_pytania="otwarte")
        tier, _ = skip_reason(row)
        self.assertEqual(tier, "AUDIT_SKIP")

    def test_normalize(self):
        self.assertEqual(normalize_letter(" a "), "A")
        self.assertIsNone(normalize_letter("X"))


if __name__ == "__main__":
    unittest.main()
