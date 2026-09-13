-- The log at a glance: how many calls, the first call and the last
-- hang-up, the minutes between them, and the minutes spent on calls. A
-- call holds a line from started_at up to ended_at, and ended_at is the
-- first minute the line was free again, so ended_at minus started_at is
-- the call's length. Times compare correctly as text because
-- YYYY-MM-DD HH:MM sorts in time order; lengths go through strftime('%s'),
-- so a call that runs past midnight still comes out right.
SELECT COUNT(*) AS calls,
       MIN(started_at) AS first_call,
       MAX(ended_at) AS last_hang_up,
       (strftime('%s', MAX(ended_at)) - strftime('%s', MIN(started_at))) / 60 AS span_minutes,
       SUM((strftime('%s', ended_at) - strftime('%s', started_at)) / 60) AS call_minutes
FROM calls;
