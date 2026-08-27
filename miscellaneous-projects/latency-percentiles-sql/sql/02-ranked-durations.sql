-- The scaffold percentiles are built on: every request ranked inside its
-- endpoint by duration, with the endpoint's request count on each row.
-- ROW_NUMBER breaks ties arbitrarily, which is fine here: equal durations
-- give the same value whichever of them a rank lands on.
SELECT endpoint,
       duration_ms,
       ROW_NUMBER() OVER (PARTITION BY endpoint ORDER BY duration_ms) AS rn,
       COUNT(*) OVER (PARTITION BY endpoint) AS n
FROM requests
ORDER BY endpoint, rn;
