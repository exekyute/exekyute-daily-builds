-- 01_load: read the pinned snapshot, never the live endpoint.

COPY solar_raw
FROM 'data/raw/ns_solarhomes_2026-07-06.csv' (FORMAT CSV, HEADER);
