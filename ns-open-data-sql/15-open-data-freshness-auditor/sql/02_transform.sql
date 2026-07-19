-- 02_transform.sql
-- Question this step answers: what does one clean, typed row per catalogued
-- asset look like, and what freshness bucket does each asset land in?

-- The pull date is the single determinism anchor. Every age in the pipeline is
-- measured against this literal date, never CURRENT_DATE, so the same pinned
-- snapshot always produces byte-identical output no matter when it re-runs.
CREATE TABLE params AS
SELECT DATE '2026-07-06' AS pull_date;

-- Clean layer: trim text, backfill blank groupings with explicit placeholder
-- labels, pull the asset's 4x4 id out of its portal URL, and cast the two
-- Socrata timestamps to dates. Rows without a name would be unidentifiable,
-- so they are dropped (the pinned snapshot has none).
CREATE TABLE catalogue_clean AS
SELECT
  regexp_extract(trim(url), '([a-z0-9]{4}-[a-z0-9]{4})$', 1)          AS uid,
  trim(name)                                                          AS name,
  lower(trim(type))                                                   AS type,
  coalesce(nullif(trim(category), ''), '(uncategorized)')             AS category,
  coalesce(nullif(trim(detailedmetadata_department), ''), '(no department)')
                                                                      AS owner,
  CAST(try_cast(last_data_updated_date     AS TIMESTAMP) AS DATE)     AS last_data_updated,
  CAST(try_cast(last_metadata_updated_date AS TIMESTAMP) AS DATE)     AS last_metadata_updated
FROM catalogue_raw
WHERE name IS NOT NULL AND trim(name) <> '';

-- Audit layer, one row per asset (this is also the BI mart). last_updated
-- prefers the data-updated date and falls back to the metadata-updated date;
-- age_months counts month boundaries between last_updated and the pull date.
-- Buckets: Fresh under 6 months, Aging 6 to 11, Stale 12 to 23, Dormant 24 and
-- up, No date when neither source date parsed. stale_or_dormant is the flag
-- the headline percent and the BI measures count.
CREATE TABLE asset_audit AS
WITH aged AS (
  SELECT
    c.uid,
    c.name,
    c.type,
    c.category,
    c.owner,
    coalesce(c.last_data_updated, c.last_metadata_updated) AS last_updated,
    date_diff(
      'month',
      coalesce(c.last_data_updated, c.last_metadata_updated),
      p.pull_date
    ) AS age_months
  FROM catalogue_clean c
  CROSS JOIN params p
)
SELECT
  uid,
  name,
  type,
  category,
  owner,
  last_updated,
  age_months,
  CASE
    WHEN last_updated IS NULL THEN 'No date'
    WHEN age_months < 6  THEN 'Fresh'
    WHEN age_months < 12 THEN 'Aging'
    WHEN age_months < 24 THEN 'Stale'
    ELSE 'Dormant'
  END AS bucket,
  CASE
    WHEN last_updated IS NULL THEN 5
    WHEN age_months < 6  THEN 1
    WHEN age_months < 12 THEN 2
    WHEN age_months < 24 THEN 3
    ELSE 4
  END AS bucket_order,
  CASE
    WHEN last_updated IS NOT NULL AND age_months >= 12 THEN 1
    ELSE 0
  END AS stale_or_dormant
FROM aged;
