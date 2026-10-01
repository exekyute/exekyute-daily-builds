# Hierarchy Rollup Queries

Roll an expense-category tree up so that every category shows its own spend beside the total for it and everything under it, to any depth, and check a hand-edited draft tree for cycles, orphans and self-parents before it goes live. The rollup joins expenses through a transitive closure, every ancestor-descendant pair built by a recursive CTE and seeded with each category as its own descendant, so a charge booked on a mid-level node like Utilities counts once in its own subtree instead of vanishing under its children. The two roots re-sum to the grand total of 5,990.04 to the cent.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-tree.sql` | The tree in outline order: every category with its depth and full ancestor path. |
| `sql/02-direct-spend.sql` | What was charged to each node itself, structure nodes shown at 0.00. |
| `sql/03-subtree-rollup.sql` | Each node's own spend beside its whole-subtree total, to any depth. |
| `sql/04-rollup-check.sql` | Two proofs: roots re-sum to the grand total, and every parent equals its own spend plus its children. |
| `sql/05-hierarchy-checks.sql` | Cycles, self-parents, and unknown parents in a hand-edited draft tree. |

## Running it

Python 3 is enough, with nothing beyond the standard library.

```
cd miscellaneous-projects/hierarchy-rollup-sql
python run.py
```

That prints all five reports against the sample data, and the test run checks the queries against hand-counted answers:

```
python run.py --test
```

The suite has nine checks: the row counts, the outline's length and first root, Electricity's depth and path, the direct spend on three nodes including the mid-node charge, four subtree totals and one leaf, both proofs, and all five draft defects. Pass all nine and the suite prints `all checks passed`.

All three CSVs are validated before any query runs. To see a rejection, point the loader at the included bad file:

```
python run.py --categories data/invalid-categories.csv
```

The run ends on row 3: `invalid-categories.csv row 3: name is empty`. Row 4 reuses id 1, which is the next thing the loader would refuse.

## How the closure works

The tree CTE walks down from the roots and builds each node's path on the way. The closure CTE produces something else: every (ancestor, descendant) pair at any distance, starting from each category paired with itself and adding one generation per step. Join expenses through the closure and group by the ancestor, and a single query gives every node's subtree total without a separate union for each level.

On the sample the closure holds 27 pairs. Eleven are categories paired with themselves. The other 16 equal the sum of the categories' depths, since a category three levels down has three ancestors above it.

Facilities shows the mechanism in one row. Its subtree of 3,199.55 is Rent's 2,460.00 plus Utilities' 739.55, and Utilities' own figure is a 55.25 charge recorded directly on it plus 600.00 of electricity and 84.30 of water below it. Query 04 then confirms that arithmetic at every node, in cents, and that the two roots re-sum to the grand total.

## The broken draft

A rollup assumes the tree really is a tree. The draft file breaks that in three ways: a category parented to itself, a parent id that exists nowhere, and a three-member loop where following parents goes 104 to 105 to 106 and back to 104. The loader refuses all three in the live tree, so the rollup queries never see them. The draft loads without those checks so that query 05 has them to find.

Query 05 climbs each category's ancestor chain and flags any category whose chain comes back to it. The hop cap is sized from the table's own row count, so a broken tree cannot walk forever and no cycle is too long to find. All three loop members are flagged.

A self-parent is kept out of that climb, so 107 is reported once, as a self-parent. Without that filter it would come back a second time as a one-member cycle. An empty result means the draft is safe to promote.

## Sample data

Eleven categories in two roots, four levels deep, and eleven August 2026 expenses totalling 5,990.04, with charges on leaves and on mid-level nodes. The draft tree is seven rows: two sound ones and one of each defect query 05 looks for, with the loop taking three rows.

## Rearrange the tree

Each bullet changes one line under `data/`. Put it back before trying the next.

- In `categories.csv`, change `6,4,Water` to `6,7,Water` to move Water under Supplies. Its 84.30 moves with it in query 03: the Utilities subtree falls from 739.55 to 655.25, Facilities from 3,199.55 to 3,115.25, and Supplies rises from 340.49 to 424.79, while Operations stays at 3,540.04. Both proofs in query 04 still pass.
- In the same file, change `1,,Operations` to `1,8,Operations`, which hangs the root under its own grandchild, Cleaning. No query runs. The loader stops with `categories.csv row 2: category 1 sits in a parent cycle`.
- In `draft-categories.csv`, change `106,104,Loop member three` to `106,101,Loop member three`. That breaks the loop, and query 05 drops to two rows: the self-parent 107 and the unknown parent of 103.

## Known limits

- The recursion guards are sized from each table's own row count, so no legitimate depth truncates a rollup. The cost is the closure itself, which holds one row per ancestor-descendant pair and grows quickly on trees that are both deep and wide.
- Outline ordering sorts by a hidden copy of the path joined with `char(31)`. A category name that itself contains that control character could still misplace a row, which ordinary text never does.
- Amounts are strictly positive. Refunds or credits need a signed-amount variant of the loader and change what the proofs assert.
- The cycle check reports every member of a loop separately rather than naming the loop once.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
