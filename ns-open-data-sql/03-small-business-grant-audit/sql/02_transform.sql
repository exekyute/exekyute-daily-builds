-- 02_transform.sql
-- Question this step sets up: which records are recipients, and which grant did
-- each one receive? A recipient is any record that received at least one of the
-- two grants. The yes/no text is trimmed and lower-cased, then turned into
-- booleans so the analysis step counts flags instead of parsing strings.
-- In this snapshot every record received at least one grant, so the WHERE keeps
-- all rows; it is written out anyway so the pipeline stays on recipients, not
-- applicants, if a future snapshot lists both.

INSERT INTO recipients
SELECT
    trim(year)                                          AS year,
    trim(type_of_business)                              AS type_of_business,
    lower(trim(received_small_business_impact)) = 'yes' AS got_sbig,
    lower(trim(received_small_business))        = 'yes' AS got_sbrsg
FROM raw_grants
WHERE lower(trim(received_small_business_impact)) = 'yes'
   OR lower(trim(received_small_business))        = 'yes';
