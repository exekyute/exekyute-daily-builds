-- 02_transform.sql
-- Question this step answers: what does one clean, typed permit-stage-jurisdiction
-- row look like?
-- Trim the text fields, cast the occurrence count to an integer and the duration
-- to a double, and drop any row missing a key value or a duration. The source
-- grain is already one row per permit per issuance stage per jurisdictional
-- breakdown (a permit such as BLAST-2021-10569 carries separate Pre Issuance and
-- Post Issuance rows), so this table is that same grain, cleaned and typed. It is
-- the frozen mart both BI faces read, and the base every aggregate rolls up from.

CREATE TABLE pt_mart AS
SELECT
  trim(permit_number)                    AS permit_number,
  trim(issuance_stage)                   AS issuance_stage,
  trim(jurisdictional_breakdown)         AS jurisdictional_breakdown,
  CAST(trim(total_occurrence) AS BIGINT) AS total_occurrence,
  CAST(trim(total_duration)   AS DOUBLE) AS total_duration
FROM pt_raw
WHERE permit_number            IS NOT NULL AND trim(permit_number)            <> ''
  AND issuance_stage           IS NOT NULL AND trim(issuance_stage)           <> ''
  AND jurisdictional_breakdown IS NOT NULL AND trim(jurisdictional_breakdown) <> ''
  AND total_duration           IS NOT NULL AND trim(total_duration)           <> '';
