# Net Pay Dashboard, spec

## Purpose
Load the payroll register CSV produced by the Payroll Run Calculator and render
a readable per-employee table plus a run summary. The file is read in the
browser with the FileReader API and is never sent anywhere.

## Inputs
The payroll register CSV, chosen with a file input. It must have this exact
header:

```
employee_id,name,pay_type,gross_pay,overtime_pay,pretax_deductions,cpp,ei,income_tax,posttax_deductions,total_deductions,net_pay
```

## Validation rules
- The header must contain exactly the twelve register columns. A wrong or
  missing header stops the load and shows which columns are missing or extra.
- A row whose field count does not match the header is reported and skipped.
- A row with a non-numeric value in any money column is reported and skipped.
- An empty file or a header-only file is handled without error and renders no
  rows.

## Logic
Pure functions live in `dashboard_logic.js` and take input, return values, and
touch no DOM. All money is handled as integer cents.

1. Split the CSV text into a header and rows, honouring simple quoted values.
2. Validate the header against the required columns.
3. Convert each money field to integer cents on read with `toCents`.
4. Build a record per valid row with the columns the table shows.
5. Sum total gross and total net across valid records, in cents.
6. Format amounts only at display time with `Intl.NumberFormat` for `en-CA` in
   Canadian dollars, so no floating-point artifacts ever appear.

## Outputs
- A table with one row per employee: employee, pay type, gross, overtime, total
  deductions, income tax, and net pay.
- A run summary: employee count, total gross, and total net.
- A status line and, when needed, a list of skipped rows or header problems.

## Edge cases
Loading the bundled `data/payroll_register.csv` renders all five employees,
including the zero-hours employee at 0.00 and the high earner whose CPP and EI
sit at the per-period caps. Pointing the tool at a non-register CSV shows a
header rejection. A row with the wrong field count or a non-numeric amount is
listed as skipped rather than rendered.

## Hand-checked example
Employee E002, Bianca Tran, in the register reads gross 1590.00 and net 1094.01.
The dashboard parses this to 159000 and 109401 cents and displays a net pay of
$1,094.01, matching the calculator to the cent. The same example is documented
in the calculator's spec.
