-- 02_transform.sql
-- Questions this step answers:
--   Which rows carry a usable farm count?
--   Which labels are the same commodity spelled two ways?
--   How do we get exactly one total per commodity per fiscal year when the source repeats a row?
--
-- Cleaning rules, applied in order:
--   1. Trim surrounding whitespace on the commodity label.
--   2. Drop rows with a null total. The source leaves the Turkey 2024-2025 total blank, and a
--      blank total is not a zero, so that row is excluded rather than counted as zero.
--   3. Fold seven singular and plural spelling variants onto one canonical label. Each pair is the
--      same commodity written two ways in different year ranges, and the two spellings never share
--      a fiscal year, so folding them never double counts within a year.
--   4. Collapse to one row per (commodity, fiscal year) by keeping the larger total. The source
--      lists three commodities twice in fiscal 2016-2017 (Strawberries, Turkey, Vegetable Crops),
--      once with a value the size of the prior year and once with a value in line with the next
--      year. Keeping the larger total follows the forward trajectory in all three cases.

DROP TABLE IF EXISTS clean_farm;
CREATE TABLE clean_farm AS
WITH canon AS (
    SELECT
        CASE trim(commodity)
            WHEN 'Apples'           THEN 'Apple'
            WHEN 'Christmas Trees'  THEN 'Christmas Tree'
            WHEN 'Eggs'             THEN 'Egg'
            WHEN 'Greenhouse Crops' THEN 'Greenhouse Crop'
            WHEN 'Hogs'             THEN 'Hog'
            WHEN 'Strawberries'     THEN 'Strawberry'
            WHEN 'Vegetable Crops'  THEN 'Vegetable Crop'
            ELSE trim(commodity)
        END                       AS commodity,
        fiscal_year,
        total_of_registered_farms AS farms
    FROM raw_farm
    WHERE total_of_registered_farms IS NOT NULL
)
SELECT commodity, fiscal_year, max(farms) AS farms
FROM canon
GROUP BY commodity, fiscal_year;

-- Fiscal-year ordering, derived from the data so the year-over-year step in 03 can compare
-- adjacent years only. Fiscal-year strings such as '2015-2016' sort correctly as text.
DROP TABLE IF EXISTS fiscal_year_dim;
CREATE TABLE fiscal_year_dim AS
SELECT fiscal_year, dense_rank() OVER (ORDER BY fiscal_year) AS yr_rank
FROM (SELECT DISTINCT fiscal_year FROM clean_farm);

-- Registered farms across all commodities in each fiscal year, the denominator for share.
DROP TABLE IF EXISTS year_total;
CREATE TABLE year_total AS
SELECT fiscal_year, sum(farms) AS year_total_farms
FROM clean_farm
GROUP BY fiscal_year;
