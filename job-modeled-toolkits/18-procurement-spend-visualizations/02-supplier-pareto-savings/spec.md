# Supplier Pareto and Savings Tracker

## Purpose
Two views over the same spend. The Supplier Pareto ranks suppliers from largest to smallest and
marks the "vital few" that make up the first 80 percent of spend, so a buyer can see where to
focus negotiation. The Savings Tracker compares realized savings against target across a list of
cost initiatives, so the team can see how a savings program is tracking.

## Inputs
Two CSV files, loaded separately.

The Pareto reads the `normalized-spend.csv` the Spend Analysis Dashboard exports. Header:

`line_id,supplier,category,contract_id,on_contract,po_amount,received_amount,invoice_amount,invoice_date`

It uses the supplier and invoice_amount columns and ignores the rest.

The Savings Tracker reads a savings-initiatives CSV. Header:

`initiative_id,category,baseline_annual,current_annual,target_savings`

| Column | Type | Notes |
| --- | --- | --- |
| initiative_id | text | Unique id, e.g. `INIT-1`. |
| category | text | The spend area the initiative covers. |
| baseline_annual | dollars | Annual spend before the initiative. |
| current_annual | dollars | Annual spend now. |
| target_savings | dollars | The savings the initiative aims for. |

Amounts are Canadian dollars.

## Validation rules
For the normalized spend file, a structural problem rejects the whole file: an empty file, a
header that is not the dashboard's export, a row without 9 fields, a blank supplier, or an
invoice amount that is not a dollar figure.

For the savings file, a structural problem (empty file, wrong header, wrong field count, an amount
that is not a dollar figure of zero or more) rejects the whole file. A row-level problem is
recorded as a review note and the row is skipped: a blank initiative id, a blank category, or an
id already seen.

## Logic
Supplier Pareto:
1. Total the invoice amount by supplier, holding cents as integers.
2. Sort suppliers by spend descending, then by name.
3. Walk the list, keeping a running cumulative total and its share of overall spend.
4. Mark each supplier as vital few from the top down to and including the first one whose
   cumulative share reaches 80 percent. Every supplier after that is the long tail.
5. Round each share half up to two decimals.

Savings Tracker:
1. For each initiative, realized savings is baseline minus current. It can be negative when
   current spend has risen above baseline, which reads as an overrun.
2. Attainment is realized divided by target, as a percentage rounded half up to two decimals.
   When target is zero the attainment is reported as not applicable, so nothing divides by zero.
3. An initiative is met when realized savings reaches or beats target.
4. Total target and total realized are summed across all valid initiatives, and overall
   attainment is total realized over total target.

## Outputs
- Supplier Pareto: tiles (total spend, supplier count, vital-few count, vital-few share), a combo
  chart of spend bars with a cumulative-share line and the 80 percent cut, and a table with each
  supplier's spend, share, and cumulative share, with the vital few highlighted.
- Savings Tracker: tiles (target, realized, overall attainment, count met), a chart of target and
  realized bars per initiative, a table with attainment per initiative, and a review-notes panel.

## Edge cases
The Pareto sample is the exact 12-line export from the Spend Analysis Dashboard, so the two views
share one dataset. The savings sample (`sample-savings-initiatives.csv`) exercises every branch:
- Clean initiatives that beat or miss target (INIT-1 through INIT-4).
- A boundary initiative with exactly 0 realized savings (INIT-5).
- An overrun where current spend rose above baseline, giving negative realized savings (INIT-6).
- A duplicate initiative id that is skipped (the second INIT-2).
- A row with a missing required field that is skipped (INIT-9, no category).

### Worked example, checked to the cent
Running the Pareto on the dashboard's export:

- Total spend is **135955.00**, the same total the dashboard reports.
- Northwind Supply leads at **65000.00**, a **47.81 percent** share. This is the same 65000.00 the
  Spend Analysis Dashboard shows for Northwind, so the two views agree to the cent.
- Cumulative share reaches 70.21 percent at Granite IT and **91.54 percent at Maple Logistics**,
  which is the supplier that crosses the 80 percent cut. So **three of the five suppliers are the
  vital few**, and they make up 91.54 percent of spend.

Running the Savings Tracker on the sample:

- Target savings total **13300.00** and realized savings total **10945.00**, an overall attainment
  of **82.29 percent** (10945.00 / 13300.00 = 0.822932..., rounded to 82.29).
- INIT-1 realizes 5000.00 against a 4000.00 target, 125 percent. INIT-6 is an overrun of -600.00
  against a 300.00 target, -200 percent, and is not met.

The test suite in `src/tests.ts` asserts each of these figures.
