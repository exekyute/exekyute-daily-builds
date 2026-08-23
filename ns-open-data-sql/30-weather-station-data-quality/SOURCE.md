# Source

- **Dataset:** NS Weather Station Data
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/d/kafq-j9u4
- **Socrata resource endpoint:** https://data.novascotia.ca/resource/kafq-j9u4.csv
- **Socrata 4x4 id:** `kafq-j9u4`
- **Licence:** Open Government Licence - Nova Scotia (attribution required)
- **Pull date:** 2026-07-25
- **Snapshot:** `data/raw/ns_weather-station_2026-07-25.csv`, 234,835 rows plus header, 11.8 MiB
- **Catalog idea:** #24

The dataset is the province's road weather information system: fixed stations that Public Works runs beside highways to watch pavement and surface conditions. It is not a general climate network, and the `site_id` codes (`RNSAM`, `RNSCB`, and so on) are road weather sites, not Environment Canada climate stations.

## Narrowing decision

The full table holds 31,803,768 rows, so the audit had to be scoped before anything was paged. The sizing step ran first:

```
https://data.novascotia.ca/resource/kafq-j9u4.json?$select=count(*)
  -> 31803768

https://data.novascotia.ca/resource/kafq-j9u4.json
  ?$select=count(*)
  &$where=datetimeutc >= '2024-01-01T00:00:00' AND datetimeutc < '2024-02-01T00:00:00'
  -> 522003
```

**Precedence branch taken: (b), the first two weeks of a calendar month.** January 2024 is the month a road weather audit wants, because that is when the network is doing the job it exists for. The whole month is 522,003 rows, which at the measured row width of roughly 53 bytes lands near 27 MB and clears the 25 MB snapshot ceiling. Cutting to the first fourteen days brings it to 234,835 rows and 11.8 MiB, comfortably inside. No station filter was needed, so branch (c) never came up: all 46 stations that reported in the window are in the snapshot.

## Window boundaries

| Bound | Value |
| --- | --- |
| Start, inclusive | `2024-01-01T00:00:00` UTC |
| End, exclusive | `2024-01-15T00:00:00` UTC |
| Whole UTC days | 14 |
| Stations | 46 |

Both bounds are literal `DATE` constants in `sql/00_schema.sql`. Nothing in the pipeline reads the clock.

## The exact pull query

Paged at 50,000 rows with a stable sort key. Paging a 234,835-row window without `$order` lets Socrata return rows in a different order per page, which duplicates some rows and drops others. A completeness audit built on that would report gaps that are artifacts of the download, so the order key is not optional here.

```
https://data.novascotia.ca/resource/kafq-j9u4.csv
  ?$select=site_id,datetimeutc,air_temperature,relative_humidity,avg_wind_speed
  &$where=datetimeutc >= '2024-01-01T00:00:00' AND datetimeutc < '2024-01-15T00:00:00'
  &$order=site_id,datetimeutc
  &$limit=50000
  &$offset=0        (then 50000, 100000, 150000, 200000, 250000)
```

Pages returned 50,000 / 50,000 / 50,000 / 50,000 / 34,835 / 0. The final empty page confirms the snapshot is the whole window, and the total matches the sizing count for the same `$where` exactly.

The five selected columns are the ones the audit needs. The table carries around forty more, most of them empty for most stations.

The snapshot is committed so the pipeline and its golden output stay reproducible after the live dataset moves. Re-pulling on a later date means re-baselining `expected/station_quality.csv` on purpose.
