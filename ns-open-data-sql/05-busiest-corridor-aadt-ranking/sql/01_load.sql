-- 01_load.sql
-- Loads the pinned CSV snapshot into raw_counts. The file name carries the pull
-- date, so the input is fixed and the run reproduces.
-- Question answered: what raw rows are we working from?

INSERT INTO raw_counts
SELECT
    "section_id",
    "highway",
    "section",
    "section_length",
    "section_description",
    "date",
    "description",
    "group",
    "type",
    "county",
    "ptrucks",
    "adt",
    "aadt",
    "direction",
    "_85pct",
    "priority_points"
FROM read_csv(
    'data/raw/ns_traffic-volumes_2026-07-05.csv',
    header = true,
    all_varchar = true
);
