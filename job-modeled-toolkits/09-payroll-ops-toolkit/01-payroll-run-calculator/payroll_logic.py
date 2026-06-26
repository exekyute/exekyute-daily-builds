"""Pure payroll calculation logic for Canadian gross-to-net pay.

No file or console input/output lives here. Every function takes plain
values and returns Decimal money quantized to cents, so the same logic can
be unit tested in isolation and reused by the command-line wrapper.

All money uses decimal.Decimal with ROUND_HALF_UP, the rounding rule used on
a Canadian pay stub: a half cent always rounds up.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

CENTS = Decimal("0.01")


def money(value):
    """Quantize any number to two decimal places using ROUND_HALF_UP."""
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PayrollConfig:
    """Canadian payroll constants applied to a single pay period.

    Defaults reflect 2024 federal CRA figures for employees outside Quebec.
    Every value can be overridden so the tool stays rule-based and
    transparent rather than locked to one year or one province.

    CPP and EI are annual programs with a yearly maximum. Here they are
    prorated across pay_periods_per_year so a single pay run applies a fair
    per-period share of the annual exemption and the annual cap.
    """

    overtime_threshold: Decimal = Decimal("44")        # Ontario ESA weekly hours
    overtime_multiplier: Decimal = Decimal("1.5")
    income_tax_rate: Decimal = Decimal("0.20")          # combined federal + provincial, flat
    pay_periods_per_year: int = 26                       # biweekly

    cpp_rate: Decimal = Decimal("0.0595")
    cpp_annual_basic_exemption: Decimal = Decimal("3500.00")
    cpp_max_annual_contribution: Decimal = Decimal("3867.50")

    ei_rate: Decimal = Decimal("0.0166")
    ei_max_annual_premium: Decimal = Decimal("1049.12")

    @property
    def cpp_period_exemption(self):
        return Decimal(self.cpp_annual_basic_exemption) / self.pay_periods_per_year

    @property
    def cpp_period_max(self):
        return Decimal(self.cpp_max_annual_contribution) / self.pay_periods_per_year

    @property
    def ei_period_max(self):
        return Decimal(self.ei_max_annual_premium) / self.pay_periods_per_year


def gross_pay(pay_type, rate, hours_worked, config):
    """Return (gross_pay, overtime_pay) for one employee as Decimal cents.

    Salaried employees are paid their per-period salary with no overtime.
    Hourly employees earn the regular rate up to the weekly threshold and the
    overtime multiplier on every hour past it.
    """
    rate = Decimal(str(rate))
    if pay_type == "salaried":
        return money(rate), money(0)

    hours = Decimal(str(hours_worked))
    threshold = config.overtime_threshold
    regular_hours = min(hours, threshold)
    overtime_hours = max(hours - threshold, Decimal("0"))

    regular = regular_hours * rate
    overtime = overtime_hours * rate * config.overtime_multiplier
    return money(regular + overtime), money(overtime)


def cpp_contribution(gross, config):
    """CPP contribution on this period's pensionable earnings.

    Applies the per-period share of the basic exemption, then caps at the
    per-period maximum so a high earner never contributes past the annual cap.
    """
    pensionable = Decimal(str(gross)) - config.cpp_period_exemption
    if pensionable <= 0:
        return money(0)
    contribution = pensionable * config.cpp_rate
    return money(min(contribution, config.cpp_period_max))


def ei_premium(gross, config):
    """EI premium on this period's insurable earnings, capped at the period max."""
    premium = Decimal(str(gross)) * config.ei_rate
    return money(min(premium, config.ei_period_max))


def income_tax(gross, pretax_deductions, config):
    """Flat combined federal and provincial income tax on taxable pay.

    Pre-tax deductions (such as a registered pension plan or union dues)
    reduce taxable income before the rate is applied.
    """
    taxable = Decimal(str(gross)) - Decimal(str(pretax_deductions))
    if taxable <= 0:
        return money(0)
    return money(taxable * config.income_tax_rate)


def calculate_pay(employee, config):
    """Compute a full pay record for one validated employee row.

    `employee` is a dict with already validated, numeric string fields:
    employee_id, name, pay_type, rate, hours_worked, pretax_deductions,
    posttax_deductions.

    Each money component is rounded to cents, then net pay is derived from the
    rounded components so the register always reconciles to the cent:
    net = gross - (pre-tax + CPP + EI + income tax + post-tax).
    """
    gross, overtime = gross_pay(
        employee["pay_type"],
        employee["rate"],
        employee["hours_worked"],
        config,
    )
    pretax = money(employee["pretax_deductions"])
    posttax = money(employee["posttax_deductions"])

    cpp = cpp_contribution(gross, config)
    ei = ei_premium(gross, config)
    tax = income_tax(gross, pretax, config)

    total_deductions = money(pretax + cpp + ei + tax + posttax)
    net = money(gross - total_deductions)

    return {
        "employee_id": employee["employee_id"],
        "name": employee["name"],
        "pay_type": employee["pay_type"],
        "gross_pay": gross,
        "overtime_pay": overtime,
        "pretax_deductions": pretax,
        "cpp": cpp,
        "ei": ei,
        "income_tax": tax,
        "posttax_deductions": posttax,
        "total_deductions": total_deductions,
        "net_pay": net,
    }
