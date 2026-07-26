-- 02_transform.sql
-- Cleaning rules, all deterministic:
--   * amounts cast to DECIMAL(18,2); a value that will not cast fails the run
--   * division: 'Programs & Business Risk Management' is the same unit as
--     'Programs and Business Risk Management' (ampersand-era spelling,
--     2014-2015 through 2017-2018), so it is canonicalized to the 'and' form.
--     'Programs' (2021-2022 onward) is kept as its own label; merging it with
--     the older unit would be an interpretive call, not a spelling fix.
--   * program_name: trim and collapse runs of spaces; blank or missing
--     program names (21 rows, all 2017-2018 exhibition and fair grants)
--     become the literal label '(program not stated)' so they group,
--     join, and export like any other program instead of vanishing on
--     NULL comparisons
--   * recipients: trim, collapse runs of spaces, and group on the
--     lowercased result (recipient_key). Display name per key is the most
--     frequent raw spelling, ties broken alphabetically. Variants beyond
--     case and spacing (e.g. 'Horticulture NS' vs 'Horticulture Nova
--     Scotia') are left as distinct recipients.
--   * fy_start: integer first year of the fiscal label, for ordering and
--     for the year-index pattern in the BI mart.

CREATE OR REPLACE TABLE clean_payments AS
SELECT
    trim(department) AS department,
    CASE
        WHEN trim(division) = 'Programs & Business Risk Management'
        THEN 'Programs and Business Risk Management'
        ELSE trim(division)
    END AS division,
    COALESCE(
        NULLIF(regexp_replace(trim(program_name), ' +', ' ', 'g'), ''),
        '(program not stated)'
    ) AS program_name,
    regexp_replace(trim(client_name), ' +', ' ', 'g') AS recipient_raw,
    lower(regexp_replace(trim(client_name), ' +', ' ', 'g')) AS recipient_key,
    CAST(payment_amount AS DECIMAL(18,2)) AS amount,
    trim(fiscal_year) AS fiscal_year,
    CAST(substr(trim(fiscal_year), 1, 4) AS INTEGER) AS fy_start
FROM raw_payments;

-- One display spelling per recipient_key: most frequent raw spelling wins,
-- alphabetical order breaks ties.
CREATE OR REPLACE TABLE recipient_display AS
SELECT recipient_key, recipient_raw AS recipient
FROM (
    SELECT
        recipient_key,
        recipient_raw,
        row_number() OVER (
            PARTITION BY recipient_key
            ORDER BY count(*) DESC, recipient_raw
        ) AS rn
    FROM clean_payments
    GROUP BY recipient_key, recipient_raw
)
WHERE rn = 1;

-- Duplicate-payment candidate groups. The rule, verbatim from spec.md:
-- rows sharing the same recipient_key, program_name, amount, and
-- fiscal_year, appearing more than once, are candidates (not confirmed
-- duplicates).
CREATE OR REPLACE TABLE dup_groups AS
SELECT
    recipient_key,
    program_name,
    amount,
    fiscal_year,
    count(*) AS occurrences
FROM clean_payments
GROUP BY recipient_key, program_name, amount, fiscal_year;
