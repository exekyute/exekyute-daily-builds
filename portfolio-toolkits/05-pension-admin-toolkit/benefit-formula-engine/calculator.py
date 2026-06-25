"""The pension math, expressed as small pure functions.

Pure means: give the same inputs, get the same output, with no printing and no
file access. That makes every function here trivial to test and easy to trust.
The CLI in benefit_engine.py is what reads files and prints; this module only
calculates.
"""

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass

from plan_rules import PlanRules

CENTS = Decimal("0.01")


def _round_money(amount: Decimal) -> Decimal:
    """Round to two decimal places using standard banker-friendly half-up."""
    return amount.quantize(CENTS, rounding=ROUND_HALF_UP)


def final_average_earnings(salaries, rules: PlanRules) -> Decimal:
    """Average the highest N salaries, where N is the plan's averaging window.

    Sorting descending and taking the top N models a "best N years" plan, which
    is the most common defined-benefit design.
    """
    top = sorted(salaries, reverse=True)[: rules.averaging_window]
    total = sum(top, Decimal("0"))
    return _round_money(total / Decimal(len(top)))


def gross_annual_pension(fae: Decimal, credited_service: int, rules: PlanRules) -> Decimal:
    """Gross yearly pension before any early-retirement reduction.

    gross = accrual_rate * years_of_service * final_average_earnings
    """
    gross = rules.accrual_rate * Decimal(credited_service) * fae
    return _round_money(gross)


def early_reduction_fraction(retirement_age: int, rules: PlanRules) -> Decimal:
    """Fraction the pension is reduced for retiring early. Zero at or after normal age."""
    if retirement_age >= rules.normal_retirement_age:
        return Decimal("0")
    years_early = rules.normal_retirement_age - retirement_age
    return rules.early_reduction_rate * Decimal(years_early)


def apply_early_reduction(gross: Decimal, reduction: Decimal) -> Decimal:
    """Apply a reduction fraction to the gross pension."""
    net = gross * (Decimal("1") - reduction)
    return _round_money(net)


@dataclass(frozen=True)
class BenefitResult:
    """Everything the calculation produced, ready for a caller to display."""

    final_average_earnings: Decimal
    credited_service: int
    service_was_capped: bool
    gross_annual: Decimal
    reduction_fraction: Decimal
    net_annual: Decimal
    monthly_payout: Decimal


def calculate_benefit(salaries, credited_service, service_was_capped, retirement_age, rules: PlanRules) -> BenefitResult:
    """Run the full pipeline and return a structured result.

    Inputs are assumed already validated by validators.py. This function only
    does arithmetic, in the order the plan text describes:
      1. Final Average Earnings
      2. Gross annual pension
      3. Early-retirement reduction
      4. Monthly payout
    """
    fae = final_average_earnings(salaries, rules)
    gross = gross_annual_pension(fae, credited_service, rules)
    reduction = early_reduction_fraction(retirement_age, rules)
    net = apply_early_reduction(gross, reduction)
    monthly = _round_money(net / Decimal("12"))

    return BenefitResult(
        final_average_earnings=fae,
        credited_service=credited_service,
        service_was_capped=service_was_capped,
        gross_annual=gross,
        reduction_fraction=reduction,
        net_annual=net,
        monthly_payout=monthly,
    )
