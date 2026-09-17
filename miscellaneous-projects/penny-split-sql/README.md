# Penny Split Queries

Five SQLite queries that split shared bills across departments by weight, so the shares add back up to the bill to the cent. Rounding each share to the nearest cent on its own misses six of the seven sample bills by up to two cents. The usual fix, putting the difference on the share with the largest weight, balances every bill but leaves a department a cent or more away from what it owes on four of them. Largest remainder cuts every share down to the cent and hands the missing cents out one each to the shares that lost the most in the cut, which balances every bill and keeps every share within a cent of exact.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-bill-log-shape.sql` | The log at a glance: bills, departments, split rows, and the total billed. |
| `sql/02-rounded-shares.sql` | The shares rounded to the nearest cent one at a time and added up per bill, and how far that total misses the bill. |
| `sql/03-largest-remainder.sql` | Every share cut down to the cent, the remainder it lost, its place in the queue for a leftover cent, and the share it ends up with. |
| `sql/04-plug-versus-split.sql` | The plug beside the largest remainder split: where the plug went, how far each method's shares miss the bill, and the furthest any share ends up from exact under each. |
| `sql/05-tied-cents.sql` | The leftover cents per department, how many were won or lost on a tie, and what each department was charged in all. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.25 or newer for window functions.

```
cd miscellaneous-projects/penny-split-sql
python run.py
```

That prints all five reports against the sample bills. The test run checks the queries and the loader against hand-computed answers:

```
python run.py --test
```

Twenty checks run. Six on the sample cover the log's shape, the rounded totals, all 36 split rows, the plug beside the split, the cents per department, and the reports as they print. Seven on bill logs built for the suite cover a 0.03 bill split five ways; a bill that splits into whole cents next to a bill with one department; three shares with weights of 2, 5 and 2, each cut by a third of a cent; departments that tie on one side of the cut rather than across it; a lower-case name tied with a capitalised one, through queries 03, 04 and 05; the largest amount and total weight the loader takes, with two shares a millionth of a cent either side of a half; and a plug that goes to the largest weight when another department ties it for the largest share, lands a whole cent out on a share that was already exact, and misses by exactly 0.510 and 0.514 of a cent. Seven exercise the loader and the command line: a bill with no split rows; row numbers in the bills file past blank lines, a line of spaces and a stray quote, along with a bad header, text after a closing quote, bad ids, a bill that is blank or only joiners or direction marks, and a line of commas; ten amounts that are malformed or out of range; a split for a bill that is not in the bills file, a department twice on one bill or written in another case, a blank department, bad weights, weights that add up past the limit, and a splits file with only a header; control and invisible characters, including every invisible character the loader refuses outside the control and format categories, rows with too many or too few fields, a renamed header, an empty file, one with only a header, one that is not UTF-8, and a folder in place of a file; a byte-order mark, spaces around fields and before a quote, untidy spacing and accents, names spelled with the zero-width joiner, the non-joiner and the direction marks, a nine-digit id, the smallest and largest amounts, and a single weight of 1000000, all of which load; and a bills file without its splits file, a file that is not there, and a test run on either file other than the sample, which the command line refuses; along with reports piped out with names that are not plain ASCII, which print, and a query file that fails, has no query result, or is not UTF-8, which stops the reports with a one-line message. The run ends with `all checks passed`.

The loader validates both CSVs before any query runs. The bills file and the splits file go together, so pass both or neither. Point it at the included bad file to see a rejection:

```
python run.py --bills data/invalid-bills.csv --splits data/splits.csv
```

It stops at the first problem, naming the row when the problem is in one: `invalid-bills.csv row 9: bill 8 has no rows in splits.csv; every bill needs at least one department to charge`. A bill with no split rows drops out of every join, so query 01 would count its 8025.00 in the total billed while queries 02 to 05 leave it out, and nobody would be charged for it.

## Rounding each share

Query 02 works out each department's share by weight and rounds it to the nearest cent. Split 100.00 of internet six ways and each department owes 16.666..., which rounds to 16.67, so the six shares come to 100.02. Split 50.00 of coffee six ways and each owes 8.333..., which rounds to 8.33, so the shares come to 49.98. Two departments splitting 245.25 of parking each owe 122.625, the half cent rounds up for both, and the shares come to 245.26. Every share is as close to exact as a cent allows, and six of the seven bills still miss. The most a bill can miss by is half a cent for each department.

## Largest remainder

Query 03 cuts every share down to the whole cent first, which can only leave the bill short, then hands out the missing cents one each. In whole numbers, `amount_cents * weight / total_weight` is the share cut down and `amount_cents * weight % total_weight` is the remainder, the part cut off, counted in parts of a cent out of the total weight. The remainders add up to exactly the cents left over, and each is less than a whole cent, so fewer cents are left over than there are departments and no department gets more than one. A `ROW_NUMBER` over the remainders, largest first, gives each department its place, and as many places as there are cents left over get one each.

On the office rent, 8025.00 by floor area, the cut shares come to 8024.97. Sales, Support and Engineering lost the most in the cut, 3400, 2600 and 2400 parts out of 3800, and get the three cents. Design has more floor area than Sales or Support but lost only 800 parts, so it pays its cut share.

The remainders are compared as whole numbers. Worked out in floating point, as the share in cents less its whole cents, two remainders that are equal can come out a hair apart: one of the suite's logs splits 10.50 by weights of 2, 5 and 2, which leaves each share a third of a cent short, and the floating-point version hands the cent to the middle share instead of going by name.

## The plug

Query 04 tries the usual fix: round every share, then put whatever the rounding missed by on the largest share, the one with the largest weight, or the name that sorts first when weights are equal. The bill balances, as the plug_off_by column shows, but the whole difference lands on one department. When rounding missed, that department ends up a cent or more away from what it owes, unless rounding missed by a single cent and the plug takes back the rounding on that very share.

On each internet bill the plug takes both extra cents off Design, which pays 16.65 for a share of 16.666..., 1.666 cents out. On the cleaning bill, a cent short, it adds the cent to Engineering, whose share had already been rounded up to 122.59, so it pays 122.60 for a share of 122.586..., 1.379 cents out. The plug stays within a cent on the software and parking bills because the extra cent comes off a share that had been rounded up, and on the office rent because rounding missed nothing. Largest remainder balances all seven bills with every share within two thirds of a cent of exact. The misses print in cents cut to three decimal places rather than rounded, so a miss under a cent never shows as 1.000.

## Where the leftover cents went

Query 05 counts the leftover cents per department, and how many were decided on a tie: two departments lost exactly the same amount in the cut, one of them got the cent, and the only difference between them was which name sorts first. A tie counts only across the line between the departments that got a cent and the ones that did not: two departments that both missed out with the same remainder, or both got a cent, won and lost nothing on it. Every sample bill split evenly leaves cents over, so every cent on it is decided on a tie. Across the sample, Design, Engineering, Finance and Operations won 11 tied cents between them, while Sales and Support, the last two names, won none and missed out 7 times. The last column is what each department was charged over all its bills, and the six totals come to the 9940.25 billed.

## Sample data

Seven shared bills from July to September, 9940.25 in all, split across the six departments of a fictional company: office rent by floor area, design software by seats for the four departments that use it, cleaning by headcount, internet and coffee evenly across all six, and parking evenly between the two departments that park. The split rows for each bill are listed in no particular order.

## Known limits

- Amounts run from 0.01 to 9999999.99, and a bill's weights add up to at most 1000000. That keeps an amount in cents times a weight under 10**15, where the whole-number arithmetic is exact and the floating-point share that queries 02 and 04 round is close enough to round the same way.
- Weights are whole numbers from 1 up. A split by a fractional basis, such as 2.5 full-time equivalents, needs scaling to whole numbers first, such as 25 in tenths.
- No credits. A negative amount is refused, since SQLite's integer division rounds toward zero, so a negative share would be cut up rather than down and the cents left over would come out negative, which query 03 never hands out. A credit can be split as a positive amount with each share then negated.
- Ties go by name in byte order, so plain capital letters sort before lower case, and accented and non-Latin letters after z, and the same departments win every tie on a bill that recurs. Nothing here rotates the order from one bill to the next.
- Every bill is split on its own. Each share is within a cent of exact on its bill, but a department's total over many bills can drift further: over the sample, Engineering is charged about 2.4 cents more than its exact shares add up to, and Sales about 2.0 cents less.
- Departments are matched by name. The loader collapses runs of spaces, settles the two ways an accented letter can be encoded, and refuses a second spelling that differs only in letter case, since one department under two spellings would come out as two in query 05. Letter case is compared with casefold, which comes close to letter case without matching it: it also reads the German sharp s as ss, so two names that differ only there are refused as one, and it does not pair the Turkish dotted and dotless i with their capitals, so a Turkish name with a dotted or dotless i in it, written in capitals and in lower case, loads as two. Names are kept as written otherwise, so a name typed with and without an accent, with a zero-width joiner in one row and without it in another, or with an emoji drawn with and without a variation selector, still counts as two departments.
- One currency, with two decimal places. Amounts in a currency with none or three need a different amount format.
- The split is written out in queries 03, 04, and 05, once each, so each file runs on its own. A change to how the leftover cents are handed out has to be made in all three.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
