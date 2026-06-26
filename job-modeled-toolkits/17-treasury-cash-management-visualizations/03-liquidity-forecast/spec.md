# Liquidity Forecast (13-Week)

## Purpose
Projects cash week by week over the next 13 weeks and flags any week that ends below a
minimum-cash buffer. A treasury analyst runs it to see whether the next quarter holds enough cash
and where the tight weeks fall. Opening cash comes from the Cash Position Dashboard and debt
maturities come from the Maturity Ladder, so the three line up on the same numbers.

## Inputs
An operating-cashflows CSV, chosen with the file picker. Header row, then one row per week, weeks 1
through 13, each present exactly once. All amounts are Canadian dollars.

| Column | Type | Meaning |
| --- | --- | --- |
| `week` | whole number 1 to 13 | the week in the horizon |
| `label` | text, not blank | a short note, e.g. `Wk of Jun 15` |
| `operating_inflows` | number, 0 or more | projected receipts that week |
| `operating_outflows` | number, 0 or more | projected operating payments that week |

Settings and optional imports on the page:

- Opening cash in dollars, the balance at the start of week 1. May be negative.
- Minimum buffer in dollars, the floor cash must stay above (default 100000).
- Import opening cash: a `closing-balances.csv` from the Cash Position Dashboard. The tool sums its
  `closing_balance` column and fills the opening-cash field.
- Import debt: a `maturities-by-week.csv` from the Maturity Ladder. The `debt_due` for each week is
  added to that week's outflows.

## Validation rules
- The header must be exactly `week,label,operating_inflows,operating_outflows`, or the file is rejected.
- Every data row must have exactly 4 fields, or it names the row and the count.
- `week` must be a whole number from 1 to 13.
- A week that appears twice is rejected and named.
- Weeks 1 through 13 must all be present. A gap is rejected and the missing week is named.
- `label` must not be blank.
- `operating_inflows` and `operating_outflows` must be dollar figures of 0 or more with at most two decimals.
- Opening cash must be a dollar amount (a negative is allowed). The buffer must be 0 or more.
- An imported `closing-balances.csv` must start with `account,closing_balance`; an imported
  `maturities-by-week.csv` must start with `week,debt_due`. A duplicate week in the maturities file
  is rejected.

## Logic
1. Week 1 opens at the opening cash. Each later week opens at the prior week's closing balance.
2. For each week, total outflows are `operating_outflows + debt_due`, where `debt_due` is 0 when no
   maturities file is loaded.
3. Net cash for the week is `operating_inflows - total_outflows`.
4. Closing balance is `opening + net`. It carries into the next week's opening.
5. Headroom is `closing - minimum_buffer`. A week whose closing is below the buffer is a breach.
6. The summary reports ending cash, the lowest closing balance and its week, the number of breaches,
   and the first breach week.
7. All money is held in integer cents through every step, so the running balance is exact to the cent.

## Outputs
On the page: summary stats, a column chart of closing cash per week with breach weeks in the flag
colour and a dashed minimum-buffer line, and a week-by-week table. The export button writes
`forecast.csv` with one row per week:

`week,label,opening,inflows,operating_outflows,debt_due,total_outflows,net,closing,breach`

The folder also ships `sample-closing-balances.csv` and `sample-maturities-by-week.csv`, the exact
files the other two tools export for the shared sample, so the wired forecast can be reproduced here
on its own.

## Edge cases
The sample exercises weeks that draw cash down past the buffer (weeks 6 and 7, the breach case),
weeks that rebuild it, and two weeks that carry debt maturities (weeks 1 and 13). The
`bad-operating-cashflows.csv` file repeats week 1 so the duplicate-week rejection can be seen. The
test page also feeds in a gap with a missing week and a bad header, and checks the run with no
maturities file loaded.

Hand-checked example, the case that ties the three tools together. Opening cash is 648000.50, the
sum of the closing balances the Cash Position Dashboard exports
(`163500.50 + 1500.00 + 500000.00 - 17000.00`). Week 1 debt of 76750.00 and week 13 debt of
75000.00 come from the Maturity Ladder. The buffer is 100000.00.

- Week 1: inflows 90000.00, operating outflows 70000.00, debt due 76750.00, so total outflows are
  146750.00. Net is `90000.00 - 146750.00 = -56750.00`. Closing is
  `648000.50 - 56750.00 = 591250.50`. Above the buffer, no breach.
- Week 6 is the first breach: it opens at 171250.50 (week 5's close), takes in 100000.00, pays out
  190000.00, nets -90000.00, and closes at 81250.50, which is 18749.50 below the buffer.
- Week 7 is the trough: it opens at 81250.50, nets `70000.00 - 110000.00 = -40000.00`, and closes at
  41250.50, which is 58749.50 below the buffer.
- Cash rebuilds from week 8 and the forecast ends at 146250.50 in week 13 after the 75000.00
  maturity. Two weeks breach the buffer, the first in week 6.
