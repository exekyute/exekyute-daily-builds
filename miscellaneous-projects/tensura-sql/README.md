# TenSura World Database

A small relational dataset about the world of *That Time I Got Reincarnated as a
Slime* (Tensei Shitara Slime Datta Ken), built as a SQLite database with a set of
analytical queries and integrity checks over it.

I built it because I enjoy the series and wanted a real subject to practice
modelling messy lore into a clean relational schema and asking real questions of
it in SQL. The characters, races,
nations, skills, evolutions, demon lords, and dragons are drawn from the light
novels and cross-checked against the series wiki. Where the numbers are contested,
the notes say so.

Everything is generated from one file, `data/tensura.json`, so the database, the
plain-SQL seed, and the CSV exports never drift apart.

## What is in it

Eleven tables in a small star shape. `characters` sits in the middle, the `dim_`
tables describe it, and the bridge tables carry the many-to-many links.

- **characters** (59) with race, home nation, debut arc, threat rank, demon-lord
  class, and a wiki-cited Existence Point figure where one is published
- **races** (38), **nations** (9), **arcs** (12), **skills** (40), **factions** (11)
- **character_skills** and **character_factions**, the two many-to-many bridges
- **evolutions**, the ordered evolution ladder for each character who has one
- **demon_lords** and **true_dragons**, extra detail for those slices of characters

That gives you things to ask: how the cast splits across races, which characters are
strongest by Existence Points, how each nation's roster compares, who climbed the
longest evolution ladder, the eight seats of the Octagram, the four True Dragons in
birth order, and how the cast grows arc by arc.

## Running it

Python 3, standard library only. No install, no server.

Build the database and the exports from the source file:

```
cd engine
python build_db.py
```

That writes `tensura.db`, `sql/seed.sql`, and the CSVs in `exports/`.

Run the analytical queries and the checks (this is the test run):

```
python run_queries.py
```

It prints every query in `sql/queries.sql` and then a set of PASS or FAIL checks
against known facts, such as there being exactly four True Dragons and eight
Octagram seats, and Rimuru holding the highest Existence Points.

Run the unit tests:

```
python -m unittest discover -s tests
```

If you would rather not run Python, you can build the same database with the SQLite
shell alone:

```
sqlite3 tensura.db ".read sql/schema.sql" ".read sql/seed.sql"
```

## The CSV exports

The `exports/` folder holds one flat CSV per table, with a data dictionary in
[exports/README.md](exports/README.md). `characters.csv` already carries readable
labels next to its keys, so it stands on its own, while the dimension and bridge
files carry the full model for anything that reads CSVs.

## A note on Existence Points

Existence Points are the series' rough measure of a being's total power. The figures
here are the ones the light novels and wiki publish, so they are filled in for the
top tier and left blank for everyone else. They come from different points in the
story, so read the EP charts as a ranking of the strongest named characters rather
than a single snapshot. Every character does have a `threat_rank`, the canon danger
class, which is the better field for a broad distribution.

## Repository layout

```
tensura-sql/
  data/
    tensura.json          the single source of truth
  sql/
    schema.sql            tables, views, indexes
    queries.sql           the analytical queries
    seed.sql              generated INSERT statements
  engine/
    build_db.py           builds tensura.db, seed.sql, and the CSVs
    run_queries.py        runs the queries and the checks
    validate.py           referential-integrity checks
    tests/                unit tests
  exports/                one CSV per table, plus the data dictionary
  tensura.db              the built SQLite database
```

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
