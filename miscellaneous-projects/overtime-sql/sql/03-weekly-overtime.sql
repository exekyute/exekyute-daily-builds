-- Minutes worked in each employee's week, and the overtime past 48 hours.
-- A week runs from 00:00 on Sunday to 00:00 the next Sunday. A shift still
-- going at that boundary is split there: the minutes before it stay in the
-- week the shift started, and the minutes after it are carried into the
-- next week, where they count toward that week's 48 hours. A shift runs at
-- most 24 hours, so it crosses at most one boundary, and a shift that ends
-- at exactly 00:00 on Sunday carries nothing over. The last column is the
-- first minute of overtime, the first minute worked once the week's 48
-- hours are done: a running total of minutes, shift by shift in start
-- order, finds the shift that passes 2880 minutes and how far into it that
-- happens.
WITH timed AS (
    SELECT
        employee,
        date(starts, '-6 days', 'weekday 0') AS week,
        CAST(strftime('%s', starts) AS INTEGER) / 60 AS start_min,
        CAST(strftime('%s', ends) AS INTEGER) / 60 AS end_min,
        CAST(strftime('%s', date(starts, '-6 days', 'weekday 0'), '+7 days') AS INTEGER) / 60 AS next_week_min
    FROM shifts
),
pieces AS (
    -- Part 0 is the shift up to the boundary, part 1 what runs past it.
    SELECT
        t.employee,
        CASE WHEN p.part = 0 THEN t.week ELSE date(t.week, '+7 days') END AS week,
        p.part,
        CASE WHEN p.part = 0 THEN t.start_min ELSE t.next_week_min END AS piece_start,
        CASE WHEN p.part = 0 THEN MIN(t.end_min, t.next_week_min) ELSE t.end_min END AS piece_end
    FROM timed t
    CROSS JOIN (SELECT 0 AS part UNION ALL SELECT 1) p
    WHERE p.part = 0 OR t.end_min > t.next_week_min
),
running AS (
    SELECT
        employee,
        week,
        part,
        piece_start,
        piece_end - piece_start AS minutes,
        SUM(piece_end - piece_start) OVER (PARTITION BY employee, week ORDER BY piece_start
                                           ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS through
    FROM pieces
),
weekly AS (
    SELECT
        employee,
        week,
        COUNT(*) AS shifts,
        SUM(CASE WHEN part = 1 THEN minutes ELSE 0 END) AS carried_in,
        SUM(minutes) AS worked,
        MAX(CASE WHEN through > 2880 AND through - minutes <= 2880
                 THEN piece_start + 2880 - (through - minutes) END) AS overtime_from
    FROM running
    GROUP BY employee, week
)
SELECT
    employee,
    week,
    shifts,
    printf('%d:%02d', carried_in / 60, carried_in % 60) AS carried_in,
    printf('%d:%02d', worked / 60, worked % 60) AS worked,
    printf('%d:%02d', MIN(worked, 2880) / 60, MIN(worked, 2880) % 60) AS regular,
    printf('%d:%02d', MAX(worked - 2880, 0) / 60, MAX(worked - 2880, 0) % 60) AS overtime,
    strftime('%Y-%m-%d %H:%M', overtime_from * 60, 'unixepoch') AS overtime_from
FROM weekly
ORDER BY employee, week;
