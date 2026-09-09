-- The roster at a glance. The last two columns are the ones to remember:
-- one technician holds no certification at all and one job requires none.
-- Neither is a data error, both are ordinary, and each one breaks a
-- different popular way of writing the question this build is about.
SELECT (SELECT COUNT(*) FROM technicians) AS technicians,
       (SELECT COUNT(*) FROM jobs) AS jobs,
       (SELECT COUNT(*) FROM holdings) AS holdings,
       (SELECT COUNT(*) FROM requirements) AS requirements,
       (SELECT COUNT(DISTINCT cert) FROM holdings) AS certs_held,
       (SELECT COUNT(DISTINCT cert) FROM requirements) AS certs_required,
       (SELECT COUNT(*) FROM technicians t
        WHERE NOT EXISTS (SELECT 1 FROM holdings h
                          WHERE h.tech_id = t.tech_id)) AS techs_holding_nothing,
       (SELECT COUNT(*) FROM jobs j
        WHERE NOT EXISTS (SELECT 1 FROM requirements r
                          WHERE r.job_id = j.job_id)) AS jobs_requiring_nothing;
