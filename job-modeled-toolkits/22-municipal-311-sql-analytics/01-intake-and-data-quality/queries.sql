-- Data-quality queries for the raw 311 intake.
--
-- Each query is preceded by a "-- name:" marker the runner uses to find it, and
-- a plain-language note on the question it answers. A row is treated as clean
-- only if it passes every check below. The clean_requests query is what the next
-- two tools read.

-- name: duplicate_ids
-- Which request ids were reported more than once? Later copies are dropped from
-- the clean set; the first copy by load order is kept.
SELECT request_id, COUNT(*) AS copies
FROM raw_requests
WHERE request_id IS NOT NULL
GROUP BY request_id
HAVING COUNT(*) > 1
ORDER BY request_id;

-- name: missing_fields
-- Which rows are missing a field the analysis needs (request id, opened date,
-- category, or department)?
SELECT load_seq, request_id, opened_date, category, department
FROM raw_requests
WHERE request_id IS NULL
   OR opened_date IS NULL
   OR category IS NULL
   OR department IS NULL
ORDER BY load_seq;

-- name: closed_before_opened
-- Which rows have a closed date that falls before the opened date? That cannot
-- happen, so the row is rejected.
SELECT load_seq, request_id, opened_date, closed_date
FROM raw_requests
WHERE closed_date IS NOT NULL
  AND closed_date < opened_date
ORDER BY load_seq;

-- name: status_inconsistent
-- Which rows have a status that disagrees with the close date? A Closed request
-- must have a close date, and an Open request must not.
SELECT load_seq, request_id, status, closed_date
FROM raw_requests
WHERE (status = 'Closed' AND closed_date IS NULL)
   OR (status = 'Open' AND closed_date IS NOT NULL)
ORDER BY load_seq;

-- name: clean_requests
-- The rows that pass every check, deduplicated to the first copy of each request
-- id. This is the dataset the backlog and SLA tools build on.
WITH flagged AS (
    SELECT load_seq
    FROM raw_requests
    WHERE request_id IS NULL
       OR opened_date IS NULL
       OR category IS NULL
       OR department IS NULL
       OR (closed_date IS NOT NULL AND closed_date < opened_date)
       OR (status = 'Closed' AND closed_date IS NULL)
       OR (status = 'Open' AND closed_date IS NOT NULL)
),
first_copy AS (
    SELECT request_id, MIN(load_seq) AS keep_seq
    FROM raw_requests
    WHERE request_id IS NOT NULL
    GROUP BY request_id
)
SELECT r.request_id, r.opened_date, r.closed_date, r.category, r.department, r.ward, r.status
FROM raw_requests r
JOIN first_copy fc ON fc.keep_seq = r.load_seq
WHERE r.load_seq NOT IN (SELECT load_seq FROM flagged)
ORDER BY r.opened_date, r.request_id;
