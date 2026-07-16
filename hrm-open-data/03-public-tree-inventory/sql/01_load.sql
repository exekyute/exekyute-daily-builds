-- 01_load: read the pinned dated snapshot, never the live endpoint. The pull
-- that produced this file, with its exact query, is recorded in SOURCE.md.

COPY trees_raw
FROM 'data/raw/hrm_public-trees_2026-07-09.csv' (FORMAT CSV, HEADER, NULLSTR '');
