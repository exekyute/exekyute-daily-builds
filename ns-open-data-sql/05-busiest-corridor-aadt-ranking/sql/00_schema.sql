-- 00_schema.sql
-- Sets up the landing table for the raw snapshot. Every column lands as text so
-- that cleaning and casting happen in one place, in 02_transform.sql.
-- Question answered: what shape does the raw Traffic Volumes snapshot take?

CREATE OR REPLACE TABLE raw_counts (
    section_id           VARCHAR,  -- segment key (highway number joined to section number)
    highway              VARCHAR,  -- provincial highway number
    section              VARCHAR,  -- section number within the highway
    section_length       VARCHAR,  -- length of the section in kilometres
    section_description  VARCHAR,  -- plain-language "from ... to ..." label for the section
    count_date           VARCHAR,  -- date of the count; only the year is used here
    description          VARCHAR,  -- location note for the individual count
    grp                  VARCHAR,  -- count group code
    type                 VARCHAR,  -- count type code (TC, VC, SA, and so on)
    county               VARCHAR,  -- three-letter county code
    ptrucks              VARCHAR,  -- percent trucks
    adt                  VARCHAR,  -- average daily traffic
    aadt                 VARCHAR,  -- annual average daily traffic (the metric this project ranks)
    direction            VARCHAR,  -- travel direction of the count, where recorded
    pct85                VARCHAR,  -- 85th percentile speed
    priority_points      VARCHAR   -- provincial priority points
);
