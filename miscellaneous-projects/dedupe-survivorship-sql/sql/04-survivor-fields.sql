-- One record per customer built field by field, each field taken by its own
-- stated rule and printed beside the record it came from.
--   full_name  the web shop's spelling before the till's, then the most
--              recently updated, then the lower record number. Within one
--              customer the names differ only in letter case and the
--              length of runs of spaces, since the key is built from
--              the name, so this picks a spelling.
--   email, phone, address  the most recently updated record that has one,
--              then the web shop's, then the lower record number. A field
--              is left blank only when no record of the customer has it.
--   opt_in     the most recently updated record's answer, and when two
--              records from the same day disagree, no. A withdrawal of
--              consent is never outvoted by a yes from the same day.
-- FIRST_VALUE takes each field from the first record in its own order.
-- Every record of a customer carries the same picks, so the first record by
-- its reference is the one printed. The match key is built as in query 01.
WITH
cleaned AS (
    SELECT
        *,
        lower(replace(replace(replace(full_name, ' ', '<>'), '><', ''), '<>', ' ')) AS name_key,
        replace(replace(replace(replace(replace(replace(phone,
            ' ', ''), '-', ''), '.', ''), '(', ''), ')', ''), '+', '') AS digits,
        source || ' ' || record_no AS record
    FROM customers
),
numbered AS (
    SELECT
        *,
        CASE WHEN length(digits) = 11 AND substr(digits, 1, 1) = '1' THEN substr(digits, 2)
             ELSE digits END AS number
    FROM cleaned
),
keyed AS (
    SELECT
        *,
        name_key || '|' || COALESCE(number, record) AS match_key,
        CASE source WHEN 'web' THEN 1 ELSE 2 END AS source_rank
    FROM numbered
),
picked AS (
    SELECT
        match_key,
        ROW_NUMBER() OVER (PARTITION BY match_key ORDER BY record) AS row_in_customer,
        FIRST_VALUE(full_name) OVER (PARTITION BY match_key
            ORDER BY source_rank, updated_on DESC, record_no) AS full_name,
        FIRST_VALUE(record) OVER (PARTITION BY match_key
            ORDER BY source_rank, updated_on DESC, record_no) AS name_from,
        FIRST_VALUE(email) OVER (PARTITION BY match_key
            ORDER BY email IS NULL, updated_on DESC, source_rank, record_no) AS email,
        FIRST_VALUE(CASE WHEN email IS NOT NULL THEN record END) OVER (PARTITION BY match_key
            ORDER BY email IS NULL, updated_on DESC, source_rank, record_no) AS email_from,
        FIRST_VALUE(phone) OVER (PARTITION BY match_key
            ORDER BY phone IS NULL, updated_on DESC, source_rank, record_no) AS phone,
        FIRST_VALUE(CASE WHEN phone IS NOT NULL THEN record END) OVER (PARTITION BY match_key
            ORDER BY phone IS NULL, updated_on DESC, source_rank, record_no) AS phone_from,
        FIRST_VALUE(address) OVER (PARTITION BY match_key
            ORDER BY address IS NULL, updated_on DESC, source_rank, record_no) AS address,
        FIRST_VALUE(CASE WHEN address IS NOT NULL THEN record END) OVER (PARTITION BY match_key
            ORDER BY address IS NULL, updated_on DESC, source_rank, record_no) AS address_from,
        FIRST_VALUE(opt_in) OVER (PARTITION BY match_key
            ORDER BY updated_on DESC, opt_in = 'yes', source_rank, record_no) AS opt_in,
        FIRST_VALUE(record) OVER (PARTITION BY match_key
            ORDER BY updated_on DESC, opt_in = 'yes', source_rank, record_no) AS opt_in_from
    FROM keyed
)
SELECT
    full_name,
    name_from,
    email,
    email_from,
    phone,
    phone_from,
    address,
    address_from,
    opt_in,
    opt_in_from
FROM picked
WHERE row_in_customer = 1
ORDER BY match_key;
