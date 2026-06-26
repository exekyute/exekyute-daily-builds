"""Tests for the Ledger Reconciliation Tool.

Run from the repository root:
    python -m unittest discover -s ledger-reconciliation/tests -v
"""

import os
import sys
import unittest
from decimal import Decimal

# Make the tool's modules (one directory up) importable.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from reconciler import (
    reconcile,
    summarize,
    MATCHED,
    VARIANCE,
    MISSING_IN_TRUSTEE,
    MISSING_IN_INTERNAL,
)


def make_ledger(records, duplicates=None, skipped=None):
    """Tiny helper to build a loader-shaped dict without touching the disk."""
    return {
        "records": records,
        "duplicates": duplicates or [],
        "skipped": skipped or [],
    }


def by_id(lines):
    """Index reconciliation lines by employee_id for easy assertions."""
    return {line.employee_id: line for line in lines}


class TestReconcile(unittest.TestCase):
    def test_exact_match(self):
        internal = make_ledger({"E1": {"amount": Decimal("100.00"), "name": "A"}})
        trustee = make_ledger({"E1": {"amount": Decimal("100.00")}})
        line = by_id(reconcile(internal, trustee))["E1"]
        self.assertEqual(line.status, MATCHED)
        self.assertEqual(line.variance, Decimal("0.00"))

    def test_variance_above_tolerance(self):
        internal = make_ledger({"E1": {"amount": Decimal("100.00"), "name": "A"}})
        trustee = make_ledger({"E1": {"amount": Decimal("90.00")}})
        line = by_id(reconcile(internal, trustee))["E1"]
        self.assertEqual(line.status, VARIANCE)
        self.assertEqual(line.variance, Decimal("10.00"))

    def test_within_tolerance_is_matched(self):
        internal = make_ledger({"E1": {"amount": Decimal("100.00"), "name": "A"}})
        trustee = make_ledger({"E1": {"amount": Decimal("100.01")}})
        line = by_id(reconcile(internal, trustee))["E1"]
        self.assertEqual(line.status, MATCHED)

    def test_missing_in_trustee(self):
        internal = make_ledger({"E1": {"amount": Decimal("100.00"), "name": "A"}})
        trustee = make_ledger({})
        line = by_id(reconcile(internal, trustee))["E1"]
        self.assertEqual(line.status, MISSING_IN_TRUSTEE)

    def test_missing_in_internal(self):
        internal = make_ledger({})
        trustee = make_ledger({"E1": {"amount": Decimal("100.00")}})
        line = by_id(reconcile(internal, trustee))["E1"]
        self.assertEqual(line.status, MISSING_IN_INTERNAL)


class TestSummarize(unittest.TestCase):
    def test_counts_each_status_and_duplicates(self):
        internal = make_ledger(
            {
                "E1": {"amount": Decimal("100.00"), "name": "A"},
                "E2": {"amount": Decimal("200.00"), "name": "B"},
                "E3": {"amount": Decimal("300.00"), "name": "C"},  # missing in trustee
            },
            duplicates=["E1"],
        )
        trustee = make_ledger(
            {
                "E1": {"amount": Decimal("100.00")},  # matched
                "E2": {"amount": Decimal("250.00")},  # variance
                "E4": {"amount": Decimal("400.00")},  # missing in internal
            }
        )
        lines = reconcile(internal, trustee)
        counts = summarize(lines, internal, trustee)
        self.assertEqual(counts[MATCHED], 1)
        self.assertEqual(counts[VARIANCE], 1)
        self.assertEqual(counts[MISSING_IN_TRUSTEE], 1)
        self.assertEqual(counts[MISSING_IN_INTERNAL], 1)
        self.assertEqual(counts["duplicates"], 1)


if __name__ == "__main__":
    unittest.main()
