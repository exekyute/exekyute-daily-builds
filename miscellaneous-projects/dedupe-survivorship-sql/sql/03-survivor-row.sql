-- One whole record kept per customer, chosen by a stated rule: the most
-- recently updated record, then on the same day the web shop's before the
-- till's, then the lower record number. ROW_NUMBER ranks each customer's
-- records in that order and the first is kept, so the name, email, phone,
-- address, consent and date printed all come from one record, as it was
-- loaded. The three keys leave no tie, since a source never uses a record
-- number twice. won_on says which part of the rule settled it, from the
-- record that came second. The match key is built as in query 01.
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
    SELECT *, name_key || '|' || COALESCE(number, record) AS match_key
    FROM numbered
),
ranked AS (
    SELECT
        *,
        COUNT(*) OVER (PARTITION BY match_key) AS records,
        ROW_NUMBER() OVER (PARTITION BY match_key ORDER BY updated_on DESC,
                           CASE source WHEN 'web' THEN 1 ELSE 2 END, record_no) AS rank_no,
        LEAD(updated_on) OVER (PARTITION BY match_key ORDER BY updated_on DESC,
                               CASE source WHEN 'web' THEN 1 ELSE 2 END, record_no) AS next_updated_on,
        LEAD(source) OVER (PARTITION BY match_key ORDER BY updated_on DESC,
                           CASE source WHEN 'web' THEN 1 ELSE 2 END, record_no) AS next_source
    FROM keyed
)
SELECT
    full_name,
    email,
    phone,
    address,
    opt_in,
    updated_on,
    record AS kept,
    records,
    CASE
        WHEN records = 1 THEN 'only record'
        WHEN updated_on > next_updated_on THEN 'newest'
        WHEN source <> next_source THEN 'same day, web shop'
        ELSE 'same day, lower number'
    END AS won_on
FROM ranked
WHERE rank_no = 1
ORDER BY match_key;
