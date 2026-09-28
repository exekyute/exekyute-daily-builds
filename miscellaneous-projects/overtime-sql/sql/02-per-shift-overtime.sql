-- Overtime the tempting way, twice over. Each shift is taken whole into the
-- week it starts in, and overtime is counted shift by shift: anything past
-- eight hours in a shift, as if each shift were a day under a daily rule.
-- Nova Scotia has no daily rule. Its overtime starts past 48 hours in a
-- week, so the per-shift column finds overtime in long shifts in weeks that
-- never reach 48 hours, and none in a week of many shorter shifts that
-- passes 48. The last column applies the 48-hour rule, but to the hours
-- grouped by the week each shift starts in, so a shift still going at 00:00
-- on Sunday puts its hours after midnight in the wrong week.
WITH timed AS (
    SELECT
        employee,
        date(starts, '-6 days', 'weekday 0') AS week,
        (CAST(strftime('%s', ends) AS INTEGER) - CAST(strftime('%s', starts) AS INTEGER)) / 60 AS minutes
    FROM shifts
)
SELECT
    employee,
    week,
    COUNT(*) AS shifts,
    printf('%d:%02d', SUM(minutes) / 60, SUM(minutes) % 60) AS worked,
    printf('%d:%02d', SUM(MAX(minutes - 480, 0)) / 60, SUM(MAX(minutes - 480, 0)) % 60) AS over_8_a_shift,
    printf('%d:%02d', MAX(SUM(minutes) - 2880, 0) / 60, MAX(SUM(minutes) - 2880, 0) % 60) AS over_48_by_start
FROM timed
GROUP BY employee, week
ORDER BY employee, week;
