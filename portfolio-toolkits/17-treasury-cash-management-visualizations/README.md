# Treasury Cash Management Visualizations

A personal project, one of several I build to model real-world job descriptions and turn them into
working business utilities. The goal is to practice applied problem-solving on the kind of work a
treasury and cash-management analyst does, while strengthening my foundational software development
skills.

Three browser visualizations that connect into one cash workflow: see where the day landed, look 13
weeks ahead, and know when the debts come due. The Cash Position Dashboard builds each bank
account's closing position for the day and exports the closing balances. The Maturity Ladder sorts
debts and obligations into weekly rungs and exports the weekly totals. The Liquidity Forecast reads
both of those, starts from the day's closing cash, layers in the weekly maturities, and projects 13
weeks against a minimum-cash buffer, flagging the weeks that fall short. All amounts are Canadian
dollars, held in integer cents so the totals are exact. Each tool is deterministic and rule-based,
with the rules written out in its spec. The logic is written in TypeScript and compiled to plain
JavaScript, which is included, so each tool opens by double-clicking its HTML file with no build
step, no framework, and no server.

## The tools
1. **[Cash Position Dashboard](01-cash-position-dashboard/)** - builds opening, inflows, outflows, and
   closing per account from a day's cash movements, flags overdrawn accounts, and exports
   `closing-balances.csv`.
2. **[Maturity Ladder](02-maturity-ladder/)** - sorts debts and obligations into weekly rungs from an
   as-of date, flags overdue items and heavy weeks, and exports `maturities-by-week.csv`.
3. **[Liquidity Forecast (13-Week)](03-liquidity-forecast/)** - reads the closing balances and the
   weekly maturities, projects cash 13 weeks ahead against a minimum buffer, and flags weeks that
   breach it.

## How they connect
The dashboard's closing balances sum to the forecast's opening cash, and the ladder's weekly totals
become debt outflows in the forecast. For the shared sample, the dashboard closes the day at
648000.50 across four accounts, the ladder places 76750.00 due in week 1 and 75000.00 in week 13,
and the forecast carries those through to a cash trough of 41250.50 in week 7, two weeks below the
100000.00 buffer. The three agree to the cent, and that worked example is written out in the
forecast's [spec.md](03-liquidity-forecast/spec.md).

## License
MIT, copyright Kevin Yu (github.com/exekyute).
