-- Relational division, written the way most people write it: join the
-- technician to the requirements they satisfy, count the distinct matches,
-- and keep the groups whose count equals the number of certifications the
-- job demands. It is correct wherever it produces a group, and the catch
-- is that a job requiring nothing produces no groups at all. Yard cleanup
-- is absent from this report entirely, and its absence reads exactly like
-- nobody qualifying rather than like a construction that cannot see it.
SELECT r.job_id,
       j.job_name,
       t.tech_id,
       t.name AS technician,
       COUNT(DISTINCT r.cert) AS certs_matched,
       (SELECT COUNT(*) FROM requirements x WHERE x.job_id = r.job_id) AS certs_required
FROM requirements r
JOIN jobs j ON j.job_id = r.job_id
JOIN holdings h ON h.cert = r.cert
JOIN technicians t ON t.tech_id = h.tech_id
GROUP BY r.job_id, j.job_name, t.tech_id, t.name
HAVING COUNT(DISTINCT r.cert) = (SELECT COUNT(*) FROM requirements x
                                 WHERE x.job_id = r.job_id)
ORDER BY r.job_id, t.name, t.tech_id;
