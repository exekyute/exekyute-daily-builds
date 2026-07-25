-- 02_transform.sql
-- Question this step answers: when was each co-op incorporated, in what form, and how
-- old is it as of the pinned pull date?
--
-- PULL DATE. Declared exactly once, here, as a literal. Every age computation in the
-- pipeline reads it from the params table. CURRENT_DATE is never used, so the output
-- is identical no matter when the pipeline runs.
CREATE OR REPLACE TABLE params AS
SELECT DATE '2026-07-06' AS pull_date;

-- Cleaning rules:
--   co_op_name / town / coop_type : trimmed, internal runs of whitespace collapsed to
--                                   one space. A blank or missing town would become
--                                   '(Unknown)'; in this snapshot none does.
--   incorporation_date : the source column is named incorporation_year but carries a
--                        full ISO date ('1998-10-08'). Cast to DATE. All 369 rows parse.
--   decade             : incorporation year floored to its decade with integer division
--                        ('//', not '/', which is float division in DuckDB), rendered
--                        as a label like '1990s'.
--   org_form           : 'N' becomes 'Non-profit', 'P' becomes 'For-profit'. Any other
--                        value would become '(Unknown)'; the snapshot holds only N and P.
--   age_years          : days from incorporation to the pull date, divided by 365.2425,
--                        rounded to one decimal place.
-- registry_id is carried through unchanged as the row identity.

INSERT INTO clean_coops
SELECT
    trim(r.registry_id)                                          AS registry_id,
    regexp_replace(trim(r.co_op_name), '\s+', ' ', 'g')          AS co_op_name,
    CASE
        WHEN r.town IS NULL OR trim(r.town) = '' THEN '(Unknown)'
        ELSE regexp_replace(trim(r.town), '\s+', ' ', 'g')
    END                                                          AS town,
    CAST(trim(r.incorporation_year) AS DATE)                     AS incorporation_date,
    year(CAST(trim(r.incorporation_year) AS DATE))               AS incorporation_year,
    CAST((year(CAST(trim(r.incorporation_year) AS DATE)) // 10) * 10 AS VARCHAR)
        || 's'                                                   AS decade,
    CASE trim(r.non_profit_n_for_profit_p)
        WHEN 'N' THEN 'Non-profit'
        WHEN 'P' THEN 'For-profit'
        ELSE '(Unknown)'
    END                                                          AS org_form,
    CASE WHEN trim(r.non_profit_n_for_profit_p) = 'N' THEN 1 ELSE 0 END
                                                                 AS is_nonprofit,
    regexp_replace(trim(r.type), '\s+', ' ', 'g')                AS coop_type,
    round(
        date_diff('day', CAST(trim(r.incorporation_year) AS DATE), p.pull_date)
        / 365.2425, 1
    )                                                            AS age_years
FROM raw_coops r
CROSS JOIN params p;
