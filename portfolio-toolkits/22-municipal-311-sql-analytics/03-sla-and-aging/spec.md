# SLA and aging

## Purpose
Measures how quickly requests are resolved against their category targets, and how
long the still-open requests have been waiting. It answers two questions a 311 analyst
is asked often: are we closing requests within target, and how old is the open
backlog. It reads the clean requests and writes two CSVs the dashboard uses.

## Inputs
- `clean_requests.csv` from the intake tool, with the columns `request_id,
  opened_date, closed_date, category, department, ward, status`.
- `sla-targets.csv`, the resolution target in days for each category, with columns
  `category` and `target_days`.

The report date is the last day of the latest month any request was opened, so the
aging is measured at a fixed point and the run repeats exactly.

## Validation rules
- Every required request column must be present, or the run stops with the missing
  columns named.
- Every request row must have an `opened_date`, or the run stops, since the intake
  tool guarantees one.

## Logic
Days are whole-day counts from the difference between two dates.

Closed requests (time to close):
- Days to close = closed date minus opened date.
- A request breaches its SLA when its days to close is greater than the category
  target. Closing exactly on the target day is on time.
- For each category: the count closed, the total days (so an exact average can be
  formed), the target, and the number of breaches.

Open requests (aging), measured as of the report date:
- Days open = report date minus opened date.
- Each open request falls in one age bucket: 0-7, 8-14, 15-30, or 31 and over.
- An open request is overdue when its days open is greater than the category target.
- For each bucket: the count open and the number overdue.

Averages are formed from the integer day totals and rounded to two decimals with
half-up rounding, in the runner. The breach rate is breaches divided by closed
requests, also rounded to two decimals.

## Outputs
- A printed time-to-close table by category and an open-aging table by bucket.
- `category-sla.csv` with columns `category, closed_count, total_days, target_days,
  breaches`. Carrying the day total lets the dashboard form the same averages without
  rounding drift.
- `sla-aging.csv` with columns `bucket, open_count, overdue`.
- A checks block, then `PASS` or `FAIL`.

## Edge cases
The sample data is built to exercise each branch:

- On-target boundary: `R-1004` closes exactly seven days out against a seven-day
  target, counted on time, not a breach.
- A clear breach: `R-1005` takes eighteen days against a ten-day target.
- A category with no breaches: NoiseComplaint, both requests well inside target.
- A category with nothing closed yet: TreeTrimming has no closed requests, so it does
  not appear in the time-to-close table but does appear in the open aging.
- Open requests spread across the age buckets, including three over thirty days.

Hand check: across the nine closed requests the day totals are Pothole 28 over 3
(average 9.33), Streetlight 34 over 2 (17.00), Graffiti 34 over 2 (17.00), and
NoiseComplaint 5 over 2 (2.50). All nine total 101 days, an overall average of 11.22.
Five of the nine breach their target, a breach rate of 55.56%. Of the five open
requests, one sits in 8-14, one in 15-30, and three in 31 and over, and four of the
five are past target. Running `python runner.py` prints these and `PASS`.
