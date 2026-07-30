-- 02_transform.sql
-- Question this step answers: what does one clean, typed booking row look like, with
-- a real booking date, a use type, and a booked-hours figure?
--
-- The grain is one row per booking. Three fields are derived here:
--   booking_date  the Hub renders "Booking Date" as a YYYY-MM-DD string; parse to DATE.
--   use_type      ice vs dry floor is carried by SERVICE, not by EVENT_TYPE. A service
--                 whose text contains "Ice" is Ice; one that contains "Dry Floor" is
--                 Dry Floor; everything else (System Booking, Noon Hour) is Other.
--   booked_hours  the Hub renders "Booking Start" and "Booking End" as local datetime
--                 strings such as "4/1/2025 10:30:00 AM" (the ArcGIS service stores
--                 them as epoch milliseconds; the CSV export formats them). Parse both
--                 to timestamps and take the gap in hours, which equals the epoch-ms
--                 difference over 3,600,000 because a single booking never crosses a
--                 daylight-saving change, so its start and end share one local offset.
--
-- Guards: drop a row whose date or either timestamp fails to parse, whose facility or
-- service is blank, or whose span is not positive and at most 24 hours. That last
-- guard removes three zero-length bookings (start equals end) and would remove any
-- negative or longer-than-a-day span; the snapshot has no negative or over-24-hour
-- rows, so exactly three rows drop and 39,855 of 39,858 remain.

CREATE TABLE ab_clean AS
WITH parsed AS (
  SELECT
    trim(facility)                                                  AS facility,
    CAST(try_strptime(trim(booking_date), '%Y-%m-%d') AS DATE)      AS booking_date,
    trim(event_type)                                                AS event_type,
    trim(service)                                                   AS service,
    try_strptime(booking_start, '%-m/%-d/%Y %-I:%M:%S %p')          AS start_ts,
    try_strptime(booking_end,   '%-m/%-d/%Y %-I:%M:%S %p')          AS end_ts
  FROM ab_raw
)
SELECT
  facility,
  booking_date,
  CAST(date_trunc('month', booking_date) AS DATE)   AS month_start,
  year(booking_date)                                AS year,
  event_type,
  service,
  CASE
    WHEN contains(service, 'Ice')       THEN 'Ice'
    WHEN contains(service, 'Dry Floor') THEN 'Dry Floor'
    ELSE 'Other'
  END                                               AS use_type,
  round((epoch(end_ts) - epoch(start_ts)) / 3600.0, 3) AS booked_hours
FROM parsed
WHERE booking_date IS NOT NULL
  AND start_ts     IS NOT NULL
  AND end_ts       IS NOT NULL
  AND facility     IS NOT NULL AND facility <> ''
  AND service      IS NOT NULL AND service  <> ''
  AND (epoch(end_ts) - epoch(start_ts)) / 3600.0 >  0
  AND (epoch(end_ts) - epoch(start_ts)) / 3600.0 <= 24;
