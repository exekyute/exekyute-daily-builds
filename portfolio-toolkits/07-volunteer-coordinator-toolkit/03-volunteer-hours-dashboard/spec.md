# Spec: Volunteer Hours Dashboard

## Purpose

Load a CSV of logged volunteer hours, total the hours for each volunteer, flag
the recognition milestones they have crossed, and call out anomalies such as
overlapping entries, an entry that runs too long, or too many hours logged in one
day. Rows that do not parse are listed separately with the reason, so the totals
only ever count clean data.

## Inputs

A CSV with the columns:

`entry_id, volunteer_id, volunteer_name, date, start_time, end_time`

- `date` is `YYYY-MM-DD`.
- `start_time` and `end_time` are 24-hour `HH:MM`.
- An entry does not cross midnight.

The CSV is loaded with the bundled sample, the bundled messy file, or a file the
user picks. Picked files are read in the browser with the `FileReader` API and
never sent anywhere.

Bundled files: `data/sample_hours.csv` (clean) and `data/messy_hours.csv` (one of
every branch).

A small config sets the behavior: milestone thresholds of `10, 25, 50, 100`
hours, a single-entry limit of `720` minutes (12 hours), and a daily limit of
`840` minutes (14 hours) per volunteer.

## Validation rules

Each row is parsed on its own. A row is rejected, with the reason recorded, when:

- it does not have exactly six fields (a short row or an extra column);
- a required field is blank;
- its `entry_id` repeats one already accepted (a duplicate);
- its `date` is not a real `YYYY-MM-DD` date;
- its `start_time` or `end_time` is not a real 24-hour `HH:MM` time; or
- its end time is not after its start time.

The header row is checked against the expected column names and a mismatch is
noted, but parsing continues.

## Logic

Each accepted entry's duration is `end_time` minus `start_time` in whole minutes,
so totals never drift the way fractional hours can. Hours are formatted as `H:MM`
only for display.

`parseCsv(text)` returns `{ rows, rejected, headerError }`. `summarize(rows,
config)` returns `{ totals, milestones, anomalies }`:

- `totals` is one row per volunteer with the entry count, total minutes, the
  `H:MM` total, and the highest milestone crossed. A total at exactly a
  threshold counts as crossed.
- `milestones` lists the volunteers who have crossed at least one threshold.
- `anomalies` lists, per volunteer, any overlapping entries on the same date
  (half-open ranges, so entries that only touch do not count), any single entry
  over the single-entry limit, and any date whose total is over the daily limit.

## Outputs

- A totals table: volunteer, entry count, total hours as `H:MM`, and a milestone
  badge.
- An anomalies panel tagged by kind: overlap, excessive entry, excessive daily.
- A rejected-rows panel naming each row that did not parse, the line number, the
  reason, and the raw text.
- A summary line counting entries, volunteers, milestones, anomalies, and
  rejected rows.

## Edge cases

- **Milestone boundary.** Ana Reyes logs exactly 600 minutes, which is 10 hours
  to the minute, and crosses the 10 hour milestone. Nine hours and change earns
  no milestone.
- **Touching entries are not an overlap.** Priya Nair logs `09:00-12:00` and
  `13:00-15:00` on one day with a clean gap, so neither is flagged. In the messy
  file Ana's `09:00-12:00` and `11:00-13:00` do overlap and are flagged.
- **Whole-minute totals.** Carmen's `10:00-12:30` is 150 minutes, shown as
  `2:30`, with no rounding.
- **One file, every branch.** `data/messy_hours.csv` carries a clean row, an
  overlapping pair, a single entry over the 12 hour limit, a day over the 14 hour
  limit, a short row, an extra column, a duplicate entry id, a bad date, a bad
  time, and an end before its start. The totals count only the clean rows, and
  every rejected row is named with its reason.
- **The blocked volunteer logs nothing.** Jordan Lee (V-105), blocked in the
  Onboarding Eligibility Validator, never appears in the clean hours. He shows up
  in the messy file only as a rejected duplicate row, never in a total, which
  fits a volunteer who was never cleared to serve.
