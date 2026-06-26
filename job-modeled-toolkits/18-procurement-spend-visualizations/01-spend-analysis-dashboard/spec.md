# Spend Analysis Dashboard

## Purpose
Take a list of procurement spend lines and show where the money goes: the total spend, broken
down by category and by supplier, with each one's share of the total. A buyer or spend analyst
runs it at month end to see the shape of spend before negotiating or reporting. It also writes a
clean, normalized file that the other two views in this repo read.

## Inputs
One CSV of spend lines. Each row is one invoiced purchase-order line. The header must be exactly:

`line_id,supplier,category,contract_id,po_amount,received_amount,invoice_amount,invoice_date`

| Column | Type | Notes |
| --- | --- | --- |
| line_id | text | Unique id for the line, e.g. `L001`. |
| supplier | text | Supplier name. |
| category | text | Spend category. |
| contract_id | text | Contract reference such as `C-1001`, or blank when the line has none. |
| po_amount | dollars | Purchase-order amount, zero or more, up to two decimals. |
| received_amount | dollars | Value of goods or services received, zero or more. |
| invoice_amount | dollars | Invoiced amount, zero or more. This is the spend figure. |
| invoice_date | date | `YYYY-MM-DD`. |

Amounts are Canadian dollars, net of recoverable taxes.

## Validation rules
Two classes of problem are handled differently.

A structural problem rejects the whole file, because nothing in it can be trusted:
- Empty file: "The file is empty."
- Header not exactly the expected eight columns: "Unexpected header. The first row must be exactly ...".
- A row without exactly 8 fields: "Row N has X fields, expected 8."
- An amount that is not a dollar figure of zero or more with at most two decimals: "Row N: po, received, and invoice amounts must each be a dollar figure ...".
- A date that is not a real `YYYY-MM-DD` date: "Row N: invoice_date ... is not a real date in YYYY-MM-DD form."

A row-level data problem is recorded as a review note and the rest of the file still processes:
- Blank line_id: the row is skipped, "Row N has no line id and was skipped."
- Blank supplier: the line is skipped, "Line X has no supplier and was skipped."
- Blank category: the line is skipped, "Line X has no category and was skipped."
- A line_id already seen: the repeat is skipped, "Line X repeats an earlier line id and was skipped."
- A category not in the taxonomy: the line is kept but flagged, "Line X uses category ..., which is not in the taxonomy."

The recognized categories are IT Hardware, Office Supplies, Logistics, Professional Services, and
Facilities. A contract id counts as on-contract when it matches the letter C, a hyphen, then
digits (for example `C-1001`); a blank or non-matching contract id reads as off-contract.

## Logic
1. Parse and validate every row by the rules above, collecting clean lines and review notes.
2. Hold every amount in integer cents so totals are exact.
3. Total the invoice amount across all clean lines.
4. Group by category and by supplier, summing the invoice amount in each group.
5. Compute each group's share as part divided by total, multiplied by 100, rounded half up to two
   decimals. Sort both breakdowns by spend descending, then by name.
6. Split spend into on-contract and off-contract using the contract rule above.
7. Write the clean lines to a normalized CSV in input order, with an added `on_contract` column
   set to Y or N.

## Outputs
- On screen: headline tiles (total spend, supplier count, category count, off-contract spend,
  flagged line count), a spend-by-category bar chart and table, a spend-by-supplier bar chart and
  table, and a review-notes panel listing every skipped or flagged line.
- A downloadable `normalized-spend.csv` with the header
  `line_id,supplier,category,contract_id,on_contract,po_amount,received_amount,invoice_amount,invoice_date`.
  This file is the input to the Supplier Pareto and Savings Tracker and to the PO/Invoice
  Compliance view.

## Edge cases
The sample data in `sample-spend-lines.csv` is built to exercise every branch:
- Clean on-contract lines with matching amounts (L001, L002, L003, L005, L007).
- An off-contract line with a blank contract id (L006, L009).
- A duplicate line id that is skipped (the second L001).
- A row with a missing required field that is skipped (L012, no supplier).
- A line whose category is not in the taxonomy, kept but flagged (L013, Stationery).
- A boundary line of exactly 0.00 (L010).
- Lines whose amounts disagree, carried through for the compliance view to judge (L004, L008).

### Worked example, checked to the cent
Running the twelve clean lines from the sample:

- Total spend is **135955.00**.
- By supplier, Northwind Supply leads at **65000.00**, which is **47.81 percent** of total spend
  (65000.00 / 135955.00 = 0.478099..., rounded to 47.81). Harbour Freight Co is smallest at
  2000.00 (1.47 percent).
- By category, IT Hardware leads at 65000.00 and the flagged Stationery bucket holds 1500.00.
  The six category totals sum back to 135955.00.
- Off-contract spend is **10000.00** (L006 at 8000.00 plus L009 at 2000.00); on-contract spend is
  125955.00.

That same 65000.00 Northwind total is the first bar the Supplier Pareto view reads from the
exported `normalized-spend.csv`, so the two views agree to the cent. The test suite in
`src/tests.ts` asserts each of these figures.
