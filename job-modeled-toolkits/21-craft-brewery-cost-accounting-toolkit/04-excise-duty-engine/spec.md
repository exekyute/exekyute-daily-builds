# Excise Duty Engine

## Purpose
Computes the federal excise duty on the beer a brewery packaged in the period,
using the Canada Revenue Agency reduced-rate brackets by ABV class. A cost
accountant runs it after the batch tool to book the duty and to feed it into the
per-SKU margin.

## Inputs
The finished-unit costs from the batch tool, which carry each packaging run's
volume and ABV class:

| Column | Type | Notes |
| --- | --- | --- |
| fg_sku | text | Finished-good SKU, used to label the run. |
| abv_class | text | `over_2_5`, `over_1_2_to_2_5`, or `not_over_1_2`. |
| packaged_litres | number | Litres packaged in this run. |

Other columns from the batch file are carried along but not used here.

A command-line figure, `--ytd-hl`, is the total beer of every ABV class already
brewed this calendar year before this run. It sets where the period's volume
falls in the reduced-rate brackets.

## Validation rules
The file is rejected, with nothing written, if any row fails a check:

- A required column is missing from the header.
- `--ytd-hl` is non-numeric or negative.
- `fg_sku` is blank.
- `abv_class` is not one of the three allowed values.
- `packaged_litres` is non-numeric, or is zero or negative.

## Logic
1. Convert each run's litres to hectolitres at 100 litres each.
2. Thread a single cumulative annual production figure, starting at `--ytd-hl`, through the runs in file order. The order of packaging sets the bracket each volume falls in.
3. For each run, split the volume across the reduced-rate brackets it spans, applying that ABV class's rate in each bracket. Anything past the 75,000 hL annual limit is charged the regular rate.
4. Total the duty by ABV class.

The rates are the CRA rates of excise duty on beer brewed in Canada, per
hectolitre, effective April 1, 2026, written out in `excise.py`. Duty is held as
`decimal.Decimal`, kept unrounded while a class totals, and quantized half up to
the cent once.

## Outputs
`excise_summary.csv`, one row per ABV class present: `abv_class`, `hectolitres`,
`excise_duty`. The margin tool and the month-end close read it.

## Edge cases
The sample data exercises each branch:

- **Several runs in one ABV class** that all sit inside the first bracket (the over 2.5% beer).
- **A run that crosses a bracket boundary**, where the radler spans the 2,000 hL line (part at the first-bracket rate, part at the second).
- **Two ABV classes** in one period, totalled separately.
- The invalid sample carries a blank SKU, a bad ABV class, and a negative volume, so the rejection path can be seen.

### Hand-checked example
Starting from 1,960.00 hL already brewed this year:

- The over 2.5% beer packages to 30.25 hL (10.65 + 7.50 + 7.10 + 5.00), taking cumulative production from 1,960.00 to 1,990.25 hL, all inside the first bracket at $3.769 per hL. Duty = $114.01.
- The radler (over 1.2% to 2.5%) packages 14.20 hL, taking cumulative production from 1,990.25 to 2,004.45 hL. The first 9.75 hL fall in the first bracket at $1.885 = $18.37875; the remaining 4.45 hL fall in the second bracket at $3.770 = $16.7765. Duty = $35.16.

Total excise duty = **$149.17**. This total is checked by `test_excise.py`, and
the month-end close books the same figure.
