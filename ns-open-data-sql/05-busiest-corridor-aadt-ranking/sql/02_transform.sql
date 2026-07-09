-- 02_transform.sql
-- Reshapes the raw counts into one AADT figure per segment per year, plus a stable
-- set of descriptive attributes for each segment.

-- Question answered: what is each segment's peak reported AADT in each year it was counted?
-- A section can hold several count rows in the same year (one per direction, or one
-- per count station). Taking the maximum gives the single busiest reported daily
-- volume on that segment that year, which stays comparable from year to year even as
-- the number of count rows changes. Rows without a numeric AADT (station-only rows,
-- blanks) drop out here.
CREATE OR REPLACE TABLE segment_year AS
SELECT
    section_id,
    CAST(count_date[1:4] AS INTEGER)  AS yr,
    MAX(TRY_CAST(aadt AS INTEGER))    AS aadt
FROM raw_counts
WHERE TRY_CAST(aadt AS INTEGER) IS NOT NULL
GROUP BY section_id, CAST(count_date[1:4] AS INTEGER);

-- Question answered: what are the descriptive details for each segment?
-- Highway and section are fixed per segment; the description and length come from the
-- most recent count so the labels line up with the latest ranking. The tie-break on
-- description keeps the pick deterministic when a segment has more than one count in
-- its latest year.
CREATE OR REPLACE TABLE segment_attr AS
WITH ranked AS (
    SELECT
        section_id,
        highway,
        section,
        county,
        section_description,
        round(TRY_CAST(section_length AS DOUBLE), 2) AS section_length_km,
        row_number() OVER (
            PARTITION BY section_id
            ORDER BY CAST(count_date[1:4] AS INTEGER) DESC, description
        ) AS rn
    FROM raw_counts
    WHERE TRY_CAST(aadt AS INTEGER) IS NOT NULL
)
SELECT section_id, highway, section, county, section_description, section_length_km
FROM ranked
WHERE rn = 1;
