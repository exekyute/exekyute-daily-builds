# Renewal worklist (Excel VBA)

## Purpose
Builds the renewal worklist in Excel from the CSV the SQL tool writes. It lays
out and color-flags every record (expiring, lapsed, paid, and records that need
review) and writes the dues, HST, late-fee, and grand totals the manager reviews.
The totals match the SQL tool to the cent.

## Inputs
- `renewal_worklist.csv` from the SQL tool (a copy ships here as
  `sample_worklist.csv`). Columns: `member_id, name, tier, status, expiry_date,
  dues, late_fee, hst, total, action`.
- For the calculation functions in `modCalc`: a tier name and a join month (1-12).

## Validation rules
- `AnnualDues` raises a clear error for an unknown tier instead of returning zero.
- `ProratedDues` raises if the join month is outside 1-12.
- `BuildRenewalWorklist` treats a row with a blank dues field as incomplete: it
  still appears on the worklist, flagged for review, but is left out of the
  totals. The completion message reports how many records need review.
- `RoundHalfUp` is used everywhere because VBA's built-in `Round` rounds half to
  even, which would disagree with the other tools by a cent.

## Logic
- **Dues by tier:** Student 75.00, Associate 150.00, Professional 300.00,
  Retired 90.00.
- **Proration:** `dues = annual * (13 - joinMonth) / 12`, rounded half up to the
  cent. The join month counts as a whole month remaining.
- **Late fee:** a flat 25.00 after the 30-day grace period (carried on the record
  as `late_fee`).
- **HST:** 13% on dues, rounded half up. The late fee is not taxed. The summary
  applies the 13% to the summed dues, not to each member, so the cents do not
  drift from the SQL figure.
- **Grand total billed:** total dues + HST + late fees.
- **Flags:** the worklist colors each row by status: expiring, lapsed, paid,
  duplicate, and incomplete (missing tier).

## Outputs
- A `Worklist` sheet: one formatted, color-flagged row per member, then a dues
  summary block (billable members, total dues, HST, late fees, grand total).
- A completion `MsgBox` with the member count, total dues, and any records that
  need review.
- `CalcSelfTest` shows a PASS/FAIL message box checking the calculation functions
  against the figures below.

## Edge cases
The sample CSV carries the same records as the SQL tool: a clean full-year
member, a prorated mid-year join, a boundary join month (December), expiring and
lapsed members, a member with a late fee, an incomplete record (blank tier and
dues), and a duplicate line.

### Hand-checked example (to the cent)
From the 10 billable members in the sample data:

- Total dues: **1733.75**
- HST (13% on dues): `RoundHalfUp(1733.75 * 0.13) = RoundHalfUp(225.3875) =`
  **225.39**
- Late fees: **25.00** (member 108)
- Grand total billed: 1733.75 + 225.39 + 25.00 = **1984.14**

Calculation functions:

- `ProratedDues("Associate", 4)` = 150.00 * 9 / 12 = **112.50**
- `ProratedDues("Student", 12)` = 75.00 * 1 / 12 = **6.25**
- `ProratedDues("Professional", 1)` = **300.00**
- `HstOnDues(1733.75)` = **225.39**

These are the same numbers the SQL runner prints and checks, so the two tools
agree to the cent.

## Manual test steps
VBA cannot be built or run from the command line, so test it in Excel:

1. Open a new workbook, press `Alt+F11` for the VBA editor.
2. `File > Import File` and import `modCalc.bas` and `RenewalWorklist.bas`.
3. Save the workbook as a macro-enabled file (`.xlsm`).
4. Back in Excel, `Alt+F8`, run `CalcSelfTest`. Expect a message box with all
   checks PASS. Screenshot it.
5. `Alt+F8`, run `BuildRenewalWorklist`, and pick `sample_worklist.csv` when
   prompted. The `Worklist` sheet fills in, color-flagged, with the summary:
   total dues 1,733.75, HST 225.39, late fees 25.00, grand total 1,984.14, and
   one record needing review. Screenshot the sheet.
6. **Invalid input:** in the VBA editor's Immediate window (`Ctrl+G`), type
   `?ProratedDues("Gold", 3)` and press Enter. It raises "Unknown membership
   tier: 'Gold'". Screenshot the error so the rejection is on record.
