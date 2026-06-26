# Payroll Run Calculator, spec

## Purpose
Read an employee timesheet CSV and compute Canadian gross-to-net pay for each
employee, hourly and salaried, then write an auditable per-employee payroll
register CSV. The register is the input for the Net Pay Dashboard tool.

## Inputs
A timesheet CSV with one row per employee and this exact header:

```
employee_id,name,pay_type,rate,hours_worked,pretax_deductions,posttax_deductions
```

- `employee_id`: unique identifier
- `name`: employee name
- `pay_type`: `hourly` or `salaried`
- `rate`: hourly rate, or the per-period salary amount for salaried staff
- `hours_worked`: hours for the period (used for hourly, expected as `0` for salaried)
- `pretax_deductions`: flat pre-tax amount such as a registered pension plan or union dues
- `posttax_deductions`: flat post-tax amount

Run configuration is supplied as command-line flags with Canadian defaults:

| Flag | Default | Meaning |
| --- | --- | --- |
| `--overtime-threshold` | `44` | Weekly hours before overtime applies (Ontario ESA) |
| `--overtime-multiplier` | `1.5` | Overtime pay multiplier |
| `--income-tax-rate` | `0.20` | Flat combined federal and provincial rate |
| `--pay-periods` | `26` | Pay periods per year, used to prorate CPP and EI |

CPP and EI constants (2024 federal figures, outside Quebec) live in
`payroll_logic.py` and are documented there: CPP rate 5.95 percent, annual basic
exemption 3500.00, annual maximum contribution 3867.50; EI rate 1.66 percent,
annual maximum premium 1049.12.

## Validation rules
Bad rows are reported and skipped; the rest of the run still completes.

- Header must contain exactly the seven required columns. A missing or extra
  column is fatal for the whole file.
- Every required field must have a value.
- A row with more fields than the header expects is rejected.
- `pay_type` must be `hourly` or `salaried`.
- `rate`, `hours_worked`, `pretax_deductions`, `posttax_deductions` must be
  non-negative numbers.
- A repeated `employee_id` keeps the first occurrence and flags later ones.
- Zero hours is valid, not an error.

## Logic
All money uses `decimal.Decimal` with ROUND_HALF_UP at two decimal places.

1. Gross pay
   - Salaried: gross equals the per-period salary, no overtime.
   - Hourly: regular hours are capped at the weekly threshold; hours past it earn
     the rate times the overtime multiplier. Gross is regular pay plus overtime pay.
2. CPP contribution: `(gross - period basic exemption) * cpp_rate`, never below
   zero, capped at the per-period maximum (annual maximum divided by pay periods).
3. EI premium: `gross * ei_rate`, capped at the per-period maximum.
4. Income tax: `(gross - pretax_deductions) * income_tax_rate`, never below zero.
5. Total deductions: pre-tax + CPP + EI + income tax + post-tax.
6. Net pay: gross minus total deductions.

Each component is rounded to cents first, then net pay is derived from the
rounded components, so every row reconciles exactly.

## Outputs
`payroll_register.csv` with this header:

```
employee_id,name,pay_type,gross_pay,overtime_pay,pretax_deductions,cpp,ei,income_tax,posttax_deductions,total_deductions,net_pay
```

All money fields are fixed-point with two decimals, never scientific notation.
The run also prints a summary: employees processed, rows rejected with reasons,
total gross, and total net.

## Edge cases
The bundled `data/sample_timesheet.csv` exercises every branch in one run:

- E001 salaried, no overtime, with a pre-tax deduction
- E002 hourly over the threshold, overtime applied (the hand-checked example below)
- E003 hourly under the threshold, no overtime
- E004 hourly with zero hours, gross and net of 0.00
- E005 salaried high earner, hits both the CPP and EI per-period caps
- E002 repeated, flagged as a duplicate
- E007 missing the `rate` value, rejected
- E008 has an extra field, rejected

Result: 5 processed, 3 rejected, total gross 13040.00, total net 9739.53.

## Hand-checked example
Employee E002, hourly, rate 30.00, 50 hours, pre-tax 50.00, post-tax 25.00, with
the default configuration (44 hour threshold, 1.5x, 20 percent tax, 26 periods):

| Step | Amount (CAD) |
| --- | --- |
| Regular pay (44 h x 30.00) | 1320.00 |
| Overtime pay (6 h x 30.00 x 1.5) | 270.00 |
| Gross pay | 1590.00 |
| CPP ((1590.00 - 134.6154) x 0.0595) | 86.60 |
| EI (1590.00 x 0.0166) | 26.39 |
| Income tax ((1590.00 - 50.00) x 0.20) | 308.00 |
| Pre-tax deduction | 50.00 |
| Post-tax deduction | 25.00 |
| Total deductions | 495.99 |
| Net pay | 1094.01 |

The Net Pay Dashboard reads this same register row and shows a net pay of
1094.01, matching to the cent.
