# Grant timeline view

## Purpose
A browser view of the drawdown timeline the engine produces. It plots the actual
allowable drawdown and the run-rate projection against the award, shows a
budget-versus-actual bar for each category, and lists the reporting deadlines with their
status. It is the read side of the grant tracker; the engine in `01` does the math.

## Inputs
The view opens with the sample timeline, categories, and deadlines built in. It can also
import a `timeline.csv` in the engine's output format.

## Logic
The view does no accounting; it arranges the engine's output:

- A drawdown chart with a line for the actual cumulative allowable spend, a dashed line
  for the run-rate projection, and a dashed rule at the award. Each period's projection
  point is colored by its status.
- Summary cards for allowable drawn, disallowed, remaining, the projection at the award
  end, and the overdue report count.
- A budget-versus-actual bar for each cost category.
- A list of reporting deadlines, each with a status of Submitted, Overdue, Due now, or
  Upcoming.

The chart geometry, the parsing, and the formatting are pure functions in
`src/timeline.js`, which the test harness imports.

## Outputs
The on-screen chart, bars, and deadline list. Nothing is written or uploaded.

## Edge cases
The sample starts on track and trends over budget, has a disallowed cost shown in its own
card, and has a report flagged overdue. Importing a partial timeline still renders against
the award.

### Hand-checked example
The summary cards show allowable drawn 100,000.00, remaining 150,000.00, and a projection
of 300,000.00 at the award end, with one report overdue, matching the engine in `01` to
the cent. `tests.html` checks these.

## How it runs
Plain HTML, CSS, and vanilla JavaScript with an inline SVG chart. It opens by
double-clicking `index.html`, keeps every file on your machine, and uses no framework, no
build step, and no server.
