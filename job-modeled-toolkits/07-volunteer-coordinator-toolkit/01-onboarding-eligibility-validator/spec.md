# Spec: Onboarding Eligibility Validator

## Purpose

Check a volunteer's completed requirements before they are scheduled. The page
flags an under-age volunteer, a missing or expired background check, any
incomplete required training, and a missing or expired waiver. A volunteer is
cleared only when every requirement is met. The cleared roster it produces is
the same roster the Shift Coverage Planner consumes, so a volunteer cleared here
is safe to schedule there.

## Inputs

A reference config, shown on the page and editable:

- `as_of_date` (`YYYY-MM-DD`): the date clearance is judged against.
- `minimum_age`: the lowest age a volunteer may be on the as-of date.
- `required_trainings`: the list of training codes every volunteer must have.
- `background_check_valid_days`: how long a passed check stays current.
- `waiver_valid_days`: how long a signed waiver stays current.

A list of volunteers, each with:

- `id` and `name`.
- `date_of_birth` (`YYYY-MM-DD`).
- `background_check`: `{ status, date }` where status is `passed`, `failed`, or
  `none`.
- `trainings_completed`: a list of training codes.
- `waiver_signed_date` (`YYYY-MM-DD`, or blank if unsigned).

The roster can be edited in the form, loaded from a `.json` file, or replaced
with a bundled sample. Files are read in the browser with the `FileReader` API
and never sent anywhere.

Bundled files: `data/volunteers_sample.json` (the realistic roster, five cleared
and one blocked), `data/volunteers_flagged.json` (one of every flag), and
`data/cleared_roster.json` (the output the Shift Coverage Planner reads).

## Validation rules

Each problem becomes a finding with a code, a location, and a plain message.
Every finding blocks clearance. A volunteer with no findings is cleared.

- **Missing id** or **missing name**.
- **Bad date of birth**: missing or not a real `YYYY-MM-DD` date.
- **Under age**: age on the as-of date is below `minimum_age`.
- **Background check missing**: no check on file, or status `none`.
- **Background check not passed**: status is `failed`.
- **Background check bad date**: the check date is not a real date, or is after
  the as-of date.
- **Background check expired**: the check is older than
  `background_check_valid_days` on the as-of date.
- **Training missing**: a required code is not in `trainings_completed`. One
  finding per missing code.
- **Waiver missing**: no signed waiver.
- **Waiver bad date** or **waiver expired**: same dating rules as the background
  check, using `waiver_valid_days`.
- **Duplicate id**: a volunteer id used more than once. Flagged on the second
  and later uses.

## Logic

The rules are pure functions over a volunteer object. `evaluate(volunteer,
config)` returns `{ id, name, cleared, findings }`, where `cleared` is true when
there are no findings. `evaluateRoster(volunteers, config)` runs every volunteer,
adds the duplicate-id check across the roster, and returns the per-volunteer
results plus a summary `{ total, clearedCount, blockedCount }`.
`toClearedRoster(...)` reduces that to `[{ id, name, cleared }]`, the exact shape
the Shift Coverage Planner reads.

Dates are plain `YYYY-MM-DD` strings. `daysBetween` and `ageOn` work in UTC so
the day math carries no timezone drift, and `parseYmd` rejects dates that are not
real calendar days (for example `2026-02-30`). Age uses the calendar: a
volunteer who turns the minimum age exactly on the as-of date clears.

## Outputs

- A results table: each volunteer with a green **Cleared** badge or a red
  **Blocked** badge and the list of reasons.
- A summary line counting cleared versus blocked.
- A cleared-roster preview in `[{ id, name, cleared }]` form, the file the Shift
  Coverage Planner uses.

## Edge cases

- **Exactly minimum age clears.** Dev Patel (V-104) is born `2008-06-01` and the
  as-of date is `2026-06-01`, so he is 18 to the day and clears.
- **The background-check window is inclusive.** Priya Nair (V-106) has a check
  dated `2025-06-01`, exactly 365 days before the as-of date, and clears. One day
  earlier would expire.
- **The cross-tool block.** Jordan Lee (V-105) has no background check, so he is
  blocked here and marked `cleared: false` in `data/cleared_roster.json`. That is
  the same file the Shift Coverage Planner ships, where the planner refuses to
  let him fill a shift. Onboarding blocking him and the planner refusing him are
  two views of the same decision.
- **One file, every flag.** `data/volunteers_flagged.json` trips under age, a
  missing check, a failed check, an expired check, a missing training, a missing
  waiver, an expired waiver, a duplicate id, a bad date of birth, a missing name,
  a missing id, and bad check and waiver dates, all from a single load.
