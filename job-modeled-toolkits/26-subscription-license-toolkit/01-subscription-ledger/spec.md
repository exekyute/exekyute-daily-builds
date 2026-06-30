# Subscription ledger

## Purpose
Turns a list of SaaS subscriptions into a costed ledger: the monthly and annual
spend on each plan, how many paid seats sit unused and what that waste is worth,
how close the renewal is, and a plain next step. The browser app in `02` reads the
file this tool writes.

## Inputs
`subscriptions.csv`, one row per subscription, with these columns:

| Column | Type | Meaning |
| --- | --- | --- |
| sub_id | text | Unique subscription identifier |
| vendor | text | Vendor name |
| plan | text | Plan name |
| plan_type | text | per_seat or flat |
| monthly_unit_cost | number | Monthly cost per seat (per_seat) or monthly flat fee (flat) |
| seats_owned | integer | Seats paid for |
| seats_used | integer | Seats actually in use |
| renewal_date | date | Next renewal, YYYY-MM-DD |
| auto_renew | text | yes or no |

## Validation rules
- Every field is present and non-empty.
- `plan_type` is per_seat or flat.
- `monthly_unit_cost` is zero or more.
- `seats_owned` is a whole number above zero.
- `seats_used` is a whole number, zero or more, and not above `seats_owned`.
- `renewal_date` is a real date in YYYY-MM-DD form.
- `auto_renew` is yes or no.
- `sub_id` does not repeat within the file.

## Logic
For each subscription:

1. Monthly cost. Per-seat plans pay `monthly_unit_cost * seats_owned`. Flat plans
   pay `monthly_unit_cost`. Annual cost is the monthly cost times twelve.
2. Unused seats = `seats_owned - seats_used` (per-seat only; flat plans have none).
3. Monthly waste = unused seats times the unit cost. Annual waste is twelve times
   that.
4. Utilization = `seats_used / seats_owned` for per-seat plans, rounded to four
   places. Flat plans have none.
5. Days to renewal = renewal date minus the as-of date.
6. Renewal status from the days remaining: Expired below zero, Due soon within 30
   days, Upcoming within 90, Current beyond that.
7. Action: Expired plans say review. A plan that auto-renews within 30 days, or
   that uses under 70 percent of its seats, is called out, and both at once is
   called out together. Everything else is OK.

Money uses `decimal.Decimal` rounded half up to the cent, matched by the browser
app to the cent.

## Outputs
`subscriptions_normalized.csv`, one row per subscription with the input columns plus
monthly_cost, annual_cost, unused_seats, monthly_waste, annual_waste, utilization,
days_to_renewal, renewal_status, and action.

## Edge cases
The sample is seeded to touch every branch: a clean per-seat plan, an underused
auto-renewing plan, a flat plan with no seat waste, a fully used plan, an expired
plan, and a renewal due within the month. `subscriptions_invalid.csv` has a plan
with more seats used than owned, so a run against it is rejected.

### Hand-checked example
Subscription S-01, Atlas CRM: 50 seats at 12.00 each, 38 used. Monthly cost is
50 * 12.00 = 600.00 and annual cost is 7,200.00. Unused seats are 12, so monthly
waste is 12 * 12.00 = 144.00 and annual waste is 1,728.00. Across the six sample
subscriptions the portfolio totals 3,675.00 a month, 44,100.00 a year, and
11,808.00 of annual seat waste. The browser app reproduces every one of these.
