# Data dictionary

## Workbook: crime_snapshot.xlsx

### Sheet `data` (one row per incident, 90 rows)

| Column | Type | Meaning |
| --- | --- | --- |
| `evt_date` | date | Event date (real Excel date, `yyyy-mm-dd`). The feed stores every event at midnight, so only the date is meaningful. |
| `evt_rin` | integer | Event record (occurrence) number. Used as the tie-breaker in the stable sort. |
| `category` | text | Crime category, from source `RUCR_EXT_D` (for example `ASSAULT`, `THEFT FROM VEHICLE`). |
| `code` | integer | Numeric UCR code, from source `RUCR`. Several codes can map to one category. |
| `location` | text | Street name of the event, from source `LOCATION`. |

Rows are sorted by (`evt_date`, then `evt_rin`).

### Sheet `summary` (labels and live formulas)

| Region | Meaning |
| --- | --- |
| `B5` | Total incidents (`COUNTA` of the data category column). |
| `A8:A11` | Category labels, alphabetical. |
| `B8:B11` | Incidents per category (`COUNTIF` against the data sheet). |
| `C8:C11` | Category share of the total, percent, one decimal (`ROUND`). |
| `B12` / `C12` | Category subtotal count and share; ties to `B5` at 90 and 100.0. |
| `B14` | Top category, by `INDEX`/`MATCH` over `MAX`. |
| `B15` | Top category incident count (`MAX`). |
| `B16` | Top category share of the total, percent, one decimal. |

### Sheet `by_area` (labels and live formulas)

| Region | Meaning |
| --- | --- |
| `A4:A85` | Location labels, alphabetical (82 distinct streets). |
| `B4:B85` | Incidents per location (`COUNTIF` against the data sheet). |
| `B86` | Location total (`SUM`); ties to 90. |

## Golden: expected/key_figures.csv

One row per key figure. Recomputed in plain Python, never read from the workbook.

| Column | Type | Meaning |
| --- | --- | --- |
| `figure` | text | `total`, `top_category`, or `category`. |
| `category` | text | Category name for `top_category` and `category` rows; blank for `total`. |
| `count` | integer | Incident count for the figure. |
| `share_pct` | number | Share of the total incidents, percent, one decimal, half-away-from-zero. |

Row order is fixed: `total`, then `top_category`, then one `category` row per
category alphabetically.
