# Spec: Regional Waste and Fuel Log Aggregator

## Purpose

Job sites each send a monthly spreadsheet of their waste tonnage and fuel use,
and every site names its columns differently. This tool reads all of those
files from one folder, translates each site's column names into one shared set
of names, checks every row, drops bad rows with a clear reason, and combines the
good rows into a single unified operational ledger.

## Inputs

- A folder (default `data/`) of monthly site spreadsheets saved as `.csv`.
- Each file must provide four pieces of information, under any of these spellings
  (matching ignores case and surrounding spaces):
  - site: `Site`, `Location`, `Facility`, `Job Site`
  - month: `Month`, `Reporting Month`, `period` (written as `YYYY-MM`)
  - waste tons: `Waste (tons)`, `Waste Tonnage`, `waste_tons`, `Waste`
  - fuel gallons: `Fuel (gal)`, `Diesel Gallons`, `Fuel Used`, `fuel_gallons`, `Fuel`

## Validation rules

- A file missing any of the four required columns is skipped as a whole, and the
  missing column is named in the report.
- A row with a blank site is skipped (we will not file activity to no site).
- A month that is not `YYYY-MM`, or whose month part is outside `01-12`, is skipped.
- A waste or fuel value that is blank, not a number, or negative is skipped.
- When the same site reports the same month more than once, the first one read is
  kept and the later one is reported as a duplicate. Files are read in filename
  order, and the sample files are numbered in the order they were received, so the
  original is kept and a resend is the one flagged.

## Logic

1. Find every `.csv` in the input folder, in sorted filename order.
2. For each file, map its header row onto the four canonical names. If anything
   is missing, skip the file.
3. For each row, clean and validate the four values, converting quantities to
   `Decimal`.
4. Deduplicate on `site + month`, keeping the first seen.
5. Sort the surviving rows by site, then month.
6. Write the ledger and print a summary of what was combined and what was dropped.

## Outputs

- `output/unified_ledger.csv` with the canonical header
  `site,month,waste_tons,fuel_gallons`, quantities written as fixed-point with two
  decimals (for example `12.50`), never scientific notation.
- A printed summary: files read, rows combined, rows skipped (each with a reason),
  and the count and names of the distinct sites.

## Edge cases

The sample data is built so a single run exercises each of these:

| Case | Where | Result |
| --- | --- | --- |
| Clean file, standard headers | `01-north-site.csv` | combined |
| Different header spellings | `02-harbor-site.csv` | normalized and combined |
| Negative fuel value | `02-harbor-site.csv` Feb | row skipped |
| Blank site | `03-ridge-site.csv` | row skipped |
| Bad month `2026-13` | `03-ridge-site.csv` | row skipped |
| Duplicate site and month | `04-north-site-resend.csv` | reported, original kept |
| Boundary value `0.00` | `01-north-site.csv` Feb | combined |
| Missing required column | `05-depot-site.csv` | whole file skipped |

## Hand-checked cross-tool value

Running the tool on the sample data produces a ledger with **3 distinct sites**:
Harbor Site, North Site, Ridge Site. (Depot Site is excluded because its file is
missing the waste column.) The Regulatory Deadline Monitor reads this same ledger
and cross-checks the same 3 sites. Both tools agreeing on this count of 3 is the
documented proof that the two tools see the same site list. See the deadline
monitor spec for the matching note.
