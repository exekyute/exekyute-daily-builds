# Spec

## Purpose

Take two pinned snapshots, the HRM Tax Rates table and the polygons that enumerate
the area rates, and present them as a live Excel workbook: a rates reference sheet,
an areas reference sheet, and a calculator that stacks every applicable area rate
onto one property and returns the total. The workbook is the face; a plain-Python
recompute of the worked examples is the golden that guards it.

## Inputs

- Tax Rates (`HRM::tax-rates`, item `a1d6cb118da642a4ae6a7b3191ae2369`), pulled to
  `data/raw/hrm_tax-rates_2026-07-13.csv`. The build keeps bill year **2025**: 165
  rows, one per `(Rate_Code, Rate_Type)`, over 72 distinct codes.
- Area-rate polygons from five layers, pulled to
  `data/raw/hrm_area-rates_2026-07-13.csv` (52 feature rows), collapsed to **46**
  distinct area codes with a label and a layer category.

See SOURCE.md for the join and the per-$100 rate basis.

## Preparation rules (build.py)

`load_rates` keeps the latest bill year and returns one record per
`(Rate_Code, Rate_Type)`, sorted by code then class. `Rate` is kept as its exact
source string so every charge is computed with `decimal.Decimal`, never a float.

`load_areas` collapses the polygon rows to one row per `AREARATE_CODE`. When a code
appears on several polygons, the last-sorting label is kept, so the axis is
deterministic (Transit `M060` resolves to `2025 Local Transit`). The one non-ASCII
glyph in a label (a curly apostrophe) is folded to a plain apostrophe so the sheet
and the terminal table stay cp1252 safe.

Getting the distinct codes and their labels is data preparation, not analysis: no
charge is computed in Python for the workbook. Excel does every lookup and every
charge through cell formulas.

## Workbook structure

Three sheets. The calculator opens first.

**rates** (reference; one row per `(Rate_Code, Rate_Type)` for 2025, rows 2 to 166):

| Col | Header | Content |
| --- | --- | --- |
| A | `Rate_Code` | the code that an area's `AREARATE_CODE` joins to |
| B | `Rate_Type` | property class (Residential, Commercial, Resource, and others) |
| C | `Rate` | the rate value (dollars, or dollars per $100) |
| D | `Calculation_Type` | `Flat Rate` or `Rate` |
| E | `Rate_Description` | the source label |
| F | `key` | a live formula `=A&"|"&B`, the composite key the calculator matches |

**areas** (reference; one row per area code, rows 2 to 47): `AREARATE_CODE`,
`DESCRIP`, `category`. The code column drives a dropdown in the calculator through
the defined name `AreaCodes`.

**calculator** (the face; inputs, labels, and live formulas only). Two worked
scenarios, each a self-contained calculator block: an assessment input, a property
class input (a dropdown of Residential, Commercial, Resource), and six code rows
(the seeded example codes plus blank rows a user can fill from the dropdown). For
each code row the sheet builds the composite key, looks up the rate and calculation
type with `INDEX`/`MATCH`, computes the charge, and takes the charge's share of the
scenario total. A note flags any code and class with no 2025 rate.

The charge formula, on each code row `r`, with the scenario's assessment cell:

    =IF($A{r}="","",IFERROR(ROUND(IF($E{r}="Flat Rate",$D{r},$D{r}*<assessment>/100),2),0))

So a `Flat Rate` charge is the rate itself and a `Rate` charge is the rate times
assessment divided by 100, rounded to the cent. The total is `SUM` of the charge
column; each share is `ROUND(100 * charge / total, 1)`.

## Worked examples

Both are recomputed in plain Python (`compute_key_figures`) for the golden and
shown live in the workbook.

**Scenario A: Residential, assessment $325,000.** Stacks two per-$100 municipal
rates and one flat community rate.

| Code | Area | Calc type | Rate | Charge |
| --- | --- | --- | --- | --- |
| M050 | Fire Protection | Rate | 0.015 | 48.75 |
| M060 | Local Transit | Rate | 0.092 | 299.00 |
| A000 | Frame Subdivision Homeowners | Flat Rate | 45 | 45.00 |
| | | | **Total** | **392.75** |

**Scenario B: Commercial, assessment $600,000.** The same lookup returns the
Commercial rate, showing the charge is class sensitive.

| Code | Area | Calc type | Rate | Charge |
| --- | --- | --- | --- | --- |
| M050 | Fire Protection | Rate | 0.039 | 234.00 |
| R000 | Petpeswick Drive Private Road | Flat Rate | 330 | 330.00 |
| A020 | Silversides Residents | Flat Rate | 100 | 100.00 |
| | | | **Total** | **664.00** |

## Cell map (every worked-example figure and the cell that holds it)

**Scenario A** (assessment `B6` = 325000, class `B7` = Residential, total `F16`):

| Figure | Cell | Value |
| --- | --- | --- |
| M050 rate | `D10` | 0.015 |
| M050 calc type | `E10` | Rate |
| M050 charge | `F10` | 48.75 |
| M050 share % | `G10` | 12.4 |
| M060 rate | `D11` | 0.092 |
| M060 calc type | `E11` | Rate |
| M060 charge | `F11` | 299.00 |
| M060 share % | `G11` | 76.1 |
| A000 rate | `D12` | 45 |
| A000 calc type | `E12` | Flat Rate |
| A000 charge | `F12` | 45.00 |
| A000 share % | `G12` | 11.5 |
| Total charge | `F16` | 392.75 |
| Total share % | `G16` | 100.0 |

**Scenario B** (assessment `B19` = 600000, class `B20` = Commercial, total `F29`):

| Figure | Cell | Value |
| --- | --- | --- |
| M050 rate | `D23` | 0.039 |
| M050 calc type | `E23` | Rate |
| M050 charge | `F23` | 234.00 |
| M050 share % | `G23` | 35.2 |
| R000 rate | `D24` | 330 |
| R000 calc type | `E24` | Flat Rate |
| R000 charge | `F24` | 330.00 |
| R000 share % | `G24` | 49.7 |
| A020 rate | `D25` | 100 |
| A020 calc type | `E25` | Flat Rate |
| A020 charge | `F25` | 100.00 |
| A020 share % | `G25` | 15.1 |
| Total charge | `F29` | 664.00 |
| Total share % | `G29` | 100.0 |

The seeded code cells are `A10:A12` (M050, M060, A000) and `A23:A25` (M050, R000,
A020); `A13:A15` and `A26:A28` are blank rows within each `SUM` range for a user to
add codes. The rate and calc type on each row come from `rates` by `INDEX`/`MATCH`
on the composite key in column C; the description in column B comes from `areas`.

## Golden (expected/key_figures.csv)

Recomputed in plain Python by `compute_key_figures`, never read back from the
workbook. Columns `scenario, figure, area_code, class, calc_type, rate,
assessment, charge, share_pct`; rows in a fixed order: for each scenario, one row
per selected code, then the scenario total. Charges round with
`decimal.ROUND_HALF_UP` to the cent and shares to one decimal, matching the
workbook's `ROUND`. `build.py verify` recomputes and diffs against this file,
printing PASS on an exact match.

## Determinism

Both snapshots are pinned and committed. The rates rows are sorted by code then
class; the area codes are sorted; a multi-label code keeps its last-sorting label.
Charges round half-away-from-zero to the cent. The workbook metadata timestamp and
every zip-entry timestamp are fixed, so a regenerated file is byte-identical. Given
the same snapshots, `build.py` always produces the same workbook and the same
figures.

## Edge cases

- **Code with no 2025 rate (`M070`).** The lookup misses; `IFERROR` returns a zero
  charge and the note column reads "no 2025 rate for this code and class". `M070`
  stays on the areas sheet as a real enumerated area.
- **Class a code does not carry.** Same handling: a Residential-only code selected
  under Commercial returns a zero charge and the note.
- **Blank code rows.** Contribute nothing to the total; their formulas short to
  blank so the sheet stays clean while the `SUM` range still covers them.
- **Rounding at the cent.** Charges use Excel `ROUND(x, 2)`, half-away-from-zero;
  the Python golden uses `decimal.ROUND_HALF_UP`, so the two agree to the decimal.
