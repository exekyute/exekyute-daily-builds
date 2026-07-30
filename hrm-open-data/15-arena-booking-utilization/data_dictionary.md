# Data dictionary: out/arena_utilization.csv

One row per arena pad and month. 288 rows, ordered by `facility` then `month_start`.
This is the golden that `run.py` verifies row for row.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `facility` | text | Arena pad name (source `Arena Pad Name` / ArcGIS `FACILITY`), e.g. Scotia One Arena. | category |
| 2 | `month_start` | date | First day of the booking month, e.g. 2025-04-01. Derived from `Booking Date`. | date |
| 3 | `year` | whole number | Calendar year of the month. | year |
| 4 | `bookings` | whole number | Count of bookings on this pad in this month. | count |
| 5 | `booked_hours` | number | Sum of booking durations for the pad-month, rounded to three decimals. Equals `ice_hours + dry_floor_hours + other_hours`. | hours |
| 6 | `ice_hours` | number | Booked hours whose `Service` text contains "Ice". | hours |
| 7 | `dry_floor_hours` | number | Booked hours whose `Service` text contains "Dry Floor". | hours |
| 8 | `other_hours` | number | Booked hours that are neither ice nor dry floor (System Booking, Noon Hour). | hours |
| 9 | `ice_share` | number | `ice_hours / booked_hours`, a fraction in [0, 1] to four decimals. 0.7011 is 70.11 percent. | fraction |
| 10 | `days_in_month` | whole number | Calendar length of the month (28 to 31). | days |
| 11 | `capacity_hours` | whole number | Nominal bookable hours for the pad-month: `days_in_month * OPEN_HOURS_PER_DAY`, with `OPEN_HOURS_PER_DAY = 18`. | hours |
| 12 | `utilization` | number | `booked_hours / capacity_hours`, to four decimals. A booking-intensity proxy, not a measured occupancy rate. See the note below. | ratio |

## How `booked_hours` is computed

A booking's duration is `Booking End` minus `Booking Start`. In the ArcGIS service both
are epoch milliseconds; the Hub CSV export renders them as local datetime strings such
as `4/1/2025 10:30:00 AM`. This build reads the CSV, parses those strings to timestamps,
and takes the gap in hours. The result equals the epoch-millisecond difference divided
by 3,600,000, because a single booking never crosses a daylight-saving change and so its
start and end share one local time offset. Bookings with a non-positive span, or a span
over 24 hours, are dropped in cleaning before any sum (three zero-length rows drop; none
are negative or over 24 hours).

## The utilization proxy and its capacity assumption

`utilization` divides the month's booked hours by a nominal capacity of
`days_in_month * 18` hours. The 18-hour figure, `OPEN_HOURS_PER_DAY`, is a **documented
constant held in the SQL** (`params` in `00_schema.sql`), not a value read from the
data, which has no opening-hours or capacity field.

The figure is a booking-intensity proxy, not a true occupancy rate, and it is **not
capped at 1.0**. Two reasons: separate bookings on one pad can overlap in wall time (a
full-day system hold recorded over the same hours as real ice bookings), and 18 hours is
a fixed assumption rather than a pad's measured operating window. So `booked_hours` can
exceed `days_in_month * 18` and `utilization` can read above 100 percent (it reaches
about 2.23 in this snapshot). Read it as a relative measure of how heavily a pad's
ledger is loaded in a month, comparable across pads and months, rather than as a share
of real open time. If `OPEN_HOURS_PER_DAY` is changed, every utilization scales by the
inverse ratio while the booked-hours and ice-split columns stay put, because they never
use the constant.

## Notes

- `ice_share + dry_floor_share + other_share = 1` by construction, since the three
  hours columns partition `booked_hours`. Only `ice_share` is materialized; the other
  two are `dry_floor_hours / booked_hours` and `other_hours / booked_hours`.
- The ledger holds forward bookings out to 2029, so later-year pad-months are sparse and
  their utilization is low. This is real scheduling, not padding.
