# License manager app

## Purpose
A browser tool for working a SaaS subscription portfolio. It shows every plan in an
editable table, recomputes the cost, the seat waste, and the renewal position as
rows change, keeps the list in the browser between visits, and prints a clean
report. It is the interactive front end to the ledger engine in `01`.

## Inputs
The app opens with the sample portfolio built in. It can also import a CSV in the
engine's input format (the columns of `subscriptions.csv`). Each row is edited in
place. An "as of" date sets the renewal clock.

## Validation rules
The app applies the same rules as the engine: plan_type is per_seat or flat, the
unit cost is zero or more, seats owned is above zero, seats used is zero or more and
not above seats owned, the renewal date is a real date, and auto_renew is yes or no.
A row that breaks a rule is shaded and shows the reason in place; its numbers are
blanked until it is fixed.

## Logic
The math is the same as the engine, mirrored in JavaScript and kept in integer
cents so amounts never show floating-point dust:

- Monthly and annual cost, by plan type.
- Unused seats and the monthly and annual waste they carry.
- Utilization, the share of owned seats in use.
- Days to renewal from the as-of date, the renewal status, and the suggested action.
- A portfolio summary: monthly and annual spend, annual seat waste, the counts of
  due-soon, expired, and underused plans, and the annual savings if every expired
  plan is dropped and every underused plan is cut back to the seats in use.

## Outputs
The on-screen table and summary, a printable report (the Print button builds a clean
report and opens the print dialog, which can save to PDF), and the portfolio saved
in the browser's localStorage so edits survive a refresh.

## Edge cases
The sample touches a clean plan, an underused auto-renewing plan, a flat plan, a
fully used plan, an expired plan, and a renewal due within the month. Entering more
used seats than owned, or any other rule break, shades the row and shows the reason.

### Hand-checked example
For S-01 the app shows monthly cost 600.00, annual cost 7,200.00, 12 unused seats,
annual waste 1,728.00, and utilization 76 percent, and the portfolio totals 3,675.00
a month and 11,808.00 of annual seat waste. These match the engine in `01` to the
cent, which is what the test page checks: open `tests.html` for the full list.

## How it runs
Plain HTML, CSS, and vanilla JavaScript. It opens by double-clicking `index.html`,
keeps every file on your machine, and uses no framework, no build step, and no
server. The pure logic in `src/subscriptions.js` is what the test harness imports.
