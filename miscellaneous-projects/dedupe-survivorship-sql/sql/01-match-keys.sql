-- How many customers the records make under six ways of matching them, and
-- what each way gets wrong. The match key, the last way, is built in three
-- steps that every query here repeats. The name is lower-cased and each run
-- of spaces in it collapsed to one: every space becomes <>, the >< pairs
-- that a run leaves are dropped, and the <> left over from each run becomes
-- one space. The loader refuses < and > in a name and has already stripped
-- spaces from both ends. The phone number keeps its digits only: the loader
-- allows nothing in a number but digits, spaces, hyphens, dots, brackets and
-- a plus sign, and a leading 1 on eleven digits is dropped, so +1 902 555
-- 0114 and (902) 555-0114 are one number. A record with no number gets its
-- own record reference in place of one, so it matches nothing but itself.
-- For each way the columns count the customers it makes, the customers made
-- of more than one record, and the customers that hold two different names
-- (names that differ in more than letter case and the length of a run of
-- spaces), two different numbers, or a record with no number beside another
-- record.
WITH
cleaned AS (
    SELECT
        *,
        lower(replace(replace(replace(full_name, ' ', '<>'), '><', ''), '<>', ' ')) AS name_key,
        replace(replace(replace(replace(replace(replace(phone,
            ' ', ''), '-', ''), '.', ''), '(', ''), ')', ''), '+', '') AS digits,
        source || ' ' || record_no AS record
    FROM customers
),
numbered AS (
    SELECT
        *,
        CASE WHEN length(digits) = 11 AND substr(digits, 1, 1) = '1' THEN substr(digits, 2)
             ELSE digits END AS number
    FROM cleaned
),
keyed AS (
    SELECT *, name_key || '|' || COALESCE(number, record) AS match_key
    FROM numbered
),
ways(way, match_on) AS (
    VALUES (1, 'each record alone'),
           (2, 'email, lower case'),
           (3, 'phone number, digits only'),
           (4, 'name, lower case, spaces collapsed'),
           (5, 'name and number, blank numbers matched'),
           (6, 'name and number, blank numbers apart')
),
grouped AS (
    -- A blank email or number is NULL, and GROUP BY puts every NULL in one
    -- group, so ways 2 and 3 lump together every record missing that value.
    SELECT
        w.way,
        w.match_on,
        COUNT(*) AS records,
        COUNT(DISTINCT k.name_key) AS names,
        COUNT(DISTINCT k.number) AS numbers,
        SUM(k.number IS NULL) AS without_number
    FROM ways w
    CROSS JOIN keyed k
    GROUP BY w.way, w.match_on, CASE w.way
        WHEN 1 THEN k.record
        WHEN 2 THEN lower(k.email)
        WHEN 3 THEN k.number
        WHEN 4 THEN k.name_key
        WHEN 5 THEN k.name_key || '|' || COALESCE(k.number, '')
        ELSE k.match_key END
)
SELECT
    match_on,
    COUNT(*) AS customers,
    SUM(records > 1) AS merged,
    SUM(names > 1) AS two_names,
    SUM(numbers > 1) AS two_numbers,
    SUM(records > 1 AND without_number > 0) AS no_number
FROM grouped
GROUP BY way, match_on
ORDER BY way;
