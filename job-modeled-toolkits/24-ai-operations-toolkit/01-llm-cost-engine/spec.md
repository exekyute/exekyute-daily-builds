# LLM cost engine

## Purpose
Turns a month of LLM usage into a costed chargeback. It prices every usage record
from an editable rate card, rolls the cost up by team and by model, splits a shared
monthly pool across teams, checks each team against its budget, and forecasts where
spend lands by month end. An AI operations analyst runs it to allocate spend and
catch a team heading over budget before the month closes.

## Inputs
Four CSV files, read from this folder by default.

`usage_log.csv`, one row per usage record:
- `record_id` (text, unique)
- `usage_date` (YYYY-MM-DD)
- `team` (text, must have a row in budgets.csv)
- `project` (text)
- `model` (text, must have a row in price_book.csv)
- `requests` (whole number, zero or more)
- `input_tokens` (whole number)
- `cached_input_tokens` (whole number, at most input_tokens)
- `output_tokens` (whole number)

`price_book.csv`, the rate card, one row per model. Rates are US dollars per one
million tokens and are sample figures meant to be replaced with your own contract rates:
- `model`, `input_per_1m`, `cached_input_per_1m`, `output_per_1m`

`shared_costs.csv`, the monthly shared pool, one row per item:
- `item`, `amount`

`budgets.csv`, one row per team:
- `team`, `monthly_budget` (greater than zero)

## Validation rules
- A missing required field stops the run, naming the record and field.
- `usage_date` must be a real date in YYYY-MM-DD form.
- `requests` and the three token fields must be whole numbers and cannot be negative.
- `cached_input_tokens` cannot exceed `input_tokens` (cached tokens are drawn from the input).
- A `model` not present in the price book is rejected, listing the known models.
- A `team` in the usage log with no budget row is rejected.
- A `record_id` that appears twice, a `model` listed twice in the price book, or a
  `team` listed twice in the budgets is rejected.
- Prices and shared amounts cannot be negative. A budget must be greater than zero.

## Logic
1. Price each usage record. Cached input tokens are billed at the cached rate, the
   rest of the input at the full input rate, and output at the output rate. The cost
   is `(uncached_input x input_rate + cached x cached_rate + output x output_rate)`
   divided by one million, rounded half up to the cent.
2. Roll the per-record cost up to a direct cost per team and per model.
3. Allocate the shared pool. Sum the shared items into one pool, then split it across
   teams in proportion to each team's direct cost, using the largest-remainder method
   so the parts sum to the pool exactly with no cent gained or lost. A team with no
   direct cost gets no share.
4. Loaded cost is a team's direct cost plus its allocated share of the pool.
5. Budget status compares loaded cost to the team's budget: over budget above it,
   near limit at or above ninety percent, within budget otherwise.
6. Forecast the month-end direct spend by straight run rate: direct spend to date
   divided by the days elapsed in the month, times the days in the month. Days elapsed
   is the day-of-month of the as-of date, which defaults to the latest date in the log.
   The shared allocation is a fixed monthly figure and is added on top of the forecast
   unchanged.

All money uses `decimal.Decimal` rounded half up to the cent.

## Outputs
- `cost_by_call.csv`: every usage record with its computed `cost`.
- `cost_by_model.csv`: requests, tokens, and cost per model.
- `cost_by_team.csv`: requests, tokens, direct cost, allocated shared cost, loaded
  cost, budget, remaining, utilization percent, status, forecast loaded cost, and
  forecast status per team. This is the file the dashboard reads.

## Edge cases
The sample data is built to exercise each branch in one run:
- A clean high-cost record (`U-2001`, frontier-large, exactly $275.00).
- A record whose cost lands on a half cent and rounds up (`U-3002`, $10.13).
- A fully cached prompt where input equals cached (`U-3003`, $0.38).
- A request with zero output tokens (`U-4004`, $0.90).
- A self-hosted model with a zero cached rate (`U-4002`, `U-5003`).
- One team over budget (Engineering), one near the limit (Sales), two within
  (Support, DataScience).
- A team that is within budget now but whose forecast crosses it (Sales, forecast
  $170.95 against a $150.00 budget).
- A shared pool whose proportional split leaves two leftover cents, handed to the two
  teams with the largest remainders (Support and DataScience).

### Hand-checked example
Run against the sample files with the as-of date of 2026-06-20 (the latest usage date):

- `U-2001`, frontier-large: 30,000,000 uncached input x $5.00 + 10,000,000 cached x
  $0.50 + 8,000,000 output x $15.00, all per million, is $150.00 + $5.00 + $120.00 = **$275.00**.
- Direct cost by team: Engineering $549.10, Sales $66.19, Support $35.06,
  DataScience $125.50. Grand direct cost **$775.85**.
- Shared pool $840.00 split by direct-cost share: Engineering $594.50, Sales $71.66,
  Support $37.96, DataScience $135.88, which sum back to **$840.00**.
- Loaded cost: Engineering $1,143.60 (over its $1,000.00 budget), Sales $137.85
  (near its $150.00 budget), Support $73.02, DataScience $261.38. Grand loaded cost
  **$1,615.85**, equal to $775.85 direct plus $840.00 shared.

The SQL model scorecard tool re-sums the per-record costs from `cost_by_call.csv` and
confirms the grand direct cost of **$775.85** independently.
