-- 99_export.sql
-- Question this step answers: what is the final, deterministic result file?
-- Write the ranked detail to out/. The ORDER BY makes the row order stable: the
-- fastest-rising offence's years come first (window_rank ascending), then each
-- offence's rows run oldest year to newest. That fixed order is what makes the
-- output byte-for-byte reproducible against expected/.

COPY (
  SELECT *
  FROM convictions_ranked
  ORDER BY window_rank, offence_statute, year_convicted
) TO 'out/convictions_ranked.csv' (HEADER, DELIMITER ',');
