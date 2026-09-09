-- The trap. Matching a technician against a job with IN, or with any join
-- on the required certifications, answers "holds at least one of these".
-- The question worth asking is "holds every one of these", and the two
-- answers are not close: seven technicians touch the pump overhaul list
-- and two can actually do the job. The last row is the same mistake
-- running the other way. Yard cleanup requires nothing, so nothing can
-- match the IN list and the naive count reports zero qualified, while
-- every technician on the roster is in fact qualified for it.
SELECT j.job_id,
       j.job_name,
       (SELECT COUNT(*) FROM requirements r
        WHERE r.job_id = j.job_id) AS certs_required,
       (SELECT COUNT(DISTINCT h.tech_id) FROM holdings h
        WHERE h.cert IN (SELECT r.cert FROM requirements r
                         WHERE r.job_id = j.job_id)) AS matched_by_any,
       (SELECT COUNT(*) FROM technicians t
        WHERE NOT EXISTS (
            SELECT 1 FROM requirements r
            WHERE r.job_id = j.job_id
              AND NOT EXISTS (SELECT 1 FROM holdings h
                              WHERE h.tech_id = t.tech_id
                                AND h.cert = r.cert))) AS qualified
FROM jobs j
ORDER BY j.job_id;
