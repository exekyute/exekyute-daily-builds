"""Compare budget against actuals and flag departments over parameters.

A department is flagged when it is over budget AND it breaches either threshold:
the percentage limit OR the dollar limit. A breach of exactly the limit is within
parameters, since the test is strictly greater than. All math uses decimal.Decimal
rounded half up to cents.
"""

from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")
HUNDRED = Decimal("100")

STATUS_UNDER = "Under budget"
STATUS_ON_BUDGET = "On budget"
STATUS_WITHIN = "Over budget (within parameters)"
STATUS_FLAGGED = "Over budget (flagged)"


def format_amount(value):
    """Return a fixed-point string for a Decimal, never scientific notation."""
    return f"{value.quantize(CENTS, rounding=ROUND_HALF_UP):f}"


class DepartmentLine:
    """One department's rolled-up budget, actual, variance, and status."""

    def __init__(self, department, budget, actual):
        self.department = department
        self.budget = budget
        self.actual = actual
        self.variance = (actual - budget).quantize(CENTS, rounding=ROUND_HALF_UP)
        if budget > 0:
            self.variance_pct = (self.variance / budget * HUNDRED).quantize(
                CENTS, rounding=ROUND_HALF_UP
            )
        else:
            self.variance_pct = None
        self.status = STATUS_ON_BUDGET
        self.reasons = []


class AnalysisResult:
    """All department lines plus the line-item findings and counts."""

    def __init__(self):
        self.departments = []
        self.flagged = []
        self.missing_from_actuals = []
        self.unbudgeted = []
        self.duplicates = 0
        self.skipped = 0


def _totals_by_department(items):
    totals = {}
    for (department, _category), value in items.items():
        totals[department] = totals.get(department, Decimal("0")) + value
    return totals


def analyze(budget_items, actual_items, pct_threshold, dollar_threshold):
    """Roll up budget and actuals by department and classify each one.

    `budget_items` and `actual_items` are dicts keyed by (department, category).
    `pct_threshold` and `dollar_threshold` are Decimals. Returns an AnalysisResult.
    """
    result = AnalysisResult()
    budget_by_dept = _totals_by_department(budget_items)
    actual_by_dept = _totals_by_department(actual_items)
    departments = sorted(set(budget_by_dept) | set(actual_by_dept))

    for department in departments:
        budget = budget_by_dept.get(department, Decimal("0")).quantize(
            CENTS, rounding=ROUND_HALF_UP
        )
        actual = actual_by_dept.get(department, Decimal("0")).quantize(
            CENTS, rounding=ROUND_HALF_UP
        )
        line = DepartmentLine(department, budget, actual)

        if line.variance > 0:
            reasons = []
            if line.variance_pct is not None and line.variance_pct > pct_threshold:
                reasons.append(
                    f"over by {line.variance_pct}% (limit {pct_threshold}%)"
                )
            if line.variance > dollar_threshold:
                reasons.append(
                    f"over by {format_amount(line.variance)} "
                    f"(limit {format_amount(dollar_threshold)})"
                )
            if reasons:
                line.status = STATUS_FLAGGED
                line.reasons = reasons
                result.flagged.append(line)
            else:
                line.status = STATUS_WITHIN
        elif line.variance < 0:
            line.status = STATUS_UNDER
        else:
            line.status = STATUS_ON_BUDGET

        result.departments.append(line)

    budget_keys = set(budget_items)
    actual_keys = set(actual_items)
    result.missing_from_actuals = sorted(budget_keys - actual_keys)
    result.unbudgeted = sorted(actual_keys - budget_keys)
    return result
