# Source

**Dataset:** HRM Tax Bill Info

**Portal page:** https://data-hrm.hub.arcgis.com/datasets/HRM::hrm-tax-bill-info

**Slug:** `HRM::hrm-tax-bill-info`

**ArcGIS item id:** `9038021815304894942498be25a315e7`

**Service:** `HRM_Tax_Bill_Info`

**FeatureServer query endpoint:**
`https://services2.arcgis.com/11XBiaBYA9Ep0yNJ/arcgis/rest/services/HRM_Tax_Bill_Info/FeatureServer/0/query`

**Licence:** Open Government Licence, Halifax. Attribution: Contains information licenced under the Open Government Licence, Halifax. Licence text: https://data-hrm.hub.arcgis.com/pages/open-data-licence

**Pull date:** 2026-07-09

**Snapshot:** `data/raw/hrm_tax-bill-info_2026-07-09.csv`, 5,383 rows. This is the compact server-side grouped result, not the raw table.

## Why a grouped pull, not the raw download

The raw table is **1,252,942 rows**, every one for `TAX_YEAR` 2024 (confirmed with `where=1=1&returnCountOnly=true` and a `TAX_YEAR` group-by, both returning 1,252,942). One row is one account's billed line at one rate. That is too large to download or commit, so the snapshot is pulled with **server-side aggregation**: the FeatureServer sums the money and counts the account lines, grouped by the five descriptive fields, and returns only the grouped rows. The account-line count over the grouped result is 1,252,942, so the grouped pull covers the whole table with nothing dropped.

## Exact query (reproducible)

The layer's `maxRecordCount` is 2000 and the grouped result is 5,383 rows, so the pull is paged with `resultOffset` in three requests (offsets 0, 2000, 4000) at `resultRecordCount=2000`. Every request is a GET to the query endpoint above with these parameters:

    where=1=1
    groupByFieldsForStatistics=TAX_GROUP,TAX_SUMMARY_GROUP,RATE_CODE,RATE_DESCRIPTION,BILL_RATE_PERCENTAGE
    orderByFields=TAX_GROUP,TAX_SUMMARY_GROUP,RATE_CODE,RATE_DESCRIPTION,BILL_RATE_PERCENTAGE
    resultOffset=0            (then 2000, then 4000)
    resultRecordCount=2000
    f=json
    outStatistics=<the JSON below, URL-encoded>

`outStatistics` (verbatim):

    [
      {"statisticType":"count","onStatisticField":"ASSESSMENT_ACCOUNT_NUMBER","outStatisticFieldName":"account_count"},
      {"statisticType":"sum","onStatisticField":"RESIDENTIAL_TAXABLE","outStatisticFieldName":"residential_taxable"},
      {"statisticType":"sum","onStatisticField":"COMMERICAL_TAXABLE","outStatisticFieldName":"commercial_taxable"},
      {"statisticType":"sum","onStatisticField":"RESOURCE_TAXABLE","outStatisticFieldName":"resource_taxable"},
      {"statisticType":"sum","onStatisticField":"BILL_VALUE","outStatisticFieldName":"bill_value"},
      {"statisticType":"sum","onStatisticField":"BILL_AMOUNT","outStatisticFieldName":"bill_amount"}
    ]

Note the source's own spelling `COMMERICAL_TAXABLE`. The grouped rows across the three pages are concatenated, taxable-class nulls (a class that does not apply to a line) are written as 0, and the result is sorted by the five group fields and saved as the dated snapshot. No app token or sign-in is needed for the public read. `run.py` reads that committed snapshot, never the live endpoint, so the build reproduces byte for byte on any future day.

## Fields in the grouped snapshot

| Column | Source field | Meaning |
| --- | --- | --- |
| `tax_group` | TAX_GROUP | Billing group, prefixed 1 to 5 (Municipal, Provincial, Area Rates, Private Roads, Business Improvement Districts) and suffixed by class and status. |
| `tax_summary_group` | TAX_SUMMARY_GROUP | Finer summary bucket within a tax group. |
| `rate_code` | RATE_CODE | Rate code applied to the line. |
| `rate_description` | RATE_DESCRIPTION | Plain-language name of the rate code (one-to-one with `rate_code`). |
| `bill_rate_percentage` | BILL_RATE_PERCENTAGE | Per-line billed rate figure carried by the source. |
| `account_count` | count of ASSESSMENT_ACCOUNT_NUMBER | Number of billed account lines in the group. An account recurs across rate codes, so this counts lines, not distinct properties. |
| `residential_taxable` | sum of RESIDENTIAL_TAXABLE | Residential taxable assessment, dollars. |
| `commercial_taxable` | sum of COMMERICAL_TAXABLE | Commercial taxable assessment, dollars. |
| `resource_taxable` | sum of RESOURCE_TAXABLE | Resource taxable assessment, dollars. |
| `bill_value` | sum of BILL_VALUE | Billed value base carried by the source, dollars. |
| `bill_amount` | sum of BILL_AMOUNT | Billed tax amount, dollars and cents. |

## Caveats

- This set is for the single year 2024. HRM Tax Bill Info has an archived companion; this snapshot is the current live layer.
- `BILL_AMOUNT` and `BILL_VALUE` arrive as floating-point sums with trailing noise (for example `4025507.6400000085`). The SQL rounds each group's billed dollars to the cent once, in `02_transform.sql`, so every downstream total is a sum of clean cents and ties exactly.
