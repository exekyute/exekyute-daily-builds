# Data dictionary

## out/mart_ev.csv

One row per installed public EV charging station. 33 rows. This is also the frozen
BI mart (`bi/exports/mart_ev.csv`).

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `evcsid` | text | EV charging station id, unique per station (33 distinct). |
| 2 | `owner` | text | Owner. Every record is `HRM`. |
| 3 | `chartype` | text | Charging level: `L2` (Level 2 AC) or `DCFC` (DC fast). |
| 4 | `connectype` | text | Connector type: `J1772`, `CCSCHADEMO`, or `CCSNACS`. |
| 5 | `power_kw` | number | Power rating in kW, two decimals (6.6, 7.0, or 175.0). |
| 6 | `location` | text | Address or place description, whitespace-normalized. |
| 7 | `access` | text | Charger access. Every record is `PUBLIC`. |
| 8 | `install_year` | integer | Install year (2024, 2025, or 2026). |
| 9 | `quantity` | integer | Available ports at the station (1 or 2). |
| 10 | `lat` | number | Latitude, WGS84, from the GeoJSON point, six decimals. |
| 11 | `lon` | number | Longitude, WGS84, from the GeoJSON point, six decimals. |

Row order: `install_year`, then `chartype`, then `connectype`, then `evcsid`.

## out/chargers_by_year.csv

Charger installs by year with a running cumulative total. 3 rows.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `install_year` | integer | Install year. |
| 2 | `chargers` | integer | Count of stations installed that year. |
| 3 | `cumulative_chargers` | integer | Running total of stations through that year. |

Row order: `install_year`. Values: 2024 → 10 (cum 10), 2025 → 19 (cum 29),
2026 → 4 (cum 33).

## out/counts_by_chartype.csv

Charger counts by charging level. 2 rows.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `chartype` | text | Charging level (`L2` or `DCFC`). |
| 2 | `chargers` | integer | Count of stations at that level. |

Row order: `chargers` descending, then `chartype`. Values: `L2` 26, `DCFC` 7.

## out/counts_by_connectype.csv

Charger counts by connector type. 3 rows.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `connectype` | text | Connector type. |
| 2 | `chargers` | integer | Count of stations with that connector. |

Row order: `chargers` descending, then `connectype`. Values: `J1772` 26,
`CCSCHADEMO` 6, `CCSNACS` 1.
