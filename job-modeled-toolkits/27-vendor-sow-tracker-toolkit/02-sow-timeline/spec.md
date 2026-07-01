# SOW timeline view

## Purpose
A browser view of the earned-value timeline the engine produces. It plots cost to
date and earned value against the contract budget week by week, lists each period and
each milestone, and summarizes the estimate at completion, the variance, and the
holdback. It is the read side of the SOW tracker; the engine in `01` does the math.

## Inputs
The view opens with the sample timeline built in. It can also import a `timeline.csv`
in the engine's output format, in which case it recovers the total budget from any
week (earned value divided by percent complete).

## Logic
The view does no accounting; it parses the timeline and arranges it:

- A burn chart with a line for cost to date, a line for earned value, and a dashed
  rule at the budget. Each week's cost point is colored by its status.
- Summary cards for total budget, estimate at completion, variance at completion,
  holdback released, and status.
- A table of every week with cost, earned value, CPI, EAC, VAC, and status.
- A table of every milestone with budget, actual cost, and variance.

The chart geometry, the parsing, and the formatting are pure functions in
`src/timeline.js`, which the test harness imports.

## Outputs
The on-screen chart and tables. Nothing is written or uploaded.

## Edge cases
The sample timeline moves between At risk and Over budget across its weeks, and the
holdback shows as released only at the final week. Importing a partial timeline (one
that is not yet complete) still renders, with the budget recovered from the earned
value and percent complete.

### Hand-checked example
The summary cards show estimate at completion 85,000.00, variance -5,000.00, and
holdback released 8,000.00, and the week 3 row shows cost 52,000.00, earned 50,000.00,
and EAC 83,200.00. These match the engine in `01` to the cent, which is what
`tests.html` checks.

## How it runs
Plain HTML, CSS, and vanilla JavaScript with an inline SVG chart. It opens by
double-clicking `index.html`, keeps every file on your machine, and uses no
framework, no build step, and no server.
