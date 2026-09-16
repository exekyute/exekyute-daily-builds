"""Load the ticket log and the holiday list into SQLite and run the business-day queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --tickets data/other.csv          load a different ticket log
    python run.py --holidays data/other.csv         load a different holiday list
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
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
TICKETS_CSV = HERE / "data" / "tickets.csv"
HOLIDAYS_CSV = HERE / "data" / "holidays.csv"
SQL_DIR = HERE / "sql"
TICKET_COLUMNS = ["ticket_id", "opened_on", "responded_on"]
HOLIDAY_COLUMNS = ["holiday_on", "name"]
# The queries build their calendar this far past the last ticket, and a
# stretch of closed days this long could push a due date off the end of it.
# The margin is written out four times, here and in queries 03, 04, and 05,
# and all four have to match.
MARGIN_DAYS = 30
CLOSED_RUN_LIMIT = 7
# Dates outside this range are refused. A 9999 sentinel or a mistyped year
# would otherwise build a calendar of millions of days, one row at a time.
EARLIEST = date(1970, 1, 1)
LATEST = date(2200, 12, 31)


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
    # carried over from where the last record ended, so a blank line in
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


def whole(path, row_num, name, raw, digits):
    if not re.fullmatch(rf"[1-9][0-9]{{0,{digits - 1}}}", raw):
        fail(path, row_num, f"{name} {raw!r} is not a whole number from 1 up, "
                            f"at most {digits} digits with no leading zero")
    return int(raw)


def parse_date(path, row_num, name, raw):
    # Shape first, since the queries compare dates as text and only a fixed
    # YYYY-MM-DD sorts in date order; then whether it is a real date.
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
        fail(path, row_num, f"{name} {raw!r} is not a date like 2026-09-15")
    try:
        value = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        fail(path, row_num, f"{name} {raw!r} is not a real date")
    if not EARLIEST <= value <= LATEST:
        fail(path, row_num, f"{name} {raw} is outside the dates these files can use, "
                            f"{EARLIEST} to {LATEST}")
    return value


def load_tickets(path):
    rows, seen = [], set()
    reader = read_csv(path, TICKET_COLUMNS)
    for i, row in records(path, reader, TICKET_COLUMNS):
        ticket_id = whole(path, i, "ticket_id", row["ticket_id"], 9)
        if ticket_id in seen:
            fail(path, i, f"ticket_id {ticket_id} appears twice; the log holds one row per ticket")
        seen.add(ticket_id)
        opened_raw = row["opened_on"]
        opened = parse_date(path, i, "opened_on", opened_raw)
        responded_raw = row["responded_on"]
        # An empty responded_on is a ticket still waiting, not a bad row.
        if not responded_raw:
            rows.append((ticket_id, opened_raw, None))
            continue
        responded = parse_date(path, i, "responded_on", responded_raw)
        if responded < opened:
            fail(path, i, f"ticket {ticket_id} was answered on {responded_raw}, "
                          f"before it was opened on {opened_raw}")
        rows.append((ticket_id, opened_raw, responded_raw))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def load_holidays(path):
    rows, seen = [], set()
    reader = read_csv(path, HOLIDAY_COLUMNS)
    for i, row in records(path, reader, HOLIDAY_COLUMNS):
        raw = row["holiday_on"]
        parse_date(path, i, "holiday_on", raw)
        if raw in seen:
            fail(path, i, f"holiday_on {raw} is listed twice")
        seen.add(raw)
        name = " ".join(row["name"].split())
        if not name:
            fail(path, i, "name is blank")
        rows.append((raw, name))
    return rows


def check_closed_runs(tickets, holidays, holidays_path):
    # The calendar the queries build stops MARGIN_DAYS past the last ticket,
    # and a long enough stretch of closed days inside that window would
    # leave a due date with no day to land on, so the loader turns such a
    # list away first. The calendar itself can run further, to reach a late
    # answer, but a closure out there moves no due date, since every due
    # date comes from an opening date.
    closed = {day for day, _ in holidays}
    opened = [datetime.strptime(t[1], "%Y-%m-%d").date() for t in tickets]
    last = max(opened) + timedelta(days=MARGIN_DAYS)
    day, run, opening = min(opened), 0, None
    while day <= last:
        if day.weekday() >= 5 or day.isoformat() in closed:
            run += 1
            opening = opening or day
        elif run >= CLOSED_RUN_LIMIT:
            break
        else:
            run, opening = 0, None
        day += timedelta(days=1)
    if run >= CLOSED_RUN_LIMIT:
        fail_file(holidays_path,
                  f"leaves the desk closed from {opening} to {day - timedelta(days=1)}, "
                  f"{run} days in a row; the calendar runs {MARGIN_DAYS} days past the last "
                  "ticket, so a due date could fall off the end of it")


def new_db(tickets, holidays):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE tickets (ticket_id INTEGER PRIMARY KEY, "
               "opened_on TEXT NOT NULL, responded_on TEXT)")
    db.execute("CREATE TABLE holidays (holiday_on TEXT PRIMARY KEY, name TEXT NOT NULL)")
    db.executemany("INSERT INTO tickets VALUES (?, ?, ?)", tickets)
    db.executemany("INSERT INTO holidays VALUES (?, ?)", holidays)
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

    check("ten tickets, nine of them answered, the log running from August 31 to September 18, "
          "the last answer on September 25, and two holidays listed",
          q(db, "01-ticket-log-shape.sql"),
          [(10, 9, 1, "2026-08-31", "2026-09-18", "2026-09-25", 2)])

    naive = q(db, "02-calendar-days.sql")
    check("the calendar clock marks four due dates on days the desk is closed",
          [(r[0], r[2], r[3]) for r in naive if r[3] != "open"],
          [(1002, "2026-09-06", "closed, weekend"), (1003, "2026-09-07", "closed, holiday"),
           (1006, "2026-09-12", "closed, weekend"), (1009, "2026-09-20", "closed, weekend")])
    # The ages are compared by their repr, so that 2 and 2.0 cannot pass for
    # each other: without the CAST, julianday hands back 2.0 where the
    # report should read 2.
    check("the calendar clock counts every day the same, in whole days, and calls five tickets missed",
          [(r[0], repr(r[5]), r[6]) for r in naive],
          [(1001, "2", "met"), (1002, "5", "missed"), (1003, "5", "missed"), (1004, "6", "missed"),
           (1005, "6", "missed"), (1006, "None", "open"), (1007, "3", "met"), (1008, "0", "met"),
           (1009, "8", "missed"), (1010, "3", "met")])

    calendar = q(db, "03-business-calendar.sql")
    check("the calendar covers 49 days, 33 of them open, from the first ticket to 30 days past the last",
          lambda: (len(calendar), calendar[0][0], calendar[-1][0], calendar[-1][3]),
          (49, "2026-08-31", "2026-10-18", 33))
    check("the numbering stands still over a weekend and a holiday, then moves on",
          [r for r in calendar if "2026-09-04" <= r[0] <= "2026-09-08"],
          [("2026-09-04", "Fri", "open", 5), ("2026-09-05", "Sat", "weekend", 5),
           ("2026-09-06", "Sun", "weekend", 5), ("2026-09-07", "Mon", "Labour Day", 5),
           ("2026-09-08", "Tue", "open", 6)])

    business = q(db, "04-business-due.sql")
    check("counted in business days, every due date is a day the desk is open and two more tickets are met",
          business,
          [(1001, "2026-08-31", "2026-09-03", "2026-09-02", 2, "met"),
           (1002, "2026-09-03", "2026-09-09", "2026-09-08", 2, "met"),
           (1003, "2026-09-04", "2026-09-10", "2026-09-09", 2, "met"),
           (1004, "2026-09-05", "2026-09-10", "2026-09-11", 4, "missed"),
           (1005, "2026-09-08", "2026-09-11", "2026-09-14", 4, "missed"),
           (1006, "2026-09-09", "2026-09-14", None, None, "open"),
           (1007, "2026-09-13", "2026-09-16", "2026-09-16", 3, "met"),
           (1008, "2026-09-14", "2026-09-17", "2026-09-14", 0, "met"),
           (1009, "2026-09-17", "2026-09-22", "2026-09-25", 6, "missed"),
           (1010, "2026-09-18", "2026-09-23", "2026-09-21", 1, "met")])
    check("the two clocks disagree on the tickets that ran through the long weekend",
          lambda: [(n[0], n[6], b[5]) for n, b in zip(naive, business) if n[6] != b[5]],
          [(1002, "missed", "met"), (1003, "missed", "met")])

    arrival = q(db, "05-arrival-rule.sql")
    check("the two tickets that arrived on closed days start on the next open day",
          [(r[0], r[1], r[2], r[3]) for r in arrival if r[3] == "yes"],
          [(1004, "2026-09-05", "2026-09-08", "yes"), (1007, "2026-09-13", "2026-09-14", "yes")])
    check("starting the clock on the next open day moves two due dates and turns one missed into met",
          lambda: [(a[0], b[2], a[4], b[5], a[7]) for a, b in zip(arrival, business)
                   if (a[2], a[4], a[7]) != (b[1], b[2], b[5])],
          [(1004, "2026-09-10", "2026-09-11", "missed", "met"),
           (1007, "2026-09-16", "2026-09-17", "met", "met")])

    # Desks built for cases the sample does not reach on its own.
    def desk(tickets, holidays=()):
        return new_db([(n, opened, responded) for n, (opened, responded) in enumerate(tickets, 1)],
                      [(day, "closed") for day in holidays])

    weekend_answer = desk([("2026-09-16", "2026-09-19")])
    check("an answer logged on a Saturday counts as the Friday before it",
          q(weekend_answer, "04-business-due.sql"),
          [(1, "2026-09-16", "2026-09-21", "2026-09-19", 2, "met")])

    # Three holidays around a weekend: December 24, 25, and 28, with the
    # 26th and 27th a weekend, so the desk is closed five days running.
    winter = desk([("2026-12-23", "2027-01-04")], ["2026-12-24", "2026-12-25", "2026-12-28"])
    check("a target set the day before a five-day closure lands on December 31",
          q(winter, "04-business-due.sql"),
          [(1, "2026-12-23", "2026-12-31", "2027-01-04", 5, "missed")])

    on_holiday = desk([("2026-09-07", "2026-09-10")], ["2026-09-07"])
    check("a ticket that arrives on a holiday counts from that day in query 04 and from the next open day in query 05",
          [q(on_holiday, "04-business-due.sql"), q(on_holiday, "05-arrival-rule.sql")],
          [[(1, "2026-09-07", "2026-09-10", "2026-09-10", 3, "met")],
           [(1, "2026-09-07", "2026-09-08", "yes", "2026-09-11", "2026-09-10", 2, "met")]])

    # On-call answers logged on a closed day before the clock in query 05
    # starts: the first on the day the ticket arrived, the second the day
    # after, both still before the desk opens again.
    on_call = desk([("2026-09-05", "2026-09-05"), ("2026-09-05", "2026-09-06")])
    check("an answer logged before the clock starts counts as 0, not as a day below zero",
          q(on_call, "05-arrival-rule.sql"),
          [(1, "2026-09-05", "2026-09-07", "yes", "2026-09-10", "2026-09-05", 0, "met"),
           (2, "2026-09-05", "2026-09-07", "yes", "2026-09-10", "2026-09-06", 0, "met")])

    # The desk shut six days at a time, the longest run the loader takes.
    # The clock in query 05 starts on the first open day and its target is
    # the fourth, 27 days out, which is what the 30-day margin is for.
    def every_seventh(first, weeks):
        start = datetime.strptime(first, "%Y-%m-%d").date()
        opens = {start + timedelta(days=7 * n + 6) for n in range(weeks)}
        return [(day.isoformat(), "Shutdown")
                for n in range(MARGIN_DAYS + 1)
                for day in [start + timedelta(days=n)]
                if day not in opens and day.weekday() < 5]

    sparse = new_db([(1, "2026-09-15", None)], every_seventh("2026-09-15", 4))
    check("a desk that opens one day a week still has its target on the calendar, 27 days out",
          [q(sparse, "04-business-due.sql"), q(sparse, "05-arrival-rule.sql")],
          [[(1, "2026-09-15", "2026-10-05", None, None, "open")],
           [(1, "2026-09-15", "2026-09-21", "yes", "2026-10-12", None, None, "open")]])

    late = desk([("2026-09-01", "2026-11-30")])
    check("the calendar reaches an answer that lands long after the 30-day margin",
          lambda: [q(late, "04-business-due.sql"), q(late, "03-business-calendar.sql")[-1]],
          [[(1, "2026-09-01", "2026-09-04", "2026-11-30", 64, "missed")],
           ("2026-11-30", "Mon", "open", 65)])

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

        head = ",".join(TICKET_COLUMNS) + "\n" + "1001,2026-08-31,2026-09-02\n"
        check("an answer dated before the ticket was opened is refused",
              rejection(load_tickets, HERE / "data" / "invalid-tickets.csv"),
              (2, "invalid-tickets.csv row 4: ticket 1003 was answered on 2026-09-01, "
                  "before it was opened on 2026-09-04"))

        check("rows are counted from where a record starts, past blank lines and a stray quote; "
              "text after a closing quote, a repeated ticket_id, and a date without its zeroes are refused",
              [rejection(load_tickets, csv_file("blank.csv", head + "\n\nx,2026-09-03,\n")),
               rejection(load_tickets, csv_file("quote.csv", head + '1002,"2026-09-03,\n'
                                                                   '1003,2026-09-04,"\n')),
               rejection(load_tickets, csv_file("after.csv", head + '1002,"2026-09-03"x,\n')),
               rejection(load_tickets, csv_file("twice.csv", head + "1001,2026-09-03,\n")),
               rejection(load_tickets, csv_file("unpadded.csv", head + "1002,2026-9-3,\n"))],
              [(2, "blank.csv row 5: ticket_id 'x' is not a whole number from 1 up, "
                   "at most 9 digits with no leading zero"),
               (2, "quote.csv row 3: a field runs across more than one line; most likely a stray quote"),
               (2, "after.csv row 3: cannot be parsed (',' expected after '\"'); most likely a stray quote"),
               (2, "twice.csv row 3: ticket_id 1001 appears twice; the log holds one row per ticket"),
               (2, "unpadded.csv row 3: opened_on '2026-9-3' is not a date like 2026-09-15")])

        check("a control character, a row with too many or too few fields, a renamed header, "
              "a date outside the range, and a file with only a header are refused, while a "
              "byte-order mark is read through",
              [rejection(load_tickets, csv_file("tab.csv", head + "1002,2026-09-03,2026-09-04\t\n")),
               rejection(load_tickets, csv_file("wide.csv", head + "1002,2026-09-03,,extra\n")),
               rejection(load_tickets, csv_file("narrow.csv", head + "1002,2026-09-03\n")),
               rejection(load_tickets, csv_file("renamed.csv", "ticket,opened_on,responded_on\n")),
               rejection(load_tickets, csv_file("range.csv", head + "1002,9999-12-01,\n")),
               rejection(load_tickets, csv_file("bare.csv", ",".join(TICKET_COLUMNS) + "\n")),
               rejection(load_tickets, csv_file("bom.csv", "\ufeff" + head))],
              [(2, "tab.csv row 3: contains the control character '\\t'"),
               (2, "wide.csv row 3: has more fields than the header"),
               (2, "narrow.csv row 3: has fewer fields than the header"),
               (2, "renamed.csv row 1: expected columns ticket_id,opened_on,responded_on, "
                   "got ['ticket', 'opened_on', 'responded_on']"),
               (2, "range.csv row 3: opened_on 9999-12-01 is outside the dates these files can use, "
                   "1970-01-01 to 2200-12-31"),
               (2, "bare.csv row 1: no data rows after the header"),
               (0, [(1001, "2026-08-31", "2026-09-02")])])

        holiday_head = ",".join(HOLIDAY_COLUMNS) + "\n2026-09-07,Labour Day\n"
        check("a holiday listed twice, one with no name, and one that is not a real date are refused, "
              "and a list the desk keeps is loaded",
              [rejection(load_holidays, csv_file("dup.csv", holiday_head + "2026-09-07,Labour Day\n")),
               rejection(load_holidays, csv_file("noname.csv", holiday_head + "2026-12-25, \n")),
               rejection(load_holidays, csv_file("unreal.csv", holiday_head + "2026-02-30,Snow Day\n")),
               rejection(load_holidays, csv_file("fine.csv", holiday_head + "2026-12-25,Christmas Day\n"))],
              [(2, "dup.csv row 3: holiday_on 2026-09-07 is listed twice"),
               (2, "noname.csv row 3: name is blank"),
               (2, "unreal.csv row 3: holiday_on '2026-02-30' is not a real date"),
               (0, [("2026-09-07", "Labour Day"), ("2026-12-25", "Christmas Day")])])

        # Either side of the limit, counting the weekends inside each run:
        # Thursday to the next Tuesday is six days shut and is taken,
        # Wednesday to the next Tuesday is seven and is turned away, and a
        # working week off is nine. These lists go straight to the check,
        # since it reads rows rather than a file.
        def shut(*days):
            return [(f"2026-09-{day}", "Shutdown") for day in days]

        waiting = [(1, "2026-09-14", None)]
        check("the desk may close for six days in a row but not seven, and a working week off is refused",
              [rejection(check_closed_runs, waiting, shut("24", "25", "28", "29"), Path("six.csv")),
               rejection(check_closed_runs, waiting, shut("23", "24", "25", "28", "29"), Path("seven.csv")),
               rejection(check_closed_runs, waiting, shut("21", "22", "23", "24", "25"), Path("week.csv"))],
              [(0, None),
               (2, "seven.csv: leaves the desk closed from 2026-09-23 to 2026-09-29, 7 days in a row; "
                   "the calendar runs 30 days past the last ticket, so a due date could fall off the end of it"),
               (2, "week.csv: leaves the desk closed from 2026-09-19 to 2026-09-27, 9 days in a row; "
                   "the calendar runs 30 days past the last ticket, so a due date could fall off the end of it")])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the business-day queries against a ticket log, the sample by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--tickets", type=Path, default=None, help="path to an alternate ticket log CSV")
    parser.add_argument("--holidays", type=Path, default=None,
                        help="path to a holiday list CSV; the sample list is used for any ticket log "
                             "unless this names another")
    args = parser.parse_args()
    # Reports are printed as UTF-8, since output piped or redirected on
    # Windows otherwise falls back to a codepage that cannot print all text.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    given = {"--tickets": args.tickets is not None, "--holidays": args.holidays is not None}
    args.tickets = args.tickets or TICKETS_CSV
    args.holidays = args.holidays or HOLIDAYS_CSV
    for flag, path in (("--tickets", args.tickets), ("--holidays", args.holidays)):
        if path.is_file():
            continue
        if given[flag]:
            parser.error(f"{flag}: '{path}' is not a file")
        parser.error(f"the sample file '{path}' is missing")
    if args.test and (args.tickets.resolve() != TICKETS_CSV.resolve()
                      or args.holidays.resolve() != HOLIDAYS_CSV.resolve()):
        parser.error("--test checks hand-computed answers for the sample files; "
                     "run it without --tickets or --holidays")

    tickets = load_tickets(args.tickets)
    holidays = load_holidays(args.holidays)
    check_closed_runs(tickets, holidays, args.holidays)
    db = new_db(tickets, holidays)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
