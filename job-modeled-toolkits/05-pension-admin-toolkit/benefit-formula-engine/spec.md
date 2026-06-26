# Spec: Benefit Formula Engine

## Purpose

Given a member's salary history, credited service, and retirement age, compute the monthly
defined-benefit pension using configurable plan rules. The calculation is deterministic: the
same inputs always produce the same payout.

## Inputs

- Salary history, supplied either as a CSV with a `year,annual_salary` header (`--salary-file`)
  or as repeated `--salary` arguments.
- `--years-of-service`: whole number of years of credited service.
- `--retirement-age`: the member's age at retirement.
- Plan rules, with defaults set in `plan_rules.py` and shared as `DEFAULT_PLAN`:
  - accrual rate: 2.0% per year of service
  - averaging window: best 5 years
  - normal retirement age: 65
  - earliest retirement age: 55
  - early-reduction rate: 6.0% per year before normal age
  - maximum credited service: 35 years

## Validation rules

- Every salary must be a positive number. Zero, negative, blank, or non-numeric values are rejected.
- Years of service must be a positive whole number. Values above the maximum are clamped to the
  maximum (and the report notes the cap), not rejected.
- Retirement age must be between the earliest retirement age (55) and 71.
- There must be at least as many salary years as the averaging window. You cannot average the
  best 5 of only 3.

## Logic

1. **Final Average Earnings (FAE)** is the average of the highest *N* annual salaries, where
   *N* is the averaging window.
2. **Gross annual pension** = accrual rate x credited service x FAE.
3. **Early-retirement reduction**: if retirement age is below normal retirement age, the
   reduction fraction is early-reduction rate x (normal age - retirement age). Net annual =
   gross x (1 - reduction). At or after normal age there is no reduction.
4. **Monthly payout** = net annual / 12, rounded to cents.

All money math uses `Decimal` so cents never drift.

## Outputs

A printed breakdown showing: final average earnings, accrual rate, credited service used (and
whether the cap applied), gross annual pension, the reduction percent applied, net annual
pension, and the monthly payout.

## Edge cases

- Retirement exactly at normal age: no reduction.
- Service above the cap: clamped to the maximum, noted in the report.
- Salary history shorter than the averaging window: clear input error.
- Age below the earliest retirement age: clear input error.

## Worked example (used as a QA cross-check)

Five salary years all equal to $100,000, 30 years of service, retirement at 65:

- FAE = $100,000.00
- Gross annual = 0.02 x 30 x 100,000 = $60,000.00
- Reduction = 0% (retiring at normal age)
- Net annual = $60,000.00
- **Monthly payout = $5,000.00**
