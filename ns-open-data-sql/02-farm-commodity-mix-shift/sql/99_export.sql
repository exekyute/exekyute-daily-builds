-- 99_export.sql
-- Question this step answers: what is the deterministic artifact this project produces?
-- Writes the commodity mix to out/commodity_mix.csv. The ORDER BY makes the file byte-for-byte
-- stable from one run to the next, so it can be diffed against expected/commodity_mix.csv.

COPY (
    SELECT commodity, fiscal_year, farms, year_total_farms, share_pct,
           prev_year_farms, yoy_change_farms, yoy_pct
    FROM commodity_mix
    ORDER BY commodity, fiscal_year
) TO 'out/commodity_mix.csv' (HEADER, DELIMITER ',');
