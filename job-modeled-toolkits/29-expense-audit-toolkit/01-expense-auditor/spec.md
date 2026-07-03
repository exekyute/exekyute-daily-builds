# Expense auditor

## Purpose
Checks travel and expense lines against a policy and flags the ones that need
review: a mileage claim that does not match the rate, an amount over its category
cap, a missing receipt, or a duplicate. This is the first pass an expense or T&E
analyst runs before approving a batch. The browser review app in `02` reads the file
this tool writes.

## Inputs
`policy.csv`, the policy as param and value rows: `mileage_rate_per_km`,
`receipt_threshold`, and one `cap.<Category>` row per category cap. The mileage rate
is set to the prescribed allowance and is meant to be updated each year.

`expenses.csv`, one row per expense:

| Column | Type | Meaning |
| --- | --- | --- |
| expense_id | text | Unique expense identifier |
| date | date | Expense date, YYYY-MM-DD |
| employee | text | Who submitted it |
| category | text | Mileage or a category named in the policy |
| amount | number | Amount claimed |
| km | number | Kilometres, for a mileage claim |
| receipt | text | yes or no |

## Validation rules
- Every field present (km may be blank for a non-mileage line).
- Category is Mileage or one named in the policy.
- Date is a real date, amount above zero, km zero or more, receipt yes or no.
- A mileage claim has kilometres above zero.
- expense_id does not repeat.

## Logic
Each expense is given zero or more flags:

- MILEAGE_MISMATCH: a mileage claim whose amount is not kilometres times the rate.
- OVER_CAP: a category amount above its daily cap.
- NO_RECEIPT: an amount above the receipt threshold with no receipt.
- DUPLICATE: the same employee, date, category, and amount appearing more than once.

A line with no flags is approved; a flagged line is sent to review. Money uses
`decimal.Decimal` rounded half up to the cent.

## Outputs
`audited.csv`, one row per expense with its computed amount, its flags (joined by a
semicolon), and its status.

## Edge cases
The sample touches a clean mileage claim, a mileage mismatch, an over-cap meal, a
missing receipt, and a duplicate pair. `expenses_invalid.csv` has a category with no
policy, so a run against it is rejected.

### Hand-checked example
A 250 km mileage claim at 0.70 per km should be 175.00; expense E-01 claims exactly
that and is approved, while E-02 claims 220.00 for 300 km (210.00 by the rate) and is
flagged. Across the seven sample expenses, 890.00 is claimed, 475.00 is flagged for
review, and 415.00 is clean. The browser app reproduces every figure.
