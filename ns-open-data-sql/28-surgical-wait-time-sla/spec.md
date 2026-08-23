# Spec: surgical wait-time SLA tracker

## Purpose

Take the province's published surgical wait-time table and answer four
questions against a stated target: which procedures and facilities have
published medians above it, how far the 90th percentile sits above the median
on each line, which facilities rank worst, and how the published provincial
series moves quarter over quarter. Every figure is deterministic and
re-derivable from the committed snapshot.

## Inputs

One file: `data/raw/ns_surgical-wait-times_2026-07-25.csv`, a pinned snapshot of
Socrata dataset `wu5w-qxki` (see SOURCE.md). Columns: period, specialty,
procedure, provider, zone, facility, year, quarter, consult_median,
consult_90th, surgery_median, surgery_90th. 6,575 rows.

The four measure columns are published statistics. This build compares them,
subtracts them, and counts them. It never recomputes a percentile, because the
dataset carries no case-level durations to recompute one from.

## Row classes and what is held out

Every snapshot row falls into exactly one of three classes. The three counts add
back to 6,575, and the golden output carries that reconciliation as a row that
must read 0.

**1. Rolling-window rows (2,561 held out).** The `period` column mixes two
different reporting products. Nine values match `YYYY_qN` and are discrete
quarters: `2023_q2` through `2025_q2`. Two more, `12month_rolling` and
`3month_rolling`, are rolling windows published alongside those quarters. The
rolling windows overlap the quarters and each other, and the 12-month set adds a
surgeon-level grain the quarterly set does not have (provider populated, facility
blank). Mixing them into a quarterly aggregate would count the same waits more
than once, so only the nine quarterly periods feed the analysis.

**2. Provincial rollup rows (1,161 held out).** Inside the quarterly periods,
rows carrying `zone = 'Total'` and `facility = 'Provincial'` are the source's own
published provincial summary. They repeat waits already reported at the
facilities, so including them in a facility-level or zone-level aggregate double
counts. They are excluded from the facility grain and used only as the published
provincial reference series behind the quarter-over-quarter trend. Reporting
them separately is deliberate: their numbers are the province's, not something
this build derived by averaging facilities.

The two markers always travel together. The output carries a
`rollup_marker_mismatches` row counting any case where `zone = 'Total'` and
`facility = 'Provincial'` disagree; it reads 0 in this snapshot, and a nonzero
value there means the exclusion rule needs revisiting before the numbers can be
trusted.

**3. Facility lines (2,853 kept).** Nine quarters, 16 facilities, 111
procedures. This is the analysis grain, and `(facility, procedure, period)` is
unique across it.

## The targets, and why they are assumptions

Both targets are named constants declared in `sql/00_schema.sql` and used
nowhere else in the pipeline. Both are stated assumptions of this build, not
official Nova Scotia or pan-Canadian standards.

**`surgery_target_days() = 182`.** The breach test applies to `surgery_median`
and to nothing else. 182 days is six months, the length the pan-Canadian
benchmark family uses for joint replacement. Real benchmarks differ by
procedure, and a cataract target and a hip replacement target are not the same
number, so applying one figure across all 111 procedures is a simplification
made on purpose: it produces a single comparable rate rather than a defensible
clinical judgment. Read a breach here as "this published median sits above the
line this build drew", not as "this facility failed a standard".

**`consult_target_days() = 90`.** A separate constant applied only to
`consult_median`. Waiting for a specialist consultation and waiting for surgery
after that consultation are different queues measured on different clocks, so
they never share a threshold. Three months is a plain round figure for the
consultation step, chosen the same way and carrying the same caveat.

Neither target is ever applied to a 90th-percentile column. The 90th percentile
describes the slow tail of a queue; comparing it to a median-shaped target would
compare two different things.

**`min_measured_rows() = 9`.** Nine is one line per quarter across the nine
quarters, the thinnest series that still spans the whole window. A facility or
procedure with fewer measured lines gets `meets_min_rows = 0` and sorts to the
bottom of its ranked section. Nothing is dropped for being thin. The flag exists
so a 25 percent rate on 8 lines (Glace Bay) is not read as heavier than a 9.88
percent rate on 769 (QE2). One facility and 10 procedures fall below the
minimum; both counts are in the exclusions section.

**`worst_lines_shown() = 25`.** How many individual lines the `worst_lines`
section carries. A display cut that changes no computed figure.

## Tail gaps

One column per measure pair, computed at the line level:

- `surgery_tail_gap = surgery_90th - surgery_median`
- `consult_tail_gap = consult_90th - consult_median`

Each is NULL when either side of its own pair is absent. A gap is a spread, not
a wait: it says how much longer the slowest tenth waited than the middle
patient, on that line, in that quarter. Surgery gaps run to a median of 92 days
and a maximum of 1,323; consult gaps to a median of 113 and a maximum of 2,130.
A short median with a long gap and a long median with a short gap are different
situations, which is why the gap gets its own column instead of being folded
into the breach test.

## Year-quarter index

`year_quarter_index = year * 4 + quarter`. It runs 8094 (`2023_q2`) to 8102
(`2025_q2`), one step per quarter, with the previous quarter always at index
minus one including across a year boundary (`2023_q4` is 8096 and `2024_q1` is
8097). The mart carries it so the Power BI prior-quarter measure has a sortable
integer to index on, which matters because this mart has no contiguous date
column and DAX time intelligence needs a marked date table.

## Analysis steps (03_analysis.sql)

1. `facility_breach`: per facility, lines published, lines with a measured
   median, lines breaching each target, both breach rates, and the
   `meets_min_rows` flag.
2. `procedure_breach`: the same per procedure.
3. `facility_worst_line` and `procedure_worst_line`: the single longest
   published `surgery_median` in each group, tie-broken so the pick is identical
   on every run. The grouped output sections carry that line's own values.
4. `worst_lines`: the 25 longest published facility surgery medians in the
   snapshot, line by line.
5. `provincial_quarter` and `provincial_trend`: the published provincial rows,
   grouped by quarter, with the quarter-over-quarter change in breach rate
   stepped over `year_quarter_index`.
6. `wait_time_sla`: the eight sections stacked into one table.
7. `mart_wait_times`: the 2,853 facility lines with both targets and both breach
   flags attached, exported for the two BI faces.

## Outputs

- `out/wait_time_sla.csv`: the sectioned result, diffed against
  `expected/wait_time_sla.csv`. 193 rows in eight sections: constants,
  coverage, exclusions, breach_summary, worst_facilities, worst_procedures,
  worst_lines, provincial_trend.
- `out/mart_wait_times.csv`, copied to `bi/exports/mart_wait_times.csv`: the
  facility-line BI mart, 2,853 rows.

## Edge cases

- **Absent measures.** The source leaves a median blank where a line has too few
  cases to publish one. 124 facility lines carry no `surgery_median` and 669
  carry no `consult_median`. A blank median is never read as a zero and never
  counts as a pass: `surgery_measured` and `consult_measured` are 0 on those
  lines, so a breach rate always divides by lines that actually carry a number.
  Both counts are reported.
- **Blank specialty and provider.** Across the snapshot, 4,738 rows have no
  specialty and 4,764 have no provider. On the 2,853 facility lines the figure
  is 100 percent for both: those two columns are populated only in the
  12-month rolling rows, which this build excludes. No analysis here reads
  either column, and all four counts are reported so the blanks are visible
  rather than assumed away.
- **Procedure label spacing.** 20 procedure labels carry a double space before a
  bracket, for example `Back Surgery  (Adult)`. Runs of spaces are collapsed.
  The collapse merges nothing: 130 distinct raw labels stay 130 distinct labels.
- **Thin denominators.** Glace Bay publishes 8 measured surgery lines across
  nine quarters. It stays in the ranking with `meets_min_rows` set to 0, which
  puts it last in its section instead of hiding it.
- **Ties.** Breach counts and rates tie heavily. Two procedures sit at 100
  percent and two more share 77.78 percent on identical counts, so no ranking
  stops at the measure.
- **First quarter of the trend.** `2023_q2` is the first period in the window,
  so its quarter-over-quarter change is blank rather than zero.

## Determinism

Every measure is an integer count or an integer day figure; rates are exact
divisions rounded to two decimals at the end and stored as `DECIMAL(9,2)`.
Every result table ends in a total `ORDER BY` whose final terms form a unique
key at that grain, so row order never depends on scan order or engine version.
Ranked sections sort on the flag first, then the measure, then facility,
procedure, and period as needed to make the order unique. The worst-line picks
inside the grouped sections use the same explicit tie-break chain rather than an
arbitrary-pick aggregate. Two consecutive runs produce byte-identical files.
