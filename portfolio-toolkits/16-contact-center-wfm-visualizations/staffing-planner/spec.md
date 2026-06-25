# Staffing Planner

## Purpose
Works out how many agents each interval of the day needs to meet a service-level
target, using the Erlang C staffing model. A workforce-management analyst runs it
against a call forecast to size rosters before a shift.

## Inputs
A forecast CSV, chosen with the file picker. Header row, then one row per interval:

| Column | Type | Meaning |
| --- | --- | --- |
| `interval` | text, `HH:MM` | start of the interval, e.g. `08:00` |
| `calls_offered` | whole number, 0 or more | calls expected to arrive in the interval |
| `aht_seconds` | number greater than 0 | average handle time per call, in seconds |

Four settings on the page, applied to every interval:

- Interval length in minutes (default 30)
- Service-level target percent (default 80)
- Answer-within threshold in seconds (default 20)
- Shrinkage percent (default 30)

## Validation rules
- The header must be exactly `interval,calls_offered,aht_seconds`, or the file is rejected.
- Every data row must have exactly 3 fields, or it names the row and the count.
- `interval` must match `HH:MM`, or the row is rejected by number.
- A repeated `interval` is rejected as a duplicate, named by row.
- `calls_offered` must be a whole number of 0 or more.
- `aht_seconds` must be a number greater than 0.
- Interval length must be a positive number of minutes.
- Service-level target must be between 1 and 100.
- Answer-within threshold must be greater than 0 seconds.
- Shrinkage must be between 0 and 99 percent.

## Logic
1. Traffic intensity in Erlangs: `A = (calls_offered * aht_seconds) / interval_seconds`, where
   `interval_seconds = interval_minutes * 60`.
2. Erlang B blocking probability, built with the stable recursion `B(0) = 1`,
   `B(n) = (A * B(n-1)) / (n + A * B(n-1))`.
3. Erlang C waiting probability: `C = B / (1 - (A / N) * (1 - B))` for `N` agents. When `N` is at
   or below `A` the centre is unstable and `C` is 1.
4. Projected service level at `N` agents:
   `SL = 1 - C * exp(-(N - A) * target_seconds / aht_seconds)`, floored at 0.
5. Required agents is the smallest `N` whose projected `SL` reaches the target fraction.
6. Occupancy at the required staffing is `A / N`.
7. Rostered agents adds shrinkage: `ceil(required / (1 - shrinkage))`.
8. An interval with 0 calls needs 0 agents and reports 100% service level.
9. Erlang values and percentages are rounded half up to 2 decimal places for display and export.

## Outputs
On the page: summary stats, a chart of required and rostered agents per interval with the
projected service-level line, and a table. The export button writes `staffing-plan.csv`:

`interval,traffic_erlangs,required_agents,projected_sl_pct,occupancy_pct,scheduled_with_shrinkage`

The Service-Level Dashboard reads the `interval` and `required_agents` columns of that file.

## Edge cases
The sample forecast exercises a clean interval (`08:00`), a peak (`10:00`), a light interval
(`12:30`), and a zero-volume interval (`23:30`). The validation rules above are checked by feeding
in a bad header, a duplicate interval, and a zero AHT.

Hand-checked example: 100 calls in a 30-minute interval (1800 seconds) at 180s AHT is
`A = 100 * 180 / 1800 = 10` Erlangs. Against an 80%-in-20s target, 13 agents project a service
level of about 79.56%, which falls short, so the tool steps up to 14 agents, which project about
88.835% (shown as 88.84%). Occupancy at 14 agents is `10 / 14 = 71.43%`. At 30% shrinkage the
roster is `ceil(14 / 0.70) = 20`. The exported row is `08:00,10.00,14,88.84,71.43,20`.
