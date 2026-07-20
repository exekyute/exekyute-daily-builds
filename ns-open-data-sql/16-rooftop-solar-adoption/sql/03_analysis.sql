-- 03_analysis: aggregate the clean rows into the three analysis tables.
-- fsa_year is the base grain (FSA x year); province_year and fsa_totals are
-- built FROM fsa_year so every downstream consumer (the golden summary, the
-- mart, the dashboard's in-browser re-derivation) adds up the same numbers.

CREATE OR REPLACE TABLE fsa_year AS
SELECT
    fsa,
    year,
    COUNT(*)          AS installs,
    ROUND(SUM(kw), 2) AS installed_kw
FROM solar_clean
GROUP BY fsa, year;

CREATE OR REPLACE TABLE province_year AS
WITH yearly AS (
    SELECT
        year,
        SUM(installs)               AS installs,
        ROUND(SUM(installed_kw), 2) AS installed_kw
    FROM fsa_year
    GROUP BY year
)
SELECT
    year,
    installs,
    installed_kw,
    SUM(installs)     OVER (ORDER BY year)           AS cumulative_installs,
    ROUND(SUM(installed_kw) OVER (ORDER BY year), 2) AS cumulative_kw,
    installs - LAG(installs) OVER (ORDER BY year)    AS yoy_install_change,
    ROUND(
        100.0 * (installs - LAG(installs) OVER (ORDER BY year))
        / NULLIF(LAG(installs) OVER (ORDER BY year), 0),
        1
    ) AS yoy_install_pct
FROM yearly;

CREATE OR REPLACE TABLE fsa_totals AS
WITH totals AS (
    SELECT
        fsa,
        SUM(installs)               AS installs,
        ROUND(SUM(installed_kw), 2) AS installed_kw
    FROM fsa_year
    GROUP BY fsa
)
SELECT
    fsa,
    installs,
    installed_kw,
    ROUND(100.0 * installs / SUM(installs) OVER (), 1) AS share_of_installs_pct,
    RANK() OVER (ORDER BY installs DESC)     AS rank_by_installs,
    RANK() OVER (ORDER BY installed_kw DESC) AS rank_by_kw
FROM totals;

-- headline: ready-to-print lines. run.py prints these; it does not compute them.
CREATE OR REPLACE TABLE headline AS
WITH prov AS (
    SELECT
        MIN(year)                 AS year_first,
        MAX(year)                 AS year_last,
        MAX(cumulative_installs)  AS total_installs,
        MAX(cumulative_kw)        AS total_kw
    FROM province_year
),
leader AS (
    SELECT fsa, installs, installed_kw, share_of_installs_pct
    FROM fsa_totals
    WHERE rank_by_installs = 1
    ORDER BY fsa
    LIMIT 1
)
SELECT 1 AS ord,
       printf('%d residential solar installations totalling %.2f kW across %d to %d.',
              prov.total_installs, prov.total_kw, prov.year_first, prov.year_last) AS line
FROM prov
UNION ALL
SELECT 2 AS ord,
       printf('Leading region: %s with %d installs (%.1f%% of the province, %.2f kW).',
              leader.fsa, leader.installs, leader.share_of_installs_pct,
              leader.installed_kw) AS line
FROM leader;
