"""Tests for the expense and travel policy auditor.

Covers the mileage recompute, each policy flag, duplicate detection, the
end-to-end run against the sample files, and the validation rules.

Run from this folder:
  python -m unittest
"""

import unittest
from decimal import Decimal

from audit import audit, duplicate_keys, flags_for, mileage_amount
from cli import load_expenses, load_policy
from validation import ValidationError, load_policy_rows, validate_expense_row


def D(value):
    return Decimal(value)


POLICY = {
    "mileage_rate": D("0.70"),
    "receipt_threshold": D("25.00"),
    "caps": {"Meals": D("75.00"), "Lodging": D("250.00"), "Supplies": D("200.00")},
}


def expense(**overrides):
    base = {
        "expense_id": "E", "date": "2026-06-01", "employee": "X", "category": "Meals",
        "amount": D("10.00"), "km": D("0"), "receipt": True,
    }
    base.update(overrides)
    return base


class UnitTests(unittest.TestCase):
    def test_mileage_amount(self):
        self.assertEqual(mileage_amount(D("250"), D("0.70")), D("175.00"))

    def test_mileage_match_no_flag(self):
        e = expense(category="Mileage", amount=D("175.00"), km=D("250"), receipt=False)
        self.assertEqual(flags_for(e, POLICY, set()), [])

    def test_mileage_mismatch_flag(self):
        e = expense(category="Mileage", amount=D("220.00"), km=D("300"), receipt=False)
        self.assertEqual(flags_for(e, POLICY, set()), ["MILEAGE_MISMATCH"])

    def test_over_cap_flag(self):
        e = expense(category="Meals", amount=D("95.00"), receipt=True)
        self.assertEqual(flags_for(e, POLICY, set()), ["OVER_CAP"])

    def test_no_receipt_flag(self):
        e = expense(category="Supplies", amount=D("40.00"), receipt=False)
        self.assertEqual(flags_for(e, POLICY, set()), ["NO_RECEIPT"])

    def test_receipt_present_no_flag(self):
        e = expense(category="Supplies", amount=D("40.00"), receipt=True)
        self.assertEqual(flags_for(e, POLICY, set()), [])

    def test_duplicate_detection(self):
        a = expense(expense_id="A", employee="M", date="2026-06-07", category="Meals", amount=D("60.00"))
        b = expense(expense_id="B", employee="M", date="2026-06-07", category="Meals", amount=D("60.00"))
        keys = duplicate_keys([a, b])
        self.assertIn("DUPLICATE", flags_for(a, POLICY, keys))


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.policy = load_policy("policy.csv")
        self.expenses = load_expenses("expenses.csv", self.policy)
        self.result = audit(self.expenses, self.policy)
        self.by_id = {r["expense_id"]: r for r in self.result["rows"]}

    def test_mileage_hand_check(self):
        self.assertEqual(self.by_id["E-01"]["computed_amount"], D("175.00"))
        self.assertEqual(self.by_id["E-01"]["status"], "Approved")
        self.assertEqual(self.by_id["E-02"]["flags"], ["MILEAGE_MISMATCH"])

    def test_each_flag_present(self):
        self.assertEqual(self.by_id["E-03"]["flags"], ["OVER_CAP"])
        self.assertEqual(self.by_id["E-04"]["flags"], ["NO_RECEIPT"])
        self.assertEqual(self.by_id["E-05"]["status"], "Approved")
        self.assertIn("DUPLICATE", self.by_id["E-06"]["flags"])
        self.assertIn("DUPLICATE", self.by_id["E-07"]["flags"])

    def test_totals(self):
        t = self.result["totals"]
        self.assertEqual(t["total_claimed"], D("890.00"))
        self.assertEqual(t["flagged_amount"], D("475.00"))
        self.assertEqual(t["approved_amount"], D("415.00"))
        self.assertEqual(t["approved_count"], 2)
        self.assertEqual(t["flagged_count"], 5)
        self.assertEqual(t["over_cap_count"], 1)
        self.assertEqual(t["no_receipt_count"], 1)
        self.assertEqual(t["duplicate_count"], 2)
        self.assertEqual(t["mileage_mismatch_count"], 1)


class ValidationTests(unittest.TestCase):
    def test_unknown_category_rejected(self):
        with self.assertRaises(ValidationError):
            validate_expense_row(
                {"expense_id": "E", "date": "2026-06-01", "employee": "X", "category": "Entertainment",
                 "amount": "10", "km": "", "receipt": "yes"}, POLICY)

    def test_mileage_needs_km(self):
        with self.assertRaises(ValidationError):
            validate_expense_row(
                {"expense_id": "E", "date": "2026-06-01", "employee": "X", "category": "Mileage",
                 "amount": "10", "km": "0", "receipt": "no"}, POLICY)

    def test_bad_receipt_rejected(self):
        with self.assertRaises(ValidationError):
            validate_expense_row(
                {"expense_id": "E", "date": "2026-06-01", "employee": "X", "category": "Meals",
                 "amount": "10", "km": "", "receipt": "maybe"}, POLICY)

    def test_policy_missing_rate_rejected(self):
        with self.assertRaises(ValidationError):
            load_policy_rows([{"param": "receipt_threshold", "value": "25"}])

    def test_invalid_expense_file_rejected(self):
        policy = load_policy("policy.csv")
        with self.assertRaises(ValidationError):
            load_expenses("expenses_invalid.csv", policy)


if __name__ == "__main__":
    unittest.main()
