# BI mart: mart_ev.csv

The frozen mart both BI tools read. One row per installed public EV charging
station, 33 rows. Written by the SQL export step and identical to `out/mart_ev.csv`.
Every measure built on this mart is a count of stations, not a sum of ports.

| Column | BI type | Meaning |
| --- | --- | --- |
| `evcsid` | Text | Station id, unique per station (33 distinct). Use `COUNTROWS` or a distinct count of it for a station count. |
| `owner` | Text | Owner. Constant `HRM`. |
| `chartype` | Text | Charging level: `L2` (Level 2) or `DCFC` (DC fast). Colour and grouping field. 2 values. |
| `connectype` | Text | Connector type: `J1772`, `CCSCHADEMO`, `CCSNACS`. 3 values. |
| `power_kw` | Decimal Number | Power rating in kW (6.6, 7, or 175). Size field on the Tableau map. |
| `location` | Text | Address or place description. Several stations can share one location. |
| `access` | Text | Charger access. Constant `PUBLIC`. |
| `install_year` | Whole Number | Install year, 2024 to 2026 (integer index; no date column). Set Summarization to Don't summarize. |
| `quantity` | Whole Number | Available ports at the station (1 or 2). |
| `lat` | Decimal Number | Latitude, WGS84, six decimals. Latitude role in Tableau. |
| `lon` | Decimal Number | Longitude, WGS84, six decimals. Longitude role in Tableau. |

Reference figures (from the SQL golden): 33 stations; cumulative 10 by 2024, 29 by
2025, 33 by 2026; `L2` 26 and `DCFC` 7; `J1772` 26, `CCSCHADEMO` 6, `CCSNACS` 1.
