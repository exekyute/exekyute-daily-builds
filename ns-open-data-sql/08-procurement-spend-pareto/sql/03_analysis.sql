-- 03_analysis.sql
-- The analysis proper. Two questions, both answered with grouping and window functions.

-- Question 1: how many dollars, and how many awards, did each canonical vendor win, and
-- what is a fair human-readable name to show for that vendor?
-- The display name is the raw spelling that carried the most dollars under the key,
-- with count and then alphabetical order as deterministic tiebreakers.
CREATE OR REPLACE TABLE vendor_totals AS
WITH variant AS (
  SELECT
    vendor_key,
    vendor_raw,
    CAST(round(sum(award_amount), 2) AS DECIMAL(18, 2)) AS variant_amount,
    count(*) AS variant_count
  FROM clean_awards
  GROUP BY vendor_key, vendor_raw
),
pick AS (
  SELECT
    vendor_key,
    vendor_raw AS vendor_display,
    row_number() OVER (
      PARTITION BY vendor_key
      ORDER BY variant_amount DESC, variant_count DESC, vendor_raw ASC
    ) AS rn
  FROM variant
),
totals AS (
  SELECT
    vendor_key,
    CAST(round(sum(award_amount), 2) AS DECIMAL(18, 2)) AS total_awarded,
    count(*) AS award_count
  FROM clean_awards
  GROUP BY vendor_key
)
SELECT
  t.vendor_key,
  p.vendor_display,
  t.award_count,
  t.total_awarded
FROM totals t
JOIN pick p
  ON p.vendor_key = t.vendor_key
 AND p.rn = 1
ORDER BY t.total_awarded DESC, t.vendor_key ASC;

-- Question 2: the Pareto curve. Rank vendors by dollars descending, carry a running
-- cumulative total and cumulative share of all award dollars, flag the smallest top set
-- whose share reaches 80 percent, and mark repeat vendors (more than one award).
-- A vendor is in the 80 percent set when the cumulative share of every vendor ranked
-- above it was still under 80 percent, so the vendor that crosses the line is included
-- and nobody past it is.
CREATE OR REPLACE TABLE vendor_pareto AS
WITH g AS (
  SELECT sum(total_awarded) AS grand_total
  FROM vendor_totals
),
ordered AS (
  SELECT
    vendor_key,
    vendor_display,
    award_count,
    total_awarded,
    row_number() OVER (ORDER BY total_awarded DESC, vendor_key ASC) AS vendor_rank,
    sum(total_awarded) OVER (
      ORDER BY total_awarded DESC, vendor_key ASC
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS cumulative_awarded
  FROM vendor_totals
)
SELECT
  o.vendor_rank,
  o.vendor_display,
  o.vendor_key,
  o.award_count,
  o.total_awarded,
  CAST(round(100.0 * o.total_awarded / g.grand_total, 4) AS DECIMAL(7, 4)) AS pct_of_total,
  CAST(round(o.cumulative_awarded, 2) AS DECIMAL(18, 2)) AS cumulative_awarded,
  CAST(round(100.0 * o.cumulative_awarded / g.grand_total, 4) AS DECIMAL(7, 4)) AS cumulative_pct,
  (100.0 * (o.cumulative_awarded - o.total_awarded) / g.grand_total) < 80.0 AS reaches_80pct_set,
  (o.award_count > 1) AS is_repeat_vendor
FROM ordered o
CROSS JOIN g
ORDER BY o.vendor_rank;
