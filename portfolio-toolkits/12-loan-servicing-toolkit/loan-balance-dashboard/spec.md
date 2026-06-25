# Loan Balance Dashboard, specification

## Purpose

Load the amortization CSV produced by the Amortization Schedule Generator
entirely in the browser using the `FileReader` API, render a table of each
period's payment, interest, principal, and remaining balance, and show a summary
line with the total interest paid and the total of payments over the life of the
loan. Money is handled in integer cents and formatted with `Intl.NumberFormat`,
so amounts never show floating-point artifacts. No data leaves the browser.

## Inputs

A CSV file chosen with the file input. It must have the header
`period,payment,interest,principal,balance` and one row per period, exactly the
shape the generator writes.

## Validation rules

Problems are reported on the page and the table does not render when any check
fails. Every problem found is listed, not just the first.

- The file must not be empty and must have the exact expected header.
- The file must have at least one schedule row after the header.
- Each row must have exactly five fields. A short or extra row is rejected with
  its line number.
- `period` must be a whole number of 1 or more.
- `payment`, `interest`, `principal`, and `balance` must each be a non-negative
  dollar amount with at most two decimal places. Letters, signs, and over-long
  decimals are rejected.

## Logic

1. Read the file text with `FileReader.readAsText`.
2. Split the text into non-empty lines, tolerating Windows or Unix line endings.
3. Check the header, then parse each row. Convert every dollar amount to an
   integer number of cents with `dollarsToCents`; no floating-point arithmetic is
   ever done on money.
4. Sum the payment cents into the total of payments and the interest cents into
   the total interest paid.
5. Format every displayed amount from cents with `Intl.NumberFormat` (USD, two
   decimals).

## Outputs

- A table with one row per period: period, payment, interest, principal, and
  remaining balance.
- A summary with the number of periods, the total interest paid, the total of
  payments, and the final balance, which reads `$0.00` for a complete schedule.

## Edge cases

- A schedule whose final balance is `0.00` shows a closed loan in the summary.
- Zero-interest rows display `$0.00` interest cleanly.
- A single decimal place such as `3.4` is read as `$3.40`, not three cents.
- A malformed CSV (wrong header, ragged rows, non-numeric or negative amounts) is
  rejected with every reason listed and renders no table. The shipped
  `sample_data/schedule_invalid.csv` exercises a short row, a non-numeric amount,
  a negative amount, and an extra-field row at once.

## Hand-checked example

Loading `sample_data/schedule.csv`, the six-period output of the generator's
`1000.00 / 12% / 6` loan, yields:

- Total interest paid: `$35.28`
- Total of payments: `$1,035.28`
- Final balance: `$0.00`

These match the generator's printed summary exactly, and the total of payments
equals the `1000.00` principal plus the `35.28` of interest.
