"""Unit tests for the capital call allocator.

Run from the capital-call-allocator folder with:
    python -m unittest discover -s tests -t . -v
"""

import unittest
from decimal import Decimal

import allocator_logic
import allocator_validation


class AllocationLogicTests(unittest.TestCase):
    def called_by_name(self, result):
        return {row["investor"]: row["called_amount"] for row in result}

    def test_clean_even_split(self):
        commitments = [
            ("Aurora", Decimal("5000000")),
            ("Brightwater", Decimal("3000000")),
            ("Cedar", Decimal("2000000")),
        ]
        result = allocator_logic.allocate_call(Decimal("100000.00"), commitments)
        called = self.called_by_name(result)
        self.assertEqual(called["Aurora"], Decimal("50000.00"))
        self.assertEqual(called["Brightwater"], Decimal("30000.00"))
        self.assertEqual(called["Cedar"], Decimal("20000.00"))
        self.assertEqual(
            sum(row["called_amount"] for row in result), Decimal("100000.00")
        )

    def test_hand_checked_remainder(self):
        # The documented example. Brightwater holds the largest dropped fraction
        # (.4545), so it receives the single reconciling cent.
        commitments = [
            ("Aurora Capital", Decimal("4000000")),
            ("Brightwater LP", Decimal("3500000")),
            ("Cedar Grove Partners", Decimal("2500000")),
            ("Dunes Family Office", Decimal("1000000")),
            ("Echo Ventures", Decimal("0")),
        ]
        result = allocator_logic.allocate_call(Decimal("250000.00"), commitments)
        called = self.called_by_name(result)
        self.assertEqual(called["Aurora Capital"], Decimal("90909.09"))
        self.assertEqual(called["Brightwater LP"], Decimal("79545.46"))
        self.assertEqual(called["Cedar Grove Partners"], Decimal("56818.18"))
        self.assertEqual(called["Dunes Family Office"], Decimal("22727.27"))
        self.assertEqual(called["Echo Ventures"], Decimal("0.00"))
        self.assertEqual(
            sum(row["called_amount"] for row in result), Decimal("250000.00")
        )

    def test_zero_commitment_gets_zero(self):
        commitments = [
            ("Funded", Decimal("1000000")),
            ("Unfunded", Decimal("0")),
        ]
        result = allocator_logic.allocate_call(Decimal("500.00"), commitments)
        called = self.called_by_name(result)
        self.assertEqual(called["Unfunded"], Decimal("0.00"))
        self.assertEqual(called["Funded"], Decimal("500.00"))

    def test_ownership_percentages_match_commitments(self):
        commitments = [
            ("Half", Decimal("5000000")),
            ("Third", Decimal("3000000")),
            ("Rest", Decimal("2000000")),
        ]
        result = allocator_logic.allocate_call(Decimal("100000.00"), commitments)
        ownership = {row["investor"]: row["ownership_pct"] for row in result}
        self.assertEqual(ownership["Half"], Decimal("50.0000"))
        self.assertEqual(ownership["Third"], Decimal("30.0000"))
        self.assertEqual(ownership["Rest"], Decimal("20.0000"))

    def test_sum_always_equals_call_total(self):
        commitments = [
            ("A", Decimal("1000000")),
            ("B", Decimal("1000000")),
            ("C", Decimal("1000000")),
        ]
        for total in ["100.00", "100.01", "0.01", "33.33", "999999.99", "1.00"]:
            result = allocator_logic.allocate_call(Decimal(total), commitments)
            self.assertEqual(
                sum(row["called_amount"] for row in result),
                Decimal(total).quantize(Decimal("0.01")),
                f"called amounts did not sum to {total}",
            )

    def test_three_equal_investors_penny_goes_to_first(self):
        commitments = [
            ("A", Decimal("1000000")),
            ("B", Decimal("1000000")),
            ("C", Decimal("1000000")),
        ]
        result = allocator_logic.allocate_call(Decimal("100.00"), commitments)
        called = self.called_by_name(result)
        # Equal remainders and equal commitments, so the name order breaks the tie.
        self.assertEqual(called["A"], Decimal("33.34"))
        self.assertEqual(called["B"], Decimal("33.33"))
        self.assertEqual(called["C"], Decimal("33.33"))

    def test_no_scientific_notation(self):
        commitments = [("A", Decimal("1000000")), ("B", Decimal("2000000"))]
        result = allocator_logic.allocate_call(Decimal("1000000000.00"), commitments)
        for row in result:
            text = format(row["called_amount"], "f")
            self.assertNotIn("E", text)
            self.assertNotIn("e", text)


class ValidationTests(unittest.TestCase):
    HEADER = ["investor", "commitment"]

    def test_valid_rows(self):
        rows = [["Aurora", "100"], ["Brightwater", "200"]]
        commitments, errors = allocator_validation.validate_commitments(self.HEADER, rows)
        self.assertEqual(errors, [])
        self.assertEqual(
            commitments, [("Aurora", Decimal("100")), ("Brightwater", Decimal("200"))]
        )

    def test_missing_field(self):
        _, errors = allocator_validation.validate_commitments(self.HEADER, [["Aurora"]])
        self.assertTrue(any("expected 2 fields" in message for message in errors))

    def test_extra_field(self):
        rows = [["Aurora", "100", "oops"]]
        _, errors = allocator_validation.validate_commitments(self.HEADER, rows)
        self.assertTrue(any("expected 2 fields" in message for message in errors))

    def test_duplicate_investor(self):
        rows = [["Aurora", "100"], ["Aurora", "200"]]
        _, errors = allocator_validation.validate_commitments(self.HEADER, rows)
        self.assertTrue(any("duplicate" in message.lower() for message in errors))

    def test_non_numeric_commitment(self):
        rows = [["Aurora", "abc"]]
        _, errors = allocator_validation.validate_commitments(self.HEADER, rows)
        self.assertTrue(any("not a valid number" in message for message in errors))

    def test_negative_commitment(self):
        rows = [["Aurora", "-5"]]
        _, errors = allocator_validation.validate_commitments(self.HEADER, rows)
        self.assertTrue(any("negative" in message for message in errors))

    def test_all_zero_total_rejected(self):
        rows = [["Aurora", "0"], ["Brightwater", "0"]]
        _, errors = allocator_validation.validate_commitments(self.HEADER, rows)
        self.assertTrue(any("greater than zero" in message for message in errors))

    def test_empty_file(self):
        commitments, errors = allocator_validation.validate_commitments(None, [])
        self.assertEqual(commitments, [])
        self.assertTrue(any("empty" in message.lower() for message in errors))

    def test_bad_header(self):
        _, errors = allocator_validation.validate_commitments(["name", "amount"], [["A", "1"]])
        self.assertTrue(any("Header" in message for message in errors))

    def test_collects_every_problem_at_once(self):
        rows = [
            ["Aurora", "100"],
            ["Aurora", "200"],          # duplicate
            ["Brightwater"],            # missing field
            ["Cedar", "100", "extra"],  # extra field
            ["Dunes", "notanumber"],    # non-numeric
            ["Echo", "-1"],             # negative
        ]
        _, errors = allocator_validation.validate_commitments(self.HEADER, rows)
        self.assertGreaterEqual(len(errors), 5)

    def test_call_total_must_be_positive(self):
        value, errors = allocator_validation.validate_call_total("0")
        self.assertIsNone(value)
        self.assertTrue(errors)

    def test_call_total_not_a_number(self):
        value, errors = allocator_validation.validate_call_total("abc")
        self.assertIsNone(value)
        self.assertTrue(errors)

    def test_call_total_valid(self):
        value, errors = allocator_validation.validate_call_total("250000.00")
        self.assertEqual(value, Decimal("250000.00"))
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
