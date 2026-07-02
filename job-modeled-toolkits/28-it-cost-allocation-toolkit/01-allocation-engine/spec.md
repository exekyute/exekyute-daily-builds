# Allocation engine

## Purpose
Splits a pool of shared IT costs across departments by a driver such as headcount,
so each department sees its share of every cost item. This is the showback an IT
finance analyst runs each month. The workbook builder in `02` turns the result into
a chargeback workbook.

## Inputs
`cost_pool.csv`, one row per shared cost item:

| Column | Type | Meaning |
| --- | --- | --- |
| item | text | Cost item name |
| amount | number | Monthly amount for the item |

`drivers.csv`, one row per department:

| Column | Type | Meaning |
| --- | --- | --- |
| department | text | Department name |
| driver_value | number | The driver, for example headcount |

## Validation rules
- Pool: every field present, amount above zero, item not repeated.
- Drivers: every field present, driver_value zero or more, department not repeated,
  and the total driver value above zero.

## Logic
For each cost item, the amount is split across the departments in proportion to their
driver value, using the largest-remainder method: each share is floored to the cent,
then the leftover cents go one at a time to the departments with the largest fractional
remainder. This makes the parts of each item sum to the item exactly, so the department
totals sum to the whole pool with no cent lost. Each department's total is the sum of
its shares across the items, and its share of the pool is that total over the pool.

Money uses `decimal.Decimal` rounded half up to the cent.

## Outputs
`allocation_matrix.csv`, one row per department with its driver, its share of each cost
item, and its total. `department_summary.csv`, one row per department with its total and
its share of the pool.

## Edge cases
The largest-remainder method is what keeps an awkward split tied to the pool. The test
suite includes a pool that does not divide evenly across equal drivers, so the leftover
cent has to be placed, and confirms the parts still sum to the whole.
`drivers_invalid.csv` has a negative driver, so a run against it is rejected.

### Hand-checked example
A 100,000 pool of three items (Cloud hosting 60,000, Security tooling 25,000, Shared
licenses 15,000) split by headcount Engineering 40, Sales 25, Support 20, Finance 15
(100 total). Engineering takes 40 percent: 24,000.00 of cloud, 10,000.00 of security,
6,000.00 of licenses, for 40,000.00 in all. The four departments take 40,000.00,
25,000.00, 20,000.00, and 15,000.00, which sum to the 100,000.00 pool. The workbook
reproduces every figure with its own formulas, to the cent.
