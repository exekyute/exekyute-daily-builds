# Spec: Operational Field Audit Validator

## Purpose

An interactive command line questionnaire for site inspectors. It asks a fixed
set of questions, forces each answer to be the right type, and keeps asking until
a valid value is given, so a typo is corrected on the spot rather than landing in
the record. When every answer is in and confirmed, it appends one timestamped line
to a text log.

## Inputs

- Typed answers to the questions defined in `questions.py`. The default set is:
  - site code: one of `NORTH`, `HARBOR`, `RIDGE` (a choice)
  - inspection date: `YYYY-MM-DD` (a date)
  - inspector name: any non-empty text
  - fuel tank reading: a non-negative number
  - inspection result: `PASS` or `FAIL` (a choice)
  - notes: any non-empty text
- A final yes or no to confirm saving.

## Validation rules

Each rule is a pure function in `core.py`, so it can be tested on its own:

- text: rejected if blank after trimming spaces.
- date: accepted only as `YYYY-MM-DD` with leading zeros, and must be a real
  calendar date, so `06/06/2026` and `2026-02-30` are both rejected.
- number: must be a number and not negative.
- choice: must match one of the listed options, ignoring case, and is stored in
  the canonical spelling.

An invalid answer is explained and asked again. The loop never crashes and never
records a bad value.

## Logic

1. Ask each question in `questions.py` in order.
2. For each answer, run the validator named by the question type. On failure,
   print the reason and ask the same question again.
3. When all answers are valid, show a summary for review.
4. Ask for confirmation. Only a clear yes saves the entry.
5. Build a timestamp as `YYYY-MM-DD HH:MM:SS` and append one pipe-delimited line
   to the log.

## Outputs

- A single appended line per confirmed audit in `audit_log.txt`, formatted as:

  ```
  timestamp | site_code | inspection_date | inspector | fuel_reading | result | notes
  ```

  for example:

  ```
  2026-06-06 14:30:00 | NORTH | 2026-06-05 | Jane Smith | 12.50 | PASS | all clear
  ```

- The number is written as fixed-point with two decimals. Any stray pipe or line
  break typed into a text answer is replaced with a space so the columns stay
  intact.

## Edge cases

A single walkthrough exercises every branch by typing one invalid answer of each
type before the valid one:

| Question | Invalid answer | Result |
| --- | --- | --- |
| Site code | `east` | rejected, asked again |
| Inspection date | `06/05/2026` | rejected, asked again |
| Inspector name | (blank) | rejected, asked again |
| Fuel reading | `-3` | rejected, asked again |
| Result | `maybe` | rejected, asked again |
| Notes with a stray `\|` | `leak \| near pump` | saved as one column, pipe neutralised |
| Confirmation | anything other than yes | nothing is saved |

## Note on the toolkit

This tool stands on its own and does not read the other two tools. Its site codes
(`NORTH`, `HARBOR`, `RIDGE`) match the sites used across the aggregator and the
deadline monitor, so a recorded audit reads naturally alongside them.
