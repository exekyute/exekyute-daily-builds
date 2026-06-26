# Operations dashboard

## Purpose
Shows the numbers from the SQL tools on one page: the backlog and flow by department
and month, the open requests by age, and time to close against target. It is the view
a 311 analyst or a supervisor would read, and it re-derives the key totals from the
CSVs so they can be checked against the SQL runners.

## Inputs
Three CSVs written by the SQL tools, chosen together in the file picker. Each is
recognized by its columns, so the order does not matter:

- `period-summary.csv` from the backlog tool: `period, department, opening,
  new_requests, closed, closing, cost_to_serve_cents`.
- `sla-aging.csv` from the SLA tool: `bucket, open_count, overdue`.
- `category-sla.csv` from the SLA tool: `category, closed_count, total_days,
  target_days, breaches`.

## Validation rules
- A file whose header matches none of the three shapes is rejected with a message
  naming the file, and nothing is drawn from it.
- A cell that should be a whole number but is not stops that file with a clear
  message.
- Each backlog row is checked against the flow identity. A row where opening + new -
  closed does not equal closing is marked, the row is shaded, and the flow identity
  card reads how many rows are off.

## Logic
- Cost to serve is summed in integer cents and shown in Canadian dollars, so it
  matches the backlog runner to the cent.
- Average days to close is formed from the day totals in `category-sla.csv`, not from
  pre-rounded averages, then rounded once to two decimals with half-up rounding, the
  same way the SLA runner rounds. Working from the totals keeps the overall average
  exact.
- Open and overdue counts are summed across the age buckets.
- A category is drawn as over target when its average days to close is greater than
  its target.

## Outputs
- A metrics strip: cost to serve, flow identity status, open requests, overdue, average
  days to close, and SLA breaches.
- A backlog chart and a flow table with the identity check and cost per row.
- An open-aging column chart with the overdue share in the accent color.
- A time-to-close chart per category with a target marker.

The dashboard reads files in the browser with the FileReader API. Nothing is uploaded.

## Edge cases
The sample CSVs in this folder are the exports from the SQL tools, so the dashboard
shows the same figures the runners print.

- Clean load: all three files load, the flow identity reads Balanced, and the totals
  match the runners.
- A broken row: `bad-period-summary.csv` has the Roads 2025-01 closing set to 9
  instead of 3. Loading it shades that row, marks it as not balancing, and the flow
  identity card reads 1 off.
- An unrecognized file: any CSV whose columns match none of the three shapes is
  rejected with a message and ignored.

Hand check: loading the three sample CSVs shows cost to serve $708.50, Roads 2025-01
opening 2, new 4, closed 3, closing 3 at $256.50, five open requests with four
overdue, and an overall time to close of 11.22 days. These match the SQL runners to
the cent. The same checks run in `tests.html`.
