# Spec

## Purpose

Take a pinned server-side grouped snapshot of HRM's 2024 tax bill lines and produce deterministic tables that answer three things: how taxable assessment and the resulting bill split across residential, commercial, and resource by tax group; which tax groups carry the largest share of the municipal bill; and which rate codes carry the highest realized rate against their taxable base.

## Inputs

Dataset: HRM Tax Bill Info, pulled with server-side aggregation to `data/raw/hrm_tax-bill-info_2026-07-09.csv` (5,383 grouped rows). See SOURCE.md for the exact `outStatistics` query. The grain of the snapshot is one row per `tax_group`, `tax_summary_group`, `rate_code`, `rate_description`, and `bill_rate_percentage`.

Columns used: all eleven snapshot columns. The three taxable classes and the billed dollars are the measures; the five descriptive fields are the grain.

## Cleaning and validation rules (02_transform.sql)

1. Trim whitespace from the five text fields.
2. Cast `account_count` and the three taxable classes to integers; cast `bill_rate_percentage` to double.
3. Round `bill_value` and `bill_amount` to the cent, once. The source delivers these as floating-point sums with trailing noise, so rounding here means every later total is a sum of clean cents that ties exactly.
4. Drop any row missing `tax_group` or `rate_code`.
5. Collapse to one row per grain by summing. The snapshot already holds one row per grain, so this is a guard: it stops a stray duplicate line from double-counting or from making the later aggregates non-deterministic.

The result is `tax_clean`, one clean typed row per grain.

## Analysis logic step by step (03_analysis.sql)

The build produces two BI marts, three golden result tables, and a headline.

**mart_tax_group** (wide, one row per grain, the Power BI and Tableau import). Carries the five descriptive fields, `account_count`, the three taxable classes, `total_taxable` (the three summed), `bill_amount`, `bill_value`, and `effective_rate`.

- `total_taxable` = `residential_taxable + commercial_taxable + resource_taxable`.
- `effective_rate` = `round(bill_amount / total_taxable, 6)`, the realized rate of billed dollars against the taxable assessment. Guarded: NULL when `total_taxable` is 0, so an exempt line that carries a bill but no taxable base never divides by zero.

**mart_tax_class** (long, one row per tax group per class with a taxable base, the stacked-bar source). Unpivots the three class columns into (`tax_group`, `class`, `taxable`) and keeps rows where `taxable > 0`.

- `share_of_total_taxable` = `round(taxable / SUM(taxable) OVER (), 6)`, each row's share of the municipal taxable base. This is the value the Tableau FIXED LOD reproduces. Every tax group is single-class in this data, so a group contributes exactly one class row (13 rows over the 13 groups that carry a taxable base).

**tax_group_summary** (golden 1, one row per tax group, all 28). Groups `tax_clean` to the tax-group level and adds:

- The three taxable classes, `total_taxable`, `bill_value`, `bill_amount` (all summed cents).
- `effective_rate` = `round(bill_amount / total_taxable, 6)`, guarded to NULL on a zero base.
- `bill_share` = `round(bill_amount / SUM(bill_amount) OVER (), 6)`, the group's share of the municipal bill (the FIXED-style share).
- `bill_rank` = `DENSE_RANK() OVER (ORDER BY bill_amount DESC)`. Rank 1 is the largest-billed group.

**taxable_by_class** (golden 2). The same content as `mart_tax_class`, pinned as a golden result so the stacked-bar source is diffed row for row.

**rate_effective** (golden 3, one row per rate code, all 72). Rolls `tax_clean` to the rate-code level across every tax group that uses the code (54 of the 72 codes span more than one group), and computes:

- `account_count`, `total_taxable`, `bill_amount` summed.
- `effective_rate` = `round(bill_amount / total_taxable, 6)`, the blended realized rate for the code, guarded to NULL on a zero base.

**headline** (two rows). Reads the totals and the largest group and writes two ready-to-read lines for the console. `run.py` prints these; it does not compute them.

## Outputs

Golden results, written to `out/` and diffed against `expected/`:

- `tax_group_summary.csv`, 28 rows, ordered by `bill_amount DESC, tax_group`.
- `taxable_by_class.csv`, 13 rows, ordered by `tax_group, class`.
- `rate_effective.csv`, 72 rows, ordered by `effective_rate DESC NULLS LAST, rate_code`.

Frozen BI marts, written to `bi/exports/` (deterministic exports of the same tables, read by both dashboards):

- `mart_tax_group.csv`, 5,383 rows, ordered by `tax_group, rate_code, bill_rate_percentage, tax_summary_group`.
- `mart_tax_class.csv`, 13 rows, ordered by `tax_group, class`.

Every column is defined in data_dictionary.md (golden results) and bi/exports/data_dictionary.md (marts).

## Determinism

The snapshot is pinned and committed. Money is rounded to the cent once in `02_transform.sql`, ratios are rounded to six decimals and stored as fixed-scale decimals, and every result query ends in an `ORDER BY`, so the same input always produces byte-identical output. The golden files under `expected/` were built from a first verified run; `run.py` re-runs the pipeline and diffs the fresh output against them, printing PASS only on an exact row-for-row match on all three.

## Numbers that tie

- Sum of `bill_amount` over the 28 tax-group rows = the sum over the 72 rate-code rows = the sum over the 5,383 wide-mart rows = **$1,001,727,311.03**, the headline total.
- Sum of `taxable` over the 13 class rows = sum of `total_taxable` over the 28 tax-group rows = **$523,318,932,375**.
- Sum of `account_count` over the tax-group rows = **1,252,942** billed account lines, which is the original source table's row count before aggregation (the committed snapshot itself is the 5,383 grouped rows).

## Edge cases

- **Exempt groups and rate codes:** an exempt line carries a `bill_amount` but a zero taxable base. `effective_rate` is NULL there (rendered as an empty field), never a divide by zero. These groups still count toward `bill_amount` totals and `bill_share`.
- **Zero taxable classes:** a class column is 0 when the tax group does not carry that class. Those rows are dropped from the class-long view (nothing to stack), which does not change the taxable total.
- **Floating-point billed dollars:** removed by the single cent-rounding in cleaning before any total is summed.
- **Duplicate grain rows:** summed away in `tax_clean` so a duplicate cannot skew a count, a total, or a rank.
