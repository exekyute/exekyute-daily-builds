# BI marts

Two frozen marts the Tableau build reads. Both are written by the SQL export step
and are identical to their twins in `out/`. The map layers both bind to the `lat`
and `lon` these marts carry; Halifax place names are not a built-in Tableau
geographic role.

## mart_stops.csv

One row per bus stop, 2348 rows. The primary map layer.

| Column | BI type | Meaning |
| --- | --- | --- |
| `busstopid` | Text | Stop id, unique per stop (2348 distinct). Use a distinct count for a stop count. |
| `stopnumber` | Text | Public stop number. |
| `location` | Text | Address or place description. Good for the map tooltip. |
| `accessible` | Whole Number | 1 when the stop is coded Accessible, else 0. A 0/1 flag; sum it for the accessible count. |
| `status` | Text | Stop status: `INS` (In Service) or `TMP` (Temporary). |
| `has_shelter` | Whole Number | 1 when the stop has a shelter, else 0. The colour split on the map. Sum it for the covered-stop count. |
| `lat` | Decimal Number | Latitude, WGS84, six decimals. Latitude role in Tableau. |
| `lon` | Decimal Number | Longitude, WGS84, six decimals. Longitude role in Tableau. |

## mart_parkride.csv

One row per park and ride lot, 15 rows. The second map layer.

| Column | BI type | Meaning |
| --- | --- | --- |
| `name` | Text | Lot name, unique per lot (15 distinct). Label on the map. |
| `capacity` | Whole Number | Posted parking capacity, in spaces. Size on the map. |
| `routes` | Text | Routes the lot serves, as published. Tooltip. |
| `lat` | Decimal Number | Latitude of the lot centroid, WGS84, six decimals. |
| `lon` | Decimal Number | Longitude of the lot centroid, WGS84, six decimals. |

Reference figures (from the SQL golden, `expected/access_summary.csv`): 2348 bus
stops; 1711 accessible (72.9 percent); 521 shelter records over 454 stops with a
shelter (shelter coverage 19.3 percent); 15 park and ride lots totalling 2444
spaces.
