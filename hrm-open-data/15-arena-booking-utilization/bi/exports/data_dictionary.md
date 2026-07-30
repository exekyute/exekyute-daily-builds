# Data dictionary: mart_arena.csv

The frozen mart both dashboards read. One row per arena pad, month, and use type. 496
rows, ordered by `facility`, `month_start`, then `use_type`. It is the long form of the
golden's ice / dry-floor / other split: the three use-type rows of a pad-month add back
to that pad-month's total booked hours, so Tableau and Power BI land on the same numbers
from the same file.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `facility` | text | Arena pad name (source `Arena Pad Name`), e.g. Scotia One Arena. Bind as a dimension. | category |
| 2 | `month_start` | date | First day of the booking month, e.g. 2025-04-01. Bind as a Date and as the Power BI date-table key. | date |
| 3 | `year` | whole number | Calendar year of the month. | year |
| 4 | `use_type` | text | `Ice`, `Dry Floor`, or `Other`, derived from `Service`. Drives the ice-versus-dry-floor split. | category |
| 5 | `bookings` | whole number | Count of bookings on this pad, in this month, of this use type. | count |
| 6 | `booked_hours` | number | Sum of booking durations for the group, to three decimals. | hours |

## Deriving figures in the tools

- **Total booked hours:** `SUM(booked_hours)` over the whole file, or the Power BI
  measure `SUM ( mart_arena[booked_hours] )`. Equals 107,533.25.
- **Ice hours and ice share:** filter `use_type = "Ice"` and sum, over the file total.
  In Power BI, `Ice Hours = CALCULATE ( [Booked Hours], mart_arena[use_type] = "Ice" )`
  and `Ice Share = DIVIDE ( [Ice Hours], [Booked Hours] )`. Ice is 75,394.0 hours,
  70.11 percent.
- **Utilization** is not carried in this mart, because it is a pad-month figure rather
  than a use-type one. It lives in the golden `out/arena_utilization.csv`
  (`utilization` column) at the pad-month grain. The Tableau heatmap colours by
  `booked_hours` from this mart; see `bi/README.md` for the optional utilization
  calculated field that rebuilds the pad-month capacity from `month_start`.
