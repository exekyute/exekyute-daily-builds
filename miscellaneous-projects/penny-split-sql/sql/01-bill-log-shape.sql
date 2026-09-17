-- The bill log at a glance: how many bills there are, how many departments
-- they are split across, how many split rows that takes, and the total
-- billed. Amounts are held in whole cents and printed as money.
SELECT (SELECT COUNT(*) FROM bills) AS bills,
       (SELECT COUNT(DISTINCT department) FROM splits) AS departments,
       (SELECT COUNT(*) FROM splits) AS splits,
       (SELECT printf('%d.%02d', SUM(amount_cents) / 100, SUM(amount_cents) % 100)
        FROM bills) AS billed;
