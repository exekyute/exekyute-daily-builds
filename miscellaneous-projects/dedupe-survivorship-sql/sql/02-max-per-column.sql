-- The quick merge, and where it goes wrong. It groups the records on the
-- same match key as query 01 and takes MAX() of every column. MAX() on text
-- is the value that sorts last, compared byte by byte, so each column comes
-- from whichever record happens to sort last in it: lower case sorts after
-- capitals, a dot after a hyphen, and 7 Pleasant St after 114 Robie St.
-- It also skips a blank, and yes sorts after no. The result can pair one
-- record's email with another's address and a third's phone number: a
-- record no source holds. in_a_record says whether any record of the
-- customer holds the whole merged row, the date aside. distinct_rows is how
-- many rows SELECT DISTINCT keeps of the customer's records, compared on
-- name, email, phone, address and opt_in: records that differ only in case
-- or spacing are different text to it, so it keeps them all. Only customers
-- with more than one record are listed.
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
spread AS (
    -- IS rather than = where a value can be blank, since NULL = NULL is not
    -- true. copy_no numbers the records that SELECT DISTINCT would take as
    -- one row, so the first of each is a row it keeps.
    SELECT
        *,
        full_name = MAX(full_name) OVER (PARTITION BY match_key)
            AND email IS MAX(email) OVER (PARTITION BY match_key)
            AND phone IS MAX(phone) OVER (PARTITION BY match_key)
            AND address IS MAX(address) OVER (PARTITION BY match_key)
            AND opt_in = MAX(opt_in) OVER (PARTITION BY match_key) AS holds_every_max,
        ROW_NUMBER() OVER (PARTITION BY full_name, email, phone, address, opt_in
                           ORDER BY record) AS copy_no
    FROM keyed
)
SELECT
    COUNT(*) AS records,
    SUM(copy_no = 1) AS distinct_rows,
    MAX(full_name) AS full_name,
    MAX(email) AS email,
    MAX(phone) AS phone,
    MAX(address) AS address,
    MAX(opt_in) AS opt_in,
    MAX(updated_on) AS updated_on,
    CASE MAX(holds_every_max) WHEN 1 THEN 'yes' ELSE 'no' END AS in_a_record
FROM spread
GROUP BY match_key
HAVING COUNT(*) > 1
ORDER BY match_key;
