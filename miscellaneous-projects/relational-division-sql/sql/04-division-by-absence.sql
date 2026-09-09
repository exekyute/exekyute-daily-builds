-- The same division stated as a double negative: keep the pairs for which
-- there is no required certification that this technician does not hold.
-- It starts from every technician rather than from the requirement rows,
-- so it never needs a group to exist, and a job requiring nothing lets
-- everyone through on the plain reading that none of its requirements is
-- unmet. The last column re-runs the counting test from query 03 against
-- the same pair, so the two constructions can be read against each other
-- row by row instead of taken on trust.
SELECT j.job_id,
       j.job_name,
       t.tech_id,
       t.name AS technician,
       CASE WHEN EXISTS (
           SELECT 1 FROM requirements r2
           JOIN holdings h2 ON h2.cert = r2.cert AND h2.tech_id = t.tech_id
           WHERE r2.job_id = j.job_id
           GROUP BY r2.job_id
           HAVING COUNT(DISTINCT r2.cert) = (SELECT COUNT(*) FROM requirements x
                                             WHERE x.job_id = j.job_id))
            THEN 'yes' ELSE 'no' END AS found_by_counting
FROM jobs j
CROSS JOIN technicians t
WHERE NOT EXISTS (
    SELECT 1 FROM requirements r
    WHERE r.job_id = j.job_id
      AND NOT EXISTS (SELECT 1 FROM holdings h
                      WHERE h.tech_id = t.tech_id
                        AND h.cert = r.cert))
ORDER BY j.job_id, t.name, t.tech_id;
