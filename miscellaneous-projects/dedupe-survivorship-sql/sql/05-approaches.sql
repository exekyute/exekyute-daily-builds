-- What each way of removing duplicates keeps and drops, on the same match
-- key as query 01: the records as loaded, SELECT DISTINCT, MAX() per column
-- as in query 02, the whole record of query 03 and the field-by-field record
-- of query 04. rows_kept is the rows each leaves. duplicates_left counts the
-- customers still on more than one row. in_no_record counts rows that match
-- no loaded record on name, email, phone, address and opt_in. blanks_known
-- counts email and address fields left blank although another record of the
-- same customer has one; a phone is never blank beside a known one, since a
-- record with no phone matches nothing. yes_over_no counts rows marked yes
-- for a customer whose newest answer is no, newest read as in query 04: the
-- latest record, and no when two from that day disagree.
-- Some cells are 0 by construction and written as 0: records and their
-- distinct copies are records, and so is a whole kept record; MAX() skips a
-- blank whenever a value exists; and the field-by-field consent is the
-- newest answer itself. Each step of the chain is named once, so SQLite
-- before 3.35, which works a CTE out again at every mention, does no more
-- work than a newer one.
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
spread AS (
    -- Each record beside what every approach picks for its customer.
    SELECT
        *,
        COUNT(*) OVER (PARTITION BY match_key) AS records,
        ROW_NUMBER() OVER (PARTITION BY match_key
                           ORDER BY updated_on DESC, source_rank, record_no) AS rank_no,
        ROW_NUMBER() OVER (PARTITION BY full_name, email, phone, address, opt_in
                           ORDER BY record) AS copy_no,
        MAX(full_name) OVER (PARTITION BY match_key) AS max_name,
        MAX(email) OVER (PARTITION BY match_key) AS max_email,
        MAX(phone) OVER (PARTITION BY match_key) AS max_phone,
        MAX(address) OVER (PARTITION BY match_key) AS max_address,
        MAX(opt_in) OVER (PARTITION BY match_key) AS max_opt_in,
        FIRST_VALUE(full_name) OVER (PARTITION BY match_key
            ORDER BY source_rank, updated_on DESC, record_no) AS best_name,
        FIRST_VALUE(email) OVER (PARTITION BY match_key
            ORDER BY email IS NULL, updated_on DESC, source_rank, record_no) AS best_email,
        FIRST_VALUE(phone) OVER (PARTITION BY match_key
            ORDER BY phone IS NULL, updated_on DESC, source_rank, record_no) AS best_phone,
        FIRST_VALUE(address) OVER (PARTITION BY match_key
            ORDER BY address IS NULL, updated_on DESC, source_rank, record_no) AS best_address,
        FIRST_VALUE(opt_in) OVER (PARTITION BY match_key
            ORDER BY updated_on DESC, opt_in = 'yes', source_rank, record_no) AS best_opt_in
    FROM keyed
),
flagged AS (
    SELECT
        match_key,
        rank_no,
        copy_no,
        (email IS NULL AND max_email IS NOT NULL)
            + (address IS NULL AND max_address IS NOT NULL) AS blanks_known,
        opt_in = 'yes' AND best_opt_in = 'no' AS yes_over_no,
        full_name = max_name AND email IS max_email AND phone IS max_phone
            AND address IS max_address AND opt_in = max_opt_in AS holds_every_max,
        max_opt_in = 'yes' AND best_opt_in = 'no' AS max_yes_over_no,
        full_name = best_name AND email IS best_email AND phone IS best_phone
            AND address IS best_address AND opt_in = best_opt_in AS holds_every_best,
        (best_email IS NULL AND max_email IS NOT NULL)
            + (best_address IS NULL AND max_address IS NOT NULL) AS best_blanks_known
    FROM spread
),
per_customer AS (
    SELECT
        COUNT(*) AS records,
        SUM(copy_no = 1) AS distinct_rows,
        SUM(blanks_known) AS loaded_blanks,
        SUM(yes_over_no) AS loaded_yes,
        SUM(CASE WHEN copy_no = 1 THEN blanks_known ELSE 0 END) AS distinct_blanks,
        SUM(copy_no = 1 AND yes_over_no) AS distinct_yes,
        MAX(holds_every_max) AS max_in_record,
        MAX(max_yes_over_no) AS max_yes,
        SUM(CASE WHEN rank_no = 1 THEN blanks_known ELSE 0 END) AS whole_blanks,
        SUM(rank_no = 1 AND yes_over_no) AS whole_yes,
        MAX(holds_every_best) AS best_in_record,
        MAX(best_blanks_known) AS best_blanks
    FROM flagged
    GROUP BY match_key
),
approaches(step, approach) AS (
    VALUES (1, 'as loaded'),
           (2, 'select distinct'),
           (3, 'max() per column'),
           (4, 'whole record'),
           (5, 'field by field')
)
SELECT
    a.approach,
    SUM(CASE a.step WHEN 1 THEN c.records WHEN 2 THEN c.distinct_rows ELSE 1 END) AS rows_kept,
    SUM(CASE a.step WHEN 1 THEN c.records > 1 WHEN 2 THEN c.distinct_rows > 1 ELSE 0 END) AS duplicates_left,
    SUM(CASE a.step WHEN 3 THEN 1 - c.max_in_record WHEN 5 THEN 1 - c.best_in_record ELSE 0 END) AS in_no_record,
    SUM(CASE a.step WHEN 1 THEN c.loaded_blanks WHEN 2 THEN c.distinct_blanks
                    WHEN 4 THEN c.whole_blanks WHEN 5 THEN c.best_blanks ELSE 0 END) AS blanks_known,
    SUM(CASE a.step WHEN 1 THEN c.loaded_yes WHEN 2 THEN c.distinct_yes
                    WHEN 3 THEN c.max_yes WHEN 4 THEN c.whole_yes ELSE 0 END) AS yes_over_no
FROM approaches a
CROSS JOIN per_customer c
GROUP BY a.step, a.approach
ORDER BY a.step;
