# Delimited Split Queries

Split a product catalog's comma-separated tags column into one row per tag, so the catalog can be searched and counted by tag. The split is a recursive CTE that walks each list with `instr` and `substr`, then trims and lowercases every piece. Searching the raw column goes wrong in two directions: `LIKE '%red%'` returns eight products when four are red, and the comma-padded fix misses any tag typed after a space.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-catalog-shape.sql` | The catalog at a glance, with a tag count taken by counting commas. |
| `sql/02-like-trap.sql` | Every product `LIKE '%red%'` returns, with its tag list printed beside it. |
| `sql/03-split-tags.sql` | Every tag list split into one row per tag, trimmed and lowercased. |
| `sql/04-three-ways.sql` | Every tag in the catalog, checked by substring LIKE, padded LIKE, and the split. |
| `sql/05-tag-counts.sql` | How many products carry each tag, and how many spellings it arrived in. |

## Running it

Python 3.7 or newer, standard library only, on SQLite 3.8.3 or newer for recursive CTEs.

```
cd miscellaneous-projects/delimited-split-sql
python run.py
```

That prints all five reports against the sample catalog. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Fourteen checks cover the comma count, the eight LIKE matches, the split and its agreement with the comma count, the spaced and single-tag cases, the four disagreements, the tag counts, and a separate list of pasted text proving tabs and non-breaking spaces trim away, then print `all checks passed`.

The loader validates the CSV before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --products data/invalid-products.csv
```

The first bad row ends the load: `invalid-products.csv row 4: product_id 'P-01' appears twice`. The loader leaves the spaces and capitals in each tag list as written, since that mess is what the queries are about; the only change it makes is the Unicode normalisation every field gets.

## The substring trap

`LIKE '%red%'` looks for three letters anywhere in the list, so it finds them inside other words. Query 02 prints the eight products it returns beside their tags, and four are not red: the desk lamp and the blanket are tagged reduced, the security camera infrared, and the shelf tiered. Nothing about the result looks wrong until the tags are read.

## The padded fix, and what it breaks

Wrapping both the list and the search in commas, `',' || tags || ',' LIKE '%,red,%'`, can only match a whole element, so reduced and infrared stop matching red. It needs each element to be exactly the tag, though, and a list typed as `white, infrared, wireless` carries a leading space on every tag after the first. The padded match finds `,white,` in that list and misses `, infrared,` and `, wireless,`.

Query 04 runs both shortcuts against every tag the catalog uses, and they fail in opposite directions. The substring version can only over-match, since a product that carries a tag always holds it as a substring, and here it over-matches red, 8 against the true 4. The padded version, for any tag free of the LIKE wildcards `%` and `_`, can only under-match, since it needs an exact element, and here it misses infrared, large, and wireless, each of which appears after a space in one of the lists.

## The split

SQLite has no function that breaks a string apart, so query 03 walks it with a recursive CTE. The seed row appends a comma so every tag ends in one, and each step cuts off the text before the next comma with `instr` and `substr`, keeps the rest, and recurses until nothing is left. Each piece is trimmed against an explicit set of characters and lowercased, so `Red, large` becomes red and large, and a piece that trims to nothing is dropped.

The split yields twenty-four tag rows, the same total query 01 reached by counting commas, which the test suite checks. Once the tags are rows, query 05 counts how many products carry each one, the way any column is counted. A LIKE can count products for a tag it is handed, as query 04 does, but it cannot discover which tags exist; that list comes from the split. Red was typed both `red` and `Red` and counts as one tag carried by four products.

## Small print in SQLite's string functions

`trim()` with one argument strips the plain space and nothing else. A tab or a non-breaking space, both of which text pasted from a web page or a word processor can carry, survives it, so `red` followed by a tab becomes a tag that never matches `red`. Every query that trims passes the set instead: the space, `char(9)` for the tab, and `char(160)`, which takes a code point and returns the two-byte UTF-8 non-breaking space.

```sql
SELECT length(trim(char(9) || 'red' || char(160))),
       length(trim(char(9) || 'red' || char(160), ' ' || char(9) || char(160)));
-- 5 | 3
```

The string functions also disagree about a NUL byte. `length()` and `substr()` stop at the first NUL, while `instr()` reads past it, so one step of the split finds the comma, cuts the piece short, and returns an empty remainder:

```sql
SELECT length(x), instr(x, ','), substr(x, 1, instr(x, ',') - 1), substr(x, instr(x, ',') + 1)
FROM (SELECT 're' || char(0) || 'd,blue,' AS x);
-- 2 | 5 | re | ''
```

That is a NUL in the first tag: `red` comes out as `re` and `blue` is lost. A NUL inside a later tag, or at the end of a list of two or more tags, does worse. An earlier `substr()` has already cut the remainder at the NUL, so its last piece has no comma after it, `instr()` returns 0, the remainder never shrinks, and the recursion never ends.

## Sample data

Twelve products from a fictional home and electronics shop, eleven with tags and one with none. The tags are placed to break the shortcuts: red appears inside reduced, infrared, and tiered, two lists are typed with a space after each comma, one tag is capitalised, and one product carries a single tag with no comma at all.

## Known limits

- The split treats every comma as a delimiter, so a tag that legitimately contains a comma cannot be stored in this column. A quoted tag would need a real parser, and a separate table of one tag per row avoids the problem entirely.
- Both LIKE versions treat `%` and `_` in a tag as wildcards: the padded search for a tag `a_b` also matches `axb`. The split compares tags as plain text and has no such problem. A wildcard can make the padded version over-match as well, so its under-match claim holds only for tags free of those two characters; the substring version only ever over-matches, wildcards or not.
- Lowercasing folds ASCII letters only, since SQLite's `lower()` leaves accented capitals as they are: `ÉTÉ` and `été` would stay two tags, and the first would print as `ÉtÉ`, a spelling in neither input. SQLite's `LIKE` is likewise case-insensitive for ASCII only.
- The trim set is the plain space, the tab, and the non-breaking space. Rarer Unicode spaces such as the em space or the ideographic space survive it, and the loader refuses every control character except the tab, since a NUL in a list can make the split cut a tag short, drop the tags after it, or never finish, depending on where it falls.
- The recursive CTE is repeated in queries 03, 04, and 05 so each file runs on its own. A catalog of any size would split once into a table of one tag per row and query that instead.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
