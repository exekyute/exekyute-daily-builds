# Loan Amortization Queries

Five SQLite queries built around a loan's month-by-month repayment schedule, where each month's interest is charged on the balance the month before left and rounded to the cent. A window function cannot do that: the balance is a result that has to feed back in as an input, and a window only reads the rows a query starts with. The window attempt charges interest on the starting principal every month, so on a 24,000.00 van loan it bills 5,184.00 of interest and still has 2,427.00 owing after the last payment. A recursive CTE carries the balance forward instead, clears the loan in its 36th month on 2,756.86 of interest, and shows what a 2,000.00 extra payment saves.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-loan-terms.sql` | Each loan's principal, rate, term, stated payment, first month's interest, and planned extra payments. |
| `sql/02-window-attempt.sql` | The window-function attempt, which charges interest on the starting principal every month. |
| `sql/03-schedule.sql` | The schedule from a recursive CTE: payment, interest, principal, and balance for every month. |
| `sql/04-totals.sql` | Each loan's total interest and total paid, and how far its final payment is from the stated one. |
| `sql/05-extra-payments.sql` | The schedule with and without the planned extra payments: months, interest saved, and how much of each plan was used. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/loan-amortization-sql
python run.py
```

That prints all five reports against the sample files. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Seventeen checks run. Seven on the sample cover the files loading, each loan's terms, the window attempt, the first three months of the van's schedule, both loans ending at 0.00 in their last month, the totals and final payments, and the extra payments. Seven on loans built for the suite cover 0 percent loans, one of them cleared early by its own payment; a payment large enough to end a loan early on an interest charge of exactly 2.025, through queries 03, 04, and 05; a balloon; queries 01, 02, and 03 on first-month interest of exactly 2.025 and of 5.0005 and on a 7.25 percent rate; query 04's totals for the 0 percent loans and those three; and extras planned for the last month of a term, mid-term, and after payoff. Three run the loader on bad files: a rate over 100 percent and a payment no more than the first month's interest; row numbers past blank lines and a stray quote, text after a closing quote, and a repeated loan_id; and extras that name an unknown loan, fall past the term, or repeat a month, next to one in the term's last month that it keeps. The run ends with `all checks passed`.

Any loans file other than the sample, named with `--loans`, runs with no extra payments unless `--extras` names a file for it, since the sample's extras are planned against the sample loans. The loader validates every CSV it is given before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --loans data/invalid-loans.csv
```

It stops at the first problem, naming the row when the problem is in one: `invalid-loans.csv row 4: loan 3 pays 300.00 a month, which is no more than its first month's interest of 375.00, so the balance would never come down`. A payment at or below the first month's interest never brings the balance down, so the loader refuses it. Let through, loan 3 would end on a final payment of 55,956.82 on a 50,000.00 loan. The check is only a floor: at 375.01, one cent over the interest, the loader takes the same loan, and its final payment is still 50,374.41.

## Why a window cannot carry the balance

Query 02 has the months, the payment, and the rate, and it tries what works for a bank ledger: a running `SUM` of each payment less its interest, taken off the principal. The catch is the interest. Month 2's interest is charged on the balance after month 1, which is what the running sum is still working out. A window reads the rows the query started with, not its own results, so it has no way to reach that balance, and this attempt charges interest on the starting principal instead. It charges the van 144.00 every month, where the real charge falls from 144.00 in month 1 to 4.43 in month 36. It bills 5,184.00 over the term against the true 2,756.86 and leaves 2,427.00 owing after the 36th payment. The espresso machine comes out 214.96 short the same way.

## The recursive schedule

Query 03's recursive CTE starts each loan at month 0 with its principal, and each step reads the row the step before it produced: it adds the month's interest to the balance, rounded to the cent, and takes off the payment. That feedback is what a recursive CTE gives and a window does not. The recursion carries only the balance; each month's interest, payment, and principal come afterward from the balances on either side of it. `MAX(..., 0)` ends a loan early when a payment would clear it, and the last month of the term is set to 0, so the final payment is whatever remains.

The final payment need not match the stated one. The stated payment is rounded to the cent, and so is every month's interest, so the van's 36 equal payments would not land exactly on zero: its last payment is 743.11, 14 cents under the stated 743.25, while the espresso machine's is 680.00, 8 cents over its 679.92. Query 04 shows that difference with its sign, along with each loan's total interest and total paid: 26,756.86 for the van and 8,159.12 for the espresso machine, principal plus interest to the cent.

## Extra payments

Query 05 runs the recursion twice for each loan, once as agreed and once with the planned extras. An extra goes in after the regular payment in the month it is planned for, cut down to whatever is still owed. The van's 2,000.00 in month 12 brings the payoff forward from month 36 to month 33 and saves 294.18 of interest. The espresso machine's 2,000.00 in month 10 is more than the 1,349.79 left after that month's payment, so only 1,349.79 goes in, the loan closes in month 10, and it saves 10.13. An extra planned for the last month of the term, or for after the loan is paid off, is not applied at all, and `extra_applied` shows how much of each plan was used.

## Sample data

Two equipment loans for a fictional café, with interest charged monthly on the balance: a delivery van, 24,000.00 at 7.20 percent a year over 36 months with a stated payment of 743.25, and an espresso machine, 7,900.00 at 6.00 percent over 12 months at 679.92. Each month's interest is rounded to the nearest cent, halves up. The extra payments file plans 2,000.00 against each loan, the van's in month 12 and the espresso machine's in month 10.

## Known limits

- Interest is charged each month at a twelfth of the annual rate. A loan that compounds on another schedule, such as a Canadian fixed-rate mortgage, usually compounded semi-annually, or one that charges interest by the day, needs a different monthly rate or a daily step.
- Halves of a cent round up. A lender that rounds halves to even, or cuts fractions off, can differ by a cent in a month, and the final payment takes up the difference.
- The rate is held in whole basis points, so it can have at most two decimals; a rate with three, such as 4.875, is refused.
- The stated payment comes from the loans file, as it would from a loan agreement. The queries do not work it out from the rate and term: the annuity formula gives a figure between cents, and lenders differ on how to round it. The espresso machine's works out to 679.9248, which is 679.92 to the nearest cent and 679.93 rounded up.
- Extra payments are one per loan per month and come off the balance after the regular payment, so an extra that goes in ends the loan sooner or makes its final payment smaller; the regular payment does not change. A lender that lowers the payment after a prepayment instead needs the payment to change inside the recursion.
- The loans file holds one payment per loan, and the loader refuses one that does not beat the first month's interest, so a loan that starts with interest-only months or a payment holiday cannot be described.
- The interest rounding is written out ten times, and a search of run.py and the sql folder for `+ 60000)` finds every copy: once in query 01, twice in each of queries 02 to 05, and once in the loader's check on the payment. A change to it has to be made in all ten, and the suite's expected answers worked out again.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
