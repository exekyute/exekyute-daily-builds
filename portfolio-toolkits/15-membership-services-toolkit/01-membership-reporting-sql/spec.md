# Membership reporting (SQL)

## Purpose
Runs the saved reports a membership coordinator pulls a few times a week: the
members expiring in the next 30 days, the members who lapsed in the past 30 days,
the monthly dues summary with HST, and the counts used to reconcile the database
against the Excel worklist. It also writes a renewal worklist CSV the Excel and
dashboard tools read.

## Inputs
- `schema.sql`: creates the `tiers` and `members` tables and seeds the four tiers
  (Student 75.00, Associate 150.00, Professional 300.00, Retired 90.00).
- `sample_members.csv`: synthetic member records. Columns:
  - `member_id` (integer; not unique, so duplicates can be caught)
  - `name` (text)
  - `tier` (text: Student, Associate, Professional, Retired; blank if incomplete)
  - `join_month` (integer 1-12: the month the member joined, used for proration)
  - `status` (text: Paid, Expiring, Lapsed, Duplicate)
  - `dues` (dollars, already prorated; blank if incomplete)
  - `late_fee` (dollars: 25.00 after the grace period, else 0.00)
  - `expiry_date` (ISO date)

## Validation rules
- A record with a blank `tier` or blank `dues` is incomplete. It still appears on
  the worklist so staff can fix it, but it is left out of the dues summary
  (`WHERE ... AND dues IS NOT NULL`).
- A record with `status = 'Duplicate'` is a mis-keyed second line. It is left out
  of the dues summary and surfaced by the reconciliation counts.
- The dues summary counts only billable rows: `status IN ('Paid', 'Expiring',
  'Lapsed')` with a non-blank `dues`.

## Logic
- **Dues by tier.** Full-year dues are Student 75.00, Associate 150.00,
  Professional 300.00, Retired 90.00.
- **Proration.** A member who joins part-way through the year is billed for the
  whole months remaining, counting the join month: `dues = annual * (13 -
  join_month) / 12`, rounded to the cent, half up. The dues are stored on the
  record; the `proration_check` report shows full-year dues beside billed dues so
  a part-year membership is easy to see.
- **Late fee.** A flat 25.00 when a member renews after the 30-day grace period.
  Stored on the record as `late_fee`.
- **HST.** 13% on dues. The late fee is not taxed. The dues summary applies the
  13% to the summed dues for each tier (not to each member one at a time), so the
  cents do not drift. Rounding is done in the runner with `Decimal`, half up.
- **Worklists.** Expiring lists `status = 'Expiring'`; lapsed lists `status =
  'Lapsed'`; both ordered by `expiry_date`. A single `CASE` adds a plain action
  label (Renew now / Overdue / Review / Current).
- **Reconciliation.** Total rows, distinct `member_id`, and billable members, so
  the gap between the database and the Excel worklist is explained by the
  duplicate and the incomplete record.

## Outputs
- Printed tables for each report.
- `renewal_worklist.csv` with one row per member:
  `member_id, name, tier, status, expiry_date, dues, late_fee, hst, total,
  action`. HST and total here are per member; the incomplete record has those
  fields blank.
- PASS/FAIL checks against the hand-checked figures below.

## Edge cases
The sample data is built to exercise each branch:
- **Clean full-year member:** 101 Ana Reyes, Professional, joined month 1, dues
  300.00.
- **Prorated mid-year join:** 102 Ben Cho, Associate, joined month 4: 150.00 *
  (13 - 4) / 12 = 150.00 * 9 / 12 = 112.50.
- **Boundary join month:** 109 Jose Mata, Student, joined month 12: 75.00 * 1 /
  12 = 6.25.
- **Expiring soon:** 104 and 105.
- **Lapsed within grace:** 106 and 107 (no late fee).
- **Late fee after grace:** 108 Ivy Lin, late_fee 25.00.
- **Incomplete record:** 111 Lee Ortiz, blank tier and dues, on the worklist but
  out of the dues summary.
- **Duplicate:** 110 Kim Noor appears twice; the second line is flagged Duplicate
  and left out of the dues summary.

### Hand-checked example (to the cent)
Billable members: 10. Dues by tier:

| Tier         | Members | Dues     | HST (13%) | Dues + HST |
|--------------|---------|----------|-----------|------------|
| Student      | 2       | 31.25    | 4.06      | 35.31      |
| Associate    | 3       | 412.50   | 53.63     | 466.13     |
| Professional | 4       | 1200.00  | 156.00    | 1356.00    |
| Retired      | 1       | 90.00    | 11.70     | 101.70     |
| **All tiers**| **10**  | **1733.75** | **225.39** | **1959.14** |

HST is `round(1733.75 * 0.13) = round(225.3875) = 225.39`. Late fees total 25.00
(member 108). Grand total billed = dues + HST + late fees = 1733.75 + 225.39 +
25.00 = **1984.14**.

Reconciliation: 12 total rows, 11 distinct members (the duplicate accounts for
the gap), 10 billable.

The Excel and dashboard tools reproduce the 1733.75 dues, 225.39 HST, 25.00 late
fees, and 1984.14 grand total exactly.
