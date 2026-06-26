# Investor Allocation Dashboard, specification

## Purpose

Show a clear, investor-facing view of a capital call allocation. The page loads
an allocation CSV produced by the Capital Call Allocator and lists each
investor's commitment, ownership percentage, called amount, and remaining
unfunded commitment, with a summary line across the whole fund. The file is read
in the browser and is never uploaded.

## Inputs

A single allocation CSV chosen with the file picker. The expected header is:

```
investor,commitment,ownership_pct,called_amount
```

This is exactly what the Capital Call Allocator writes. A copy lives in
`sample_data/allocation.csv`.

## Validation rules

The page reports a clear message and shows no table when:

- The file is empty.
- The header is not `investor,commitment,ownership_pct,called_amount`.
- There are no investor rows.
- A row does not have exactly four fields (the line number is named).
- An investor name is blank.
- A commitment or called amount is not a valid dollar figure.

## Logic

1. Read the file text with the `FileReader` API.
2. Split the text into a header and rows.
3. Convert every dollar value to whole cents so the arithmetic stays exact.
4. For each investor, compute the remaining unfunded commitment as
   `commitment - called`, and recompute the ownership percentage as
   `commitment / total commitment * 100`. Recomputing ownership is a cross-check
   against the value the allocator wrote.
5. Sum the commitments, called amounts, and remaining amounts for the summary.
6. Format every dollar value with `Intl.NumberFormat` for display.

All money handling is in integer cents. Dollars appear only at the formatting
step, so no floating-point artifacts can reach the screen.

## Outputs

An on-screen table with one row per investor (investor, commitment, ownership,
called amount, remaining unfunded) and a summary line showing the investor count,
total commitment, total called, and total remaining unfunded. Nothing is written
to disk and nothing leaves the browser.

## Edge cases

- A zero-commitment investor shows as 0.00 commitment, 0.0000% ownership,
  0.00 called, and 0.00 remaining.
- A malformed file (wrong header, short or long row, non-numeric amount) shows a
  plain message naming the problem and leaves the previous table hidden.
- Wide tables scroll sideways inside their container rather than breaking the
  page layout.

## Cross-tool agreement (hand-checked example)

`sample_data/allocation.csv` is the exact output of the Capital Call Allocator
for a 250,000.00 call across Aurora Capital, Brightwater LP, Cedar Grove
Partners, Dunes Family Office, and Echo Ventures (see the allocator's `spec.md`).
Loaded into this dashboard, the figures reconcile:

| Investor              | Commitment     | Ownership | Called      | Remaining unfunded |
| --------------------- | -------------- | --------- | ----------- | ------------------ |
| Aurora Capital        | $4,000,000.00  | 36.3636%  | $90,909.09  | $3,909,090.91      |
| Brightwater LP        | $3,500,000.00  | 31.8182%  | $79,545.46  | $3,420,454.54      |
| Cedar Grove Partners  | $2,500,000.00  | 22.7273%  | $56,818.18  | $2,443,181.82      |
| Dunes Family Office   | $1,000,000.00  |  9.0909%  | $22,727.27  | $977,272.73        |
| Echo Ventures         | $0.00          |  0.0000%  | $0.00       | $0.00              |

Summary: total commitment $11,000,000.00, total called **$250,000.00**, total
remaining unfunded $10,750,000.00. The total called equals the call amount
exactly, which is the same penny-accurate figure the allocator produced.
