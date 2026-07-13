-- 02_transform.sql
-- Question this step answers: what does one clean, typed row per permit look
-- like, and what is the pinned pull-date constant every later step reads?
-- Cast the text columns to their real types, derive the issue year and month
-- from the issuance date, and keep one row per source permit record. The source
-- carries 18,316 records; a permit number can repeat (16,030 are distinct), so
-- source_object_id is kept as the stable per-record key that fixes row order.

CREATE TABLE permit_mart AS
SELECT
  CAST(source_object_id AS BIGINT)                             AS source_object_id,
  trim(permit_number)                                          AS permit_number,
  EXTRACT(year  FROM TRY_CAST(NULLIF(trim(date_of_permit_issuance), '') AS DATE))
                                                               AS issue_year,
  EXTRACT(month FROM TRY_CAST(NULLIF(trim(date_of_permit_issuance), '') AS DATE))
                                                               AS issue_month,
  trim(community)                                              AS community,
  trim(district)                                               AS district,
  trim(work_type)                                              AS work_type,
  trim(primary_work_scope)                                     AS primary_work_scope,
  ROUND(TRY_CAST(NULLIF(trim(estimated_project_value), '') AS DOUBLE), 2)
                                                               AS project_value,
  TRY_CAST(NULLIF(trim(net_new_units), '') AS INTEGER)         AS net_new_units,
  TRY_CAST(NULLIF(trim(number_of_storeys), '') AS INTEGER)     AS storeys,
  trim(permit_status)                                          AS permit_status,
  TRY_CAST(NULLIF(trim(latitude), '')  AS DOUBLE)              AS lat,
  TRY_CAST(NULLIF(trim(longitude), '') AS DOUBLE)              AS lon
FROM permits_raw;

-- The single pinned pull-date constant. Every year comparison reads it so no
-- step ever calls CURRENT_DATE. The latest full issue year is the calendar year
-- before the pull year: the snapshot runs into the pull year (2026), which is
-- only partial, so the most recent complete year is 2025.
CREATE TABLE params AS
SELECT
  DATE '2026-07-09'                                   AS pull_date,
  EXTRACT(year FROM DATE '2026-07-09')::INTEGER - 1   AS latest_full_year;
