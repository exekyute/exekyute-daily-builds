-- 03_analysis.sql
-- Builds every audit breakdown, then stacks them into one sectioned result
-- table (funding_audit). Dollar math stays in DECIMAL(18,2) end to end;
-- percentages are display values rounded to two decimals.

-- Grand total, the number every breakdown must tie back to.
CREATE OR REPLACE TABLE grand_total AS
SELECT
    count(*)                          AS payments,
    CAST(sum(amount) AS DECIMAL(18,2)) AS amount
FROM clean_payments;

-- Per-recipient totals over the whole window, ranked by dollars.
-- Tie-break on recipient_key keeps the ranking reproducible.
CREATE OR REPLACE TABLE recipient_totals AS
SELECT
    row_number() OVER (ORDER BY sum(c.amount) DESC, c.recipient_key) AS rnk,
    d.recipient,
    c.recipient_key,
    count(*) AS payments,
    CAST(sum(c.amount) AS DECIMAL(18,2)) AS amount
FROM clean_payments c
JOIN recipient_display d USING (recipient_key)
GROUP BY d.recipient, c.recipient_key
ORDER BY rnk;

-- Per-program totals, ranked by dollars, tie-break on program name.
CREATE OR REPLACE TABLE program_totals AS
SELECT
    row_number() OVER (ORDER BY sum(amount) DESC, program_name) AS rnk,
    program_name,
    count(*) AS payments,
    CAST(sum(amount) AS DECIMAL(18,2)) AS amount
FROM clean_payments
GROUP BY program_name
ORDER BY rnk;

-- Division dollars by fiscal year, with year-over-year change computed by
-- LAG over each division's own observed year sequence.
CREATE OR REPLACE TABLE division_year_totals AS
SELECT
    fiscal_year,
    fy_start,
    division,
    count(*) AS payments,
    CAST(sum(amount) AS DECIMAL(18,2)) AS amount,
    CAST(
        sum(amount) - lag(sum(amount)) OVER (PARTITION BY division ORDER BY fy_start)
        AS DECIMAL(18,2)
    ) AS yoy_change,
    CAST(ROUND(
        (sum(amount) - lag(sum(amount)) OVER (PARTITION BY division ORDER BY fy_start))
        / lag(sum(amount)) OVER (PARTITION BY division ORDER BY fy_start) * 100, 2)
        AS DECIMAL(9,2)
    ) AS yoy_pct
FROM clean_payments
GROUP BY fiscal_year, fy_start, division
ORDER BY fy_start, division;

-- Duplicate-payment candidates: groups from dup_groups that occur more
-- than once. amount is the single repeated payment; extra_amount is the
-- dollars in occurrences beyond the first.
CREATE OR REPLACE TABLE duplicate_candidates AS
SELECT
    row_number() OVER (ORDER BY g.amount DESC, d.recipient, g.fiscal_year) AS rnk,
    d.recipient,
    g.program_name,
    g.fiscal_year,
    g.amount,
    g.occurrences,
    CAST(g.amount * (g.occurrences - 1) AS DECIMAL(18,2)) AS extra_amount
FROM dup_groups g
JOIN recipient_display d USING (recipient_key)
WHERE g.occurrences > 1
ORDER BY rnk;

-- The sectioned audit result. Sections, in file order:
--   summary               headline figures
--   totals_tie            each breakdown re-summed; all rows must equal the grand total
--   top_recipients        top 25 recipients by dollars, with cumulative share
--   program_shares        all programs by dollars, with share of total
--   yoy_division          division dollars per fiscal year with YoY change
--   duplicate_candidates  the flagged groups
CREATE OR REPLACE TABLE funding_audit AS
WITH sections AS (

    SELECT
        1 AS section_order, 'summary' AS section, 1 AS rank,
        'grand_total_dollars' AS measure,
        '' AS fiscal_year, '' AS division, '' AS program_name, '' AS recipient,
        payments,
        amount,
        CAST(100.00 AS DECIMAL(9,2)) AS share_pct,
        CAST(NULL AS DECIMAL(9,2)) AS cumulative_share_pct,
        CAST(NULL AS DECIMAL(18,2)) AS yoy_change,
        CAST(NULL AS DECIMAL(9,2)) AS yoy_pct
    FROM grand_total

    UNION ALL

    SELECT
        1, 'summary', 2, 'top_10_recipient_dollars',
        '', '', '', '',
        (SELECT sum(payments) FROM recipient_totals WHERE rnk <= 10),
        (SELECT CAST(sum(amount) AS DECIMAL(18,2)) FROM recipient_totals WHERE rnk <= 10),
        (SELECT CAST(ROUND(sum(amount) / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2))
         FROM recipient_totals WHERE rnk <= 10),
        NULL, NULL, NULL

    UNION ALL

    SELECT
        1, 'summary', 3, 'duplicate_candidate_extra_dollars',
        '', '', '', '',
        (SELECT COALESCE(sum(occurrences - 1), 0) FROM duplicate_candidates),
        (SELECT CAST(COALESCE(sum(extra_amount), 0) AS DECIMAL(18,2)) FROM duplicate_candidates),
        (SELECT CAST(ROUND(COALESCE(sum(extra_amount), 0) / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2))
         FROM duplicate_candidates),
        NULL, NULL, NULL

    UNION ALL

    SELECT
        2, 'totals_tie', 1, 'sum_by_recipient', '', '', '', '',
        (SELECT sum(payments) FROM recipient_totals),
        (SELECT CAST(sum(amount) AS DECIMAL(18,2)) FROM recipient_totals),
        NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        2, 'totals_tie', 2, 'sum_by_program', '', '', '', '',
        (SELECT sum(payments) FROM program_totals),
        (SELECT CAST(sum(amount) AS DECIMAL(18,2)) FROM program_totals),
        NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        2, 'totals_tie', 3, 'sum_by_division_year', '', '', '', '',
        (SELECT sum(payments) FROM division_year_totals),
        (SELECT CAST(sum(amount) AS DECIMAL(18,2)) FROM division_year_totals),
        NULL, NULL, NULL, NULL

    UNION ALL

    SELECT
        3, 'top_recipients', rnk, '',
        '', '', '', recipient,
        payments,
        amount,
        CAST(ROUND(amount / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        CAST(ROUND(
            sum(amount) OVER (ORDER BY rnk) / (SELECT amount FROM grand_total) * 100, 2)
            AS DECIMAL(9,2)),
        NULL, NULL
    FROM recipient_totals
    WHERE rnk <= 25

    UNION ALL

    SELECT
        4, 'program_shares', rnk, '',
        '', '', program_name, '',
        payments,
        amount,
        CAST(ROUND(amount / (SELECT amount FROM grand_total) * 100, 2) AS DECIMAL(9,2)),
        NULL, NULL, NULL
    FROM program_totals

    UNION ALL

    SELECT
        5, 'yoy_division',
        row_number() OVER (ORDER BY fy_start, division),
        '',
        fiscal_year, division, '', '',
        payments,
        amount,
        NULL, NULL,
        yoy_change,
        yoy_pct
    FROM division_year_totals

    UNION ALL

    SELECT
        6, 'duplicate_candidates', rnk, '',
        fiscal_year, '', program_name, recipient,
        occurrences,
        amount,
        NULL, NULL,
        extra_amount,
        NULL
    FROM duplicate_candidates
)
SELECT * FROM sections
ORDER BY section_order, rank;

-- BI mart: one row per source payment, cleaned and flagged, so Power BI
-- can re-derive every headline without recomputing any cleaning rule.
CREATE OR REPLACE TABLE mart_funding_audit AS
SELECT
    c.fiscal_year,
    c.fy_start AS fiscal_year_start,
    c.division,
    c.program_name,
    d.recipient,
    c.amount AS payment_amount,
    CASE WHEN g.occurrences > 1 THEN 1 ELSE 0 END AS is_duplicate_candidate,
    g.occurrences AS dup_occurrences
FROM clean_payments c
JOIN recipient_display d USING (recipient_key)
JOIN dup_groups g
  ON g.recipient_key = c.recipient_key
 AND g.program_name  = c.program_name
 AND g.amount        = c.amount
 AND g.fiscal_year   = c.fiscal_year
ORDER BY c.fy_start, c.division, c.program_name, d.recipient, c.amount;
