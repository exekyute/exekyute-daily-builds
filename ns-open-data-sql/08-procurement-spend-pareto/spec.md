# Spec

## Purpose

Measure how concentrated Nova Scotia's awarded tender spending is among vendors. The build sums award dollars per vendor, ranks vendors from largest to smallest, traces a running cumulative share of all award dollars, and flags the smallest top set that reaches 80 percent. It also counts each vendor's awards and marks repeat vendors. The headline is how few vendors it takes to reach 80 percent of the dollars.

## Inputs

One dataset: Awarded Public Tenders (`m6ps-8j6u`), pulled to `data/raw/ns_awarded-tenders_2026-07-05.csv` (32,829 rows). Details in SOURCE.md.

Two columns carry the analysis:

- `vendor`: the awarded vendor name, free text.
- `awarded_amount`: the award value, stored as text in the source.

The other columns (tender id, entity, goods and service and construction flags, dates, description) are loaded but not used here.

## Cleaning and validation rules

All rules are fixed and applied in `sql/02_transform.sql`.

**Amount parsing.** `awarded_amount` is cast to a number and rounded to the cent. In this snapshot every value parses cleanly. A row is kept only when the amount is greater than zero, because a spend Pareto is about dollars actually awarded. That drops the 823 rows recorded at exactly zero and the single negative row (a correction), which carry no spend.

**Vendor name normalization.** Two derived strings come from `vendor`:

1. A cleaned name: decode the `&amp;` HTML entity to `&`, uppercase, replace every character that is not a letter, digit, ampersand, or space with a space, then collapse runs of spaces. This makes case and punctuation variants match, so `Dexter Construction Co. Ltd.` and `DEXTER CONSTRUCTION CO. LTD.` become the same string.
2. A vendor key: from the cleaned name, strip trailing corporate-suffix words (LTD, LIMITED, INC, INCORPORATED, CO, COMPANY, COMPANIES, CORP, CORPORATION, LP, LLP, ULC). This merges legal-form variants onto one entity, so `DEXTER CONSTRUCTION`, `DEXTER CONSTRUCTION CO LTD`, and `DEXTER CONSTRUCTION COMPANY LIMITED` all collapse to the key `DEXTER CONSTRUCTION` (1,842 rows in this snapshot). It does not merge misspellings such as `DEXTER CONSRUCTION`, since a fixed rule cannot tell a typo from a different name.

**Exclusions.** A row is dropped when its vendor key is blank, or when the key is one of a fixed set of placeholders that stand in for "not one vendor": `VARIOUS`, `VARIOUS VENDORS`, `MULTIPLE`, `MULTIPLE VENDORS`, `N A` (from `N/A`), `NA`, `NONE`, `TBD`, `TBA`, `UNKNOWN`. Matching is exact on the key, so a real vendor name that merely contains one of these words is kept.

After all rules, 31,754 of the 32,829 rows remain, covering 9,305 distinct vendors and $18,515,725,689.17 in award dollars.

## Analysis logic, step by step

Steps run in filename order. `run.py` runs the files and holds no logic.

1. **Sum by vendor** (`sql/03_analysis.sql`, question 1). Group the cleaned awards by vendor key. For each key, sum the award dollars (`total_awarded`) and count the awards (`award_count`). Choose a human-readable display name: the raw spelling that carried the most dollars under that key, with award count and then alphabetical order as tiebreakers.
2. **Rank and running total** (`sql/03_analysis.sql`, question 2). Order vendors by dollars descending, breaking ties by vendor key so the order is fixed. Assign `vendor_rank` and a running `cumulative_awarded` with a window function over that order.
3. **Cumulative share.** Divide each vendor's dollars, and the running total, by the grand total to get `pct_of_total` and `cumulative_pct`.
4. **80 percent flag.** A vendor is in the 80 percent set (`reaches_80pct_set`) when the cumulative share of every vendor ranked above it was still under 80 percent. The vendor that crosses the line is included; nobody past it is. This is the smallest top set that reaches 80 percent.
5. **Repeat-vendor rule.** `is_repeat_vendor` is true when the vendor's `award_count` is greater than one.

## Outputs

One file, `out/vendor_pareto.csv`, one row per vendor ordered by rank. Columns are defined in data_dictionary.md. The committed golden copy is `expected/vendor_pareto.csv`.

## Edge cases

- **Blank amounts, zero, and negative.** No amounts are blank in this snapshot. Zero amounts (823) and the one negative amount are excluded as non-spend.
- **Blank vendor.** 23 rows have no vendor and are excluded.
- **Placeholder vendors.** Exact-match placeholder keys (VARIOUS, MULTIPLE VENDORS, N/A, and so on) are excluded.
- **Vendor-name variants.** Case, punctuation, and legal-suffix variants are merged by the vendor key. Misspellings are not merged.
- **Compound and multi-vendor strings.** A few records name several vendors in one field (for example an RFSQ bundle). These do not match a placeholder key exactly, so they are kept as their own entity rather than split, which a fixed rule cannot do reliably. They are labelled as written.

## Determinism and money

The snapshot is pinned and committed. Every result query ends in `ORDER BY`, and the rank order is fully determined (dollars descending, then vendor key), so ranks never wobble between runs. Money is parsed once, rounded to the cent, summed as fixed-point decimals, and carried as `DECIMAL(18,2)` end to end, so totals and the running total tie to the cent. Shares are carried as `DECIMAL(7,4)`. Running `python run.py` twice produces byte-identical output, which is what the golden diff checks.
