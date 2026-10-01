# Snapshot Diff Queries

Reconcile two dated exports of the same price list in SQLite and sort every SKU into added, removed, changed, or unchanged. The changed rows come from EXCEPT, which compares whole rows and treats NULL as an ordinary value, so it finds six changes where joining on SKU and comparing columns with `<>` finds four. The two the join misses are a price arriving from unset and a price leaving for unset.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-snapshots-shape.sql` | Both snapshots at a glance: line counts, unset prices, shared and total SKUs. |
| `sql/02-the-trap.sql` | Every shared SKU under the naive comparison and the NULL-safe one, side by side. |
| `sql/03-added-and-removed.sql` | The SKUs that exist on one side only, from EXCEPT in both directions. |
| `sql/04-changed.sql` | The changed rows, recovered by EXCEPT across whole rows. |
| `sql/05-reconciliation.sql` | The four buckets, and the check that they partition the SKUs exactly. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/snapshot-diff-sql
python run.py
```

That prints all five reports against the sample snapshots. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Twelve checks cover both NULL crossings, the both-unset case, the four-versus-six count, the added and removed lists, all six changed rows, the agreement between the two constructions in queries 02 and 04, and the reconciliation, then print `all checks passed`.

The loader validates each CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --before data/invalid-duplicate-sku.csv
```

It stops on the first problem and names the row: `invalid-duplicate-sku.csv row 4: sku 'A-100' appears twice; EXCEPT and INTERSECT return distinct rows, so a repeated SKU has no meaning in a diff`. For the same reason, both tables declare the SKU a primary key, which would reject the row on its own; the loader checks first so the failure arrives as a named line rather than a database error.

## The trap

`NULL <> 12.00` is neither true nor false. It is NULL, which a `CASE WHEN` treats as not true, so the row falls through to the ELSE and gets reported as unchanged. Query 02 puts that verdict beside the NULL-safe one for all eleven shared SKUs, and the two differ on exactly the rows where a price crossed into or out of the unset state: B-200 gained a price of 12.00 and B-201 lost one, and the naive rule calls both unchanged.

B-202 is the case worth staring at. It is unset in both snapshots, both rules call it unchanged, and only one of them means it. The NULL-safe comparison evaluates the values as equal; the naive one arrives at the same word by falling through, the same way it fell through for B-200.

## What EXCEPT buys

`IS NOT` fixes the comparison one column at a time. EXCEPT fixes it wholesale: it compares whole rows with NULL treated as a value, so query 04 selects all six changed rows without a single NULL-safe comparison anywhere in that selection. The two `IS NOT` expressions left in the query only label which field moved, and getting them wrong loses the label while the row still appears.

Three columns need little care. Thirty columns need thirty correct hand-written comparisons when the diff is a join, and the one that gets missed drops its row entirely.

Query 03 uses the same operator for the set question, SKUs present on one side only, in both directions. Written the other common way, as `NOT IN` against a subquery, that question returns nothing at all the moment the subquery yields a single NULL, since a value compared to NULL is unknown rather than unequal. EXCEPT has no such failure mode.

## The reconciliation

Query 05 builds the four buckets from EXCEPT and INTERSECT and checks that they partition the fifteen SKUs appearing in either file exactly once each: two added, two removed, six changed, five unchanged. If those four counts miss the union total, the diff has double-counted or dropped something and no other number on the page is worth reading. The last column carries the cost of the shortcut, the two changed rows the naive comparison reports as unchanged.

## SQLite's NULL handling

`IS NOT` is SQLite's NULL-safe inequality, and query 02's second verdict rests on it. The standard spelling, `IS DISTINCT FROM`, runs in SQLite 3.50 and is a syntax error on 3.34.0 and 3.31.1.

| Expression | 3.50.4 | 3.34.0 and 3.31.1 |
| --- | --- | --- |
| `NULL <> 12.00` | NULL | NULL |
| `NULL IS NOT 12.00` | 1 | 1 |
| `NULL IS DISTINCT FROM 12.00` | 1 | syntax error |

Set operators sidestep the problem. EXCEPT and INTERSECT match two NULLs as the same value, even though `NULL = NULL` is itself NULL. B-202, unset in both files, reaches the unchanged bucket in query 05 that way, with no special case written for it.

```sql
SELECT NULL = NULL;
-- NULL
SELECT 'B-202', NULL INTERSECT SELECT 'B-202', NULL;
-- B-202 | NULL
```

Formatting has a NULL rule of its own. `printf('%.2f', NULL)` returns the text `0.00`, so a `COALESCE` wrapped around it never fires. Swap that into query 02 and both B-200 and B-202 show a before price of 0.00. Every price column here is a CASE that catches the NULL before `printf` sees it.

```sql
SELECT COALESCE(printf('%.2f', NULL), 'not set');
-- 0.00
```

## Sample data

Thirteen lines in each snapshot of a fictional parts catalogue, August 1 and September 1, 2026, with eleven SKUs in common. The differences are placed one per kind: a price rise, a price cut, a description edit at a steady price, one row changing both fields, a price arriving from unset, and a price leaving for unset. Two SKUs were added and two removed, and one row sits unset in both files, which is the case that has to come out unchanged. The later file is not in SKU order, and none of these queries depends on row order.

## Known limits

- The diff compares SKU text exactly, after the loader strips whitespace around it. Within one export, two SKUs differing only by case or spacing are refused, since one of them is a typo. Across the two exports nothing catches it: a SKU capitalised differently in the later file reads as one removed and one added, which is the right set answer to the question as asked and almost certainly not what happened.
- Two snapshots, no history. Three exports mean running this pairwise, and a row that changed and changed back looks unchanged across the outer pair.
- An unset price is treated as a value that rows can be equal on, which is what makes B-202 unchanged. A file where blank means "unknown" rather than "not set yet" wants those rows excluded from the unchanged bucket instead.
- The changed rows are found by EXCEPT and then joined back for display, so the full column list is written out twice in query 04 and twice more in query 05. Adding a column to the table means adding it to all four copies.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
