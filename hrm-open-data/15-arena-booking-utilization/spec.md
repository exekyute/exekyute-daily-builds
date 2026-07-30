# Spec

## Purpose

Take a pinned snapshot of Halifax municipal arena bookings and produce two
deterministic files: a frozen use-type mart both BI faces read, and a facility-month
golden that answers, for each arena pad and month, how many hours were booked, how
that time splits across ice, dry floor, and other use, and how full the pad was
against a nominal capacity.

## Inputs

Dataset: Parks and Recreation Arena Bookings
(`HRM::parks-and-recreation-arena-bookings`), pulled to
`data/raw/hrm_arena-bookings_2026-07-13.csv`. See SOURCE.md.

Columns used (six of fifteen): `Arena Pad Name`, `Booking Date`, `Booking Start`,
`Booking End`, `Event Type`, `Service`. The other nine columns (OBJECTID, UID,
Facility Name, Day of Week, Account Name, User Group Type, User Category, Add Date,
Modified Date) are not read.

## The capacity assumption (read this before trusting a utilization number)

The dataset has no capacity or opening-hours field. To express bookings as a
utilization, this build fixes a single documented constant:

    OPEN_HOURS_PER_DAY = 18

held as a one-row `params` table in `00_schema.sql`, referenced once in
`03_analysis.sql`, and never derived from the data. A month's nominal capacity for one
pad is `days_in_month * 18` hours, and

    utilization = booked_hours / (days_in_month * OPEN_HOURS_PER_DAY)

This is a booking-intensity proxy, not a measured occupancy rate. Two properties make
that explicit and honest:

1. **It is not capped at 1.0.** Separate bookings on the same pad can overlap in wall
   time (a full-day system hold recorded over the same hours as real ice bookings), and
   the 18-hour day is a fixed assumption rather than the pad's true operating window. So
   `booked_hours` can exceed `days_in_month * 18` and utilization can read above 100
   percent. In this snapshot it reaches about 2.23. The figure ranks how heavily a pad's
   ledger is loaded in a month; it does not claim a share of real open time.
2. **It is fully deterministic.** The constant is fixed, the calendar length is exact,
   and the booked hours are a pinned sum, so the same input always yields the same
   utilization.

Change the number and every utilization scales by the inverse ratio; the ice split and
the booked-hours totals do not move, because they never use the constant.

## Load (00_schema.sql, 01_load.sql)

`00_schema.sql` drops and recreates the tables so a re-run starts clean, creates the
`params` table with `OPEN_HOURS_PER_DAY = 18`, and declares the raw landing table with
every column typed VARCHAR. `01_load.sql` reads the committed snapshot with
`all_varchar = true` and selects the six needed columns by their CSV aliases, so type
detection is never relied on and the unused columns are dropped at load.

## Cleaning and validation rules (02_transform.sql)

`ab_clean` is the cleaned, typed mart at the source grain, one row per booking:

1. Trim `facility` (the pad name) and `service`.
2. Parse `Booking Date` (`%Y-%m-%d`) to a DATE, and derive `month_start`
   (`date_trunc('month', ...)`) and `year` from it. Month attribution uses the booking
   date, not the start timestamp, so a booking that runs past midnight still counts in
   the month it was booked for.
3. Derive `use_type` from `service`: `Ice` if the service text contains "Ice",
   `Dry Floor` if it contains "Dry Floor", otherwise `Other` (System Booking, Noon
   Hour). The two ice and dry-floor tests are mutually exclusive in this data, and the
   ice test is applied first.
4. Parse `Booking Start` and `Booking End` (`%-m/%-d/%Y %-I:%M:%S %p`) to timestamps and
   compute `booked_hours = (epoch(end) - epoch(start)) / 3600`, rounded to three
   decimals. This equals the epoch-millisecond difference over 3,600,000 that the raw
   ArcGIS fields would give, because a single booking never spans a daylight-saving
   change.
5. Drop a row where the date or either timestamp fails to parse, where `facility` or
   `service` is blank, or where `booked_hours` is not greater than 0 and at most 24. The
   `<= 24` and `> 0` guards remove absurd and non-positive spans; in this snapshot they
   drop exactly three zero-length bookings (start equals end) and nothing else, leaving
   39,855 of 39,858 rows. No negative or over-24-hour spans exist.

No de-duplication is applied: the grain is one row per booking and each booking is a
distinct ledger entry.

## Analysis logic step by step (03_analysis.sql)

**mart_use** (the frozen BI mart, one row per facility, month, and use type). Groups
`ab_clean` by `facility`, `month_start`, `year`, `use_type` and reports `bookings`
(the count of bookings in the group) and `booked_hours` (their summed duration, rounded
to three decimals). The three use-type rows of a facility-month partition its total, so
summing `booked_hours` back over use types returns the facility-month total exactly.

**facility_month** (the golden, one row per facility and month). Groups `ab_clean` by
`facility`, `month_start`, `year` and reports:

- `bookings` = `COUNT(*)`, `booked_hours` = `round(SUM(booked_hours), 3)`.
- `ice_hours`, `dry_floor_hours`, `other_hours` = conditional sums of `booked_hours` by
  use type. They add back to `booked_hours` on every row.
- `ice_share` = `round(ice_hours / booked_hours, 4)`, guarded against a zero
  denominator.
- `days_in_month` = `day(last_day(month_start))`, the calendar length.
- `capacity_hours` = `days_in_month * OPEN_HOURS_PER_DAY` (the params constant).
- `utilization` = `round(booked_hours / capacity_hours, 4)`, guarded against a zero
  denominator. See the capacity assumption above.

**headline** (three ready-to-print lines): the total booked hours across all pads and
months with the facility and month counts; the ice share of hours with the dry-floor
and other shares alongside; and the busiest facility by booked hours. `run.py` prints
these lines; it does not compute them.

## Outputs

`out/arena_utilization.csv` (generated) and `expected/arena_utilization.csv` (golden,
committed). 288 rows, one per facility and month. Every column is defined in
`data_dictionary.md`. Row order is fixed by `ORDER BY facility, month_start` in
99_export.sql.

`bi/exports/mart_arena.csv` (frozen mart, committed). 496 rows, one per facility,
month, and use type, ordered by `facility, month_start, use_type`. Columns defined in
`bi/exports/data_dictionary.md`. Both BI faces bind to this file and recompute nothing.

## Edge cases

- **Zero-length bookings:** three rows carry `Booking Start` equal to `Booking End`
  (all on 2025-11-03); the `booked_hours > 0` guard drops them before any sum.
- **Overlapping bookings on one pad:** the ledger can hold a full-day system hold and
  concurrent real bookings on the same pad, so summed booked hours can exceed a day.
  This is why the utilization proxy can read above 100 percent; it is documented rather
  than clamped.
- **Forward bookings:** the ledger spans 2025 through 2029 because arenas schedule
  seasons ahead. Later years are sparse, so their per-month utilization is low. All rows
  are kept; nothing is filtered by date.
- **The pad named "Arena":** one of the twelve `Arena Pad Name` values is literally
  `Arena`. It is the busiest by booked hours, inflated in part by full-day system holds.
  It is reported as the data records it.

## Determinism

The snapshot is pinned and committed. The capacity constant is fixed in the SQL, every
result query ends in an `ORDER BY`, and every figure is rounded (hours to three
decimals, rates to four), so the same input always produces byte-identical output.
`expected/arena_utilization.csv` was built from a first verified run; `run.py` re-runs
the pipeline and diffs the fresh output against it, printing PASS only on an exact
row-for-row match.
