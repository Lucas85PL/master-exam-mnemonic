"""Test evaluate_consensus_majority (3/5)."""
import unittest

from openrouter_consensus import evaluate_consensus_majority


def _votes(*letters):
    return [{"model": f"m{i}", "letter": l} for i, l in enumerate(letters)]


class TestConsensusMajority(unittest.TestCase):
    def test_auto_ok_three_of_five(self):
        v = _votes("A", "A", "B", "A", "C")
        action, letter, _ = evaluate_consensus_majority(v, "A", min_agree=3)
        self.assertEqual(action, "AUTO_OK")
        self.assertEqual(letter, "A")

    def test_no_majority(self):
        v = _votes("A", "B", "C", "A", "B")
        action, _, detail = evaluate_consensus_majority(v, "A", min_agree=3)
        self.assertEqual(action, "NO_MAJORITY")
        self.assertIn("agree_db=2", detail)

    def test_api_failures_still_ok(self):
        v = _votes("C", "C", None, "C", None)
        action, letter, _ = evaluate_consensus_majority(v, "C", min_agree=3)
        self.assertEqual(action, "AUTO_OK")
        self.assertEqual(letter, "C")


if __name__ == "__main__":
    unittest.main()
