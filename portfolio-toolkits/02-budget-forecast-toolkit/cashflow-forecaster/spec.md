# Spec: Cash Flow Moving-Average Forecaster

## Purpose

Take a history of monthly net cash flows and apply standard arithmetic moving averages to project
the upcoming quarter and estimate how many months of cash runway remain. This models the
forward-looking planning work of turning recent results into a simple, defensible projection.

## Inputs

- `--history`: history CSV with a `period,net_cash_flow` header. A negative net cash flow is a net
  outflow (burn) for that period. Default `data/cash_flow_history.csv`.
- `--starting-cash`: current cash balance. Default `250000.00`.
- `--window`: number of recent periods to average over. Default `3`.
- `--output`: path for the projection CSV. Default `output/forecast.csv`.

## Validation rules

- The `period` and `net_cash_flow` columns must both be present. A missing column is a clear,
  immediate error with a non-zero exit code.
- A missing history file is a clear error, not a crash.
- A row with a blank period or a blank or non-numeric net cash flow is skipped and counted.
- A repeated period is counted and the first occurrence is kept.
- There must be at least `window` usable periods. Fewer is a clear error.
- Starting cash must be numeric and the window must be a whole number of at least 1.

## Logic

All math uses `decimal.Decimal` rounded half up to cents.

1. Read the history in order, keeping usable rows.
2. Simple moving average: the mean of the last `window` net cash flows (each period weighted equally).
3. Weighted moving average: the last `window` flows weighted 1, 2, ... window from oldest to newest,
   divided by the sum of the weights, so the most recent period carries the most weight.
4. Project the upcoming quarter (the next 3 periods) by carrying each average forward, tracking the
   projected ending cash after each period.
5. Runway: when the average net cash flow is negative, `runway = starting_cash / absolute average`.
   When the average is zero or positive, report that cash is not being drawn down.

## Outputs

- A table of the usable history: period, net cash flow.
- The window, the starting cash, and both moving averages.
- A projected quarter table for each average: period, projected net cash flow, projected ending cash,
  and the runway in months.
- A findings block: usable periods, duplicate periods skipped, rows skipped.
- A projection CSV written to `--output` with both methods.

## Edge cases

- A series with a clear net burn so the runway is finite and meaningful.
- A sign change in the history so the simple and weighted averages visibly differ.
- A zero net cash flow period (boundary).
- A blank net cash flow (skipped, counted) and a non-numeric one (skipped, counted).
- A repeated period (counted, first kept).
- Exactly `window` usable periods (the minimum that still computes), covered in the tests.
- Fewer than `window` usable periods (clear error).
- A YYYY-MM period at a year boundary (December rolls to January of the next year).

## Sample data design

`data/cash_flow_history.csv` is seeded so one run exercises every path:

- `2025-07` through `2026-02` trend from a positive month into a steady burn, including a `0.00`
  month and a sign change, so simple and weighted averages differ.
- `2025-12` appears twice (duplicate, first kept, counted).
- `2026-01` has a blank amount (skipped, counted).
- `2026-03` has a non-numeric amount `abc` (skipped, counted).

After cleaning, 7 usable periods remain. With the default window of 3, the last three flows are
`-22000.00`, `-18000.00`, and `-20000.00`.

`data/invalid_sample/short_history.csv` has only 2 usable periods, for the not-enough-history demo.

## Hand-checked values

Last three usable flows: `-22000.00`, `-18000.00`, `-20000.00`.

- Simple moving average: `(-22000.00 + -18000.00 + -20000.00) / 3 = -20000.00`.
- Weighted moving average: `(1 * -22000.00 + 2 * -18000.00 + 3 * -20000.00) / 6 = -118000.00 / 6 =
  -19666.67` after rounding half up.
- Runway at the simple average: `250000.00 / 20000.00 = 12.50` months.
- Runway at the weighted average: `250000.00 / 19666.67 = 12.71` months.

These are the figures the tool prints for the sample data.
