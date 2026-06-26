# Intake and data quality

## Purpose
Takes a raw export of 311 service requests and separates the rows that are safe to
analyze from the rows that have problems. It is the first step in the pipeline: the
clean rows it writes are what the backlog and SLA tools read. A 311 data analyst
would run this before any reporting so the later numbers rest on sound data.

## Inputs
A CSV of raw service requests, one row per request, with these columns:

- `request_id` (text) - the reference number for the request.
- `opened_date` (date, YYYY-MM-DD) - when the request was logged.
- `closed_date` (date, YYYY-MM-DD, or empty) - when it was resolved, empty if still open.
- `category` (text) - the type of request, for example Pothole or Graffiti.
- `department` (text) - the department that owns the request.
- `ward` (text) - the ward the request came from.
- `status` (text) - Open or Closed.

## Validation rules
- Every required column must be present in the header. If one is missing, the run
  stops with the list of missing columns.
- `opened_date` and `closed_date`, when present, must be real dates in YYYY-MM-DD
  form. A malformed date stops the run with the row number and the bad value, so a
  broken file never loads.

## Logic
The run reads the file, then runs five data-quality queries. A row is clean only if
it passes all four checks below; the fifth query collects the survivors.

1. Duplicate ids. Any `request_id` reported more than once is listed. The first copy
   by load order is kept; the later copies are dropped from the clean set.
2. Missing fields. Any row missing `request_id`, `opened_date`, `category`, or
   `department` is flagged and dropped.
3. Closed before opened. Any row whose `closed_date` is earlier than its
   `opened_date` is flagged and dropped.
4. Status disagrees with the close date. A Closed row must have a close date and an
   Open row must not. Rows that break this are flagged and dropped.
5. Clean requests. The rows that pass every check, deduplicated to the first copy of
   each id, sorted by opened date. These are written to `clean_requests.csv`.

No rounding happens in this tool. It only sorts requests into clean and flagged.

## Outputs
- A printed report: each flagged group as its own small table, then the clean rows.
- `clean_requests.csv` with the columns `request_id, opened_date, closed_date,
  category, department, ward, status`, holding only the clean rows.
- A checks block comparing the flagged and clean counts to the expected numbers,
  then `PASS` or `FAIL`.

## Edge cases
The sample data in `sample-requests.csv` is built so one run touches every branch.
Eighteen raw rows reduce to fourteen clean rows:

- Clean case: `R-1003`, a pothole opened and closed inside January.
- Boundary case: `R-1004`, closed exactly seven days after opening, which the SLA
  tool treats as on time rather than a breach.
- Duplicate: `R-1004` is reported a second time; the second copy is dropped.
- Missing field: `R-6001` has no category and is dropped.
- Closed before opened: `R-6002` has a close date before its open date and is dropped.
- Status inconsistency: `R-6003` is marked Closed but has no close date and is dropped.

Hand check: of the eighteen raw rows, exactly four are removed (one duplicate copy,
one missing field, one closed-before-opened, one status mismatch), leaving fourteen
clean rows. Running `python runner.py` prints these counts and `PASS`.

To see a file rejected outright, run `python runner.py bad-requests.csv`. Its first
row has `not-a-date` in `opened_date`, so the run stops with a clear message and does
not write any output.
