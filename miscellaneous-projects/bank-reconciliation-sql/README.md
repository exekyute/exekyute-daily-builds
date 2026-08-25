# Bank Reconciliation Queries

Five SQLite queries that reconcile a business ledger against its bank statement: exact matches on date and amount, a second pass that lets a cheque clear up to three days late, everything unmatched on either side, and a one-row report that explains the gap between the books to the cent. Amounts load as integer cents so floats never touch a sum, and the exact pass joins on a `ROW_NUMBER` sequence so two identical payments on the same day pair one-to-one instead of cross-joining into four matches. On the sample month the books differ by 612.13, and the report proves the unmatched rows account for exactly that.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-side-by-side.sql` | Both books stacked with a source column: row counts and totals, showing the gap the rest of the set explains. |
| `sql/02-exact-matches.sql` | One-to-one matches on date and amount, duplicates paired by sequence. |
| `sql/03-tolerance-matches.sql` | Same amount, dates up to three days apart, each ledger row taking its nearest candidate. |
| `sql/04-unmatched.sql` | Everything neither pass could pair, both sides in one list. These rows are the reconciling items. |
| `sql/05-reconciliation-report.sql` | The one-row statement, ending in `explained` and `unexplained` columns. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/bank-reconciliation-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-counted answers:

```
python run.py --test
```

Ten checks cover the book totals, the duplicate pair matching one-to-one, the day gaps on the tolerance matches, the pair that misses the window, the unmatched rows on both sides, and the full report row, then print `all checks passed`.

The loader validates both CSVs before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --ledger data/invalid-ledger.csv
```

It stops on the first problem and names the row: `invalid-ledger.csv row 3: amount '-320.455' has more than 2 decimal places`. The row after that has a date without zero padding, which the loader would catch next.

## How the matching works

Pass one pairs rows with the same date and the same amount. The trap is duplicates: the sample has two 85.00 fuel payments on July 8 in both books, and a plain join on date and amount would produce four matches. `ROW_NUMBER` numbers each side's rows inside their (date, amount) group, the join adds that sequence to its conditions, and the two pairs come out one-to-one.

Pass two runs only on what pass one left behind: same amount to the cent, dates at most three days apart, which is how a cheque written on July 15 finds its clearing on July 18. Each ledger row takes its nearest candidate by day gap, and a second ranking keeps every bank line to one ledger row, so nothing gets counted twice. The boundary is inclusive, so three days matches, and the sample's 200.00 pair sitting five days apart stays unmatched on both sides.

## What the leftovers mean

The unmatched list is the actual reconciliation: cheque 216 written but not yet cleared, the July 30 card settlement still in transit, and on the bank side the account fee, the interest, and a terminal rental the ledger never recorded. It also holds the planted error: the ledger says cheque 217 was 120.00 and the bank cleared 102.00, so both rows surface unmatched. Their difference is 18.00, divisible by 9, the old bookkeeper's sign of a transposed digit.

The report's last two columns carry the proof. The gap between the books equals the unmatched ledger sum minus the unmatched bank sum, so `unexplained` prints 0.00 when the reconciliation accounts for everything.

## Sample data

One fictional bakery month, July 2026: 12 ledger entries totalling 2,040.30 and 13 bank lines totalling 1,428.17. Five pairs match exactly, three match within the window (day gaps of 1, 3, and 3), four ledger entries and five bank lines stay unmatched, and the 612.13 difference between the books is fully explained.

## Known limits

- The tolerance pass is greedy nearest-first. When two ledger rows want the same bank line, the closest claimant wins and the loser stays unmatched rather than being retried against its next-best candidate, so a rare contested month can under-match. The report identity still holds either way.
- Amounts must match to the cent in both passes. A keying error like the planted 120.00 against 102.00 lands on both unmatched lists rather than being guessed into a match.
- The three-day window is a constant repeated in three SQL files.
- SQLite gained a real `FULL OUTER JOIN` in 3.39. The unmatched query uses two anti-joins with `UNION ALL` instead, which runs on anything with window functions, 3.25 or newer.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
