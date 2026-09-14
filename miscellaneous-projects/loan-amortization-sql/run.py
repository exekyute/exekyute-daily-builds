"""Load the loans and planned extra payments into SQLite and run the amortization queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --loans data/other.csv            load a different loans file, with no extra payments
    python run.py --loans data/other.csv --extras data/other-extras.csv
                                                    the same, with extra payments planned against it
"""

import argparse
import contextlib
import csv
import io
import re
import sqlite3
import sys
import tempfile
import unicodedata
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent
LOANS_CSV = HERE / "data" / "loans.csv"
EXTRAS_CSV = HERE / "data" / "extra-payments.csv"
SQL_DIR = HERE / "sql"
LOAN_COLUMNS = ["loan_id", "name", "principal", "annual_rate", "months", "payment"]
EXTRA_COLUMNS = ["loan_id", "month", "amount"]
MONEY = r"[0-9]+(\.[0-9]{1,2})?"
CAP = 10 ** 11


def fail(path, row_num, message):
    print(f"{Path(path).name} row {row_num}: {message}", file=sys.stderr)
    sys.exit(2)


def fail_file(path, message):
    print(f"{Path(path).name}: {message}", file=sys.stderr)
    sys.exit(2)


def read_csv(path, columns):
    # utf-8-sig strips the byte-order mark that Excel puts on its CSV exports.
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as err:
        fail_file(path, err.strerror or "cannot be read")
    except UnicodeDecodeError:
        fail_file(path, "is not UTF-8 text")
    # strict, because the lenient parser folds text that follows a closing
    # quote back into the field and hands over a garbled row without a word.
    reader = csv.reader(io.StringIO(text, newline=""), strict=True)
    try:
        header = next(reader)
    except StopIteration:
        fail_file(path, "is empty")
    except csv.Error as err:
        fail(path, 1, f"cannot be parsed ({err})")
    if header != columns:
        fail(path, 1, f"expected columns {','.join(columns)}, got {header}")
    return reader


def records(path, reader, columns):
    # Yields each record with the line it started on. reader.line_num is where
    # a record ended, which for a stray quote can be many lines on. start is
    # carried over from the previous record's end, so a blank line in
    # between has to move it on as well.
    start = reader.line_num + 1
    try:
        for fields in reader:
            if not fields:
                start = reader.line_num + 1
                continue
            if any(ch in f for f in fields for ch in "\r\n"):
                fail(path, start, "a field runs across more than one line; "
                                  "most likely a stray quote")
            bad = next((ch for f in fields for ch in f
                        if unicodedata.category(ch) == "Cc"), None)
            if bad is not None:
                fail(path, start, f"contains the control character {bad!r}")
            if len(fields) > len(columns):
                fail(path, start, "has more fields than the header")
            if len(fields) < len(columns):
                fail(path, start, "has fewer fields than the header")
            yield start, {k: v.strip() for k, v in zip(columns, fields)}
            start = reader.line_num + 1
    except csv.Error as err:
        fail(path, start, f"cannot be parsed ({err}); most likely a stray quote")


def cents(path, row_num, name, raw):
    if not re.fullmatch(MONEY, raw):
        fail(path, row_num, f"{name} {raw!r} is not an amount like 743.25")
    value = int(Decimal(raw) * 100)
    if value == 0:
        fail(path, row_num, f"{name} is zero")
    if value >= CAP:
        fail(path, row_num, f"{name} {raw} is 1,000,000,000.00 or more, "
                            "beyond anything this sample is meant for")
    return value


def whole(path, row_num, name, raw, digits):
    if not re.fullmatch(rf"[1-9][0-9]{{0,{digits - 1}}}", raw):
        fail(path, row_num, f"{name} {raw!r} is not a whole number from 1 up, "
                            f"at most {digits} digits with no leading zero")
    return int(raw)


def interest_on(balance, rate_bp):
    # The same rounding the queries use: nearest cent, halves up.
    return (balance * rate_bp + 60000) // 120000


def load_loans(path):
    loans = {}
    reader = read_csv(path, LOAN_COLUMNS)
    for i, row in records(path, reader, LOAN_COLUMNS):
        loan_id = whole(path, i, "loan_id", row["loan_id"], 9)
        if loan_id in loans:
            fail(path, i, f"loan_id {loan_id} appears twice")
        name = " ".join(row["name"].split())
        if not name:
            fail(path, i, "name is blank")
        principal = cents(path, i, "principal", row["principal"])
        rate = row["annual_rate"]
        if not re.fullmatch(MONEY, rate):
            fail(path, i, f"annual_rate {rate!r} is not a percentage like 7.20: "
                          "digits with at most two decimals and no % sign")
        rate_bp = int(Decimal(rate) * 100)
        if rate_bp > 10000:
            fail(path, i, f"annual_rate {rate} is over 100 percent; "
                          "most likely basis points typed as a percentage")
        months = whole(path, i, "months", row["months"], 3)
        if months > 600:
            fail(path, i, f"months {months} is over 600, a 50-year term")
        payment = cents(path, i, "payment", row["payment"])
        # A payment that does not beat the first month's interest never
        # brings the balance down, and the last month would have to pay at
        # least the whole loan and a month's interest.
        first = interest_on(principal, rate_bp)
        if payment <= first:
            fail(path, i, f"loan {loan_id} pays {payment / 100:.2f} a month, which is no more than "
                          f"its first month's interest of {first / 100:.2f}, "
                          "so the balance would never come down")
        loans[loan_id] = (loan_id, name, principal, rate_bp, months, payment)
    if not loans:
        fail(path, 1, "no data rows after the header")
    return list(loans.values())


def load_extras(path, loans):
    terms = {loan[0]: loan[4] for loan in loans}
    rows, seen = [], set()
    reader = read_csv(path, EXTRA_COLUMNS)
    for i, row in records(path, reader, EXTRA_COLUMNS):
        loan_id = whole(path, i, "loan_id", row["loan_id"], 9)
        if loan_id not in terms:
            fail(path, i, f"loan {loan_id} is not in the loans file")
        month = whole(path, i, "month", row["month"], 3)
        if month > terms[loan_id]:
            fail(path, i, f"month {month} is past loan {loan_id}'s {terms[loan_id]}-month term")
        if (loan_id, month) in seen:
            fail(path, i, f"loan {loan_id} has two extra payments in month {month}; "
                          "the file holds one per loan per month")
        seen.add((loan_id, month))
        rows.append((loan_id, month, cents(path, i, "amount", row["amount"])))
    return rows


def new_db(loans, extras):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE loans (loan_id INTEGER PRIMARY KEY, name TEXT NOT NULL, "
               "principal INTEGER NOT NULL, rate_bp INTEGER NOT NULL, "
               "months INTEGER NOT NULL, payment INTEGER NOT NULL)")
    db.execute("CREATE TABLE extra_payments (loan_id INTEGER NOT NULL REFERENCES loans, "
               "month INTEGER NOT NULL, amount INTEGER NOT NULL, PRIMARY KEY (loan_id, month))")
    db.executemany("INSERT INTO loans VALUES (?, ?, ?, ?, ?, ?)", loans)
    db.executemany("INSERT INTO extra_payments VALUES (?, ?, ?)", extras)
    return db


def print_table(headers, rows):
    cells = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h)
              for i, h in enumerate(headers)]
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip())
    print("  ".join("-" * w for w in widths))
    for row in cells:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))).rstrip())


def run_query(db, sql_path):
    try:
        cursor = db.execute(sql_path.read_text(encoding="utf-8"))
    except sqlite3.Error as err:
        fail_file(sql_path, f"did not run: {err}")
    headers = [d[0] for d in cursor.description]
    return headers, cursor.fetchall()


def run_all(db):
    for sql_path in sorted(SQL_DIR.glob("*.sql")):
        print(f"=== {sql_path.name} ===")
        headers, rows = run_query(db, sql_path)
        print_table(headers, rows)
        print()


def run_tests(db):
    failures = 0

    def check(label, got, want):
        # got can be a function, so a query that hands back NULLs or no rows
        # fails its own check instead of stopping the suite with a traceback.
        nonlocal failures
        if callable(got):
            try:
                got = got()
            except Exception as err:
                got = f"raised {type(err).__name__}: {err}"
        if got == want:
            print(f"PASS  {label}")
        else:
            failures += 1
            print(f"FAIL  {label}\n      got:  {got!r}\n      want: {want!r}")

    def q(conn, name):
        return run_query(conn, SQL_DIR / name)[1]

    check("two loans and two planned extra payments loaded",
          db.execute("SELECT (SELECT COUNT(*) FROM loans), (SELECT COUNT(*) FROM extra_payments)").fetchone(),
          (2, 2))

    check("each loan's terms, first month's interest, and planned extras",
          q(db, "01-loan-terms.sql"),
          [(1, "Delivery van", "24000.00", "7.20", 36, "743.25", "144.00", "2000.00"),
           (2, "Espresso machine", "7900.00", "6.00", 12, "679.92", "39.50", "2000.00")])

    check("the window attempt charges interest on the starting principal and leaves money owing",
          q(db, "02-window-attempt.sql"),
          [(1, 36, "5184.00", "2427.00"), (2, 12, "474.00", "214.96")])

    schedule = q(db, "03-schedule.sql")
    check("the van's first three months charge 144.00, 140.40, and 136.79, the last rounded from 136.7874",
          schedule[:3],
          [(1, 1, "743.25", "144.00", "599.25", "23400.75"), (1, 2, "743.25", "140.40", "602.85", "22797.90"),
           (1, 3, "743.25", "136.79", "606.46", "22191.44")])
    check("each loan runs its full term and ends at 0.00 on a final payment that differs from the stated one",
          lambda: [(r[0], r[1], r[2], r[5]) for i, r in enumerate(schedule)
                   if i + 1 == len(schedule) or schedule[i + 1][0] != r[0]],
          [(1, 36, "743.11", "0.00"), (2, 12, "680.00", "0.00")])

    check("the van's final payment is 14 cents short of the stated one, the espresso machine's 8 cents over",
          q(db, "04-totals.sql"),
          [(1, 36, "743.25", "743.11", "-0.14", "2756.86", "26756.86"),
           (2, 12, "679.92", "680.00", "+0.08", "259.12", "8159.12")])

    check("the extras save 294.18 on the van, and only 1,349.79 of the espresso machine's 2,000.00 is used",
          q(db, "05-extra-payments.sql"),
          [(1, 36, 33, "2756.86", "2462.68", "294.18", "2000.00", "2000.00"),
           (2, 12, 10, "259.12", "248.99", "10.13", "2000.00", "1349.79")])

    # Loans built for cases the sample does not reach on its own.
    def book(loans, extras=()):
        return new_db([(n, f"loan {n}", *terms) for n, terms in enumerate(loans, 1)], list(extras))

    # Two payments of 333.33 leave 333.34, a cent more than the stated
    # payment, so only the last month of the term can clear it. The second
    # loan's 400.00 payments clear it in month 3 of 12.
    zero = book([(100000, 0, 3, 33333), (100000, 0, 12, 40000)])
    check("at 0 percent the final payment takes the leftover cents, and a payment that clears a loan early ends it",
          q(zero, "03-schedule.sql"),
          [(1, 1, "333.33", "0.00", "333.33", "666.67"), (1, 2, "333.33", "0.00", "333.33", "333.34"),
           (1, 3, "333.34", "0.00", "333.34", "0.00"),
           (2, 1, "400.00", "0.00", "400.00", "600.00"), (2, 2, "400.00", "0.00", "400.00", "200.00"),
           (2, 3, "200.00", "0.00", "200.00", "0.00")])

    # 405.00 at half a percent a month is exactly 2.025 of interest.
    early = book([(100000, 600, 12, 60000)])
    check("a payment larger than the loan needs ends it early, and 2.025 of interest rounds to 2.03",
          q(early, "03-schedule.sql"),
          [(1, 1, "600.00", "5.00", "595.00", "405.00"), (1, 2, "407.03", "2.03", "405.00", "0.00")])
    check("queries 04 and 05 total that loan on the month it ends, with the same 2.03",
          [q(early, "04-totals.sql"), q(early, "05-extra-payments.sql")],
          [[(1, 2, "600.00", "407.03", "-192.97", "7.03", "1007.03")],
           [(1, 2, 2, "7.03", "7.03", "0.00", "0.00", "0.00")]])

    balloon = book([(1000000, 1200, 6, 15000)])
    check("a payment 50.00 over the first month's interest leaves a balloon in the last month",
          q(balloon, "04-totals.sql"),
          [(1, 6, "150.00", "9842.41", "+9692.41", "592.41", "10592.41")])

    # A first month's interest of exactly 2.025, one of 5.0005 that rounds
    # down, and a rate of 7.25 percent, whose 725 basis points do not split
    # into twelve whole monthly ones. The sample's first months come to
    # whole cents, and its rates split evenly.
    halves = book([(40500, 600, 12, 3486), (100010, 600, 12, 8608), (2400000, 725, 36, 74380)])
    check("queries 01, 02, and 03 round 2.025 of interest up to 2.03 and 5.0005 down to 5.00, "
          "and charge 145.00 at 7.25 percent",
          [q(halves, "01-loan-terms.sql"), q(halves, "02-window-attempt.sql"),
           [r for r in q(halves, "03-schedule.sql") if r[1] == 1]],
          [[(1, "loan 1", "405.00", "6.00", 12, "34.86", "2.03", "0.00"),
            (2, "loan 2", "1000.10", "6.00", 12, "86.08", "5.00", "0.00"),
            (3, "loan 3", "24000.00", "7.25", 36, "743.80", "145.00", "0.00")],
           [(1, 12, "24.36", "11.04"), (2, 12, "60.00", "27.14"), (3, 36, "5220.00", "2443.20")],
           [(1, 1, "34.86", "2.03", "32.83", "372.17"), (2, 1, "86.08", "5.00", "81.08", "919.02"),
            (3, 1, "743.80", "145.00", "598.80", "23401.20")]])

    check("query 04 totals the 0 percent loans and those three",
          [q(zero, "04-totals.sql"), q(halves, "04-totals.sql")],
          [[(1, 3, "333.33", "333.34", "+0.01", "0.00", "1000.00"),
            (2, 3, "400.00", "200.00", "-200.00", "0.00", "1000.00")],
           [(1, 12, "34.86", "34.84", "-0.02", "13.30", "418.30"),
            (2, 12, "86.08", "86.03", "-0.05", "32.81", "1032.91"),
            (3, 36, "743.80", "743.67", "-0.13", "2776.67", "26776.67")]])

    # A balloon's last month owes far more than its stated payment, so it
    # shows whether that month's payment is kept apart from any extra: 50.00
    # planned for it is never applied, while 100.00 planned for month 2 goes
    # in whole. The third loan is cleared by an extra in month 2, with
    # another still planned for month 4.
    late = book([(1000000, 1200, 6, 15000), (1000000, 1200, 6, 15000), (500000, 600, 6, 84798)],
                [(1, 6, 5000), (2, 2, 10000), (3, 2, 1000000), (3, 4, 30000)])
    check("an extra in the term's last month or after payoff is never applied, and one mid-term goes in whole",
          q(late, "05-extra-payments.sql"),
          [(1, 6, 6, "592.41", "592.41", "0.00", "50.00", "0.00"),
           (2, 6, 6, "592.41", "588.35", "4.06", "100.00", "100.00"),
           (3, 6, 2, "87.87", "45.89", "41.98", "10300.00", "3349.93")])

    # The loader, on the included bad file and on small files written here.
    # A crash on one of these files comes back as a value too, so it fails
    # its check like any other wrong answer; a file the loader accepts comes
    # back with what it loaded.
    def rejection(load, *args):
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                loaded = load(*args)
        except SystemExit as stop:
            return stop.code, err.getvalue().strip()
        except Exception as crash:
            return f"raised {type(crash).__name__}", str(crash)
        return 0, loaded

    with tempfile.TemporaryDirectory() as tmp:
        def csv_file(name, text):
            path = Path(tmp) / name
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            return path

        header = ",".join(LOAN_COLUMNS) + "\n"
        head = header + "1,Van,24000.00,7.20,36,743.25\n"
        check("a rate over 100 percent and a payment no more than the first month's interest are refused, "
              "that interest rounded half up",
              [rejection(load_loans, csv_file("rate.csv", header + "1,Van,24000.00,720,36,743.25\n")),
               rejection(load_loans, HERE / "data" / "invalid-loans.csv"),
               rejection(load_loans, csv_file("equal.csv", header + "1,Tiny,405.00,6.00,12,2.03\n"))],
              [(2, "rate.csv row 2: annual_rate 720 is over 100 percent; "
                   "most likely basis points typed as a percentage"),
               (2, "invalid-loans.csv row 4: loan 3 pays 300.00 a month, which is no more than "
                   "its first month's interest of 375.00, so the balance would never come down"),
               (2, "equal.csv row 2: loan 1 pays 2.03 a month, which is no more than "
                   "its first month's interest of 2.03, so the balance would never come down")])

        check("rows are counted from where a record starts, past blank lines and a stray quote; "
              "text after a closing quote and a repeated loan_id are refused",
              [rejection(load_loans, csv_file("blank.csv", head + "\n\nx,Oven,4000.00,8.00,24,181.00\n")),
               rejection(load_loans, csv_file("quote.csv", head + '2,"Oven,4000.00,8.00,24,181.00\n'
                                                                  '3,Cooler,1000.00,6.00,12,90.00"\n')),
               rejection(load_loans, csv_file("after.csv", head + '2,"Oven"x,4000.00,8.00,24,181.00\n')),
               rejection(load_loans, csv_file("twice.csv", head + "1,Oven,4000.00,8.00,24,181.00\n"))],
              [(2, "blank.csv row 5: loan_id 'x' is not a whole number from 1 up, at most 9 digits with no leading zero"),
               (2, "quote.csv row 3: a field runs across more than one line; most likely a stray quote"),
               (2, "after.csv row 3: cannot be parsed (',' expected after '\"'); most likely a stray quote"),
               (2, "twice.csv row 3: loan_id 1 appears twice")])

        sample = load_loans(LOANS_CSV)
        planned = ",".join(EXTRA_COLUMNS) + "\n1,12,2000.00\n"
        check("extras for an unknown loan, past the term, or twice in a month are refused, and one in the last month is kept",
              [rejection(load_extras, csv_file("unknown.csv", planned + "3,4,100.00\n"), sample),
               rejection(load_extras, csv_file("past.csv", planned + "1,37,100.00\n"), sample),
               rejection(load_extras, csv_file("again.csv", planned + "1,12,500.00\n"), sample),
               rejection(load_extras, csv_file("last.csv", planned + "1,36,100.00\n"), sample)],
              [(2, "unknown.csv row 3: loan 3 is not in the loans file"),
               (2, "past.csv row 3: month 37 is past loan 1's 36-month term"),
               (2, "again.csv row 3: loan 1 has two extra payments in month 12; the file holds one per loan per month"),
               (0, [(1, 12, 200000), (1, 36, 10000)])])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the amortization queries against loan files, the samples by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--loans", type=Path, default=None, help="path to an alternate loans CSV")
    parser.add_argument("--extras", type=Path, default=None,
                        help="path to an extra payments CSV; by default the sample loans get the sample "
                             "extras and any other loans file gets none")
    args = parser.parse_args()
    # Reports are printed as UTF-8, since output piped or redirected on
    # Windows otherwise falls back to a codepage that cannot print all text.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    given = {"--loans": args.loans is not None, "--extras": args.extras is not None}
    if args.loans is None:
        args.loans = LOANS_CSV
    # The sample extra payments are planned against the sample loans' ids and
    # terms, so by default they go with the sample loans and nothing else.
    if args.extras is None and args.loans.resolve() == LOANS_CSV.resolve():
        args.extras = EXTRAS_CSV
    for flag, path in (("--loans", args.loans), ("--extras", args.extras)):
        if path is None or path.is_file():
            continue
        if given[flag]:
            parser.error(f"{flag}: '{path}' is not a file")
        parser.error(f"the sample file '{path}' is missing")
    if args.test and (args.loans.resolve() != LOANS_CSV.resolve()
                      or args.extras.resolve() != EXTRAS_CSV.resolve()):
        parser.error("--test checks hand-computed answers for the sample files; run it without --loans or --extras")

    loans = load_loans(args.loans)
    extras = load_extras(args.extras, loans) if args.extras is not None else []
    db = new_db(loans, extras)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
