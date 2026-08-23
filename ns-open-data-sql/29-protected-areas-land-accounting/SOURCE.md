# Source

- **Dataset:** The Nova Scotia Protected Areas System
- **Portal:** Nova Scotia Open Data, https://data.novascotia.ca
- **Dataset page:** https://data.novascotia.ca/d/ticv-5du5
- **Socrata resource endpoint:** https://data.novascotia.ca/resource/ticv-5du5.csv
- **Socrata 4x4 id:** `ticv-5du5`
- **Licence:** Open Government Licence - Nova Scotia (attribution required), https://novascotia.ca/opendata/licence.asp
- **Pull date:** 2026-07-25
- **Snapshot:** `data/raw/ns_protected-areas_2026-07-25.csv`, 1,161 rows plus header
- **Catalog idea:** #44

## The exact pull

```
https://data.novascotia.ca/resource/ticv-5du5.csv?$select=objectid,pro_name,protect1,protect2,owner,authority,status,stat_date,lgl_effect,ha_gis,shape_leng,shape_area&$order=objectid&$limit=5000
```

The `$select` is doing real work, not tidying. The layer's first column is
`the_geom`, a MULTIPOLYGON with thousands of coordinate pairs per row; a plain
`.csv` pull of the whole layer returns tens of megabytes of geometry that this
build never reads. Naming the twelve attribute columns keeps the snapshot at
246 KB. `$order=objectid` fixes row order at the server, and `$limit=5000`
clears the 1,161 rows in one request with room to spare.

## What came back

Six of the twelve requested columns are empty in every row of the current
publication: `protect2`, `stat_date`, `lgl_effect`, `reference`, `created_da`,
and `last_edi00`. That is not a pull artifact. Asking the server to count them
returns zero:

```
https://data.novascotia.ca/resource/ticv-5du5.json?$select=count(stat_date)
```

`stat_date` is the layer's designation year, and it is the column a time series
would need. See spec.md for how the pipeline handles that and what it means for
the BI guide. The columns are still named in the `$select` and still land in the
raw table, so a future republication that refills them needs no code change.

The snapshot is committed so the pipeline and its golden output stay
reproducible after the live layer moves. Re-pulling on a later date means
re-baselining `expected/protected_areas.csv` on purpose.
