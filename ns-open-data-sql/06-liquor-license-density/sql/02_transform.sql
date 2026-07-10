-- 02_transform.sql
-- Question this step answers: which community and license type does each row belong to,
-- once the raw text is cleaned?
--
-- Cleaning rules:
--   community    : city_town trimmed. A blank or missing city_town becomes '(Unknown)'
--                  so the license is still counted rather than silently dropped.
--   license_type : trimmed, and internal runs of whitespace collapsed to one space, so
--                  'Permanent  Special Occasion' (double space in the source) folds into
--                  'Permanent Special Occasion'.
-- license_number is carried through unchanged as the row identity.

INSERT INTO clean_licenses
SELECT
    license_number,
    regexp_replace(trim(license_type), '\s+', ' ', 'g') AS license_type,
    CASE
        WHEN city_town IS NULL OR trim(city_town) = '' THEN '(Unknown)'
        ELSE trim(city_town)
    END AS community
FROM raw_licenses;
