# AI operations dashboard

## Purpose
A single page that shows where an AI program's spend stands against budget and which
model is the current pick for a task. It reads the cost engine's team rollup and the
scorecard tool's output and lays them out for a quick read. An AI operations analyst
or their lead opens it to see the month at a glance.

## Inputs
Two CSV files, loaded with the file pickers or from the built-in sample.

`cost_by_team.csv`, the cost engine's team rollup. The dashboard uses these columns:
- `team`, `direct_cost`, `allocated_shared`, `loaded_cost`, `monthly_budget`,
  `forecast_loaded`. A file missing any of these is rejected with a message.

`model_scorecard.csv`, the scorecard tool's output. The dashboard uses:
- `rank`, `model`, `accuracy`, `f1`, `p95_latency_ms`, `cost_per_correct`, `score`.

## Validation rules
- A file missing a required column is rejected and the message names the columns.
- A money cell that is not a number is rejected.
- Files are read in the browser with the FileReader API and are not sent anywhere.

## Logic
1. Parse each CSV into rows.
2. For each team, read the loaded cost, budget, and forecast as whole cents, then
   re-derive the utilization percent and the budget status (over budget, near limit at
   or above ninety percent, within budget) rather than trusting the input columns. This
   is the same rule the cost engine applies, so the two agree.
3. Sum the loaded cost, budget, and forecast across teams, and count the teams over budget.
4. Sort teams by loaded cost, highest first, and draw each as a bar against its budget.
5. Read the scorecard rows, sort by rank, and mark rank one as the current pick.

Money is held in whole cents and formatted with `Intl.NumberFormat`, so amounts never
show floating-point artifacts and match the Python and SQL tools to the cent.

## Outputs
A rendered page with four summary figures (loaded spend, total budget, month-end
forecast, teams over budget), a per-team budget panel, and the ranked model scorecard.
Nothing is written to disk.

## Edge cases
- The sample loads on open, so the page is populated without choosing a file.
- One team over budget (Engineering) draws in the accent color, one near the limit
  (Sales) carries the outlined badge, and two are within budget.
- A team whose forecast crosses its budget (Sales) shows the higher forecast figure.
- `cost_by_team_bad.csv` in this folder is missing the `loaded_cost` column, so loading
  it shows the rejection message instead of a broken view.

### Hand-checked example
Loading the sample, the loaded-spend figure reads **$1,615.85**, the same grand total
the cost engine reports. Engineering shows $1,143.60 of a $1,000.00 budget and is
flagged over budget. The scorecard ranks frontier-mini first with a score of 80.00.
