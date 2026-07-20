# Spec

## Purpose

Take a pinned snapshot of the Halifax Crime incident feed and present it as a
live Excel workbook: the raw incidents on one sheet, and a formula-driven summary
by category and by area on the others. The workbook is the face; a plain-Python
recompute is the golden that guards it.

## Inputs

Dataset: Crime (`HRM::crime`, item `f6921c5b12e64d17b5cd173cafb23677`), pulled to
`data/raw/hrm_crime_2026-07-13.csv`, 90 incident rows. See SOURCE.md.

Columns used: `EVT_DATE` (event date), `EVT_RIN` (occurrence number),
`RUCR_EXT_D` (category), `RUCR` (numeric UCR code), `LOCATION` (street). The
`OBJECTID`, `EVT_RT`, `x`, and `y` columns are carried in the snapshot but not
brought into the workbook.

## Preparation rules (build.py, load_snapshot)

1. Parse `EVT_DATE` from `M/D/YYYY 12:00:00 AM` to a date (the feed stores every
   event at midnight, so only the date carries meaning).
2. Cast `EVT_RIN` and `RUCR` to integer; trim whitespace on `RUCR_EXT_D` and
   `LOCATION`.
3. Sort the incidents by the stable key (`evt_date`, then `evt_rin`) so the data
   sheet and any recompute are byte-reproducible from the snapshot.

Getting the distinct category and location axis labels is data preparation, not
analysis: the labels are sorted alphabetically without counting, and Excel does
all of the counting through cell formulas.

## Workbook structure

Three sheets. The data sheet occupies rows 1 (header) and 2 to 91 (90 incidents).

**data** (raw incidents, sorted by `evt_date`, `evt_rin`):

| Col | Header | Content |
| --- | --- | --- |
| A | `evt_date` | event date, real Excel date, format `yyyy-mm-dd` |
| B | `evt_rin` | occurrence number (the sort tie-breaker) |
| C | `category` | crime category (`RUCR_EXT_D`) |
| D | `code` | numeric UCR code (`RUCR`) |
| E | `location` | street name |

**summary** (labels and live formulas only):

- The category counts use `COUNTIF` over `data!$C$2:$C$91`.
- Shares use `ROUND(100 * count / total, 1)`; Excel `ROUND` is half-away-from-zero.
- The total uses `COUNTA` of the category column, and the by-category subtotal
  `SUM`s the four category counts; the two tie at 90.
- The top category is found by formula (`INDEX`/`MATCH` over `MAX`), never by
  reading a pre-sorted row.

**by_area** (labels and live formulas only): one `COUNTIF` per distinct location
over `data!$E$2:$E$91`, alphabetical, with a `SUM` total.

## Cell map (every key figure and the cell that holds it)

On the **summary** sheet:

| Key figure | Cell | Formula |
| --- | --- | --- |
| Total incidents | `B5` | `=COUNTA(data!$C$2:$C$91)` |
| ASSAULT count | `B8` | `=COUNTIF(data!$C$2:$C$91,A8)` |
| ASSAULT share % | `C8` | `=ROUND(100*B8/$B$5,1)` |
| BREAK AND ENTER count | `B9` | `=COUNTIF(data!$C$2:$C$91,A9)` |
| BREAK AND ENTER share % | `C9` | `=ROUND(100*B9/$B$5,1)` |
| THEFT FROM VEHICLE count | `B10` | `=COUNTIF(data!$C$2:$C$91,A10)` |
| THEFT FROM VEHICLE share % | `C10` | `=ROUND(100*B10/$B$5,1)` |
| THEFT OF VEHICLE count | `B11` | `=COUNTIF(data!$C$2:$C$91,A11)` |
| THEFT OF VEHICLE share % | `C11` | `=ROUND(100*B11/$B$5,1)` |
| Category subtotal (count) | `B12` | `=SUM(B8:B11)` |
| Category subtotal (share %) | `C12` | `=ROUND(100*B12/$B$5,1)` |
| Top category | `B14` | `=INDEX($A$8:$A$11,MATCH(MAX($B$8:$B$11),$B$8:$B$11,0))` |
| Top category incidents | `B15` | `=MAX($B$8:$B$11)` |
| Top category share % | `B16` | `=ROUND(100*B15/$B$5,1)` |

The category rows run alphabetically: `A8` ASSAULT, `A9` BREAK AND ENTER, `A10`
THEFT FROM VEHICLE, `A11` THEFT OF VEHICLE.

## Golden (expected/key_figures.csv)

Recomputed in plain Python by `compute_key_figures`, never read back from the
workbook. Columns `figure, category, count, share_pct`; rows in a fixed order: the
total, the top category, then one row per category alphabetically. Shares round
with `decimal.ROUND_HALF_UP` to one decimal, matching the workbook's `ROUND`.
`build.py verify` recomputes and diffs against this file, printing PASS on an exact
match.

## Determinism

The snapshot is pinned and committed. The data sheet is sorted by (`evt_date`,
`evt_rin`); the category and location axes are alphabetical; the top category
breaks ties by category name. Shares round half-away-from-zero. The workbook
metadata timestamp is fixed, so a regenerated file is byte-stable. Given the same
snapshot, `build.py` always produces the same figures.

## Edge cases

- **Rolling feed:** a later pull returns different incidents, a different count,
  and a different date window; the workbook still reproduces exactly from whatever
  snapshot is committed. SOURCE.md records the observed window.
- **Multiple UCR codes per category:** several `RUCR` codes map to one
  `RUCR_EXT_D` (for example 1420, 1430, 1460 are all ASSAULT). The summary groups
  on the category text, so the codes roll up correctly; `code` is kept on the data
  sheet for reference.
- **Ties for top category:** broken alphabetically by category name in the Python
  recompute; the workbook's `MATCH` returns the first row of the alphabetical
  axis, so the two agree. The current snapshot has a clear single top category.
