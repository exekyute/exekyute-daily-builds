-- 99_export: write the golden summary and the Tableau-ready mart.
-- Both queries end in ORDER BY so the files are byte-for-byte reproducible.

COPY (
    SELECT
        year,
        installs,
        installed_kw,
        cumulative_installs,
        cumulative_kw,
        yoy_install_change,
        yoy_install_pct
    FROM province_year
    ORDER BY year
) TO 'out/solar_adoption.csv' (HEADER, DELIMITER ',');

COPY (
    SELECT
        fsa,
        year,
        installs,
        installed_kw
    FROM fsa_year
    ORDER BY fsa, year
) TO 'out/mart_solar.csv' (HEADER, DELIMITER ',');
