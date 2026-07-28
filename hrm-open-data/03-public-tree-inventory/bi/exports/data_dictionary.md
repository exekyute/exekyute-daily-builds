# Data dictionary: mart_trees.csv

The frozen dashboard mart. One row per tree, 78,896 rows. Tableau, Power BI, and
the browser dashboard all read this one file, so a viewer can flip between the
three faces and read the same figure. Written by `sql/99_export.sql`, ordered by
`tree_id`.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `tree_id` | text | Asset identifier (`TREEID`), unique across all 78,896 rows. |
| 2 | `species_common` | text | Common species name, trimmed and whitespace-collapsed. `Unidentified` on the 4,763 rows where the source recorded no name or the literal `Unknown Species`. |
| 3 | `species_scientific` | text | Scientific name in binomial case, genus capitalized and the rest lowercased. `Unknown` on 4,625 rows. |
| 4 | `dbh` | integer | DBH size-class code, 1 to 9. A tier code, not a centimetre measurement. Blank on 575 rows. |
| 5 | `dbh_class` | text | Size tier: Class 1-2, Class 3-4, Class 5-6, Class 7-9, or Unknown where the code is blank. |
| 6 | `setting` | text | General location: Street right-of-way (73,045 rows) or Open space (5,851). |
| 7 | `wires` | text | Overhead wires: Clear of wires (43,803), Under wires (34,445), or Unknown where the source flag is blank (648). |
| 8 | `install_year` | integer | Recorded planting year, 2013 to 2025. Blank on 68,899 rows; only 9,997 trees carry one. |
| 9 | `owner` | text | HRM (69,565 rows) or Unknown (9,331). |
| 10 | `status` | text | Asset status. `Installed` on every row in this snapshot. |
| 11 | `lat` | number | WGS84 latitude, six decimals. |
| 12 | `lon` | number | WGS84 longitude, six decimals. |

The two species columns are cleaned independently, so they do not always agree:
138 rows carry a scientific name (`Acer freemanii`) while `species_common` reads
`Unidentified`. Count species off `species_common`, which is the column both the
SQL ranking and the `Distinct Species` measure use.

`dbh` and `install_year` land as whole numbers, so Power BI defaults both to
summarize-by-sum. Neither sums to anything meaningful: `dbh` is an ordinal tier
code and `install_year` is a calendar year. The report averages `dbh` through the
`Avg DBH` measure and uses `install_year` as a chart axis.

## How to bind the geography

Halifax communities and districts are not built-in geographic roles in Tableau,
so the map binds to the `lat` and `lon` this mart already carries, not to a named
role. Every row in this snapshot carries a coordinate, so none drop from the map.

## Reconciliation

- `COUNT` of all rows is **78,896**, the inventory total the SQL golden, the
  Tableau map, and the Power BI card all report.
- `DISTINCTCOUNT` of `species_common` excluding `Unidentified` is **250**, the
  distinct-species figure. Counting the bucket in returns 251.
- `COUNT` of rows with `species_common = 'Norway Maple'` is **10,276**, which is
  **13.02 percent** of the inventory, the top-species share on both reports.
- Grouping by `dbh_class`, Class 1-2 leads with **41,855** rows, **53.05 percent**
  of the inventory.
- Grouping by `setting`, Street right-of-way holds **73,045** rows, **92.58
  percent**.
- `COUNT` of rows with a non-blank `install_year` is **9,997**, every one of them
  between **2013** and **2025**.
