-- The useful complement of the division: the technicians who fail a job by
-- exactly one certification, and which one. A qualified-or-not answer says
-- who can work today; this says what the shortest path to more coverage
-- is. Every row here is one course booking away from turning into a row of
-- query 04. Technicians missing two or more are left out on purpose, since
-- the point of the report is the near edge, not the whole gap. The id rides
-- along with the name in all three reports, because two people on one crew
-- can share a name and a reader has to be able to tell their rows apart.
SELECT r.job_id,
       j.job_name,
       t.tech_id,
       t.name AS technician,
       r.cert AS missing_cert
FROM requirements r
JOIN jobs j ON j.job_id = r.job_id
CROSS JOIN technicians t
WHERE NOT EXISTS (SELECT 1 FROM holdings h
                  WHERE h.tech_id = t.tech_id AND h.cert = r.cert)
  AND (SELECT COUNT(*) FROM requirements r2
       WHERE r2.job_id = r.job_id
         AND NOT EXISTS (SELECT 1 FROM holdings h2
                         WHERE h2.tech_id = t.tech_id
                           AND h2.cert = r2.cert)) = 1
ORDER BY r.job_id, t.name, t.tech_id;
