-- Pre-posting checks against the draft journal, the file where next month's
-- entries wait: entries whose debits and credits disagree, postings to
-- account codes the chart does not carry, and single-line entries that can
-- never balance. An empty result means the draft can post.
WITH per_entry AS (
    SELECT entry_id,
           COUNT(*) AS lines,
           SUM(COALESCE(debit_cents, 0)) AS debits,
           SUM(COALESCE(credit_cents, 0)) AS credits
    FROM draft_journal
    GROUP BY entry_id
)
SELECT 'unbalanced entry' AS issue,
       entry_id,
       printf('debits %.2f vs credits %.2f', debits / 100.0, credits / 100.0) AS detail
FROM per_entry
WHERE debits <> credits
UNION ALL
SELECT 'single-line entry',
       entry_id,
       'one line cannot balance'
FROM per_entry
WHERE lines = 1
UNION ALL
SELECT 'unknown account',
       d.entry_id,
       'account ' || d.account_code || ' is not in the chart'
FROM draft_journal d
WHERE d.account_code NOT IN (SELECT account_code FROM accounts)
ORDER BY issue, entry_id;
