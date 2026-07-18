# Data dictionary: golden results

Three golden tables under `out/` (verified against `expected/`). All dollar figures are rounded to the cent; all rates and shares are stored as fixed six-decimal values. Empty cells mark a rate that is undefined against a zero taxable base.

## out/tax_group_summary.csv

One row per tax group, all 28. Ordered by `bill_amount` descending, then `tax_group`.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `tax_group` | text | Billing group, prefixed 1 to 5 and suffixed by class and status. | category |
| 2 | `account_count` | integer | Billed account lines in the group. Counts lines, not distinct properties. | count |
| 3 | `residential_taxable` | integer | Residential taxable assessment. | dollars |
| 4 | `commercial_taxable` | integer | Commercial taxable assessment. | dollars |
| 5 | `resource_taxable` | integer | Resource taxable assessment. | dollars |
| 6 | `total_taxable` | integer | Columns 3 to 5 summed. | dollars |
| 7 | `bill_value` | number | Billed value base carried by the source, summed. | dollars.cents |
| 8 | `bill_amount` | number | Tax billed for the group. | dollars.cents |
| 9 | `effective_rate` | number | `bill_amount / total_taxable`, six decimals. Empty where `total_taxable` is 0. | rate |
| 10 | `bill_share` | number | `bill_amount / municipal total bill`, six decimals. | share (0 to 1) |
| 11 | `bill_rank` | integer | Rank of the group by `bill_amount`, largest first. | rank (1 = top) |

## out/taxable_by_class.csv

One row per tax group per class that carries a taxable base, 13 rows. Ordered by `tax_group`, then `class`. Same content as `bi/exports/mart_tax_class.csv`.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `tax_group` | text | Billing group. | category |
| 2 | `class` | text | Assessment class: `Residential`, `Commercial`, or `Resource`. | category |
| 3 | `taxable` | integer | Taxable assessment for the class in the group. | dollars |
| 4 | `share_of_total_taxable` | number | `taxable / municipal total taxable`, six decimals. | share (0 to 1) |

## out/rate_effective.csv

One row per rate code, all 72. Ordered by `effective_rate` descending (empty rates last), then `rate_code`.

| # | Column | Type | Meaning | Units |
| --- | --- | --- | --- | --- |
| 1 | `rate_code` | text | Rate code. | code |
| 2 | `rate_description` | text | Plain-language name of the rate code. | text |
| 3 | `account_count` | integer | Billed account lines that carry this rate code. | count |
| 4 | `total_taxable` | integer | Taxable assessment billed at this rate code, across all tax groups. | dollars |
| 5 | `bill_amount` | number | Tax billed at this rate code, across all tax groups. | dollars.cents |
| 6 | `effective_rate` | number | `bill_amount / total_taxable`, six decimals. Empty where `total_taxable` is 0. | rate |

## Notes

- `effective_rate` is the realized rate of billed dollars against taxable assessment. It differs from the source's `bill_rate_percentage` because of caps, exemptions, and the billing base, which is exactly what makes it worth computing.
- The three `bill_amount` totals (by tax group, by rate code, and over the wide mart) all sum to $1,001,727,311.03. The taxable totals all sum to $523,318,932,375.
