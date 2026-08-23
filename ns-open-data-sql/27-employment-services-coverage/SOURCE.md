# Source

**Dataset:** Nova Scotia Works Employment Services Centre Locations

**Portal page:** https://data.novascotia.ca/d/x7cs-y5zd

**Resource CSV:** https://data.novascotia.ca/resource/x7cs-y5zd.csv

**Socrata 4x4 id:** `x7cs-y5zd`

**Licence:** Open Government Licence - Nova Scotia. Attribution: contains information licensed under the Open Government Licence - Nova Scotia.

**Pull date:** 2026-07-25

**Snapshot:** `data/raw/ns_nsworks-centres_2026-07-25.csv`, 47 data rows.

**Catalog idea:** #38.

## How the snapshot was pulled

Socrata caps a default response at 1000 rows, so the pull asks for a larger page and pins the sort:

    https://data.novascotia.ca/resource/x7cs-y5zd.csv?$limit=5000&$order=region,center_name

The whole dataset is 47 rows, so one page returns everything. No app token is needed for a one-off pull. The response is saved verbatim as the dated snapshot above and committed: `run.py` reads that file and never the live endpoint, which is what makes the golden output reproducible.

## Columns in the source

| Column | Meaning |
| --- | --- |
| `region` | Nova Scotia Works service region |
| `center_name` | Name of the service provider organization, not of the individual site |
| `street_address` | Civic address of the site |
| `city_town` | Community the site sits in |
| `postal_code` | Full postal code, first three characters are the FSA |
| `phone` | Public phone number |
| `email` | Public email address |
| `web` | Provider website |
| `x_coordinate` | **Latitude**, despite the name. See the warning below. |
| `y_coordinate` | **Longitude**, despite the name. See the warning below. |
| `location_1` | The same point written `(latitude, longitude)` |
| `location_details` | Free-text site note, blank on 29 of 47 rows |
| `facebook` | Provider Facebook page |
| `twitter` | Provider Twitter account |

## Warning: the coordinate columns are named backwards

Most geographic data puts longitude in x and latitude in y. This dataset does the opposite. `x_coordinate` holds values near 45, which is a Nova Scotia latitude, and `y_coordinate` holds values near -62, which is a Nova Scotia longitude. The source's own `location_1` field settles it: on all 47 rows `location_1` reads exactly `(x_coordinate, y_coordinate)`, and a Socrata location literal is written latitude first.

Read x as longitude and y as latitude, the way the names invite, and every centre plots at about 45 degrees east and 62 degrees south: the Southern Ocean off Antarctica. `sql/02_transform.sql` renames the two columns once, and the exported mart carries them as `latitude` and `longitude` so nothing downstream has to remember the trap.

## Known defect in the source text

One `street_address` value, the Saint Joseph du Moine site, contains `UniversitÃ©` where the source intended `Université`: a character that was encoded twice on the publisher's side. Every other accented value in the file is clean UTF-8. The pipeline passes the value through exactly as published rather than guessing at a repair, and it feeds no measure. See spec.md.
