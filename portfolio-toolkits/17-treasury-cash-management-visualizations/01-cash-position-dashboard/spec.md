# Cash Position Dashboard

## Purpose
Builds the daily cash position for each bank account from a list of the day's movements, then
consolidates across accounts. A treasury or cash-management analyst runs it each morning to see
where every account opened, what moved through it, and where it closed.

## Inputs
A cash-movements CSV, chosen with the file picker. Header row, then one row per movement. All
amounts are Canadian dollars.

| Column | Type | Meaning |
| --- | --- | --- |
| `date` | text, `YYYY-MM-DD` | date of the movement |
| `account` | text, letters, numbers, hyphens | account id, e.g. `CAD-OPS` |
| `direction` | `opening`, `in`, or `out` | opening balance, an inflow, or an outflow |
| `amount` | number, 0 or more, up to 2 decimals | the dollar amount |
| `description` | text | a short note, no commas |

Each account must have exactly one `opening` row. Inflows and outflows are listed one per row.

## Validation rules
- The header must be exactly `date,account,direction,amount,description`, or the file is rejected.
- Every data row must have exactly 5 fields, or it names the row and the count.
- `date` must be a real calendar date in `YYYY-MM-DD` form, or the row is rejected by number.
- `account` may use only letters, numbers, and hyphens.
- `direction` must be `opening`, `in`, or `out`.
- `amount` must be a dollar figure of 0 or more with at most two decimals.
- A row that is an exact copy of an earlier row is rejected as a duplicate.
- Each account must have exactly one `opening` row. A second one, or none, is rejected and named.

## Logic
1. Group the movements by account.
2. For each account, the opening balance comes from its `opening` row, inflows are the sum of its
   `in` rows, and outflows are the sum of its `out` rows.
3. Closing balance per account: `opening + inflows - outflows`.
4. An account whose closing balance is below zero is flagged as overdrawn.
5. The consolidated totals are the sums of opening, inflows, outflows, and closing across all
   accounts. The "as of" date is the latest date seen in the file.
6. All money is held in integer cents through every step, so the totals are exact to the cent.
   Accounts are sorted by id for stable output.

## Outputs
On the page: summary stats, a bar chart of closing balance per account with overdrawn bars in the
flag colour, and a table of opening, inflows, outflows, and closing per account. The export button
writes `closing-balances.csv`:

`account,closing_balance`

The Liquidity Forecast reads this file and sums the `closing_balance` column to set its opening
cash.

## Edge cases
The sample file exercises a clean account (`CAD-OPS`), an overdrawn account that pays out past its
balance (`CAD-TAX`), a zero-activity account that carries its opening straight to close
(`CAD-RESERVE`), and a small everyday account (`CAD-PAYROLL`). The `bad-cash-movements.csv` file
holds a second opening row for one account so the rejection can be seen. The test page also feeds
in a bad header, a missing opening row, and an exact duplicate row.

Hand-checked example: `CAD-OPS` opens at 250000.00, takes in 82000.00 + 15500.50 = 97500.50, and
pays out 64000.00 + 120000.00 = 184000.00, so it closes at
`250000.00 + 97500.50 - 184000.00 = 163500.50`. `CAD-PAYROLL` closes at
`40000.00 - 38500.00 = 1500.00`. `CAD-TAX` closes at `5000.00 - 22000.00 = -17000.00` and is
flagged overdrawn. `CAD-RESERVE` closes at `500000.00`. The consolidated closing is
`163500.50 + 1500.00 - 17000.00 + 500000.00 = 648000.50`, which is the figure the Liquidity
Forecast picks up as opening cash.
