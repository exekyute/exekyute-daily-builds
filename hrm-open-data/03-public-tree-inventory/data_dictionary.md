# Data dictionary

Definitions for the generated outputs. Column names are lowercase with underscores.
Every table is built from `trees_clean`, one row per tree, so all of them sum to the
same 78,896-tree total.

## out/species_ranking.csv (golden)

Identified species only, ranked by tree count. The counts plus the unidentified count in
`summary.csv` equal the whole inventory.

| Column | Type | Definition |
| --- | --- | --- |
| `species_rank` | integer | `RANK()` by `tree_count` descending, `species_common` ascending. Ties share a rank. |
| `species_common` | string | Common species name, trimmed and whitespace-collapsed. |
| `species_scientific` | string | Representative scientific name for that common name: the most frequent one recorded, ties broken alphabetically, in binomial case. |
| `tree_count` | integer | Number of trees of this species. |
| `share_of_all_pct` | decimal (2 dp) | `tree_count` as a percent of all 78,896 trees. |

## out/dbh_class_distribution.csv (golden)

One row per DBH size-class tier, all trees. `DBH` is an integer size-class code 1 to 9
(not a centimetre measurement); see SOURCE.md.

| Column | Type | Definition |
| --- | --- | --- |
| `dbh_class` | string | `Class 1-2`, `Class 3-4`, `Class 5-6`, `Class 7-9`, or `Unknown` (null code). |
| `tree_count` | integer | Number of trees in the tier. |
| `share_pct` | decimal (2 dp) | Tier count as a percent of all trees. |

Row order is fixed by an internal class ordinal (smallest tier first, `Unknown` last).

## out/wires_distribution.csv (golden)

One row per overhead-wires category, all trees. This is the categorical dimension the
build uses in place of the condition rating the dataset does not record.

| Column | Type | Definition |
| --- | --- | --- |
| `wires` | string | `Clear of wires`, `Under wires`, or `Unknown` (blank flag). |
| `tree_count` | integer | Number of trees in the category. |
| `share_pct` | decimal (2 dp) | Category count as a percent of all trees. |

## out/setting_distribution.csv (golden)

One row per general-location category, all trees.

| Column | Type | Definition |
| --- | --- | --- |
| `setting` | string | `Street right-of-way` (`ROW`) or `Open space` (`OSP`); `Unknown` otherwise. |
| `tree_count` | integer | Number of trees in the category. |
| `share_pct` | decimal (2 dp) | Category count as a percent of all trees. |

## out/summary.csv (golden)

One row per headline metric, values as text so counts, decimals, and names share a
column.

| `metric` | Meaning |
| --- | --- |
| `total_trees` | All trees on the inventory (78,896). |
| `identified_trees` | Trees with an identified species. |
| `unidentified_trees` | Trees in the `Unidentified` bucket. |
| `distinct_species` | Count of distinct identified common species (250). |
| `top_species` | Most common species by count. |
| `top_species_count` | Its tree count. |
| `top_species_share_pct` | Its share of all trees. |
| `most_common_dbh_class` | The largest DBH tier. |
| `trees_with_install_year` | Trees with a plausible recorded planting year. |
| `install_year_earliest` | Earliest recorded planting year. |
| `install_year_latest` | Latest recorded planting year. |

## bi/exports/mart_trees.csv (copy of out/mart_trees.csv)

One row per tree. This is the grain both dashboards consume; each re-derives the golden
figures by aggregating these rows.

| Column | Type | Definition |
| --- | --- | --- |
| `tree_id` | string | Unique asset identifier (`TREEID`). |
| `species_common` | string | Common species name, or `Unidentified`. |
| `species_scientific` | string | Scientific name in binomial case, or `Unknown`. |
| `dbh` | integer | DBH size-class code 1 to 9, or empty. |
| `dbh_class` | string | DBH tier (see above). |
| `setting` | string | General location. |
| `wires` | string | Overhead-wires category. |
| `install_year` | integer | Recorded planting year in 1900 to 2026, or empty. |
| `owner` | string | `HRM` or `Unknown`. |
| `status` | string | Asset status, `Installed`. |
| `lat` | decimal (6 dp) | Latitude, WGS84. |
| `lon` | decimal (6 dp) | Longitude, WGS84. |

Sort order is `tree_id`, fixed by the export query.

## dashboard/data.js

The five exported aggregates, re-emitted by `run.py` as a JavaScript `DATA` object
(`summary`, `species`, `dbh`, `wires`, `setting`) so the dashboard opens from disk with
no server and no fetch. The dashboard re-derives total trees and distinct species from
these rows and checks them against `summary`.
