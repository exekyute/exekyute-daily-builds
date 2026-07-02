"""Tests for the IT cost-allocation engine.

Covers the largest-remainder split (including a case that needs a leftover cent),
the end-to-end allocation against the sample files, the tie-out to the pool, and
the validation rules.

Run from this folder:
  python -m unittest
"""

import unittest
from decimal import Decimal

from allocation import allocate_amount, build_allocation
from cli import load_drivers, load_pool
from validation import ValidationError, validate_driver_row, validate_pool_row


def D(value):
    return Decimal(value)


class AllocateTests(unittest.TestCase):
    def test_clean_split(self):
        shares = allocate_amount(D("60000"), {"Engineering": D("40"), "Sales": D("25"),
                                              "Support": D("20"), "Finance": D("15")})
        self.assertEqual(shares["Engineering"], D("24000.00"))
        self.assertEqual(shares["Sales"], D("15000.00"))
        self.assertEqual(shares["Support"], D("12000.00"))
        self.assertEqual(shares["Finance"], D("9000.00"))

    def test_parts_sum_to_amount(self):
        shares = allocate_amount(D("60000"), {"A": D("40"), "B": D("25"), "C": D("20"), "D": D("15")})
        self.assertEqual(sum(shares.values()), D("60000.00"))

    def test_residual_cent_handled(self):
        # 100.00 across three equal drivers cannot divide evenly; the leftover cent
        # goes to the first key by remainder so the parts still sum to 100.00.
        shares = allocate_amount(D("100.00"), {"A": D("1"), "B": D("1"), "C": D("1")})
        self.assertEqual(sum(shares.values()), D("100.00"))
        self.assertEqual(sorted(shares.values()), [D("33.33"), D("33.33"), D("33.34")])


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.pool = load_pool("cost_pool.csv")
        self.drivers = load_drivers("drivers.csv")
        self.result = build_allocation(self.pool, self.drivers)
        self.by_dept = {r["department"]: r for r in self.result["rows"]}

    def test_pool_total(self):
        self.assertEqual(self.result["pool_total"], D("100000.00"))

    def test_hand_checked_department(self):
        eng = self.by_dept["Engineering"]
        self.assertEqual(eng["allocations"]["Cloud hosting"], D("24000.00"))
        self.assertEqual(eng["allocations"]["Security tooling"], D("10000.00"))
        self.assertEqual(eng["allocations"]["Shared licenses"], D("6000.00"))
        self.assertEqual(eng["total"], D("40000.00"))
        self.assertEqual(eng["pct_of_pool"], D("0.4000"))

    def test_each_department_total(self):
        self.assertEqual(self.by_dept["Sales"]["total"], D("25000.00"))
        self.assertEqual(self.by_dept["Support"]["total"], D("20000.00"))
        self.assertEqual(self.by_dept["Finance"]["total"], D("15000.00"))

    def test_allocated_total_ties_to_pool(self):
        self.assertEqual(self.result["allocated_total"], self.result["pool_total"])

    def test_column_totals_match_item_amounts(self):
        for item in self.result["items"]:
            self.assertEqual(self.result["column_totals"][item], self.result["item_amounts"][item])


class ValidationTests(unittest.TestCase):
    def test_pool_zero_amount_rejected(self):
        with self.assertRaises(ValidationError):
            validate_pool_row({"item": "x", "amount": "0"})

    def test_driver_negative_rejected(self):
        with self.assertRaises(ValidationError):
            validate_driver_row({"department": "Sales", "driver_value": "-1"})

    def test_invalid_driver_file_rejected(self):
        with self.assertRaises(ValidationError):
            load_drivers("drivers_invalid.csv")


if __name__ == "__main__":
    unittest.main()
