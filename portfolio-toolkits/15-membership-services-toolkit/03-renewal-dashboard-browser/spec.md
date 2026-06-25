# Renewal dashboard (browser)

## Purpose
Shows the renewal worklist at a glance: how many members are expiring or lapsed,
how many need review, dues by tier, and the dues/HST/late-fee totals. It reads
the CSV the SQL tool writes and reproduces its figures to the cent.

## Inputs
- `renewal_worklist.csv` from the SQL tool, loaded with the file picker, or the
  built-in sample (the same data, embedded in `sample-data.js` for one-click
  loading). Columns: `member_id, name, tier, status, expiry_date, dues,
  late_fee, hst, total, action`.

## Validation rules
- A row with a blank tier or blank dues is incomplete: it still shows on the
  worklist with a "Review" badge, but is left out of the dues totals.
- A row with status `Duplicate` is left out of the totals and counted under
  "Need review".
- Only billable rows (`Paid`, `Expiring`, `Lapsed`, with dues present) feed the
  dues summary.

## Logic
- Money is parsed into integer cents and rounded half up, the same as the SQL and
  Excel tools.
- HST is 13% on dues, applied to the summed dues (not per member), so it matches
  the SQL figure. The late fee is not taxed.
- Grand total billed = total dues + HST + late fees.
- The dues-by-tier bars scale to the largest tier total.

## Outputs
- Four count cards: expiring, lapsed, paid, need review.
- A dues-by-tier bar chart and a dues summary panel (billable members, total
  dues, HST, late fees, grand total).
- The full worklist table with a status badge per row.
- A reconciliation line: total rows, distinct members, billable members.

## Edge cases
The sample data carries a clean full-year member, a prorated mid-year join, a
boundary join month, expiring and lapsed members, a member with a late fee, an
incomplete record (blank tier and dues), and a duplicate line. `tests.html`
checks the parsing, rounding, counts, and totals.

### Hand-checked example (to the cent)
From the 10 billable members: total dues 1,733.75, HST `round(173375 * 0.13) =
22539` cents = 225.39, late fees 25.00, grand total billed 1,984.14. Expiring 3,
lapsed 2, paid 6, need review 2. Reconciliation: 12 rows, 11 distinct members.
These are the same numbers the SQL runner prints and checks.
