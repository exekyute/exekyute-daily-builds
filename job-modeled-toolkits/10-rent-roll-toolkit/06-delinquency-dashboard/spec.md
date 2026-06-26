# Spec: Delinquency Dashboard

## Purpose

Load the aging CSV the ledger produces and show delinquency by bucket. The page reads
the file in the browser, validates every row, totals what is owed overall and per
aging bucket, and renders a table of charges with the most overdue first. Severity is
shown by tinting each row from the base tone toward the accent tone as the bucket
worsens. Nothing is sent anywhere.

## Inputs

- An aging CSV, chosen with the file picker and read in the browser with the
  `FileReader` API. Default sample: `data/aging.csv`, the file the ledger in
  `05-delinquency-aging-ledger` writes.
- Required columns, matched by name in the header (case-insensitive); extra columns
  are allowed and ignored: `unit`, `tenant`, `charge_type`, `due_date`, `balance`,
  `days_overdue`, `bucket`, `late_fee`, `total_owed`.
- Money values may include `$`, commas, and spaces. `due_date` is `YYYY-MM-DD`.
  `days_overdue` is a whole number. `bucket` is one of `current`, `1-30`, `31-60`,
  `61-90`, `90+`.

## Validation rules

**Whole-file checks** stop the load with a single message:

- The file is not empty.
- The header contains every required column. A missing column is named.

**Row-level checks** do not stop the load. A failing row is left out of the table and
listed in the issues panel with its line number and reason:

- The row has the same number of fields as the header.
- `unit` is present and not a duplicate of an earlier row.
- `tenant` is present.
- `balance`, `late_fee`, and `total_owed` parse as money.
- `days_overdue` is a whole number.
- `due_date` is a valid `YYYY-MM-DD` date.
- `bucket` is one of the five known aging buckets.

## Logic

All money is handled in integer cents and formatted for display with
`Intl.NumberFormat`. The summary totals the open balance, the late fees, and the total
owed across all valid charges, and again within each of the five buckets, which are
keyed in fixed aging order so the strip always shows current through 90+ even when a
bucket is empty. The charges table is sorted by bucket severity, most overdue first,
and within a bucket by the largest amount owed first. Sorting returns a new array and
never changes the loaded data.

## Outputs

- A summary strip: delinquent charge count, open balance, late fees, and total owed.
  The total owed card uses the accent tone when above zero.
- A by-bucket table: the count, balance, late fees, and total owed in each of the five
  buckets, in aging order, each tinted by severity.
- A charges table, most overdue first, with each charge's balance, days overdue,
  bucket badge, late fee, and total owed. Rows are tinted from the base tone toward
  the accent tone as the bucket worsens.
- An issues panel listing every rejected row by line number and reason, hidden when
  there are none.

## Edge cases

- **Totals match the ledger.** The sample totals to a total owed of `$10,807.50`, the
  same figure the ledger printed in its footer, so the two tools agree to the cent.
- **Every bucket shown.** The by-bucket table always lists all five buckets in order,
  including any that hold no charges, so the shape of the report never shifts.
- **Worst first.** The charges table leads with Unit 107 in the `90+` bucket and ends
  with Unit 101 in `current`. The leading rows carry the strongest accent tint.
- **One file, every problem.** `data/messy_aging.csv` keeps two valid charges in the
  table while the issues panel shows a bad field count, a duplicate unit, a non-numeric
  money value, and an unknown bucket, all from a single load.
- **Bad header.** `data/invalid_aging.csv` is missing `total_owed`, so it is refused
  with a message naming the missing column instead of building a half-empty table.
