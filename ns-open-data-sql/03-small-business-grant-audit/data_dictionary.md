# Data dictionary: out/grants_by_type_year.csv

One row per business type per year, computed on grant recipients. Sorted by year, then most recipients first, then business type.

| Column | Type | Meaning | Units |
| --- | --- | --- | --- |
| `year` | text | Program year the grants were awarded, as published in the source. Every row in this snapshot is 2020. | year |
| `type_of_business` | text | Business classification as published in the source (for example, Restaurant with onsite dining). 14 distinct values. | category |
| `recipients` | integer | Number of recipient records of this business type in this year. A recipient is a record that received at least one of the two grants. Sums across all rows to the snapshot row count. | records |
| `sbig_recipients` | integer | Of those recipients, how many received the Small Business Impact Grant (SBIG). | records |
| `sbrsg_recipients` | integer | Of those recipients, how many received the Small Business Reopening and Support Grant (SBRSG). A record can be counted in both grant columns if it received both. | records |
| `pct_of_recipients` | decimal | This type's `recipients` as a percentage of all recipients across every type and year, rounded to two decimals. The concentration measure. | percent |

## Notes

- There is no dollar column in the source, so every measure here is a count of recipient records, not an amount paid.
- `sbig_recipients` and `sbrsg_recipients` overlap: a record that received both grants adds to both. They are not meant to sum to `recipients`.
- `pct_of_recipients` values across all rows add to about 100, off only by rounding.
