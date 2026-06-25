# MRR Movement Waterfall

## Purpose
Takes a monthly recurring-revenue ledger and shows how the recurring revenue base moves from one
month to the next, splitting the change into new, expansion, contraction, and churned revenue. A
revenue or subscription analyst runs it to explain why closing MRR differs from opening MRR, and
to hand the movement table to the churn and renewal dashboard.

## Inputs
A ledger CSV with one row per customer per month that customer is active. Header and columns:

- `customer_id` (text) - a stable identifier for the customer.
- `plan` (text) - one of `Basic`, `Pro`, or `Enterprise`.
- `signup_month` (text, `YYYY-MM`) - the month the customer first started.
- `month` (text, `YYYY-MM`) - the month this recurring revenue applies to.
- `mrr` (number) - recurring revenue for that month, in dollars, greater than zero.

A customer that is not active in a month simply has no row for that month. That absence is how
the tool sees churn.

## Validation rules
The tool stops at the first problem and names the row.

- The header must be exactly `customer_id,plan,signup_month,month,mrr`.
- Every row must have exactly five fields.
- `customer_id` must not be blank.
- `plan` must be one of `Basic`, `Pro`, or `Enterprise`.
- `signup_month` and `month` must be valid `YYYY-MM` months (month number 01 to 12).
- `month` must not be earlier than `signup_month`.
- A `customer_id` and `month` pair must not repeat.
- `mrr` must be a positive amount with up to two decimals, greater than zero.

## Logic
1. Read every distinct month in the ledger and sort them in ascending order.
2. For each month, build a map of customer to MRR for that month and for the month before it.
3. Opening is the sum of the prior month's MRR. Closing is the sum of this month's MRR.
4. Classify each customer:
   - active this month but not last month: the full amount counts as **new**.
   - active both months with a higher amount: the increase counts as **expansion**.
   - active both months with a lower amount: the decrease counts as **contraction**.
   - active last month but not this month: the prior amount counts as **churned**.
5. The identity holds every month: closing equals opening plus new plus expansion minus
   contraction minus churn. The first month has no prior month, so it opens at zero and its whole
   book is new.

All money is held in integer cents through the whole calculation, so the totals stay exact. The
export writes dollars with two decimals.

## Outputs
On screen: a waterfall for the selected month (opening, then new and expansion in green, then
contraction and churn in red, then closing), a stat summary, and a table of every month. An MRR
or ARR toggle multiplies the display by twelve for the annual view. Money shows in Canadian
dollars.

Exported file `mrr-movement.csv` with the header
`month,opening_mrr,new_mrr,expansion_mrr,contraction_mrr,churned_mrr,closing_mrr`, one row per
month. The churn and renewal dashboard reads this file.

## Edge cases
The sample ledger is built to exercise every branch in one run:

- **Clean carry-forward:** C001 holds steady at 200.00 from January through March.
- **Expansion:** C001 rises from 200.00 to 300.00 in April; C003 rises from 800.00 to 1,000.00
  in March.
- **Contraction:** C004 falls from 200.00 to 150.00 in April.
- **Churn:** C002 is active January through March, then has no April row, so its 50.00 churns.
- **New in a later month:** C008 and C009 first appear in April; C010 first appears in May.
- **First month boundary:** January opens at zero and is entirely new.

Worked example, April 2025, checked to the cent:

- Opening (March total) = 200.00 + 50.00 + 1,000.00 + 200.00 + 50.00 + 800.00 + 200.00 =
  **2,500.00**.
- New = C008 50.00 + C009 200.00 = **250.00**.
- Expansion = C001 from 200.00 to 300.00 = **100.00**.
- Contraction = C004 from 200.00 to 150.00 = **50.00**.
- Churn = C002 50.00 = **50.00**.
- Closing = 2,500.00 + 250.00 + 100.00 - 50.00 - 50.00 = **2,750.00**, which equals the April
  total 300.00 + 1,000.00 + 150.00 + 50.00 + 800.00 + 200.00 + 50.00 + 200.00.

The churn and renewal dashboard reads this same April row and rebuilds closing from the
components, landing on 2,750.00 as well, with gross revenue retention 96.00% and net revenue
retention 100.00%. The two tools agree to the cent.
