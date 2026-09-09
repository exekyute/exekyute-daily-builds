# Relational Division Queries

Five SQLite queries that answer which technicians hold every certification a job requires, the question relational algebra calls division. The obvious way to write it answers a different question. Matching technicians against the required certifications with `IN` finds everyone holding at least one of them, and on the sample roster that is seven people for a job two people can actually do. Then the two standard correct constructions, counting and absence, are run side by side and made to disagree on purpose.

## The queries

| File | What it answers |
| --- | --- |
| `sql/01-roster-shape.sql` | The roster at a glance, ending on the two records that break things. |
| `sql/02-any-versus-all.sql` | Per job: how many technicians match any requirement, and how many meet all. |
| `sql/03-division-by-counting.sql` | The qualified pairs, found by counting matched certifications. |
| `sql/04-division-by-absence.sql` | The same division stated as a double negative, with the counting verdict beside it. |
| `sql/05-one-cert-away.sql` | The technicians who fail a job by exactly one certification, and which one. |

## Running it

Python 3, standard library only.

```
cd miscellaneous-projects/relational-division-sql
python run.py
```

That prints all five reports against the sample roster. The test run checks the queries against hand-computed answers:

```
python run.py --test
```

Eleven checks cover the any-versus-all counts, both constructions, the exact job they disagree on, the technician holding nothing, and the near-miss list, then print `all checks passed`.

The loader validates all four CSVs before any query runs. Point it at the included bad file to see a rejection:

```
python run.py --holdings data/invalid-holdings.csv
```

It stops on the first problem and names the row: `invalid-holdings.csv row 4: tech_id 'T-99' is not in technicians.csv; a link to an unknown record would vanish from every join`. A certification held by a technician who does not exist can never produce a qualified pair, because queries 03, 04, and 05 all reach the roster and join it away. It still lands in the holdings total in query 01 and in the any-of count in query 02, neither of which touches the roster, and that is the worse half: a number that moves with no person behind it.

## Any of, versus all of

The two questions differ by one word and by a great deal of meaning. Query 02 puts the counts beside each other, and the pump overhaul line is the one to read: three certifications required, seven technicians holding at least one of them, two technicians holding all three. A staffing report built on the first number overstates the crew by three and a half times and looks entirely reasonable.

The yard cleanup line is the same mistake running the other way. That job requires no certifications, so nothing can match the `IN` list and the naive count reports zero technicians qualified. Every technician on the roster is qualified for it, including the one who holds no certification at all, because there is no requirement any of them fails.

## Counting, and its blind spot

Query 03 is how the division usually gets written: join each technician to the requirements they satisfy, count the distinct matches per technician per job, and keep the groups whose count equals what the job demands. It is correct wherever it produces a group, and it produces seven.

It cannot produce a group for yard cleanup. With no requirement rows there is nothing to join to, nothing to count, and no group to test, so the job is absent from the report entirely. Absence reads exactly like nobody qualifying, which is the wrong answer stated in the most convincing way available.

## Absence, and vacuous truth

Query 04 states the same division as a double negative: keep the pairs for which there is no required certification that this technician does not hold. It starts from the technicians rather than from the requirement rows, so it never needs a group to exist. For yard cleanup the inner query finds no unmet requirement for anybody, because it finds no requirement at all, and all eight technicians come through.

The loader allows an empty requirements file for the same reason, so the maximal form of this is reachable: with nothing required anywhere, query 04 returns every technician for every job and query 03 returns no rows at all.

That is vacuous truth, and it is the right answer rather than a quirk. "Holds every certification in an empty set" is true the same way "every unicorn in this room is blue" is true. Query 04's last column re-runs the counting test against each pair it returns, so the divergence is visible on the page: seven rows say the counting version found them too, and the eight yard cleanup rows say it did not.

## One certification away

Query 05 is the operationally useful complement. Three technicians are one certification short across four technician and job pairs: Cyd Marsh needs hydraulics for the pump overhaul, Bo Ellis needs working at height and Fin Oduya needs confined space for the tank inspection, and Fin Oduya again needs a forklift ticket for the structural weld. Each row is one course booking away from becoming a row of query 04.

## Sample data

Eight technicians, four jobs, six certifications, twenty-two holdings, and nine requirements, arranged so each job exercises a different shape: two qualified out of seven who match something, four out of six, exactly one out of seven, and one job with no requirements at all. One technician holds no certification, which makes the empty-requirement case visible on the roster rather than only in the arithmetic.

## Known limits

- The division matches certification text exactly. The loader collapses surrounding and repeated spaces before comparing, so padding cannot create a second code, and it shares one vocabulary across both files so a spelling differing only by letter case is refused rather than split. Anything else that differs is a different code and passes: `HEIGHTS` in a requirement, or `HEI GHT` with a space through the middle, is simply a code nobody holds, and the job it belongs to becomes unqualifiable with nothing to indicate why.
- Reports carry the technician id beside the name, since two people on one crew can share a name and their rows would otherwise be indistinguishable. Names still drive the sort order, with the id breaking ties.
- Certifications have no expiry date here. A real roster carries an expiry per holding and the division runs against the certifications valid on the date of the job, which turns every `EXISTS` into a dated one.
- Query 03 is left as it is rather than repaired. Wrapping it in a technicians cross join with a LEFT JOIN would recover the empty-requirement case, at which point it is the absence version wearing a heavier costume.
- The near-miss report stops at one missing certification. Widening it to two is a change to one comparison, and the output grows quickly: of the seventeen technician and job pairs that fail a job, four are one certification short and twelve are two or fewer.

## License

Released under the MIT License. See [LICENSE](LICENSE).
Copyright (c) 2026 Kevin Yu (https://github.com/exekyute).
