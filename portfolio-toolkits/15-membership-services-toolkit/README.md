# Membership services toolkit

A personal project, one of several I build to model real-world job descriptions
and turn them into working business utilities. The goal is to practice applied
problem-solving on the kind of work a membership services coordinator does,
processing renewals and keeping the member database and the Excel worklist in
agreement, while strengthening my foundational software development skills.

The repo holds three small tools that share one data story. A SQL tool runs the
saved membership reports and writes a renewal worklist CSV. An Excel VBA tool
imports that CSV and builds the formatted, color-flagged worklist with the totals
the manager reviews. A browser dashboard reads the same CSV and shows the week at
a glance. All three are deterministic and rule-based, with the rules written out
in each tool's spec, and they agree to the cent: total dues 1,733.75, HST 225.39,
late fees 25.00, grand total billed 1,984.14. No framework, no build step, and no
server, and nothing is uploaded.

## The tools
1. **Membership reporting (SQL)** - SQLite reports for the weekly expiring and
   lapsed worklists, the monthly dues summary with HST, and the reconciliation
   counts. Writes the renewal worklist CSV the other two tools read.
2. **Renewal worklist (Excel VBA)** - a macro that imports the CSV and builds the
   formatted, flagged worklist with dues, HST, late-fee, and grand totals.
3. **Renewal dashboard (browser)** - a page that reads the CSV and shows counts,
   dues by tier, and the totals at a glance.

## How they connect
The SQL tool is the anchor: it runs here, applies HST with `Decimal` rounding,
and checks every total against the hand-checked figures in its spec. The Excel
and browser tools reproduce those same figures, so the three agree to the cent.

## License
MIT, copyright Kevin Yu (github.com/exekyute).
