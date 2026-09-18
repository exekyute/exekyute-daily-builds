# Bill of Materials Queries

Five SQLite queries that explode a bill of materials. From the lines saying what each assembly is made of, they work out every raw part a product takes, what a week's build plan needs of each, where the shelf falls short, and how many of each item the stock could build on its own. The walk down the bill is a recursive CTE that multiplies the quantities as it goes. Written with UNION, the usual default, it drops any route that reaches a part with the same quantity as another, and in the sample that hides a 30-bolt and a 12-bearing shortfall behind totals that look covered.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-bom-shape.sql` | The bill at a glance: products, subassemblies, raw parts, lines, and the order lines and units on the plan. |
| `sql/02-union-explosion.sql` | The raw parts one unit of each product takes, walked with UNION, which drops a repeated route. |
| `sql/03-explosion.sql` | The same walk with UNION ALL: every raw part per unit, how many routes reach it, and the deepest level it turns up at. |
| `sql/04-build-plan.sql` | What the week's plan needs of each raw part against what is on hand, and what the UNION walk would have asked for. |
| `sql/05-buildable.sql` | How many of each item on the plan the stock could build alone, and the part that runs out first. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/bom-explosion-sql
python run.py
```

That prints all five reports against the sample files. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Nineteen checks run. Six on the sample cover the bill's shape, the UNION walk, the full explosion with its routes and depths, the build plan with its shortfalls, what each item could build alone, and all five reports as they print, down to their column names, row counts and first rows, along with a query file that fails, has no query result or is not UTF-8, which stops them with a one-line message. Six on bills built for the suite cover two routes that arrive with the same quantity next to two that differ; quantities multiplied five levels down, with a shortcut to the same part, next to a chain whose one route is as long as the bill, which the level cap has to let through; a four-way tie for the bottleneck that only the code order settles, a part with none on hand, and a subassembly on the plan; a million of a part per unit on two items at the most units the plan allows, with every total checked to be a whole number; one of the costliest bills the loader allows and one near the route limit, which have to finish inside the step budget; and a loop put straight into the database, which the level cap stops in the UNION ALL walks, beside a query that would run for ever, which the step budget stops. Seven exercise the loader and the command line: a loop of two parts and one of three, each named by the line that closes it; part codes in lower case, with a space, with a doubled, leading or trailing hyphen, too long or blank, next to one of exactly 24 characters and one with two hyphens, which load; row numbers past blank lines, a line of spaces and a stray quote, along with a bad header or one in another order, text after a closing quote, a part listed in itself, a line given twice, and quantities that are zero, fractional, zero-padded or too large; a bill with more routes than the queries walk, one route over, and a ladder whose routes double at every rung; a part needed more than a million times over for one unit, by one over, only once two routes are added, three levels down, on a product that sorts after another, at a subassembly partway down, or along a chain of a thousand lines at the largest quantity; a bill of more than 100000 lines, stopped as it is read; two products each under the route limit and together over it; and a plan whose items explode past the route limit; next to a bill of exactly 100000 routes, a subassembly needed exactly a million times over, and a part needed exactly a million times over three levels down, which load; on the plan a raw part, an unknown code, a code in lower case, an item listed twice, bad quantities and a plan with only a header, and in the stock count an assembly, an unknown part, a part in lower case, a part counted twice, bad counts and a raw part left out; rows with too many or too few fields, a line of commas, a tab, a renamed header, an empty file, one with only a header, one that is not UTF-8 and a folder, next to a byte-order mark, spaces around fields and the largest counts, which load; and on the command line, files given without the other two, a file that is not there, a test run on any file other than the sample, the defaults, the sample files spelled another way, three files of your own, and output and messages written as UTF-8, from main itself as well as its helper. The run ends with `all checks passed`.

The loader validates all three CSVs before any query runs. The bill, the plan and the stock count go together, so pass all three or none. Point it at the included bad bill to see a rejection:

```
python run.py --bom data/invalid-bom.csv --orders data/orders.csv --stock data/stock.csv
```

It stops at the first problem in the rows, naming the row. Loops are looked for once every row has passed, and one is reported by the line that closes it, with the loop spelled out:

```
invalid-bom.csv row 42: HUB-ASSY -> WHEEL-20 closes the loop WHEEL-20 -> HUB-ASSY -> WHEEL-20; an assembly cannot contain itself
```

A loop would send the walks round and round. The loader refuses it before any query runs. If one got into the database anyway, the level cap limits how deep the UNION ALL walks go and the step budget stops any query that still runs on, so nothing runs for ever, but the numbers from a walk the cap cut short would mean nothing.

## The explosion

Query 03 starts from each product's own lines and joins the parts found so far back to the bill, multiplying the quantity at each step down: the city bike takes two wheels of 32 spokes, so 64 spokes. A part reached by more than one route is counted once along each. The cargo bike takes 2 bearings in the bottom bracket of its frame kit and 2 in the hub of each of its two wheels, 6 in all over 3 routes, and the routes and deepest columns show how each part was reached.

Query 02 is the same walk written with UNION. UNION keeps one copy of any row it has already seen, and a row here holds only the product, the part and the quantity so far, so two routes that reach a part with the same quantity make the same row. The cargo bike's three routes to bearings all arrive as 2, and UNION counts 2 bearings where the bike takes 6; its two routes to a hub shell arrive as 1 each, and UNION counts 1. Every bike comes out 4 bolts short, because two of its routes to bolts both arrive as 4. The city bike's bearings come out right: 2 from the bottom bracket and 4 from its two hubs are different numbers, so UNION keeps both. The query is right wherever the numbers happen to differ.

## The build plan

Query 04 explodes each item on the plan, multiplies by the units ordered, and adds the parts up across the plan. The plan runs short of five parts: 30 BOLT-M5, 12 BEARING, 6 CABLE, 2 FRAME-KIDS and 1 FRAME-TUBES. Walked with UNION, the same plan asks for 130 bolts and 142 bearings, both covered by the 200 and 150 on the shelf, so two of the five shortfalls would not show.

## Building alone

Query 05 asks how many of each item the stock could build if the item had it to itself. The part that runs out first sets the count and is named as the bottleneck. Only the kids bike falls short on its own, 6 of 8 for want of FRAME-KIDS. Every other item could be built in full alone, although query 04 has the plan as a whole running short of bolts, bearings, cables and frame tubes: those parts are shared, and query 05 does not charge one item's use of them against another. On the spare wheels, RIM-26 and TYRE-26 both run out at 40, and the tie goes to the code that sorts first.

## Sample data

Three bikes built by a fictional workshop from eight subassemblies and sixteen raw parts, on 40 lines. The city and cargo bikes share a frame kit, all three take the same fork kit, and both wheel sizes take the same hub. The week's plan is 12 city bikes, 5 cargo bikes, 8 kids bikes and 6 spare 26-inch wheels, set against a stock count of every raw part. The bill is listed in no particular order.

## Known limits

- Stock is counted for raw parts only. Subassemblies already built and on the shelf, such as finished wheels, are not taken off what the plan needs; that would take a netting step at each level.
- Query 05 measures each item alone. It does not share out stock between items or put one item ahead of another, so it can show every item as buildable while query 04 shows the plan running short.
- Quantities are whole units. A part used by length or weight, half a metre of cable, needs a unit small enough to count in whole numbers.
- There are no lead times, scrap allowances, dates on which a line comes into force, or alternative parts.
- Part codes are capital letters and digits joined by single hyphens, at most 24 characters. A line's quantity runs from 1 to 99999, as does an item's on the plan, and a stock count from 0 to 999999999999. One unit of anything may take at most 1000000 of a raw part, and the products, and separately the items on the plan, may explode into at most 100000 routes down the bill, since the queries walk every route as a row. Every line adds a route, so a bill also stops at 100000 lines.
- A query that runs past 100000 thousand SQLite steps is stopped with an error. The largest bill the limits above allow takes about a fifth of that.
- The walk is written out in queries 03, 04 and 05, and the UNION walk in 02 and 04, so each file runs on its own. A change to how the walk works has to be made in each copy.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
