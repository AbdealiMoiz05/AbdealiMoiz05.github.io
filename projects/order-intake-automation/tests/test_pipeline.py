"""Quick checks on the parts most likely to break. Run: python3 -m unittest discover tests"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import extract  # noqa: E402

CUSTOMERS = extract.load_customers()


class RulesReader(unittest.TestCase):
    def test_table_row_skips_line_number_and_description_numbers(self):
        text = ("From: x <a@northfield-motors.example>\nDate: 01/11/2026\nPO number: 45112345\n"
                "2    | WB-3300  | Wiper blade, flat 600mm |     40 | £    5.98 | 10/12/2026\n")
        r = extract.rules_extract(text, CUSTOMERS)
        self.assertEqual(r["lines"], [{"part_no": "WB-3300", "quantity": 40, "unit_price": 5.98,
                                       "requested_date": "2026-12-10"}])
        self.assertEqual(r["confidence"], "high")

    def test_free_text_date_without_year_rolls_into_next_year(self):
        self.assertEqual(extract.parse_date("needed by the 8th January", date(2026, 11, 2)), "2027-01-08")

    def test_correction_in_thread_is_low_confidence(self):
        text = ("From: x <a@mcv-leyland.example>\nDate: 02/11/2026\nSubject: Order 45512345\n"
                "line 1 (SP-1001) should be 100, not 150.\n  - SP-1001  qty 150  @ £3.78  by 20/11/2026\n")
        r = extract.rules_extract(text, CUSTOMERS)
        self.assertEqual(r["confidence"], "low")
        self.assertIn("correction_in_thread", r["uncertain_fields"])
        self.assertEqual(len(r["lines"]), 1)  # the correction line has no price, so it is not a new line

    def test_missing_po_is_reported(self):
        r = extract.rules_extract("PO number: to follow\nFrom: a@tvev.example\n", CUSTOMERS)
        self.assertIsNone(r["po_number"])
        self.assertIn("po_number", r["uncertain_fields"])


if __name__ == "__main__":
    unittest.main()
