-- 02_transform.sql
-- Question this step answers: what does one clean, typed row per tax group, rate
-- code, and bill rate percentage look like?
-- Trim the text fields, cast the counts and taxable dollars to integers, cast the
-- rate to double, and round the billed dollars to the cent. Then collapse to
-- exactly one row per grain by summing, so a stray duplicate snapshot line could
-- never double-count or make the later aggregates non-deterministic. The snapshot
-- already carries one row per grain, so this GROUP BY is a guard, not a reshape.
-- Money is rounded to two decimals here, once, so every later total is a sum of
-- clean cents and ties exactly with no floating-point drift.

CREATE TABLE tax_clean AS
SELECT
  trim(tax_group)                          AS tax_group,
  trim(tax_summary_group)                  AS tax_summary_group,
  trim(rate_code)                          AS rate_code,
  trim(rate_description)                   AS rate_description,
  CAST(bill_rate_percentage AS DOUBLE)     AS bill_rate_percentage,
  SUM(CAST(account_count       AS BIGINT)) AS account_count,
  SUM(CAST(residential_taxable AS BIGINT)) AS residential_taxable,
  SUM(CAST(commercial_taxable  AS BIGINT)) AS commercial_taxable,
  SUM(CAST(resource_taxable    AS BIGINT)) AS resource_taxable,
  CAST(round(SUM(CAST(bill_value  AS DOUBLE)), 2) AS DECIMAL(18, 2)) AS bill_value,
  CAST(round(SUM(CAST(bill_amount AS DOUBLE)), 2) AS DECIMAL(18, 2)) AS bill_amount
FROM tax_raw
WHERE tax_group IS NOT NULL AND trim(tax_group) <> ''
  AND rate_code IS NOT NULL AND trim(rate_code) <> ''
GROUP BY
  trim(tax_group),
  trim(tax_summary_group),
  trim(rate_code),
  trim(rate_description),
  CAST(bill_rate_percentage AS DOUBLE);
