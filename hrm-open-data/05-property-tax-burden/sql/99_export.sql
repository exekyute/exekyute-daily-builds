-- 99_export.sql
-- Question this step answers: what are the final, deterministic result files and
-- the frozen BI marts?
-- Write the three golden results to out/ and the two frozen marts to bi/exports/.
-- Every query ends in an ORDER BY so the row order is stable and the output is
-- byte-for-byte reproducible against expected/. The marts are the exact tables
-- Tableau and Power BI import, so both tools read the same frozen cents the golden
-- diff verifies.

-- Golden 1: tax-group summary, ranked by bill amount (largest first).
COPY (
  SELECT *
  FROM tax_group_summary
  ORDER BY bill_amount DESC, tax_group
) TO 'out/tax_group_summary.csv' (HEADER, DELIMITER ',');

-- Golden 2: taxable by tax group and class (the stacked-bar source).
COPY (
  SELECT *
  FROM taxable_by_class
  ORDER BY tax_group, class
) TO 'out/taxable_by_class.csv' (HEADER, DELIMITER ',');

-- Golden 3: effective rate by rate code (highest realized rate first).
COPY (
  SELECT *
  FROM rate_effective
  ORDER BY effective_rate DESC NULLS LAST, rate_code
) TO 'out/rate_effective.csv' (HEADER, DELIMITER ',');

-- Frozen wide mart for both BI tools.
COPY (
  SELECT *
  FROM mart_tax_group
  ORDER BY tax_group, rate_code, bill_rate_percentage, tax_summary_group
) TO 'bi/exports/mart_tax_group.csv' (HEADER, DELIMITER ',');

-- Frozen long mart for the Tableau stacked bar.
COPY (
  SELECT *
  FROM mart_tax_class
  ORDER BY tax_group, class
) TO 'bi/exports/mart_tax_class.csv' (HEADER, DELIMITER ',');
