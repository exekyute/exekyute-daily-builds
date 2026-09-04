# Balance Drift Queries

Five SQLite queries that rebuild a ledger's running balance from its amounts, hold it against the balance column the system recorded, and answer the questions a closing gap cannot: since when the books have been off, by how much, and in how many separate mistakes. On the sample ledger the closing balance is only 30.00 off, and the queries show that number is two breaks, plus 100.00 and minus 130.00, mostly cancelling each other.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-ledger-shape.sql` | The ledger at a glance, ending on the closing gap everyone checks first. |
| `sql/02-rebuild-balance.sql` | Every row with its rebuilt balance, recorded balance, and running drift. |
| `sql/03-break-points.sql` | The exact rows where the ledger breaks its own arithmetic, and each error introduced. |
| `sql/04-drift-regimes.sql` | Stretches of constant drift: from when to when the books were off by how much. |
| `sql/05-audit-note.sql` | One line for the audit note: first break, break count, total error, drift showing. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/balance-drift-sql
python run.py
```

That prints all five reports against the sample ledger. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Eleven checks cover the closing gap, the drift on both sides of both breaks, the full regime table, and the audit note, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --ledger data/invalid-ledger.csv
```

It stops on the first problem and names the row: `invalid-ledger.csv row 4: txn_id 4 is not consecutive; expected 3`. The gap check exists because the running balance only means anything in exact sequence: a missing transaction produces the same symptom as a recording error, so the loader refuses to guess which one it is looking at. The one thing the loader deliberately does not validate is the balance arithmetic itself; broken arithmetic is data here, and finding it is the queries' whole job.

## The rebuild

The balance each row should show is the running sum of every amount up to and including it: `SUM(amount_cents) OVER (ORDER BY txn_id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)`. The opening balance needs no anchor constant anywhere, because the opening line is just row one carrying the opening amount. Drift is the recorded balance minus that running sum, and it has a shape worth reading: it sits at zero while the ledger ties, jumps when a row is mis-recorded, then holds its new value through every correct row that follows. A wrong balance does not heal; it rides along.

Query 03 finds the same rows a different way, and the two constructions agreeing is the point. Instead of a running total, it checks each row locally with LAG: the previous recorded balance plus this row's amount must equal this row's recorded balance, with row one measured against a pre-opening balance of zero. The rows that fail the local check are exactly the rows where 02's drift changes value, and the local version names the error each row introduced on its own.

## Drift regimes

Query 04 turns the drift column into an interval report with the flag-then-running-sum trick: a row opens a new regime when its drift differs from the row before, and a running count of openings numbers the regimes. The sample splits into three: twelve clean rows, eleven rows carrying plus 100.00, and eight rows carrying minus 30.00. That last number is the compounding lesson: a regime's drift is the sum of every error so far, so the 130.00 mistake on August 31 shows up as a drift of minus 30.00, its own size visible only in query 03.

## The audit note

Query 05 compresses the investigation into the line an auditor writes: first break on August 16 at Invoice 1045 payment, error 100.00, two breaks in all, 230.00 of total recording error, nineteen rows still off, closing drift minus 30.00. The gap between the last two numbers is the reason this build exists: books that are barely off can still be badly wrong, and the closing balance alone cannot tell the difference.

## Sample data

Thirty-one rows of a fictional small firm's operating account: an opening line of 1,000.00 dated July 31, 2026, then thirty transactions through September 4. Two breaks are planted. On August 16 a 250.00 deposit moves the recorded balance up by 350.00, and on August 31 a 75.00 vendor payment knocks 205.00 off it. Rebuilt closing 3,150.00, recorded closing 3,120.00, both breaks engineered so every drift value is hand-checkable.

## Known limits

- Drift detection sees disagreement between the amounts and the recorded balances. A transaction that is missing or invented with a consistently updated balance rebuilds cleanly and never flags; catching that takes reconciliation against a second source, which is a different build.
- txn_id is the order authority. The sequence must start at 1 and arrive gapless, so a file truncated above its own opening line is refused, and a break on the opening line lands on row one, measured against a pre-opening balance of zero.
- The drift construction is repeated in three SQL files rather than shared through a view, the price of keeping every query a single standalone statement.
- One account per file. Several accounts mean PARTITION BY account on every window and the regime numbering restarting per account.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
