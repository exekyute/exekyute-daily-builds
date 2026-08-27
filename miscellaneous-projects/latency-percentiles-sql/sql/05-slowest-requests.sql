-- The three slowest requests per endpoint, with when they happened: the rows
-- an on-call engineer actually opens after the p99 looks wrong. The same
-- ROW_NUMBER scaffold, partitioned and ordered the other way, is the
-- standard top-N-per-group move.
WITH ranked AS (
    SELECT endpoint,
           request_ts,
           duration_ms,
           ROW_NUMBER() OVER (PARTITION BY endpoint ORDER BY duration_ms DESC, request_ts) AS slowness
    FROM requests
)
SELECT endpoint,
       slowness,
       duration_ms,
       request_ts
FROM ranked
WHERE slowness <= 3
ORDER BY endpoint, slowness;
