"""Testy pdf_cross_page (merge, heurystyki)."""
import unittest

from pdf_cross_page import (
    _parse_answers_from_text,
    count_options,
    merge_parse_results,
    should_try_cross_page,
)


class TestCrossPage(unittest.TestCase):
    def test_merge_options(self):
        base = {
            "nr": 5,
            "pytanie": "Pytanie test",
            "odp_a": "odp A",
            "odp_b": None,
            "poprawna_odpowiedz": None,
        }
        extra = {
            "odp_b": "odp B",
            "odp_c": "odp C",
            "odp_d": "odp D",
            "poprawna_odpowiedz": "C",
        }
        m = merge_parse_results(base, extra)
        self.assertEqual(m["odp_b"], "odp B")
        self.assertEqual(m["poprawna_odpowiedz"], "C")
        self.assertEqual(count_options(m), 4)

    def test_should_try_incomplete(self):
        parsed = {"odp_a": "x", "poprawna_odpowiedz": "A"}
        self.assertTrue(
            should_try_cross_page(parsed, "/fake.pdf", 0, "format1_4col", 1, None)
        )

    def test_parse_after_hint_skips_earlier_options(self):
        block = (
            "36. c. stara odpowiedz c\n"
            "Po czynności kompensacji dewiacji kompasu magnetycznego należy:\n"
            "a. pozostawić poprzednią tabelę dewiacji\n"
            "37. b. ponownie określić tabelę dewiacji\n"
            "B\n"
        )
        hint = "Po czynności kompensacji dewiacji kompasu magnetycznego należy:"
        p = _parse_answers_from_text(block, 37, pytanie_hint=hint)
        self.assertEqual(p["odp_a"], "pozostawić poprzednią tabelę dewiacji")
        self.assertIsNone(p.get("odp_c"))

    def test_parse_continuation_stops_at_next_question(self):
        block = (
            "37.\n"
            "B\n"
            "c. nie należy określać tabeli dewiacji\n"
            "Nowe pytanie:\n"
            "a. na kursach, gdzie przyjmują one najmniejsze wartości\n"
            "38. b. inna odpowiedz\n"
        )
        p = _parse_answers_from_text(block, 37, continuation_only=True)
        self.assertEqual(p["odp_c"], "nie należy określać tabeli dewiacji")
        self.assertEqual(p["poprawna_odpowiedz"], "B")
        self.assertIsNone(p.get("odp_a"))

    def test_should_not_try_complete(self):
        parsed = {
            "odp_a": "a",
            "odp_b": "b",
            "odp_c": "c",
            "odp_d": "d",
            "poprawna_odpowiedz": "B",
        }
        self.assertFalse(
            should_try_cross_page(parsed, "/fake.pdf", 0, "format1_4col", 1, None)
        )


if __name__ == "__main__":
    unittest.main()
