"""Testy ensemble_decision."""
import unittest

from ensemble_decision import FUZZY_THRESHOLD, decide_ensemble_tier


def _sim(a, b):
    if not a or not b:
        return 0
    return 100 if str(a).strip() == str(b).strip() else 50


class TestEnsembleDecision(unittest.TestCase):
    def test_ok_letter_and_options(self):
        row = {
            "poprawna_odpowiedz": "B",
            "odp_a": "aa",
            "odp_b": "bb",
            "odp_c": None,
            "odp_d": None,
        }
        parsed = {
            "poprawna_odpowiedz": "B",
            "odp_a": "aa",
            "odp_b": "bb",
            "cross_page": False,
            "pages": [1],
        }
        scores = {"A": 100, "B": 100}
        tier, _ = decide_ensemble_tier(row, parsed, scores, _sim)
        self.assertEqual(tier, "ENSEMBLE_OK")

    def test_mismatch_letter(self):
        row = {"poprawna_odpowiedz": "A", "odp_a": "x", "odp_b": "y", "odp_c": None, "odp_d": None}
        parsed = {
            "poprawna_odpowiedz": "C",
            "odp_a": "x",
            "odp_b": "y",
            "pages": [0],
        }
        tier, detail = decide_ensemble_tier(row, parsed, {"A": 100, "B": 100}, _sim)
        self.assertEqual(tier, "ENSEMBLE_REVIEW_MISMATCH")
        self.assertIn("pdf=C", detail)


if __name__ == "__main__":
    unittest.main()
