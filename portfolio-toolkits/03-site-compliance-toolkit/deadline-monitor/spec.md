# Spec: Regulatory Deadline Monitor

## Purpose

Read a log of environmental compliance requirements, each with a due date,
compare every due date to a chosen "today", and print a dashboard that groups the
work by urgency so nothing overdue is missed. It can also read the unified ledger
built by the waste and fuel aggregator and flag any site that has operational
activity but no tracked compliance deadline.

## Inputs

- `data/compliance_log.csv` with the columns `site, requirement, due_date, status`.
  `due_date` is written as `YYYY-MM-DD`. `status` is `open` or `complete`.
- A current date. By default the tool uses the real today. Pass `--today YYYY-MM-DD`
  to fix the date so the dashboard is reproducible (used for the screenshots).
- An optional unified ledger to cross-check against. By default it looks for the
  aggregator's `../waste-fuel-aggregator/output/unified_ledger.csv`.

## Validation rules

- A `due_date` that is not strictly `YYYY-MM-DD` (with leading zeros) is rejected,
  so a date is never ambiguous.
- A row with a blank site or a blank requirement is rejected.
- A status that is not `open` or `complete` is treated as `open` and reported.
- A repeated `site + requirement` is reported as a duplicate and counted once.
- Every rejected row is listed with its row number and a reason.

## Logic

1. Read the log and validate every row, keeping the clean ones.
2. For each open item, compute `days_until = due_date - today` and sort it into a
   band:
   - `OVERDUE` when `days_until` is below 0,
   - `DUE TODAY` when `days_until` is exactly 0,
   - `DUE SOON` when `days_until` is 1 to 14 (the `DUE_SOON_DAYS` constant),
   - `UPCOMING` when `days_until` is above 14.
3. Completed items go into a separate `COMPLETE` band regardless of date.
4. Sort each band by due date then site.
5. Load the distinct sites from the unified ledger and flag any that have no
   tracked deadline (a compliance gap).
6. Print the dashboard and write a copy to `output/dashboard.txt`.

## Outputs

- A printed dashboard grouped by urgency band, each line showing the explicit due
  date, the site, the requirement, and a plain day count (for example
  `due in 4 days`, `due today`, `17 days overdue`).
- A cross-check section listing the ledger sites and any compliance gap.
- A copy of the dashboard written to `output/dashboard.txt`.

## Edge cases

The sample data is built so a single run (with `--today 2026-06-06`) exercises
each of these:

| Case | Entry | Result |
| --- | --- | --- |
| Overdue item | Stormwater permit renewal, 2026-05-20 | OVERDUE, 17 days |
| Due exactly today (boundary) | Air quality self-report, 2026-06-06 | DUE TODAY |
| Due soon | Spill kit inspection, 2026-06-10 | DUE SOON, 4 days |
| Due in exactly 14 days (boundary) | Hazardous waste manifest, 2026-06-20 | DUE SOON, 14 days |
| Upcoming | Annual compliance audit, 2026-08-01 | UPCOMING |
| Completed | Q1 emissions report, 2026-04-15 | COMPLETE |
| Bad date format | Tank integrity test, 06/01/2026 | rejected |
| Blank site | Safety checklist sign-off | rejected |
| Duplicate | Stormwater permit renewal (again) | reported |
| Unknown status | Noise monitoring report, status `pending` | kept as open, reported |
| Site with activity, no deadline | Ridge Site (in ledger only) | compliance gap |

## Hand-checked cross-tool value

The aggregator's ledger holds **3 distinct sites**: Harbor Site, North Site, and
Ridge Site. This monitor reads that same ledger, confirms the same count of 3, and
checks each one against the compliance log. North Site and Harbor Site both have
tracked deadlines, while Ridge Site has waste and fuel activity but no deadline, so
it is reported as a compliance gap. Both tools agreeing on the count of 3 sites is
the documented proof that they see the same site list. See the aggregator spec for
the matching note.
