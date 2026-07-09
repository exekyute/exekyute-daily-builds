# Data dictionary: out/corridor_ranking.csv

One row per highway segment that has at least one valid AADT reading in the snapshot. Ordered by `current_aadt` descending, with `section_id` as the tie-break.

| Column | Type | Units | Meaning |
| --- | --- | --- | --- |
| `aadt_rank` | integer | rank | Position of the segment by its latest AADT, busiest first. Tied AADT values share a rank. |
| `section_id` | text | none | Segment key. Every count in the source belongs to one section id. |
| `highway` | text | none | Provincial highway number the segment sits on (for example 102, 111, 4). |
| `section` | text | none | Section number within the highway. |
| `county` | text | none | Three-letter Nova Scotia county code (for example HFX for Halifax, LUN for Lunenburg). |
| `section_description` | text | none | Plain-language "from ... to ..." label for the segment, taken from its most recent count. |
| `section_length_km` | number | kilometres | Length of the segment, from its most recent count, rounded to two decimals. Blank if the source length is missing. |
| `current_year` | integer | calendar year | Year of the segment's most recent count. |
| `current_aadt` | integer | vehicles per day | Peak reported AADT for the segment in its most recent count year. |
| `prior_year` | integer | calendar year | Year of the segment's previous count. Blank if the segment has only one count. |
| `prior_aadt` | integer | vehicles per day | Peak reported AADT for the segment in its previous count year. Blank if the segment has only one count. |
| `yoy_growth_pct` | number | percent per year | Annualized growth from the previous count to the most recent one, rounded to two decimals. Blank if the segment has only one count. |
| `growth_rank` | integer | rank | Position of the segment among the fastest-growing established corridors (previous AADT at least 5,000 and previous count within three years), fastest first. Blank when the segment is outside that filter. |
| `capacity_threshold` | integer | vehicles per day | The capacity threshold applied to the flag. Constant 10,000 (see spec.md). |
| `over_capacity` | boolean | none | `true` when `current_aadt` is at or above `capacity_threshold`, otherwise `false`. |
