-- 00_schema.sql
-- Question this step answers: what engine setup and tables does the pipeline
-- use, and why does this build need the spatial extension?
-- This is the one build in the batch that runs an actual spatial join: each
-- zoning polygon is assigned to the community whose boundary contains the
-- polygon's centroid. That needs point-in-polygon geometry, so the spatial
-- extension is loaded here (it stays loaded for the whole connection). The raw
-- tables are created in 01_load from the committed GeoJSON with ST_Read, which
-- infers the column types and exposes the polygon as a geom column, so no
-- explicit column list is declared here. Every table is dropped first so a
-- re-run starts from a clean, repeatable state.

INSTALL spatial;
LOAD spatial;

DROP TABLE IF EXISTS zoning_raw;
DROP TABLE IF EXISTS gsa_raw;
DROP TABLE IF EXISTS zoning_tagged;
DROP TABLE IF EXISTS mart_landuse;
DROP TABLE IF EXISTS community_mix_ranking;
DROP TABLE IF EXISTS class_area_overall;
DROP TABLE IF EXISTS headline;
