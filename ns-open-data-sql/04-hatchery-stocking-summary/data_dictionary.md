# Data dictionary: out/stocking_summary.csv

One row per county, waterbody, waterbody type, species, and year. The first five
columns are the grouping key and together identify a row.

| Column | Type | Units | Meaning |
| --- | --- | --- | --- |
| `county` | text | | County the waterbody sits in (for example Annapolis, Inverness). |
| `waterbody` | text | | Name of the water stocked (for example MARGAREE). |
| `waterbody_type` | text | | Class of water: Brook, Flowage, Lake, Pond, or River. |
| `species` | text | | Fish species released, trimmed of stray whitespace (for example Brook Trout). |
| `stocking_year` | integer | calendar year | Year of the stocking date, from 1976 to 2025. |
| `stocking_events` | integer | count | Number of stocking records in the group. The effort measure. |
| `fish_released` | integer | fish | Total fish released in the group. |
| `avg_length_cm` | number | centimetres | Average measured length at release, over records that recorded a positive length. Blank when none was measured. |
| `avg_weight_g` | number | grams | Average measured weight at release, over records that recorded a positive weight. Blank when none was measured. |

Notes:

- `avg_length_cm` and `avg_weight_g` are rounded to two decimals.
- A blank average means no record in that group carried a positive measurement;
  it does not mean the fish had zero size.
- `stocking_events` counts records, so an event that released zero fish still
  adds one to the count while adding nothing to `fish_released`.
