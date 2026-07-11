-- 00_schema.sql
-- Question: what relations does this build use, and how do we start from a clean slate?
-- Dropping first makes a fresh `python run.py` reproducible even on a reused connection.
-- No data is touched here; the load happens in 01_load.sql.

DROP VIEW  IF EXISTS surplus_league;
DROP VIEW  IF EXISTS municipal_operating;
DROP TABLE IF EXISTS raw_operating_fund;
