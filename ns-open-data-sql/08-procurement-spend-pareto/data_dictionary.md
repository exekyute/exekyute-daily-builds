# Data dictionary: out/vendor_pareto.csv

One row per vendor, ordered by `vendor_rank`. Money is in Canadian dollars, to the cent. Shares are percentages of all award dollars in the cleaned data.

| Column | Type | Meaning |
| --- | --- | --- |
| `vendor_rank` | integer | Rank of the vendor by total award dollars, largest first (1 is the biggest). Ties are broken by `vendor_key` so the rank is stable. |
| `vendor_display` | text | Human-readable vendor name: the raw spelling that carried the most dollars under this vendor's key. |
| `vendor_key` | text | Normalized vendor name used to group awards: uppercased, punctuation removed, and trailing corporate-suffix words stripped. Spelling and legal-form variants share one key. |
| `award_count` | integer | Number of awards summed into this vendor (each a retained row from the source). More than one means a repeat vendor. |
| `total_awarded` | decimal(18,2) | Total award dollars for this vendor, in CAD, to the cent. |
| `pct_of_total` | decimal(7,4) | This vendor's share of all award dollars, as a percentage (0 to 100). |
| `cumulative_awarded` | decimal(18,2) | Running total of award dollars for this vendor and every vendor ranked above it, in CAD, to the cent. |
| `cumulative_pct` | decimal(7,4) | Running share of all award dollars through this vendor, as a percentage (0 to 100). |
| `reaches_80pct_set` | boolean | True when this vendor is in the smallest top set whose cumulative share reaches 80 percent. The vendor that crosses 80 percent is included; vendors past it are false. |
| `is_repeat_vendor` | boolean | True when `award_count` is greater than one. |
