-- 02_transform.sql
-- Question this step answers: which rows are real awarded dollars paid to a named vendor,
-- and what is the canonical vendor name for each?
--
-- Cleaning and validation rules (all deterministic):
--   Amount:  parse awarded_amount to a number, round to the cent, keep only positive
--            amounts. Zero, negative, and blank amounts are not award spend, so they drop.
--   Vendor:  decode the "&amp;" HTML entity, uppercase, turn every character that is not a
--            letter, digit, ampersand, or space into a space, then collapse runs of spaces.
--            This makes case and punctuation variants land on the same string.
--   Key:     from the cleaned name, strip trailing corporate-suffix words (LTD, LIMITED,
--            INC, CO, COMPANY, CORP, LP, LLP, ULC and their spellings). This merges legal-form
--            variants (for example "Dexter Construction", "Dexter Construction Co. Ltd.",
--            "DEXTER CONSTRUCTION COMPANY LIMITED") onto one vendor_key. It does not attempt
--            fuzzy or typo matching, which cannot be done from a rule alone.
--   Exclude: blank keys and placeholder keys that stand in for "not one vendor" (VARIOUS,
--            MULTIPLE VENDORS, N/A, NONE, and so on).

CREATE OR REPLACE TABLE clean_awards AS
WITH parsed AS (
  SELECT
    CAST(round(TRY_CAST(awarded_amount AS DOUBLE), 2) AS DECIMAL(18, 2)) AS award_amount,
    vendor AS vendor_raw,
    trim(regexp_replace(
      regexp_replace(
        upper(replace(coalesce(vendor, ''), '&amp;', '&')),
        '[^A-Z0-9& ]', ' ', 'g'),
      ' +', ' ', 'g')) AS vendor_clean
  FROM raw_tenders
),
keyed AS (
  SELECT
    award_amount,
    vendor_raw,
    vendor_clean,
    trim(regexp_replace(
      vendor_clean,
      '( (LTD|LIMITED|INC|INCORPORATED|CO|COMPANY|COMPANIES|CORP|CORPORATION|LP|LLP|ULC))+$',
      '', 'g')) AS vendor_key
  FROM parsed
)
SELECT
  award_amount,
  vendor_raw,
  vendor_key
FROM keyed
WHERE award_amount > 0
  AND vendor_key <> ''
  AND vendor_key NOT IN (
    'VARIOUS', 'VARIOUS VENDORS', 'MULTIPLE', 'MULTIPLE VENDORS',
    'N A', 'NA', 'NONE', 'TBD', 'TBA', 'UNKNOWN'
  );
