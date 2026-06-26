# Backlog and flow

## Purpose
Rolls the clean service requests forward month by month and shows, for each
department, how the open backlog changes: how many requests carry in, how many are
opened, how many are closed, and how many carry out. It also totals the cost to serve
the requests closed each month. A 311 analyst would use this for a monthly operations
report.

## Inputs
- `clean_requests.csv` from the intake tool, with the columns `request_id,
  opened_date, closed_date, category, department, ward, status`.
- `category-cost-rates.csv`, the standard cost to serve one request of each category,
  with columns `category` and `cost_cad` (dollars, for example `85.50`).

The reporting months are taken from the open dates in the data, so the report covers
every month a request was opened.

## Validation rules
- Every required request column must be present, or the run stops with the missing
  columns named.
- Every request row must have an `opened_date`. A blank one means the intake tool was
  not run first, and the run stops with that message.

## Logic
For each department and month, using half-open month bounds [start, next):

- Opening backlog: requests opened before the month and still open at its start
  (no close date, or closed on or after the start).
- New: requests opened during the month.
- Closed: requests with a close date during the month.
- Closing backlog: requests opened before the next month and still open at its start.
  This is counted on its own, not derived, so the identity below can be confirmed.
- Cost to serve: the sum of the category rate for every request closed during the
  month.

The flow identity opening + new - closed = closing must hold for every department and
month. The runner checks all rows.

Money is held in integer cents. The dollar rates are converted to cents once, on load,
with `Decimal` and half-up rounding. Counts times whole-cent rates stay exact, so the
totals match the dashboard to the cent. Rounding happens in the runner, named here.

## Outputs
- A printed table, one row per department and month, with opening, new, closed,
  closing, and cost to serve.
- `period-summary.csv` with columns `period, department, opening, new_requests,
  closed, closing, cost_to_serve_cents`, read by the operations dashboard.
- A checks block, then `PASS` or `FAIL`.

## Edge cases
The sample data carries requests across three months so the backlog visibly moves:

- Carry-in: December requests form the opening backlog for January. Roads opens
  January with two carried-in requests, which equals its December closing of two.
- A request opened in one month and closed in a later month (`R-1005`, opened January,
  closed February) counts as new in January and closed in February.
- A department with no closures in a month (Parks) shows a growing backlog and zero
  cost to serve.
- A department that clears its backlog (Bylaw, closing zero at the end of February).

Hand check: for Roads in 2025-01, opening 2 + new 4 - closed 3 = closing 3. The three
closed that month are all potholes at $85.50, so the cost to serve is 3 x $85.50 =
$256.50. Across every department and month the cost to serve totals $708.50. Running
`python runner.py` prints these and `PASS`. The dashboard re-derives the same Roads
identity and the same $708.50 total from `period-summary.csv`, so the two agree to the
cent.
