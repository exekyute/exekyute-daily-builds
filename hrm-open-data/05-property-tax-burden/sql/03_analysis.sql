-- 03_analysis.sql
-- The analytical core. Two marts for the BI faces, three golden result tables,
-- and a headline. Every dollar is already rounded to the cent in 02_transform, so
-- each SUM below is a sum of clean cents and the group totals tie to the grand
-- total exactly. effective_rate is guarded against a zero taxable base (exempt
-- lines carry a bill but no taxable assessment), rendering NULL there rather than
-- dividing by zero.

-- Mart 1 (wide): one row per tax group, rate code, and bill rate percentage, the
-- grain of the grouped pull. Powers the Power BI import and the Tableau
-- effective-rate sheet. total_taxable is the three class columns summed;
-- effective_rate is the realized rate of bill against taxable assessment.
CREATE TABLE mart_tax_group AS
SELECT
  tax_group,
  tax_summary_group,
  rate_code,
  rate_description,
  bill_rate_percentage,
  account_count,
  residential_taxable,
  commercial_taxable,
  resource_taxable,
  (residential_taxable + commercial_taxable + resource_taxable) AS total_taxable,
  bill_amount,
  bill_value,
  CASE
    WHEN (residential_taxable + commercial_taxable + resource_taxable) > 0
    THEN CAST(round(CAST(bill_amount AS DOUBLE)
               / (residential_taxable + commercial_taxable + resource_taxable), 6) AS DECIMAL(18, 6))
  END AS effective_rate
FROM tax_clean;

-- Mart 2 (long): one row per tax group per class that carries a taxable base.
-- Unpivots the three class columns so a stacked bar can colour taxable by class.
-- share_of_total_taxable is each row's share of the municipal taxable base, the
-- value the Tableau FIXED LOD reproduces. Every tax group is single-class in this
-- data, so a group contributes exactly one class row.
CREATE TABLE mart_tax_class AS
WITH unpiv AS (
  SELECT tax_group, 'Residential' AS class, SUM(residential_taxable) AS taxable
  FROM tax_clean GROUP BY tax_group
  UNION ALL
  SELECT tax_group, 'Commercial' AS class, SUM(commercial_taxable) AS taxable
  FROM tax_clean GROUP BY tax_group
  UNION ALL
  SELECT tax_group, 'Resource' AS class, SUM(resource_taxable) AS taxable
  FROM tax_clean GROUP BY tax_group
),
nonzero AS (
  SELECT * FROM unpiv WHERE taxable > 0
)
SELECT
  tax_group,
  class,
  taxable,
  CAST(round(CAST(taxable AS DOUBLE) / SUM(taxable) OVER (), 6) AS DECIMAL(18, 6)) AS share_of_total_taxable
FROM nonzero;

-- Golden 1: taxable by tax group and class, plus the bill by tax group with its
-- share of the municipal total and a rank. One row per tax group, all 28,
-- including the exempt groups that carry a bill against a zero taxable base.
CREATE TABLE tax_group_summary AS
WITH g AS (
  SELECT
    tax_group,
    SUM(account_count)       AS account_count,
    SUM(residential_taxable)  AS residential_taxable,
    SUM(commercial_taxable)   AS commercial_taxable,
    SUM(resource_taxable)     AS resource_taxable,
    SUM(residential_taxable + commercial_taxable + resource_taxable) AS total_taxable,
    SUM(bill_value)           AS bill_value,
    SUM(bill_amount)          AS bill_amount
  FROM tax_clean
  GROUP BY tax_group
)
SELECT
  tax_group,
  account_count,
  residential_taxable,
  commercial_taxable,
  resource_taxable,
  total_taxable,
  bill_value,
  bill_amount,
  CASE WHEN total_taxable > 0
       THEN CAST(round(CAST(bill_amount AS DOUBLE) / total_taxable, 6) AS DECIMAL(18, 6)) END AS effective_rate,
  CAST(round(CAST(bill_amount AS DOUBLE) / SUM(bill_amount) OVER (), 6) AS DECIMAL(18, 6))    AS bill_share,
  DENSE_RANK() OVER (ORDER BY bill_amount DESC)                                               AS bill_rank
FROM g;

-- Golden 2: the class-long view frozen as a result, one row per tax group per
-- class with a taxable base. Same content as mart 2, pinned for the golden diff.
CREATE TABLE taxable_by_class AS
SELECT tax_group, class, taxable, share_of_total_taxable
FROM mart_tax_class;

-- Golden 3: effective rate by rate code, rolled across every tax group that uses
-- the code (54 of the 72 codes span more than one group). effective_rate is the
-- blended rate of billed dollars against the taxable base for that code.
CREATE TABLE rate_effective AS
WITH r AS (
  SELECT
    rate_code,
    MIN(rate_description)                                            AS rate_description,
    SUM(account_count)                                              AS account_count,
    SUM(residential_taxable + commercial_taxable + resource_taxable) AS total_taxable,
    SUM(bill_amount)                                               AS bill_amount
  FROM tax_clean
  GROUP BY rate_code
)
SELECT
  rate_code,
  rate_description,
  account_count,
  total_taxable,
  bill_amount,
  CASE WHEN total_taxable > 0
       THEN CAST(round(CAST(bill_amount AS DOUBLE) / total_taxable, 6) AS DECIMAL(18, 6)) END AS effective_rate
FROM r;

-- Headline: the total 2024 bill across all groups and the single largest group,
-- as two ready-to-read lines for the console. run.py prints these; it computes
-- nothing.
CREATE TABLE headline AS
SELECT
  1 AS ord,
  'Total 2024 property tax billed across all tax groups: $'
    || format('{:,.2f}', CAST((SELECT SUM(bill_amount) FROM tax_clean) AS DOUBLE))
    || ' on $' || format('{:,.0f}', CAST((SELECT SUM(total_taxable) FROM tax_group_summary) AS DOUBLE))
    || ' of taxable assessment.' AS line
UNION ALL
SELECT
  2 AS ord,
  'Largest group: ' || tax_group || ', $' || format('{:,.2f}', CAST(bill_amount AS DOUBLE))
    || ' billed (' || format('{:.1f}', CAST(100.0 * bill_share AS DOUBLE))
    || '% of the municipal total).' AS line
FROM tax_group_summary
WHERE bill_rank = 1
ORDER BY ord;
