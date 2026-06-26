"""Plan rules for the Benefit Formula Engine.

A pension plan's text gets translated into a small set of numbers and switches.
Keeping them all in one dataclass means the business rules live in exactly one
place. Change the plan here, and every calculation follows the new rules.

All rates are stored as Decimal so the money math stays exact (no float drift).
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class PlanRules:
    """The configurable rules of a defined-benefit pension plan.

    accrual_rate          Fraction of final average earnings earned per year of
                          service. 0.02 means 2 percent per year.
    averaging_window      How many of the member's highest salary years are
                          averaged to form Final Average Earnings (FAE).
    normal_retirement_age The age at which a member can retire with no penalty.
    earliest_retirement_age The youngest age a member is allowed to retire.
    early_reduction_rate  Fraction the pension is reduced for each year the member
                          retires before normal retirement age. 0.06 means 6 percent
                          per year.
    max_credited_service  Service is capped at this many years. Anything above it
                          is clamped, not rejected.
    """

    accrual_rate: Decimal = Decimal("0.02")
    averaging_window: int = 5
    normal_retirement_age: int = 65
    earliest_retirement_age: int = 55
    early_reduction_rate: Decimal = Decimal("0.06")
    max_credited_service: int = 35


# A single shared default so the CLI and the tests agree on the same plan.
DEFAULT_PLAN = PlanRules()
