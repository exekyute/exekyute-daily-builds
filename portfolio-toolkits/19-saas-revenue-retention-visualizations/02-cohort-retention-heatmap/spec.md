# Cohort Retention Heatmap

## Purpose
Groups customers by the month they signed up and shows how much of each cohort stays over the
months that follow, as a heatmap. A revenue or subscription analyst runs it to see whether newer
cohorts hold better than older ones, and to separate revenue retention from logo retention.

## Inputs
The same ledger CSV the MRR Movement Waterfall reads, one row per customer per month that customer
is active. Header and columns:

- `customer_id` (text) - a stable identifier for the customer.
- `plan` (text) - one of `Basic`, `Pro`, or `Enterprise`.
- `signup_month` (text, `YYYY-MM`) - the month the customer first started. This sets the cohort.
- `month` (text, `YYYY-MM`) - the month this recurring revenue applies to.
- `mrr` (number) - recurring revenue for that month, in dollars, greater than zero.

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
1. Read the distinct signup months and sort them. Each is a cohort.
2. Find the latest month in the ledger. The widest cohort sets the number of offset columns.
3. For each cohort, the starting revenue is the sum of its customers' MRR in the signup month,
   and the starting count is the number of customers in the cohort.
4. For each offset (months since signup), find the calendar month and sum the cohort's MRR and
   count its active customers in that month.
5. Revenue retention is retained revenue over starting revenue. Logo retention is active
   customers over the starting count. Both are rounded to two decimals, half up.
6. A calendar month past the end of the ledger has no data, so that cell is left blank rather
   than shown as zero.

All money is held in integer cents through the whole calculation, so the totals stay exact.

## Outputs
On screen: a heatmap with one row per cohort and one column per offset month. Cell colour deepens
with retention, the text shows the rounded percent, and hovering a cell shows the exact figures. A
measure dropdown switches between revenue retention and logo retention. Money shows in Canadian
dollars.

Exported file `cohort-retention.csv` with the header `cohort,start_mrr,cohort_size,month_0,...`,
one row per cohort, holding the revenue retention percents.

## Edge cases
The sample ledger is built to exercise every branch in one run:

- **Full retention:** the March cohort (C006, C007) holds 100% revenue and 100% logos every
  month it is observed.
- **Expansion above 100%:** the January cohort rises above its start as C001 and C003 expand.
- **Churn shows as a logo drop:** the January cohort loses C002 in its fourth month, so logo
  retention falls to 66.67% while revenue retention stays above 100%.
- **Contraction shows as a revenue dip:** the February cohort falls to 80% revenue in its third
  month as C004 contracts, while both customers are still active.
- **Short cohort with blanks:** the May cohort (C010) has data only at offset 0; later cells are
  blank.

Worked example, the January 2025 cohort, checked to the cent:

- Starting revenue (offset 0, January) = C001 200.00 + C002 50.00 + C003 800.00 = **1,050.00**,
  three customers.
- Offset 3 (April) retained revenue = C001 300.00 + C003 1,000.00 = **1,300.00** (C002 has
  churned). Revenue retention = 1,300.00 / 1,050.00 = **123.81%**.
- Offset 3 active customers = 2 of 3, so logo retention = **66.67%**.

This cohort reads from the same ledger the MRR Movement Waterfall uses, so the two views describe
one book of business from two angles.
