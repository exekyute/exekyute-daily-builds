# Expense review app

## Purpose
A browser tool for working an expense batch. It checks every line against the policy,
shows the flags, and lets a reviewer approve or reject the flagged lines with a reason.
Clean lines are approved on their own. Decisions are kept in the browser and the batch
can be printed as a report. It is the review front end to the auditor in `01`.

## Inputs
The app opens with the sample expenses and policy built in. It can import an
`expenses.csv` in the engine's input format. The policy (mileage rate, receipt
threshold, category caps) is built in to match the engine.

## Validation rules
The app applies the same rules as the engine: category is Mileage or one in the policy,
the date is real, the amount is above zero, kilometres are zero or more (above zero for
a mileage line), and the receipt is yes or no. An imported line that breaks a rule is
left out of the queue.

## Logic
The flagging is the same as the engine, mirrored in JavaScript with money in integer
cents:

- Mileage mismatch, over cap, missing receipt, and duplicate, the four flags.
- A reviewer decision per flagged line (approve or reject, with a reason). Clean lines
  are auto-approved.
- A summary of total claimed, the flagged amount, the approved and rejected amounts by
  decision, and how many lines are still pending.

## Outputs
The on-screen review queue, a printable report (the Print button builds a clean report
and opens the print dialog, which can save to PDF), and the batch and the decisions
saved in localStorage so the review survives a refresh.

## Edge cases
The sample touches every flag. A "flagged only" toggle hides the clean lines so a
reviewer can work the queue. Rejecting a line tints its row and moves its amount into
the rejected total.

### Hand-checked example
The summary shows total claimed 890.00 and flagged 475.00, with two lines auto-approved
for 415.00, matching the engine in `01` to the cent. `tests.html` checks the flagging
and the totals.

## How it runs
Plain HTML, CSS, and vanilla JavaScript. It opens by double-clicking `index.html`, keeps
every file on your machine, and uses no framework, no build step, and no server. The pure
logic in `src/audit.js` is what the test harness imports.
