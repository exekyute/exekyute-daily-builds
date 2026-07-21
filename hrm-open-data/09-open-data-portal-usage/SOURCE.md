# Source

**Dataset:** Open Data Analytics

**Portal page:** https://data-hrm.hub.arcgis.com/datasets/HRM::open-data-analytics

**Hub slug:** `HRM::open-data-analytics`

**Item id:** `f88dc9dab9bb4c59bc277f3676f89724`

**Service name:** `Open_Data_Analytics`

**CSV download (full layer):**
https://data-hrm.hub.arcgis.com/api/download/v1/items/f88dc9dab9bb4c59bc277f3676f89724/csv?layers=0

**ArcGIS REST query endpoint:**
https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/Open_Data_Analytics/FeatureServer/0/query

**Licence:** Open Government Licence, Halifax. Attribution: Contains information licenced under the Open Government Licence, Halifax.

**Pull date:** 2026-07-13

**Snapshot:** `data/raw/hrm_open-data-analytics_2026-07-13.csv`, 14,102 rows, one row per dataset and month (see the aggregation below). This is not the raw layer; it is a compact roll-up committed as the reproducibility anchor. `run.py` reads that file, never the live endpoint.

## This is a big-data source; the raw rows are not committed

The live layer is a Table (no geometry) of **639,108 rows**, one row per dataset per usage-stamp date. Confirmed live on the pull date against the FeatureServer:

    .../FeatureServer/0/query?where=1=1&returnCountOnly=true&f=json
      -> {"count": 639108}

    .../FeatureServer/0/query?where=1=1&f=json
      &outStatistics=[
        {"statisticType":"min","onStatisticField":"Date","outStatisticFieldName":"min_date"},
        {"statisticType":"max","onStatisticField":"Date","outStatisticFieldName":"max_date"},
        {"statisticType":"sum","onStatisticField":"Usage","outStatisticFieldName":"total_usage"}]
      -> min_date 2014-04-01, max_date 2025-10-18, total_usage 555050254

The fields, read from `.../FeatureServer/0?f=json`, are: `Dataset` (the dataset name, inline, so no join to any catalogue is needed), `OD_ID`, `Date`, `Usage` (integer hit count), `SOURCE`, `LAST_UPDATED`. The dataset name being carried inline is why the Open Data Catalogue layer is not needed for this build.

At 639,108 rows the raw layer is too large to commit. It was pulled once to a working file and rolled up to a compact `(dataset, month_start, usage)` grain, and only that roll-up is committed. The steps below reproduce the snapshot from the endpoint on any future day.

## How the snapshot was pulled and aggregated

1. Request the full-layer CSV export. The download endpoint above is asynchronous: the first request returns a JSON `ExportingData` status, and the CSV streams once the export finishes (a few polite retries). The exported file carries the same 639,108 rows. In the CSV export the `Date` field renders as a US-format string, for example `1/6/2015 12:00:00 AM`, where the REST `f=json` view returns the same instant as epoch milliseconds.

2. Roll the raw rows up to one row per dataset and month with DuckDB, summing `Usage`. This is the verbatim aggregation used to write the committed snapshot:

        CREATE TABLE agg AS
          SELECT
            trim(Dataset) AS dataset,
            CAST(date_trunc('month',
              strptime(Date, '%-m/%-d/%Y %I:%M:%S %p')::DATE) AS DATE) AS month_start,
            SUM(CAST(Usage AS BIGINT)) AS usage
          FROM read_csv('<downloaded full csv>', header = true, all_varchar = true)
          WHERE Dataset IS NOT NULL AND trim(Dataset) <> ''
          GROUP BY 1, 2;

        COPY (
          SELECT dataset, month_start, usage
          FROM agg
          ORDER BY dataset, month_start
        ) TO 'data/raw/hrm_open-data-analytics_2026-07-13.csv' (HEADER, DELIMITER ',');

   The roll-up is a faithful sum: it keeps every dataset-month, including months with a zero usage total, and its `SUM(usage)` equals the live `555050254` exactly. The analytical decision to keep only months a dataset actually drew usage (`usage > 0`) is made later, in `sql/02_transform.sql`, not in the snapshot. The roll-up reduces 639,108 raw rows to 14,102 committed rows across 237 datasets and the months 2014-04 to 2025-10.

## Columns in the source layer

| Column | Meaning |
| --- | --- |
| `Dataset` | Name of the open-data item the usage was recorded against |
| `OD_ID` | Internal open-data item id |
| `Date` | Date the usage was stamped (epoch ms in REST, US date string in the CSV export) |
| `Usage` | Recorded hit count for that dataset on that date |
| `SOURCE` | Access channel, for example `ARCGIS` |
| `LAST_UPDATED` | When the analytics record was last refreshed |

## Columns in the committed snapshot

| Column | Meaning |
| --- | --- |
| `dataset` | Dataset name, trimmed |
| `month_start` | First day of the month the usage falls in, `YYYY-MM-DD` |
| `usage` | Sum of `Usage` for that dataset in that month |
