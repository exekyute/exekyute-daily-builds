# Rank Three Ways

One sales table and five SQLite queries that show exactly where ROW_NUMBER, RANK, and DENSE_RANK stop agreeing. The instruction is the same in every case, top three reps in each region, and the three functions select twelve, thirteen, and seventeen people. At a flat bonus that is a 5,000.00 spread decided by which window function someone typed.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-region-shape.sql` | Each region at a glance, ending on how many reps share an amount with someone. |
| `sql/02-three-ranks.sql` | Every rep with all three ranks side by side. |
| `sql/03-top-three.sql` | Every rep any top-three rule selects, with a column per rule. |
| `sql/04-disagreements.sql` | Only the reps the rules disagree about, each with the reason. |
| `sql/05-bonus-cost.sql` | What each rule costs, and what each rule is actually for. |

## Running it

Python 3, standard library only. Query 02 uses a named WINDOW clause, so SQLite 3.28 or newer is needed; the runner checks the version and says so rather than failing on syntax.

```
cd miscellaneous-projects/rank-three-ways-sql
python run.py
```

That prints all five reports against the sample table. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Twelve checks cover the three-way tie for first, the tie that straddles the cutoff, the one-cent gap, all five disagreements, and the three bonus totals, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --sales data/invalid-sales.csv
```

It stops on the first problem and names the row: `invalid-sales.csv row 4: rep 'Avery Chen' appears twice; the reports identify reps by name`. Every report keys on the rep name alone, so the same name in a second region would read as one person holding two ranks at once.

## What the three functions do

Down a region ordered by sales, ROW_NUMBER counts rows, RANK counts places, and DENSE_RANK counts distinct amounts. With no ties anywhere the three are the same function wearing different names, which the West region demonstrates: one cent separates Sage Bright at 42,000.00 from Tobin Clark at 41,999.99, and that cent is enough to make all three agree on every row. Ties are exact-equality events, and everything interesting here follows from one.

The window definitions in `sql/02-three-ranks.sql` carry the subtlety:

```
WINDOW ordered AS (PARTITION BY region ORDER BY sales_cents DESC, rep),
       tied AS (PARTITION BY region ORDER BY sales_cents DESC)
```

ROW_NUMBER runs over `ordered` because it hands out distinct numbers and would otherwise pick between equals unpredictably. RANK and DENSE_RANK run over `tied`, with no rep-name tiebreak, and that omission is deliberate. Adding a unique tiebreak to their ORDER BY makes every key distinct, leaves no two rows as peers, and quietly turns both functions into second and third copies of ROW_NUMBER. A tiebreak that fixes one function silently disables the other two.

## Where they disagree

South has three reps tied at 50,000.00. RANK gives all three first place and resumes at four; DENSE_RANK gives all three first place and resumes at two. So `dense_rank <= 3` reaches down to the third distinct amount and selects the entire region, all five reps, for a top-three prize.

East has the uncomfortable case. Three reps posted exactly 43,000.00, and the top-three cutoff falls in the middle of them. RANK and DENSE_RANK keep all three. ROW_NUMBER keeps two and cuts Piper Lund, whose number is identical to the two reps it kept, because the tiebreak sorts on the rep name and P follows N and O. Query 04 separates that from the other four disagreements for a reason: a rep inside the top three distinct amounts but below the third place was excluded by a defensible judgment about how wide a prize should be, while Piper Lund was excluded by the alphabet.

## The cost

Query 05 prices the choice at a flat 1,000.00 per selected rep: 12,000.00 under ROW_NUMBER, 13,000.00 under RANK, 17,000.00 under DENSE_RANK. Each is defensible when the rule matches the intent. ROW_NUMBER fits a fixed budget of exactly three prizes per region, where something has to break a tie and the tiebreak should be a stated policy rather than a sort artifact. RANK fits a standings board, where anyone standing in the top three belongs there. DENSE_RANK fits tiered awards, where the top three amounts define the bands and headcount follows.

## Sample data

Twenty-one reps across four regions for one quarter, engineered so each region exercises a different tie shape: a three-way tie for first in South, a three-way tie that straddles the third-place cutoff in East, two separate two-way ties in North, and no ties at all in West. Sales are held as integer cents so a one-cent difference is a real difference.

## Known limits

- The cutoff is a constant three in three SQL files, and the bonus is a constant 1,000.00 in one. Both belong in a parameters table once a second prize structure exists.
- ROW_NUMBER's tiebreak on rep name is deterministic and arbitrary. Deterministic matters, since an unordered tiebreak lets the same query pay different people on different runs. Arbitrary means the sort key should be replaced by whatever the compensation plan says wins a tie: earliest close date, highest margin, or a split award. The sort is also byte order rather than letter order under SQLite's default collation, so a lowercase or accented first letter loses to every plain uppercase one, which is a second reason a real roster should not be paid by this key.
- One quarter, one metric. Ranking by a different measure, or over several periods, means changing eleven ORDER BY clauses across four files together, since only the ROW_NUMBER windows carry the tiebreak.
- Query 01 counts reps at the top and reps in a tie with correlated subqueries that rescan the region once per row. That reads clearly at twenty-one reps and turns quadratic on a real roster, where both columns belong in window functions over the same partition.
- Regions are ranked independently and never compared. A rep who ranks third in the strongest region outsold every rep in another region and still counts as third here.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
