# Spec

## Purpose

Count who received Nova Scotia's two COVID-era small-business grants, broken down by business type and year, and measure how concentrated the grants were across types. The result is a small, deterministic table that answers: for each business type, how many recipients, how many received each grant, and what share of all recipients does the type hold?

## Inputs

Source dataset: **Applicants and Recipients of Small Business Impact Grant and Small Business Reopening and Support Grant** (`xaty-cfpq`), pulled as a pinned snapshot into data/raw/. Details and pull method in SOURCE.md.

Columns used (all published as text):

| Source column | Used as |
| --- | --- |
| `year` | program year |
| `type_of_business` | business classification, 14 distinct values |
| `received_small_business_impact` | did the record receive the Impact Grant (SBIG), yes or no |
| `received_small_business` | did the record receive the Reopening and Support Grant (SBRSG), yes or no |

The `ns_small_business` name column is loaded but not used in the output; it carries no analytical weight once records are grouped by type.

**Recipients, not applicants.** A recipient is any record that received at least one of the two grants. The analysis runs on recipients only. In this snapshot every record is a recipient, so the recipient filter keeps all rows, but it is written explicitly so the pipeline stays correct on a future snapshot that also lists applicants who received nothing.

## Cleaning and validation rules

- The yes/no flags are trimmed and lower-cased before comparison, so stray whitespace or casing does not change a count.
- Each flag becomes a boolean: `got_sbig` and `got_sbrsg`. A record is a recipient when either boolean is true.
- No dollar column exists in this dataset, so no money is summed. The output is counts of recipients.
- Business type is used exactly as published. No types are merged or renamed.

## Analysis logic, step by step

The steps map one to one onto the sql/ files. run.py runs them in order and holds no logic.

1. **00_schema.sql** creates `raw_grants` (the snapshot, all text) and `recipients` (year, type, and the two grant booleans).
2. **01_load.sql** loads the dated snapshot from data/raw/ into `raw_grants` via a filename glob, so the date is not hard-coded in SQL.
3. **02_transform.sql** filters to recipients (at least one grant) and turns the yes/no text into the `got_sbig` and `got_sbrsg` booleans.
4. **03_analysis.sql** groups recipients by year and business type and computes: `recipients` (count of records), `sbig_recipients` and `sbrsg_recipients` (counts that received each grant), and `pct_of_recipients` (the type's recipients as a percentage of all recipients, rounded to two decimals). This percentage is the concentration measure.
5. **99_export.sql** copies the result to out/grants_by_type_year.csv, ordered by year, then most recipients first, then business type.

## Outputs

out/grants_by_type_year.csv, one row per (year, business type), with recipient counts, per-grant counts, and each type's share of all recipients. Every column is defined in data_dictionary.md. The golden copy is expected/grants_by_type_year.csv.

## Edge cases

- **No dollar column.** The source carries no grant amount, so the project reports counts of recipients only and says so. Nothing sums money.
- **Unknown or unexpected business types.** Types are taken as published and grouped verbatim, so a new type in a future snapshot flows through as its own row without special handling.
- **Repeated records.** Organization names repeat, and some full rows repeat, but the source has no unique business identifier. Records are counted as published rather than deduplicated, since removing repeats would require a guess about business identity that the data does not support.
- **Applicants who received nothing.** None appear in this snapshot, but the recipient filter would exclude them if they did.

## Determinism

Every result query ends in ORDER BY, and the export repeats the same ORDER BY so row order never depends on scan order. The snapshot is pinned in data/raw/ and read from disk, not the network. The recipient counts sum to the snapshot row count (4,227). A first verified run produced expected/grants_by_type_year.csv; `python run.py` regenerates the output and prints PASS only when it matches the golden copy line for line.
