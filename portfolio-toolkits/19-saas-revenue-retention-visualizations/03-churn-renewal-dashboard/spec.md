# Churn and Renewal Dashboard

## Purpose
Reads the movement table the MRR Movement Waterfall exports and turns it into the retention
metrics a revenue or subscription analyst reports each month: the MRR churn rate, gross revenue
retention, and net revenue retention. With a renewals file it also lists the contracts coming up
for renewal in the months ahead.

## Inputs
Two CSV files.

Movement CSV, the file the MRR Movement Waterfall exports. Header and columns:

- `month` (text, `YYYY-MM`).
- `opening_mrr`, `new_mrr`, `expansion_mrr`, `contraction_mrr`, `churned_mrr`, `closing_mrr`
  (numbers, dollars, zero or more).

Renewals CSV. Header and columns:

- `customer_id` (text) - a stable identifier for the customer.
- `mrr` (number) - the recurring revenue up for renewal, in dollars, greater than zero.
- `renewal_month` (text, `YYYY-MM`) - the month the current term ends.
- `term_months` (whole number) - the length of the term, one or more.

## Validation rules
Each parser stops at the first problem and names the row.

Movement CSV:

- The header must be the seven columns the waterfall exports, in order.
- Every row must have exactly seven fields, a valid `YYYY-MM` month, no repeated month, and money
  values with up to two decimals.
- Every row must reconcile: opening plus new plus expansion minus contraction minus churn must
  equal closing. A file that does not reconcile is rejected, so the dashboard never reports off a
  broken table.

Renewals CSV:

- The header must be exactly `customer_id,mrr,renewal_month,term_months`.
- Every row must have exactly four fields.
- `customer_id` must not be blank and must not repeat.
- `mrr` must be a positive amount with up to two decimals.
- `renewal_month` must be a valid `YYYY-MM` month.
- `term_months` must be a whole number of one or more.

## Logic
For each movement month with an opening base above zero:

- **MRR churn rate** = churned / opening.
- **Gross revenue retention (GRR)** = (opening - contraction - churned) / opening.
- **Net revenue retention (NRR)** = (opening + expansion - contraction - churned) / opening.

A month that opens at zero has no base to retain against, so its rates are left undefined and show
as n/a. All percentages are rounded to two decimals, half up. Money is held in integer cents.

For renewals, the window runs from the month after the as-of month through the as-of month plus
the horizon. Renewals are grouped by renewal month, counted, and summed.

## Outputs
On screen: a retention chart with the net and gross retention lines and a faint churn-rate bar per
month against a 100% reference line, a retention table, and an upcoming-renewals bar chart and
table driven by the as-of month and horizon controls. A stat summary shows the latest month's
metrics and the value up for renewal in the window.

## Edge cases
The sample movement file is the exact export from the waterfall's sample ledger, so the two tools
share one book of business. It exercises every branch:

- **No base:** January opens at zero, so its rates are n/a.
- **Expansion lifting NRR above GRR:** March has 200.00 of expansion and no losses, so GRR is
  100.00% while NRR is 115.38%.
- **Losses on both sides:** April has both contraction and churn, the worked example below.
- **Clean month:** May has no losses, so churn is 0.00% and GRR is 100.00%.

The renewals sample groups three renewals into June, one into July, and one into August for a
three-month window from the end of May, and pushes the September, October, November, and
next-January renewals outside it.

Worked example, April 2025, checked to the cent. The waterfall exports the April row
`opening 2,500.00, new 250.00, expansion 100.00, contraction 50.00, churn 50.00, closing
2,750.00`. The dashboard reads that row and rebuilds closing from the components,
2,500.00 + 250.00 + 100.00 - 50.00 - 50.00 = 2,750.00, the same figure the waterfall reports. From
those components:

- MRR churn rate = 50.00 / 2,500.00 = **2.00%**.
- Gross revenue retention = (2,500.00 - 50.00 - 50.00) / 2,500.00 = 2,400.00 / 2,500.00 =
  **96.00%**.
- Net revenue retention = (2,500.00 + 100.00 - 50.00 - 50.00) / 2,500.00 = 2,500.00 / 2,500.00 =
  **100.00%**.

The waterfall and the dashboard agree on the April closing of 2,750.00 to the cent, which is the
proof the two tools describe the same numbers.

Upcoming renewals, as of the end of May 2025 with a three-month horizon: June 650.00 across 3 renewals
(C001 300.00, C004 150.00, C007 200.00), July 1,000.00 (C003), August 50.00 (C005), for 1,700.00
across 5 renewals in the window.
