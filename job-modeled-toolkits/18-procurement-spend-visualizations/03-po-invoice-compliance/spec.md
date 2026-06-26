# PO/Invoice Compliance

## Purpose
Check procurement spend against two compliance rules and flag what fails. Spend should sit on a
contract, and on each line the purchase order, the goods receipt, and the invoice should agree
within tolerance, the usual three-way match. A buyer or accounts-payable reviewer runs this to
catch off-contract spend and invoices that do not line up before they are paid.

## Inputs
One CSV: the `normalized-spend.csv` the Spend Analysis Dashboard exports. Header:

`line_id,supplier,category,contract_id,on_contract,po_amount,received_amount,invoice_amount,invoice_date`

| Column | Type | Notes |
| --- | --- | --- |
| line_id | text | Line id. |
| supplier | text | Supplier name. |
| category | text | Spend category. |
| contract_id | text | Contract reference, or blank. |
| on_contract | Y or N | Whether the line is covered by a recognized contract. |
| po_amount | dollars | Purchase-order amount. |
| received_amount | dollars | Value of goods or services received. |
| invoice_amount | dollars | Invoiced amount. |
| invoice_date | date | `YYYY-MM-DD`. |

Amounts are Canadian dollars.

## Validation rules
A structural problem rejects the whole file: an empty file, a header that is not the dashboard's
export, a row without 9 fields, an on_contract value that is not Y or N, or an amount that is not
a dollar figure of zero or more.

## Logic
For each line:
1. Off-contract check. When on_contract is N, the line is flagged as off-contract spend.
2. Three-way-match tolerance. The tolerance is the greater of 5.00 dollars or 1 percent of the
   purchase-order amount, rounded to the nearest cent.
3. Three-way match. The line passes when the purchase order, the receipt, and the invoice all sit
   within that tolerance of one another. When any pair differs by more than the tolerance the line
   is a match exception, and each breach adds a plain-language reason:
   - invoice exceeds PO by the difference,
   - invoice under PO by the difference,
   - invoice exceeds receipt by the difference,
   - receipt short of PO by the difference.
4. A line is fully compliant when it is on-contract and passes the match.

Headline figures: compliant line count and percentage, off-contract line count and invoiced
amount, match-exception line count and invoiced amount, and total invoiced. A line that is both
off-contract and a match exception counts once toward exceptions in the breakdown bar, so the
parts sum to the total.

## Outputs
- Tiles: percent of lines compliant, off-contract spend and line count, match-exception spend and
  line count, and total invoiced.
- A compliance breakdown bar split by line count into compliant, off-contract, and exception.
- A flagged-lines table listing each off-contract or exception line with its PO, received, and
  invoice amounts and the reasons.

## Edge cases
The sample is the exact 12-line export from the Spend Analysis Dashboard, so this view shares one
dataset with the other two. It exercises every branch:
- Clean on-contract lines that match (L001, L002, L003, L005, L007).
- Off-contract lines with a blank contract (L006, L009).
- An invoice over the PO and the receipt, a match exception (L004).
- An invoice over the receipt with the receipt short of the PO, a match exception (L008).
- A difference of 5.00 inside a 60.00 tolerance that still matches (L014 boundary).
- A line of exactly 0.00 that matches (L010 boundary).

### Worked example, checked to the cent
Running the dashboard's export through the checks:

- L004 has a 12000.00 PO, a 12000.00 receipt, and a 12450.00 invoice. The tolerance is 120.00
  (1 percent of 12000.00). The invoice is 450.00 over both the PO and the receipt, well past
  tolerance, so it is a match exception.
- L008 has a 3000.00 PO, a 2950.00 receipt, and a 3000.00 invoice. The tolerance is 30.00. The
  invoice is 50.00 over the receipt and the receipt is 50.00 short of the PO, so it is a match
  exception.
- L014 has a 6000.00 PO and a 6005.00 invoice. The tolerance is 60.00, so the 5.00 difference is
  inside tolerance and the line matches.
- Across the twelve lines: **2 off-contract lines for 10000.00**, **2 match exceptions for
  15450.00**, and **8 fully compliant lines**, a **66.67 percent** compliant rate (8 / 12).
- Total invoiced is **135955.00**, the same total the Spend Analysis Dashboard reports, so the
  two views agree to the cent.

The test suite in `src/tests.ts` asserts each of these figures.
