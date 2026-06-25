# Service-Level Dashboard

## Purpose
Reads a day of interval actuals and shows how each interval performed against the service-level
target: service level, abandon rate, average speed of answer, handle time, and occupancy. When the
staffing plan is loaded too, each interval is checked against the agents it was meant to have.

## Inputs
An actuals CSV, chosen with the file picker. Header row, then one row per interval:

| Column | Type | Meaning |
| --- | --- | --- |
| `interval` | text, `HH:MM` | start of the interval |
| `calls_offered` | whole number, 0 or more | calls that arrived |
| `calls_answered` | whole number, 0 or more | calls answered, cannot exceed offered |
| `answered_within_threshold` | whole number, 0 or more | answered inside the target time, cannot exceed answered |
| `total_wait_seconds` | number, 0 or more | total seconds callers waited before answer |
| `total_handle_seconds` | number, 0 or more | total seconds agents spent handling calls |
| `agents_scheduled` | whole number, 0 or more | agents on calls during the interval |

Optionally a staffing-plan CSV, the file the Staffing Planner exports. Only its `interval` and
`required_agents` columns are read, so a plan with extra columns still loads.

Two settings on the page: interval length in minutes (default 30) and service-level target percent
(default 80).

## Validation rules
- The actuals header must be exactly the seven columns above, or the file is rejected.
- Every data row must have exactly 7 fields, or it names the row and the count.
- `interval` must match `HH:MM`; a repeated interval is rejected as a duplicate, named by row.
- `calls_offered`, `calls_answered`, `answered_within_threshold`, and `agents_scheduled` must be
  whole numbers of 0 or more.
- `total_wait_seconds` and `total_handle_seconds` must be numbers of 0 or more.
- `calls_answered` cannot exceed `calls_offered`, named by row.
- `answered_within_threshold` cannot exceed `calls_answered`, named by row.
- The plan file must have `interval` and `required_agents` columns, or it is rejected.
- Interval length must be a positive number of minutes; service-level target must be 1 to 100.

## Logic
For each interval, with `interval_seconds = interval_minutes * 60`:

1. Service level: `answered_within_threshold / calls_offered`, as a percent.
2. Abandon rate: `(calls_offered - calls_answered) / calls_offered`, as a percent.
3. Average speed of answer: `total_wait_seconds / calls_answered`, in seconds.
4. Average handle time: `total_handle_seconds / calls_answered`, in seconds.
5. Occupancy: `total_handle_seconds / (agents_scheduled * interval_seconds)`, as a percent.
6. Coverage, when a plan is loaded: `agents_scheduled - required_agents`. A negative number is
   understaffed against plan.
7. An interval is a breach when its service level is below the target.
8. An interval with 0 calls reports 100% service level, 0 for the other rates, and no breach.
9. Overall service level for the day is volume-weighted: total answered within threshold over total
   offered, not the simple mean of the interval percents.
10. Percentages and seconds are rounded half up to 2 decimal places.

## Outputs
On the page: summary stats, a service-level bar per interval with a dashed line at the target and
breaches drawn in the breach colour, a coverage chart of scheduled against required agents (shown
only when a plan is loaded), and a table with each breach row highlighted.

## Edge cases
The sample actuals exercise a clean covered interval (`08:00`), two understaffed breaches (`09:00`
and `10:00`), and a zero-volume interval (`23:30`). The validation rules are checked by feeding in
`calls_answered` greater than `calls_offered` and a duplicate interval.

Hand-checked example, the `08:00` row of the sample actuals on a 30-minute interval: 98 offered,
96 answered, 82 within threshold, 1450 wait-seconds, 17400 handle-seconds, 14 agents scheduled.
Service level is `82 / 98 = 83.67%`. Abandon is `2 / 98 = 2.04%`. ASA is `1450 / 96 = 15.10s`.
AHT is `17400 / 96 = 181.25s`. Occupancy is `17400 / (14 * 1800) = 69.05%`. Against the staffing
plan, required is 14, so coverage is `14 - 14 = 0`. Service level 83.67% is above the 80% target,
so the interval is not a breach.
