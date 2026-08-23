# Spec: employment-services coverage

## Purpose

Turn the province's list of Nova Scotia Works employment services centres into a coverage picture: how many centres each region and town holds, which postal areas they reach, and how completely each centre publishes its contact details. Every figure is deterministic and re-derivable from the committed snapshot.

## Inputs

One file: `data/raw/ns_nsworks-centres_2026-07-25.csv`, a pinned snapshot of Socrata dataset `x7cs-y5zd` (see SOURCE.md). 47 rows, one per centre. Columns: region, center_name, street_address, city_town, postal_code, phone, email, web, x_coordinate, y_coordinate, location_1, location_details, facebook, twitter.

Two things about the shape of this file are worth stating before any rule:

- **`center_name` is the provider, not the site.** Sixteen organizations run the 47 centres, so the name repeats. The YMCA of Greater Halifax/Dartmouth alone runs nine. Region plus centre name is therefore not unique, and neither is region plus centre name plus town: one provider runs two sites in Sydney. What is unique across all 47 rows is region, centre name, town, and street address together, and that is the sort key the mart export uses.
- **There is no county column.** The dataset carries region and city_town and nothing between them, and no town-to-county mapping ships with it, so county does not appear anywhere in this build.

## The reversed-coordinate trap

In this dataset the column named `x_coordinate` holds **latitude** and the column named `y_coordinate` holds **longitude**. That is the reverse of the usual convention and the reverse of the other Nova Scotia geographic datasets in this series. The source's own `location_1` field is the evidence: on all 47 rows it reads exactly `(x_coordinate, y_coordinate)`, and a Socrata location literal is written latitude first. The observed ranges agree, 43.53 to 46.69 in `x_coordinate` and -66.12 to -59.97 in `y_coordinate`.

`sql/02_transform.sql` does the rename once, at the only point where the source column names are still visible:

    try_cast(trim(r.x_coordinate) AS DOUBLE) AS latitude,
    try_cast(trim(r.y_coordinate) AS DOUBLE) AS longitude

Every table, export, and document after that point uses `latitude` and `longitude` by those names. `bi/exports/mart_services.csv` carries the corrected names, which is why the Tableau guide can say "give `latitude` the Latitude geographic role" without a caveat attached.

## The declared region universe

`REGION_UNIVERSE`, declared in `sql/00_schema.sql` as the constant table `const_region_universe`, holds five labels: Annapolis Valley, Cape Breton, HRM, Northern, South Shore. `region_coverage` left joins from that constant onto the observed centres, so a declared region holding zero centres materializes as a row reading `centres = 0` instead of disappearing from the result the way a `GROUP BY` would let it.

**Where the list comes from.** It is transcribed from the region labels the publisher uses in this snapshot and then frozen into SQL. It is not derived at run time, but neither is it corroborated by an independent Nova Scotia Works region registry: the department's own site did not yield a machine-readable region list on the pull date, and the Socrata metadata for the dataset carries no description or value domain for the `region` column. So the universe is a declaration, and it is worth being precise about what that declaration catches.

- A region that disappears from a later snapshot gets caught, and is reported as a zero-centre row.
- A region label that appears in a later snapshot without being declared gets caught too, counted under the `region_not_in_universe` exclusion class.
- A sixth Nova Scotia Works region that the dataset has never published does not get caught. If one exists and has never appeared in the data, this build has no way to see it.

On this snapshot the gap count is 0 of 5, so the measure is a drift guard rather than a finding about unserved territory.

## The FSA derivation

An FSA, a forward sortation area, is the **first three characters** of a Canadian postal code, uppercased: `B3J`, not `B`. The rule uses the named constants `fsa_length = 3` and `fsa_pattern = '^[A-Z][0-9][A-Z]$'` from `const_rules`:

    upper(substr(trim(postal_code), 1, 3))

A blank postal code yields a NULL FSA and is counted under `postal_code_blank`. A non-blank postal code whose first three characters fail the letter-digit-letter pattern is counted under `postal_code_malformed` and keeps whatever three characters it has, so its row still appears in the FSA section rather than being dropped. On this snapshot both counts are 0: all 47 postal codes are present, seven characters long, and well formed, and they resolve to 32 distinct FSAs.

## Contact-channel completeness

`CONTACT_CHANNELS`, the constant table `const_contact_channel`, declares the four public channels in report order: email, web, facebook, twitter. A centre carries a channel when the field holds a non-blank value. That means published, not verified: the pipeline does not dial the number or open the URL, so a dead link still counts as carried. The completeness table is driven by the declared list, so a channel that no centre published would still report as a zero row.

## No population source

This build carries no population data, so it computes no residents-per-centre or per-capita measure of any kind; centre counts are counts, not access rates.

## Outputs

- `out/services_coverage.csv`, diffed against `expected/services_coverage.csv`. Six sections in one table: `summary`, `exclusions`, `region_coverage`, `city_coverage`, `fsa_coverage`, `contact_completeness`. 97 rows.
- `out/mart_services.csv`, copied to `bi/exports/mart_services.csv`: one row per centre, 47 rows, with corrected latitude and longitude for the Tableau face.
- `dashboard/data.js`, the same 47 mart rows re-emitted as a `const DATA = [...]` literal so the browser dashboard opens under `file://` with no server. It holds no logic and no computed figures.

The headline the golden output carries, and the numbers the dashboard and the Tableau viz must both reproduce:

| Measure | Value |
| --- | --- |
| Centres | 47 |
| Declared regions / regions with centres | 5 / 5 |
| Regions with zero centres | 0 |
| Towns | 42 |
| FSAs | 32 |
| Service providers | 16 |
| Busiest region | Cape Breton, 12 centres, 25.53% |
| Busiest town | Halifax, 3 centres |
| Busiest FSA | B0E, 5 centres across 5 towns, 10.64% |
| Email / web / Facebook published | 47 each, 100.00% |
| Twitter published | 36, 76.60% |
| Centres publishing all four channels | 36 |

The centre counts in `region_coverage`, `city_coverage`, and `fsa_coverage` each re-sum to 47 independently.

## Edge cases

- **The top of the region ranking is a tie.** Cape Breton and HRM both hold 12 centres. Every ranking in this build breaks ties on a name, so Cape Breton takes rank 1 by alphabetical order and not by scan order. Anything that ranks these regions by count alone, including a chart's default sort, may legitimately show HRM first; that is a presentation difference, not a disagreement about the data.
- **One provider, many sites.** Because `center_name` is the organization, counting distinct centre names gives 16, not 47. The two are reported as separate measures rather than being conflated.
- **A town belongs to one region.** No town in this snapshot appears under more than one region label, so `city_coverage` carries region as a plain column. If a later snapshot split a town across regions, that town would appear as two rows, one per region, and the section total would still be 47.
- **FSAs cross towns and providers.** B0E covers five centres in five different towns, and B0W covers four. FSA rows therefore carry a town count and no region, since an FSA is not guaranteed to sit inside one region.
- **`location_details` is blank on 29 of 47 rows.** The column is a free-text site note that feeds no measure, so it is not carried into the mart and is not counted as an exclusion.
- **One double-encoded character in the source.** The Saint Joseph du Moine street address reads `UniversitÃ©` where the publisher intended `Université`. Every other accented value in the file is clean UTF-8. The value passes through verbatim: repairing it would mean guessing at the publisher's intent, the field feeds no measure, and a silent repair is exactly the kind of undeclared edit this series avoids. It is recorded here and in SOURCE.md instead.

## Exclusion classes

No row is ever dropped. Each class below counts the rows a less careful build would have lost, and every class is reported even at zero.

| Class | Count on this snapshot |
| --- | --- |
| `region_not_in_universe` | 0 |
| `postal_code_blank` | 0 |
| `postal_code_malformed` | 0 |
| `coordinate_out_of_bounds` | 0 |

`coordinate_out_of_bounds` checks each point against the declared Nova Scotia window in `const_rules`, latitude 43.0 to 47.5 and longitude -67.0 to -59.0. It is the check that would have fired loudly had the latitude and longitude columns been read in the order their names suggest.

## Determinism

Every result query ends in a total `ORDER BY` whose last term is unique, so row order is reproducible regardless of engine version or machine. Ranks come from `ROW_NUMBER` over an ordering that already ends in a unique tie-breaker, never from a sort on the measure alone, which matters here because the top of the region ranking is a genuine tie:

- `region_coverage`: centres descending, then region name.
- `city_coverage`: centres descending, then region, then town.
- `fsa_coverage`: centres descending, then FSA.
- `contact_completeness`: the declared channel order.
- `mart_services`: region, centre name, town, street address. Unique across all 47 rows, as noted above.

Shares are computed as an exact division and then cast to `DECIMAL(6,2)`, so `100.00` writes with both decimals and the file is byte-stable run to run. The snapshot is pinned and committed; replacing it means re-baselining `expected/services_coverage.csv` deliberately.
