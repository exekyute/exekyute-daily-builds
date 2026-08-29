# Hierarchy Rollup Queries

Five SQLite queries that walk an expense-category tree with recursive CTEs: the outline with depths and full paths, direct spend per node, subtree totals rolled up to every ancestor, a self-proving consistency check, and integrity checks that catch cycles, orphans, and self-parents before they can send a recursive query walking forever. The rollup rests on a transitive closure, ancestor-descendant pairs built recursively and seeded with each category as its own descendant, so a charge on a mid-level node like Utilities counts once in its own subtree instead of vanishing under the children. The grand total of 5,990.04 re-sums from the two roots to the cent.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-tree.sql` | The tree in outline order: every category with its depth and full ancestor path. |
| `sql/02-direct-spend.sql` | What was charged to each node itself, structure nodes shown at 0.00. |
| `sql/03-subtree-rollup.sql` | Each node's own spend beside its whole-subtree total, to any depth. |
| `sql/04-rollup-check.sql` | Two proofs: roots re-sum to the grand total, and every parent equals its own spend plus its children. |
| `sql/05-hierarchy-checks.sql` | Cycles, self-parents, and unknown parents in a hand-edited draft tree. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/hierarchy-rollup-sql
python run.py
```

That prints all five reports against the sample data. The test run checks the queries against hand-counted answers:

```
python run.py --test
```

Nine checks cover the outline, the depths, the mid-node charge surviving, every subtree total, both proofs, and all five draft defects, then print `all checks passed`.

The loader validates all three CSVs before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --categories data/invalid-categories.csv
```

It stops on the first problem and names the row: `invalid-categories.csv row 3: name is empty`. The row after that reuses an existing id, which the loader would catch next.

## How the closure works

The tree CTE walks down from the roots, building each node's path as it goes. The closure CTE does something different: it produces every (ancestor, descendant) pair at any distance, starting from each category paired with itself and extending one generation per step. Join expenses through the closure and group by the ancestor, and every node's subtree total falls out of one query, no per-level unions.

Facilities shows the whole mechanism in one row: its subtree of 3,199.55 is Rent's 2,460.00 plus Utilities' 739.55, and Utilities' own figure is a 55.25 charge recorded directly on it plus 600.00 of electricity and 84.30 of water below it. The consistency query then proves that arithmetic holds at every node, in cents, and that the two roots re-sum to the grand total.

## The broken draft

Rollups assume the tree is actually a tree. The draft file breaks that three ways people really do: a category parented to itself, a parent id that exists nowhere, and a three-member loop where following parents goes 104 to 105 to 106 and back to 104. The loader refuses all three in the live tree, so the rollup queries can trust their input; the draft loads unchecked on purpose, because finding these problems in SQL is the point. The check query climbs each category's ancestor chain and flags anyone whose chain returns to them, with a hop cap sized from the table's own row count so a broken tree cannot walk forever and no cycle is too long to find. All three loop members are flagged, and an empty result means the draft is safe to promote.

## Sample data

Eleven categories in two roots, four levels deep, and eleven August 2026 expenses totalling 5,990.04, with charges landing on leaves and mid-level nodes both. The draft tree is seven rows carrying exactly the three defects the checks exist to find.

## Known limits

- The recursion guards are sized from each table's own row count, so no legitimate depth truncates a rollup. The cost is the closure itself, which holds one row per ancestor-descendant pair and grows quickly on trees that are both deep and wide.
- Outline ordering sorts by a hidden copy of the path joined with `char(31)`. A category name that itself contains that control character could still misplace a row, which ordinary text never does.
- Amounts are strictly positive. Refunds or credits need a signed-amount variant of the loader and change what the proofs assert.
- The cycle check reports every member of a loop separately rather than naming the loop once.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
