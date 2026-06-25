# Spec: Shift Coverage Planner

## Purpose

Take the shifts that need filling and the volunteers signed up for them, and
flag understaffed and overstaffed shifts and any volunteer double-booked across
overlapping shifts. Only cleared volunteers count toward coverage. Assigning an
uncleared volunteer is rejected and named, so a shift cannot be filled by
someone who is not cleared. The cleared roster this tool reads is the same file
the Onboarding Eligibility Validator produces.

## Inputs

- **Shifts**: each has `id`, `role`, `date` (`YYYY-MM-DD`), `start` and `end`
  (24-hour `HH:MM`), `min`, and `max`.
- **Assignments**: each is a `{ shiftId, volunteerId }` pair, one volunteer
  signed up for one shift.
- **Cleared roster**: a list of `{ id, name, cleared }`. This is the file the
  Onboarding Eligibility Validator emits, shipped here as
  `data/cleared_roster.json`.

Shifts and assignments are edited in the form or loaded from the bundled sample.
The cleared roster can be replaced by loading a `.json` file, read in the browser
with the `FileReader` API and never sent anywhere.

Bundled files: `data/shifts_sample.json`, `data/assignments_sample.json`, and
`data/cleared_roster.json`.

## Validation rules

A shift is **invalid** when its id is missing, its start or end is not a real
24-hour time, its end is not after its start, or its min and max are not whole
numbers with max at least min. An invalid shift is reported and does not get a
coverage count.

An assignment is **rejected**, and does not count toward coverage, when:

- its shift id is not in the schedule;
- it repeats a `{ shiftId, volunteerId }` pair already seen (a duplicate);
- the volunteer is not on the cleared roster; or
- the volunteer is on the roster but not cleared.

## Logic

All times are converted to whole minutes from midnight. Shifts are single-day.
Two time ranges overlap on a half-open basis: `[start, end)`, so two shifts that
only touch at a boundary, for example `09:00-12:00` and `12:00-15:00`, do not
overlap.

`planCoverage(shifts, assignments, roster)` returns `{ shifts, conflicts,
rejected, summary }`:

- Each shift gets a `clearedCount` of distinct cleared volunteers assigned to it
  and a `status` of `ok`, `understaffed`, `overstaffed`, or `invalid`.
  Understaffed is `clearedCount < min`; overstaffed is `clearedCount > max`.
- `conflicts` lists each volunteer booked on two overlapping valid shifts on the
  same date, with the conflicting shift pair. Only assignments that count toward
  coverage are considered.
- `rejected` lists each assignment that did not count, with the reason.

## Outputs

- A coverage table: role and id, date and time, cleared count against min and
  max, a status badge, and who fills the shift.
- A double-booked panel listing each volunteer on overlapping shifts.
- A rejected-assignments panel naming each assignment that did not count and why.
- A summary line counting covered, understaffed, overstaffed, double-booked, and
  rejected.

## Edge cases

- **An uncleared volunteer cannot fill a shift.** Jordan Lee (V-105) is
  `cleared: false` in `data/cleared_roster.json`, the same file the Onboarding
  Eligibility Validator produces, where he was blocked for a missing background
  check. He is the only volunteer assigned to the Setup crew shift (S-4, which
  needs 1). His assignment is rejected and the shift is left understaffed at
  `0 / 1, 1`. Onboarding blocking him and the planner refusing him are two views
  of the same decision. No cleared volunteer can be conjured, so the shift stays
  open until a cleared volunteer is assigned.
- **Touching shifts are not a conflict.** Ana Reyes (V-101) works `09:00-12:00`
  and `12:00-15:00` on the same day. The ranges meet at `12:00` but do not
  overlap, so she is not double-booked. Ben Cho (V-102) works `09:00-12:00` and
  `10:00-13:00`, which do overlap, so he is flagged.
- **Coverage boundaries.** S-1 sits exactly at its minimum (2 of 2 to 3) and is
  OK. S-2 sits exactly at both min and max (2 of 2, 2) and is OK. S-3 has three
  cleared volunteers against a max of 2 and is overstaffed.
- **One schedule, every branch.** The sample loads an OK shift, an understaffed
  shift, an overstaffed shift, an invalid shift, a duplicate assignment, an
  assignment to an unknown shift, a double-booking, and a boundary touch in a
  single plan.
