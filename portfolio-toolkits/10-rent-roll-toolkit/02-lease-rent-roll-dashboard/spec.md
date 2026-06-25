# Spec: Lease and Rent Roll Dashboard

## Purpose

Load the rent roll CSV the calculator produces and show, at a glance, what every
unit owes this month and which leases need a renewal soon. The page reads the file
in the browser, validates every row, renders a per-unit table, totals the billed
amount, and flags any lease ending within a configurable window. Nothing is sent
anywhere.

## Inputs

- A rent roll CSV, chosen with the file picker and read in the browser with the
  `FileReader` API. Default sample: `data/sample_rent_roll.csv`, the file the
  calculator in `01-rent-roll-proration-calculator` writes.
- Required columns, matched by name in the header (case-insensitive). Extra columns
  are allowed and ignored: `unit`, `tenant`, `monthly_rent`, `prorated_rent`,
  `late_fee`, `amount_due`, `lease_end`.
- An "as of" date input (default `2026-06-12`, the billing reference date) and an
  expiry window in days input (default `60`). Both decide only which leases are
  flagged; changing either re-renders without reloading the file.
- Money values may include `$`, commas, and spaces. `lease_end` is `YYYY-MM-DD`.

## Validation rules

**Whole-file checks** stop the load with a single message:

- The file is not empty.
- The header contains every required column. A missing column is named.
- The as-of date is a real `YYYY-MM-DD` date and the window is a whole number of
  days, 0 or more.

**Row-level checks** do not stop the load. A failing row is left out of the table
and listed in the issues panel with its line number and reason:

- The row has the same number of fields as the header.
- `unit` is present and not a duplicate of an earlier row.
- `tenant` is present.
- `monthly_rent`, `prorated_rent`, `late_fee`, and `amount_due` parse as money.
- `lease_end` parses as a real `YYYY-MM-DD` date.

## Logic

All money is handled in integer cents, parsed once from the CSV text and formatted
for display with `Intl.NumberFormat`, so no floating point artifact ever shows. For
each valid row, the days until expiry is `lease_end - asOf` in whole days. A lease is
flagged when `daysUntil <= window`, which includes leases that have already passed
their end (a non-positive days value). The summary totals `amount_due` across the
valid rows as total billed, counts the units, and counts the flagged leases.

## Outputs

- A summary strip: units billed, total billed, and how many leases are flagged for
  renewal within the window. The flagged card switches to the accent tone when the
  count is above zero.
- A table of valid units with tenant, monthly rent, prorated rent, late fee, amount
  due, lease end, and days to expiry. Flagged rows carry an accent "expiring" badge
  and a tinted row.
- An issues panel listing every rejected row by line number and reason, hidden when
  there are none.

## Edge cases

- **Expiry boundary.** A lease ending exactly `window` days out is flagged; one day
  beyond is not. With the default as-of of `2026-06-12` and a 60-day window, Unit 104
  ending `2026-08-11` is exactly 60 days out and is flagged.
- **Already past end.** A lease whose `lease_end` is on or before the as-of date reads
  as flagged, with a non-positive days-until value.
- **Prorated match.** Unit 101 shows prorated rent `$750.00`, the same figure the
  calculator computed by hand for a `2026-06-16` move-in, proving the two tools agree
  to the cent. The total billed of `$7,025.00` also matches the calculator footer.
- **One file, every problem.** `data/messy_rent_roll.csv` keeps two valid units in the
  table while the issues panel shows a bad field count, a duplicate unit, and a
  non-numeric money value, all from a single load.
- **Bad header.** `data/invalid_rent_roll.csv` is missing `amount_due`, so it is
  refused with a message naming the missing column instead of building a half-empty
  table.
