-- 01_load: read the committed snapshot into the text landing table.
-- The path is relative to the project folder; run.py sets that as the working
-- directory before it runs any SQL.
--
-- The location column carries embedded newlines inside its quotes, so the CSV
-- reader has to honour quoting. It does, and nothing here parses that column.

COPY ltc_raw
FROM 'data/raw/ns_ltc-facilities_2026-07-25.csv'
    (FORMAT CSV, HEADER TRUE, QUOTE '"', ESCAPE '"');
