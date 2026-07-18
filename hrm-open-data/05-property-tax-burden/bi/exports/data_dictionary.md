# Data dictionary: frozen BI marts

Two marts, written by the SQL export step and read by both dashboards. Tableau and Power BI recompute nothing structural: they bind to these frozen cents so a viewer can flip between the two faces and read the same figure to the decimal. All dollar figures are rounded to the cent; rates and shares are fixed six-decimal values; empty `effective_rate` marks a zero taxable base.

## mart_tax_group.csv (wide)

One row per `tax_group`, `tax_summary_group`, `rate_code`, `rate_description`, and `bill_rate_percentage`, 5,383 rows. Ordered by `tax_group`, `rate_code`, `bill_rate_percentage`, `tax_summary_group`. This is the Power BI import and the source of the Tableau effective-rate sheet.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `tax_group` | text | Billing group, prefixed 1 to 5 and suffixed by class and status. |
| 2 | `tax_summary_group` | text | Finer summary bucket within a tax group. |
| 3 | `rate_code` | text | Rate code applied to the line. |
| 4 | `rate_description` | text | Plain-language name of the rate code. |
| 5 | `bill_rate_percentage` | number | Per-line billed rate figure carried by the source. |
| 6 | `account_count` | integer | Billed account lines in this group. |
| 7 | `residential_taxable` | integer | Residential taxable assessment, dollars. |
| 8 | `commercial_taxable` | integer | Commercial taxable assessment, dollars. |
| 9 | `resource_taxable` | integer | Resource taxable assessment, dollars. |
| 10 | `total_taxable` | integer | Columns 7 to 9 summed, dollars. |
| 11 | `bill_amount` | number | Tax billed, dollars and cents. |
| 12 | `bill_value` | number | Billed value base carried by the source, dollars and cents. |
| 13 | `effective_rate` | number | `bill_amount / total_taxable`, six decimals. Empty where `total_taxable` is 0. |

## mart_tax_class.csv (long)

One row per tax group per class that carries a taxable base, 13 rows. Ordered by `tax_group`, `class`. This is the source of the Tableau stacked bar.

| # | Column | Type | Meaning |
| --- | --- | --- | --- |
| 1 | `tax_group` | text | Billing group. |
| 2 | `class` | text | Assessment class: `Residential`, `Commercial`, or `Resource`. |
| 3 | `taxable` | integer | Taxable assessment for the class in the group, dollars. |
| 4 | `share_of_total_taxable` | number | `taxable / municipal total taxable`, six decimals. |

## Totals to check after import

- Power BI, `mart_tax_group`: SUM(`bill_amount`) = **1,001,727,311.03**; SUM(`total_taxable`) = **523,318,932,375**; SUM(`account_count`) = **1,252,942**.
- Tableau, `mart_tax_class`: SUM(`taxable`) = **523,318,932,375**.
