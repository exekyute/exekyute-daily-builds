# BI mart: mart_capital.csv

The frozen mart both BI tools read. One row per capital-project record (one
project at one location in one budget year), 2,650 rows. Written by the SQL
export step and identical to `out/mart_capital.csv`. This dataset has no dollar
field; every measure built on this mart is a count of records.

| Column | BI type | Meaning |
| --- | --- | --- |
| `proj_no` | Text | Project number. Repeats across locations and years (280 distinct). Use `COUNT` of it, or `COUNTROWS`, for a project count. |
| `proj_name` | Text | Project name. |
| `loc_desc` | Text | Location description; blank on some records. |
| `work_desc` | Text | Description of the capital work. |
| `category` | Text | Raw budget category as published. |
| `category_norm` | Text | Normalized category folding the raw duplicates. Colour and grouping field. 16 values. |
| `asset_type` | Text | Asset type; blank rows are labelled `(unspecified)`. 15 values. |
| `year` | Whole Number | Budget year, 2013 to 2021 (integer index; no date column). Set Summarization to Don't summarize. |
| `lat` | Decimal Number | Latitude, WGS84, six decimals. Latitude role in Tableau. |
| `lon` | Decimal Number | Longitude, WGS84, six decimals. Longitude role in Tableau. |

Reference figures (from the SQL golden): 2,650 records; Roads 1,245 (47.0%);
Parks & Playgrounds 558; Buildings 386; `(unspecified)` asset type 2,388.
