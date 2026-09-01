# Trial Balance Queries

Five SQLite queries that close a month of double-entry books: every journal entry checked for balance, accounts netted onto their landing side, a trial balance whose two columns must agree to the cent, and pre-posting checks that catch the draft entries which would break it. Money lives as integer cents, and the totals row ties at 21,190.00 on both sides. The month also carries a quiet lesson: sales of 5,290.00 against 5,490.00 of expenses, a 200.00 loss the balance sheet still absorbs exactly.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-chart-and-activity.sql` | The chart of accounts with each account's normal side derived from its type, plus gross postings. |
| `sql/02-entry-balance.sql` | Debits equal credits per entry, whatever the line count. |
| `sql/03-account-balances.sql` | Each account netted to one balance on its landing side, with contra balances flagged. |
| `sql/04-trial-balance.sql` | The statement itself, ending in a totals row that must tie. |
| `sql/05-journal-checks.sql` | Unbalanced entries, unknown accounts, and single-line entries in the draft journal. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/trial-balance-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-posted answers:

```
python run.py --test
```

Ten checks cover the derived normal sides, all twelve entries balancing, the three-line compound entry, the key account balances, the tie at 21,190.00, and all four flagged draft issues, then print `all checks passed`.

The loader validates all three CSVs before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --journal data/invalid-journal.csv
```

It stops on the first problem and names the row: `invalid-journal.csv row 3: a line needs exactly one of debit or credit`. The row after that fills neither side, which the loader would catch next.

## How the balance proves itself

Entry by entry, debits must equal credits, and the month-end compound entry shows the law is about totals, not pairs: two debit lines against one credit line, balanced all the same. Net each account as debits minus credits, put positive results in the debit column and negative ones in the credit column, and the two column totals are forced to agree, because every entry balanced and every posting landed on exactly one account. Any daylight between the totals means something upstream broke.

The accounting equation falls out of the same output. Assets total 15,700.00 (cash 7,920.00, receivables 820.00, inventory 760.00, equipment 6,200.00), and the other side carries payables of 900.00 plus capital of 15,000.00 minus the month's 200.00 loss: 15,700.00 exactly.

## The draft checks

The posted journal is protected at load: a posting to an account the chart does not carry is refused before SQL ever sees it, and every line must carry exactly one of debit or credit. The draft journal loads without the account check on purpose, because finding its problems is the fifth query's job: an entry off by 50.00, a posting to account 9999, and a single line that can never balance, which surfaces under two checks at once. An empty result means the draft can post.

## Sample data

Ten accounts and twelve August 2026 entries across 25 lines for a fictional cafe: owner investment, equipment, inventory on account, cash and credit sales with their costs, rent, wages, a supplier payment, a collection, and one compound sale. Gross postings run 36,480.00 on each side. The draft journal is seven lines carrying exactly the three defects the checks exist to find.

## Known limits

- A trial balance that ties is necessary, not sufficient. An entry posted to the wrong account, or wrong by the same amount on both sides, ties anyway; the statement only catches one-sided breaks.
- There are no closing entries. Revenue and expense accounts keep their balances instead of folding into equity, so the accounting equation needs the net result added by hand, as above.
- One currency, no sub-ledgers, and the memo is free text with no linking.
- Every line of an entry must share one date, enforced at load, which forbids the rare legitimate cross-date correction entry.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
