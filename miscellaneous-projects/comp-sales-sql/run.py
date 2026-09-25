"""Load a daily sales log into SQLite and run the comparable-sales queries.

Usage:
    python run.py                     run every query in sql/
    python run.py --test              run the assertion suite
    python run.py --sales log.csv     load a different log
"""

import argparse
import contextlib
import csv
import datetime
import io
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
SALES_CSV = HERE / "data" / "sales.csv"
SQL_DIR = HERE / "sql"
COLUMNS = ["sale_date", "store", "sales"]
CODE = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")
CODE_LENGTH = 24
FIRST_DAY, LAST_DAY = datetime.date(1970, 1, 1), datetime.date(2200, 12, 31)
# At most 999999.99 a row and at most this many rows keep every total under
# 10**13 cents, or under twice that for the same-date totals in queries 02
# and 05, which count 1 March twice across a leap day. The growth arithmetic
# multiplies a total by 2000, so it stays a whole number well inside SQLite's
# 64-bit integers.
MOST_ROWS = 100_000
# A line of the file may hold at most this many characters. A real row holds
# a few dozen.
LINE_CAP = 1_000_000
# A query that runs past this many thousand SQLite steps is stopped. The
# sample takes under a hundred. The costliest log tried within the limits
# above takes under a fifth of it, on SQLite 3.31 and 3.34 as on 3.50, so
# only a query that would run away reaches it.
STEP_BUDGET = 200_000


def fail(path, row_num, message):
    print(f"{Path(path).name} row {row_num}: {message}", file=sys.stderr)
    sys.exit(2)


def fail_file(path, message):
    print(f"{Path(path).name}: {message}", file=sys.stderr)
    sys.exit(2)


def shown(raw):
    # A value is cut short in a message, so one enormous field cannot flood
    # the screen.
    if len(raw) <= 40:
        return repr(raw)
    over = len(raw) - 40
    return f"{raw[:40]!r} and {over} more character" + ("" if over == 1 else "s")


def read_lines(path, handle):
    # Hands the file over a line at a time, reading at most LINE_CAP + 3
    # characters of any line: the cap, a byte-order mark and a CRLF ending.
    # A longer line is refused, so neither a log far past the row limit nor
    # one enormous line is ever held in memory whole. The byte-order mark
    # that Excel puts on its CSV exports is dropped here.
    number = 0
    while True:
        line = handle.readline(LINE_CAP + 3)
        if not line:
            return
        number += 1
        if number == 1 and line.startswith("\ufeff"):
            line = line[1:]
        if len(line.rstrip("\r\n")) > LINE_CAP:
            fail(path, number, f"runs past {LINE_CAP} characters on one line")
        yield line


def parsed(path, handle):
    # Each line is parsed on its own and handed on with its row and its text.
    # No field of a log runs across lines, so a quote left open is caught on
    # its own row and nothing is held past the end of a line. strict, because
    # the lenient parser folds text that follows a closing quote back into
    # the field and hands over a garbled row without a word.
    for number, line in enumerate(read_lines(path, handle), 1):
        try:
            fields = next(csv.reader([line], strict=True), [])
        except csv.Error as err:
            # The parser's own words, with a hint only where it can be backed.
            if "field limit" in str(err):
                fail(path, number, f"has a field over {csv.field_size_limit()} characters long")
            if "expected after" in str(err):
                fail(path, number, f"cannot be parsed ({err}); a quoted field has to end at its closing quote")
            if "end of data" in str(err):
                fail(path, number, f"cannot be parsed ({err}); a quote is left open at the end of the line, "
                                   "and no field can run onto the next")
            fail(path, number, f"cannot be parsed ({err})")
        yield number, fields, line


def blank(fields):
    # A line holding nothing but spaces is as blank as an empty one.
    return len(fields) <= 1 and not "".join(fields).strip(" ")


def open_csv(path, handle, columns):
    # Returns the parsed lines still to come and the row the header is on.
    lines = parsed(path, handle)
    try:
        number, header, line = next(lines)
        # Blank lines before the header are passed over, as they are between
        # rows.
        while blank(header):
            number, header, line = next(lines)
    except StopIteration:
        fail_file(path, "is empty")
    except UnicodeDecodeError:
        fail_file(path, "is not UTF-8 text")
    except OSError as err:
        fail_file(path, err.strerror or "cannot be read")
    if [f.strip(" ") for f in header] != columns:
        # The header is shown as the file has it, so a quoted comma or a
        # trailing one still shows.
        got = line.rstrip("\r\n")
        fail(path, number, f"expected columns '{','.join(columns)}', got {shown(got)}")
    return lines, number


def records(path, lines, columns):
    # Yields each record with its row, one line apiece.
    try:
        for number, fields, _ in lines:
            if blank(fields):
                continue
            if len(fields) > len(columns):
                fail(path, number, "has more fields than the header")
            if len(fields) < len(columns):
                fail(path, number, "has fewer fields than the header")
            yield number, {k: v.strip(" ") for k, v in zip(columns, fields)}
    except UnicodeDecodeError:
        fail_file(path, "is not UTF-8 text")
    except OSError as err:
        fail_file(path, err.strerror or "cannot be read")


def date_of(path, row_num, raw):
    # The queries match days as text and step through them with SQLite's date
    # functions, so a day is held to one form and has to be on the calendar.
    # SQLite turns 2025-02-29 into 1 March as soon as it adds days to it, and
    # 3.50 does so even in a bare date(), so it is refused.
    match = re.fullmatch(r"([0-9]{4})-([0-9]{2})-([0-9]{2})", raw)
    try:
        day = datetime.date(*(int(g) for g in match.groups())) if match else None
    except ValueError:
        day = None
    if day is None or not FIRST_DAY <= day <= LAST_DAY:
        fail(path, row_num, f"sale_date {shown(raw)} is not a calendar date written like 2025-12-07, "
                            f"from {FIRST_DAY} to {LAST_DAY}")
    return raw


def code(path, row_num, raw):
    # Stores are matched exactly, so a code is held to one plain form:
    # capital letters A to Z and digits 0 to 9, joined by single hyphens.
    # One typed another way would be a second store, open on the days the
    # first looked shut.
    if len(raw) > CODE_LENGTH or not CODE.fullmatch(raw):
        fail(path, row_num, f"store {shown(raw)} is not a store code: capital letters A to Z and digits 0 to 9, "
                            f"joined by single hyphens, at most {CODE_LENGTH} characters")
    return raw


def cents(path, row_num, raw):
    # Two decimal places, no sign, no thousands separator, no currency mark.
    # 0.00 is a day the store opened and sold nothing, and counts as open.
    match = re.fullmatch(r"(0|[1-9][0-9]{0,5})\.([0-9]{2})", raw)
    if not match:
        fail(path, row_num, f"sales {shown(raw)} is not an amount from 0.00 to 999999.99 written like 1843.20")
    return int(match.group(1)) * 100 + int(match.group(2))


def report_weeks(first, last):
    # The same rule the queries use: from the first Sunday that is at least
    # 364 days after the log's first day, to the last Saturday on or before
    # its last day. date.weekday() counts Monday as 0, so Sunday is 6.
    start = first + datetime.timedelta(days=364)
    start += datetime.timedelta(days=(6 - start.weekday()) % 7)
    end = last - datetime.timedelta(days=(last.weekday() - 5) % 7)
    return start, end


def load(path):
    path = Path(path)
    try:
        folder = path.is_dir()
    except OSError:
        # Python 3.7 raises here for a name Windows cannot hold.
        folder = False
    if folder:
        fail_file(path, "is a folder, not a file")
    try:
        handle = open(path, encoding="utf-8", newline="")
    except OSError as err:
        fail_file(path, err.strerror or "cannot be read")
    rows, seen = [], set()
    with handle:
        lines, header_line = open_csv(path, handle, COLUMNS)
        for i, row in records(path, lines, COLUMNS):
            day = date_of(path, i, row["sale_date"])
            store = code(path, i, row["store"])
            amount = cents(path, i, row["sales"])
            if (day, store) in seen:
                fail(path, i, f"{store} appears twice for {day}; one row per store and day, "
                              "with the day's sales added together")
            seen.add((day, store))
            rows.append((day, store, amount))
            # The file is read a line at a time, so a log far past the limit
            # is never read to the end.
            if len(rows) > MOST_ROWS:
                fail(path, i, f"the log runs past {MOST_ROWS} rows")
    if not rows:
        fail(path, header_line, "no data rows after the header")
    first = min(day for day, _, _ in rows)
    last = max(day for day, _, _ in rows)
    start, end = report_weeks(datetime.date.fromisoformat(first), datetime.date.fromisoformat(last))
    if start > end:
        fail_file(path, f"the log runs from {first} to {last}, and none of its Sunday-to-Saturday weeks has "
                        "the same week 52 weeks earlier in the log as well; that takes at least 371 days")
    return rows


def new_db(rows):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE sales (sale_date TEXT NOT NULL, store TEXT NOT NULL, sales_cents INTEGER NOT NULL, "
               "PRIMARY KEY (sale_date, store))")
    db.executemany("INSERT INTO sales VALUES (?, ?, ?)", rows)
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
    # SQLite calls budget every thousand steps and stops the query once it
    # returns true, so a query that would run away uses up the budget and
    # stops with an error instead.
    steps = [0]

    def budget():
        steps[0] += 1
        return steps[0] > STEP_BUDGET

    db.set_progress_handler(budget, 1000)
    try:
        cursor = db.execute(sql_path.read_text(encoding="utf-8"))
        if cursor.description is None:
            raise sqlite3.ProgrammingError("has no query result to print")
        return [d[0] for d in cursor.description], cursor.fetchall()
    except sqlite3.OperationalError:
        if steps[0] > STEP_BUDGET:
            raise sqlite3.OperationalError(f"stopped after {STEP_BUDGET} thousand steps")
        raise
    finally:
        db.set_progress_handler(None, 1000)


def run_all(db, sql_dir=SQL_DIR):
    for sql_path in sorted(sql_dir.glob("*.sql")):
        if sql_path.is_dir():
            fail_file(sql_path, "is a folder, not a query file")
        try:
            headers, rows = run_query(db, sql_path)
        except (sqlite3.Error, sqlite3.Warning) as err:
            fail_file(sql_path, f"did not run: {err}")
        except UnicodeDecodeError:
            fail_file(sql_path, "is not UTF-8 text")
        except OSError as err:
            fail_file(sql_path, err.strerror or "cannot be read")
        print(f"=== {sql_path.name} ===")
        print_table(headers, rows)
        print()


def run_tests(db):
    failures = 0

    def check(label, got, want):
        # got is a function, so a query that does not run fails its own
        # check instead of stopping the suite. A failure prints with ascii(),
        # so it shows even on a console that cannot print the characters.
        nonlocal failures
        try:
            got = got()
        except (Exception, SystemExit) as err:
            got = f"raised {type(err).__name__}: {err}"
        if got == want:
            print(f"PASS  {label}")
        else:
            failures += 1
            print(f"FAIL  {label}\n      got:  {got!a}\n      want: {want!a}")

    def q(conn, name):
        return run_query(conn, SQL_DIR / name)[1]

    def printed(conn, name):
        # The rows of a report as print_table lays them out, below the rule.
        headers, rows = run_query(conn, SQL_DIR / name)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            print_table(headers, rows)
        return out.getvalue().splitlines()[2:]

    names = ["01-log-shape.sql", "02-same-date-naive.sql", "03-comp-stores.sql", "04-weekly-comp.sql",
             "05-weekday-three-ways.sql"]

    check("five stores trade between 2024-12-02 and 2026-01-31, one of them from 2024-12-21 and one with "
          "21 days shut",
          lambda: q(db, "01-log-shape.sql"),
          [("BEDFORD", "2024-12-02", "2026-01-31", 405, 21),
           ("CLAYTON-PARK", "2024-12-21", "2026-01-31", 407, 0),
           ("NORTH-END", "2024-12-02", "2026-01-31", 426, 0),
           ("QUINPOOL", "2024-12-02", "2026-01-31", 426, 0),
           ("SPRING-GARDEN", "2024-12-02", "2026-01-31", 426, 0)])

    check("against the same date a year earlier each Saturday meets a Friday and each Sunday a Saturday, "
          "Saturdays reading +50.2 and Sundays -35.1, and with every store counted the eight weeks read +15.7",
          lambda: q(db, "02-same-date-naive.sql"),
          [("Sun", "Sat", 8, "77715.99", "119659.85", "-35.1"),
           ("Mon", "Sun", 8, "61436.22", "67757.74", "-9.3"),
           ("Tue", "Mon", 8, "65872.07", "53422.00", "+23.3"),
           ("Wed", "Tue", 8, "72594.68", "58799.37", "+23.5"),
           ("Thu", "Wed", 8, "71632.48", "55209.36", "+29.7"),
           ("Fri", "Thu", 8, "106781.57", "66330.61", "+61.0"),
           ("Sat", "Fri", 8, "136095.96", "90640.00", "+50.2"),
           ("all days", None, 56, "592128.97", "511818.93", "+15.7")])

    check("store by store, the store that opened in December 2024 counts on its 43 days with a day 52 weeks "
          "earlier, the one shut in January 2025 on its other 35, and comparable stores come to +2.2",
          lambda: q(db, "03-comp-stores.sql"),
          [("BEDFORD", 56, 35, 35, "138588.24", "91084.53", "88316.69", "+3.1"),
           ("CLAYTON-PARK", 56, 43, 43, "88279.46", "66417.04", "63032.22", "+5.4"),
           ("NORTH-END", 56, 56, 56, "97538.61", "97538.61", "99580.00", "-2.1"),
           ("QUINPOOL", 56, 56, 56, "118745.82", "118745.82", "117037.01", "+1.5"),
           ("SPRING-GARDEN", 56, 56, 56, "148976.84", "148976.84", "143794.08", "+3.6"),
           ("all stores", 280, 246, 246, "592128.97", "522762.84", "511760.00", "+2.2")])

    check("week by week, all-store growth runs from +3.1 to +34.1 while comparable stores stay between -0.2 and "
          "+4.4, and 2025-12-28 to 2026-01-03 is one week",
          lambda: q(db, "04-weekly-comp.sql"),
          [("2025-12-07 to 2025-12-13", "79361.54", "66240.00", "+19.8", 28, "67597.92", "66240.00", "+2.1"),
           ("2025-12-14 to 2025-12-20", "86823.54", "76840.00", "+13.0", 29, "76724.74", "76840.00", "-0.2"),
           ("2025-12-21 to 2025-12-27", "82536.18", "79091.73", "+4.4", 35, "82536.18", "79091.73", "+4.4"),
           ("2025-12-28 to 2026-01-03", "72449.23", "70245.75", "+3.1", 35, "72449.23", "70245.75", "+3.1"),
           ("2026-01-04 to 2026-01-10", "67383.63", "55620.00", "+21.2", 31, "57289.44", "55620.00", "+3.0"),
           ("2026-01-11 to 2026-01-17", "68140.67", "50828.49", "+34.1", 28, "52145.66", "50828.49", "+2.6"),
           ("2026-01-18 to 2026-01-24", "67667.93", "50920.95", "+32.9", 28, "51645.16", "50920.95", "+1.4"),
           ("2026-01-25 to 2026-01-31", "67766.25", "61973.08", "+9.3", 32, "62374.51", "61973.08", "+0.6"),
           ("total", "592128.97", "511760.00", "+15.7", 246, "522762.84", "511760.00", "+2.2")])

    check("by weekday, every store against the same date runs from -35.1 to +61.0, every store against the "
          "same weekday from +8.0 to +31.5, and comparable stores from -6.1 to +16.2",
          lambda: q(db, "05-weekday-three-ways.sql"),
          [("Sun", "-35.1", "+14.7", "+1.0"),
           ("Mon", "-9.3", "+15.0", "+1.4"),
           ("Tue", "+23.3", "+12.0", "-1.4"),
           ("Wed", "+23.5", "+31.5", "+16.2"),
           ("Thu", "+29.7", "+8.0", "-6.1"),
           ("Fri", "+61.0", "+17.8", "+3.3"),
           ("Sat", "+50.2", "+13.8", "+2.1"),
           ("all days", "+15.7", "+15.7", "+2.2")])

    def reports():
        # For each report: its heading, column names, the rule under them, how
        # many rows it prints, and the first and last of them.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run_all(db)
        lines = out.getvalue().split("\n")
        heads = [n for n, line in enumerate(lines) if line.startswith("===")]
        sections = []
        for k, at in enumerate(heads):
            end = heads[k + 1] if k + 1 < len(heads) else len(lines)
            rows = [line for line in lines[at + 3:end] if line]
            sections.append((lines[at], lines[at + 1], lines[at + 2], len(rows), rows[0], rows[-1]))
        return sections

    class Gone:
        # A folder whose one query file is gone by the time it is read.
        def __init__(self, folder):
            self.path = Path(folder) / "01-gone.sql"

        def glob(self, pattern):
            return [self.path]

    def broken_reports():
        results = []
        with tempfile.TemporaryDirectory() as folder:
            for name, data in (("broken", b"SELEC 1;"), ("empty", b""), ("ansi", b"-- caf\xe9\nSELECT 1;"),
                               ("folder", None)):
                sub = Path(folder) / name
                sub.mkdir()
                if data is None:
                    (sub / f"01-{name}.sql").mkdir()
                else:
                    (sub / f"01-{name}.sql").write_bytes(data)
                err = io.StringIO()
                try:
                    with contextlib.redirect_stderr(err):
                        run_all(db, sub)
                    results.append((0, ""))
                except SystemExit as stop:
                    results.append((stop.code, err.getvalue().strip()))
            err = io.StringIO()
            try:
                with contextlib.redirect_stderr(err):
                    run_all(db, Gone(folder))
                results.append((0, ""))
            except SystemExit as stop:
                results.append((stop.code, err.getvalue().strip()))
        return results

    check("all five reports print as tables, with their column names, a rule as wide as each column, how many "
          "rows each prints and the first and last of them, the blank a report leaves printing as a blank "
          "cell; and a query file that fails, has no query result, is not UTF-8 or is gone by the time it is "
          "read, or a folder named like one, stops them with a one-line message",
          lambda: [reports(), broken_reports()],
          [[("=== 01-log-shape.sql ===",
             "store          first_day   last_day    days_open  days_closed",
             "-------------  ----------  ----------  ---------  -----------", 5,
             "BEDFORD        2024-12-02  2026-01-31  405        21",
             "SPRING-GARDEN  2024-12-02  2026-01-31  426        0"),
            ("=== 02-same-date-naive.sql ===",
             "weekday   compared_with  days  sales      same_date_last_year  growth_pct",
             "--------  -------------  ----  ---------  -------------------  ----------", 8,
             "Sun       Sat            8     77715.99   119659.85            -35.1",
             "all days                 56    592128.97  511818.93            +15.7"),
            ("=== 03-comp-stores.sql ===",
             "store          days_open  open_year_before  comp_days  sales      comp_sales  comp_last_year  comp_pct",
             "-------------  ---------  ----------------  ---------  ---------  ----------  --------------  --------",
             6,
             "BEDFORD        56         35                35         138588.24  91084.53    88316.69        +3.1",
             "all stores     280        246               246        592128.97  522762.84   511760.00       +2.2"),
            ("=== 04-weekly-comp.sql ===",
             "week                      sales      last_year  all_stores_pct  comp_days  comp_sales  comp_last_year"
             "  comp_pct",
             "------------------------  ---------  ---------  --------------  ---------  ----------  --------------"
             "  --------", 9,
             "2025-12-07 to 2025-12-13  79361.54   66240.00   +19.8           28         67597.92    66240.00"
             "        +2.1",
             "total                     592128.97  511760.00  +15.7           246        522762.84   511760.00"
             "       +2.2"),
            ("=== 05-weekday-three-ways.sql ===",
             "weekday   same_date_all_stores  same_weekday_all_stores  same_weekday_comp",
             "--------  --------------------  -----------------------  -----------------", 8,
             "Sun       -35.1                 +14.7                    +1.0",
             "all days  +15.7                 +15.7                    +2.2")],
           [(2, '01-broken.sql: did not run: near "SELEC": syntax error'),
            (2, "01-empty.sql: did not run: has no query result to print"),
            (2, "01-ansi.sql: is not UTF-8 text"),
            (2, "01-folder.sql: is a folder, not a query file"),
            (2, "01-gone.sql: No such file or directory")]])

    def reversed_sample():
        # The sample again, stored newest first in a table with no key, so no
        # index hands the rows back in date order unless a query sorts them.
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE sales (sale_date TEXT NOT NULL, store TEXT NOT NULL, "
                     "sales_cents INTEGER NOT NULL)")
        conn.executemany("INSERT INTO sales VALUES (?, ?, ?)", list(reversed(load(SALES_CSV))))
        return [q(conn, name) == q(db, name) for name in names]

    check("the sample stored newest first, in a table with no key to keep it in order, gives the same five "
          "reports",
          reversed_sample, [True] * 5)

    # Logs built for cases the sample does not reach on its own. None of them
    # goes through the loader.
    def days(first, last):
        day, out = datetime.date.fromisoformat(first), []
        while day <= datetime.date.fromisoformat(last):
            out.append(day)
            day += datetime.timedelta(days=1)
        return out

    def weekday(day):
        # Sunday as 0, as strftime('%w') counts.
        return (day.weekday() + 1) % 7

    # One store, open every day from 2023-02-24 to 2024-03-09, selling 100.00
    # on Sundays up to 700.00 on Saturdays in both years. 29 February 2024
    # falls in the first report week.
    leap = new_db([(d.isoformat(), "A", 10000 * (weekday(d) + 1)) for d in days("2023-02-24", "2024-03-09")])
    check("after a leap day the same date a year earlier is 366 days back, so each weekday meets the one two "
          "before it, and 2024-02-29 and 2024-03-01 both land on 2023-03-01, which counts twice; the same "
          "weekday 52 weeks back reads 0.0 throughout on a store that sold the same each weekday",
          lambda: [q(leap, "02-same-date-naive.sql"), q(leap, "04-weekly-comp.sql"),
                   q(leap, "05-weekday-three-ways.sql")],
          [[("Sun", "Sat", 1, "100.00", "700.00", "-85.7"),
            ("Sun", "Fri", 1, "100.00", "600.00", "-83.3"),
            ("Mon", "Sun", 1, "200.00", "100.00", "+100.0"),
            ("Mon", "Sat", 1, "200.00", "700.00", "-71.4"),
            ("Tue", "Mon", 1, "300.00", "200.00", "+50.0"),
            ("Tue", "Sun", 1, "300.00", "100.00", "+200.0"),
            ("Wed", "Tue", 1, "400.00", "300.00", "+33.3"),
            ("Wed", "Mon", 1, "400.00", "200.00", "+100.0"),
            ("Thu", "Wed", 1, "500.00", "400.00", "+25.0"),
            ("Thu", "Tue", 1, "500.00", "300.00", "+66.7"),
            ("Fri", "Wed", 2, "1200.00", "800.00", "+50.0"),
            ("Sat", "Thu", 2, "1400.00", "1000.00", "+40.0"),
            ("all days", None, 14, "5600.00", "5400.00", "+3.7")],
           [("2024-02-25 to 2024-03-02", "2800.00", "2800.00", "0.0", 7, "2800.00", "2800.00", "0.0"),
            ("2024-03-03 to 2024-03-09", "2800.00", "2800.00", "0.0", 7, "2800.00", "2800.00", "0.0"),
            ("total", "5600.00", "5600.00", "0.0", 14, "5600.00", "5600.00", "0.0")],
           [("Sun", "-84.6", "0.0", "0.0"), ("Mon", "-50.0", "0.0", "0.0"), ("Tue", "+100.0", "0.0", "0.0"),
            ("Wed", "+60.0", "0.0", "0.0"), ("Thu", "+42.9", "0.0", "0.0"), ("Fri", "+50.0", "0.0", "0.0"),
            ("Sat", "+40.0", "0.0", "0.0"), ("all days", "+3.7", "0.0", "0.0")]])

    # Three stores. A and B trade every day of the report weeks and of the
    # weeks 52 weeks earlier, except that B is shut from Thursday 2026-01-08
    # to Saturday 2026-01-10. C opens on 2025-01-08, and trades on 2025-01-19,
    # 52 weeks before a day it is shut. The log ends on a Friday, after a part
    # week in which only A and C trade.
    shut = []
    for d in days("2025-01-03", "2025-01-18"):
        shut += [(d.isoformat(), "A", 10000), (d.isoformat(), "B", 20000)]
        shut += [(d.isoformat(), "C", 5000)] if d.isoformat() >= "2025-01-08" else []
    shut.append(("2025-01-19", "C", 5000))
    for d in days("2026-01-04", "2026-01-17"):
        shut += [(d.isoformat(), "A", 11000), (d.isoformat(), "C", 6000)]
        shut += [] if "2026-01-08" <= d.isoformat() <= "2026-01-10" else [(d.isoformat(), "B", 19000)]
    for d in days("2026-01-18", "2026-01-23"):
        shut += [(d.isoformat(), "A", 11000)]
        shut += [] if d.isoformat() == "2026-01-18" else [(d.isoformat(), "C", 6000)]
    shut = new_db(shut)
    check("a store shut now takes the days 52 weeks earlier out of comparable sales with it while every store "
          "still counts them, a store that opens counts from 52 weeks after its first day, and the part week "
          "at the end of the log is left out",
          lambda: [q(shut, name) for name in names[1:]],
          [[("Sun", "Sat", 2, "720.00", "650.00", "+10.8"), ("Mon", "Sun", 2, "720.00", "650.00", "+10.8"),
            ("Tue", "Mon", 2, "720.00", "650.00", "+10.8"), ("Wed", "Tue", 2, "720.00", "650.00", "+10.8"),
            ("Thu", "Wed", 2, "530.00", "700.00", "-24.3"), ("Fri", "Thu", 2, "530.00", "700.00", "-24.3"),
            ("Sat", "Fri", 2, "530.00", "700.00", "-24.3"), ("all days", None, 14, "4470.00", "4700.00", "-4.9")],
           [("A", 14, 14, 14, "1540.00", "1540.00", "1400.00", "+10.0"),
            ("B", 11, 14, 11, "2090.00", "2090.00", "2200.00", "-5.0"),
            ("C", 14, 11, 11, "840.00", "660.00", "550.00", "+20.0"),
            ("all stores", 39, 39, 36, "4470.00", "4290.00", "4150.00", "+3.4")],
           [("2026-01-04 to 2026-01-10", "1950.00", "2300.00", "-15.2", 15, "1770.00", "1700.00", "+4.1"),
            ("2026-01-11 to 2026-01-17", "2520.00", "2450.00", "+2.9", 21, "2520.00", "2450.00", "+2.9"),
            ("total", "4470.00", "4750.00", "-5.9", 36, "4290.00", "4150.00", "+3.4")],
           [("Sun", "+10.8", "+10.8", "+1.5"), ("Mon", "+10.8", "+10.8", "+1.5"), ("Tue", "+10.8", "+10.8", "+1.5"),
            ("Wed", "+10.8", "+2.9", "+2.9"), ("Thu", "-24.3", "-24.3", "+6.0"), ("Fri", "-24.3", "-24.3", "+6.0"),
            ("Sat", "-24.3", "-24.3", "+6.0"), ("all days", "-4.9", "-5.9", "+3.4")]])

    # A log that starts on a Sunday. Z sold nothing in its first week, 4.00 a
    # day in its third, 12.34 and 5.00 a day in the same weeks a year later,
    # and nothing at all in the second week of either year. empty has one
    # report week, and no row in it or in the week 52 weeks earlier. short is
    # a table of 370 days from a Sunday, too short for a report week; the
    # loader refuses it, and the queries have to print no rows for it.
    zero = new_db([(d.isoformat(), "Z", 0) for d in days("2025-01-05", "2025-01-11")]
                  + [(d.isoformat(), "Z", 400) for d in days("2025-01-19", "2025-01-25")]
                  + [(d.isoformat(), "Z", 1234) for d in days("2026-01-04", "2026-01-10")]
                  + [(d.isoformat(), "Z", 500) for d in days("2026-01-18", "2026-01-24")])
    empty = new_db([("2025-01-06", "KIT", 100), ("2026-01-19", "KIT", 100)])
    short = new_db([("2025-01-05", "Z", 100), ("2026-01-09", "Z", 100)])
    check("a log that starts on a Sunday reports from exactly 52 weeks later, a week with no sales in either "
          "year still prints, and growth on a year earlier that sold nothing is left blank, in the printed "
          "reports too; a log whose only report week has no row in either year still prints every total line; "
          "and a table too short for a report week, which the loader refuses, gives no report rows",
          lambda: [q(zero, "04-weekly-comp.sql"), q(zero, "03-comp-stores.sql")[0],
                   q(zero, "02-same-date-naive.sql")[0], q(zero, "05-weekday-three-ways.sql")[0],
                   printed(zero, "04-weekly-comp.sql")[:2], printed(zero, "05-weekday-three-ways.sql")[0],
                   printed(zero, "02-same-date-naive.sql")[0], [q(empty, name)[-1] for name in names[1:]],
                   q(empty, "03-comp-stores.sql"), [q(short, name) for name in names[1:]]],
          [[("2026-01-04 to 2026-01-10", "86.38", "0.00", None, 7, "86.38", "0.00", None),
            ("2026-01-11 to 2026-01-17", "0.00", "0.00", None, 0, "0.00", "0.00", None),
            ("2026-01-18 to 2026-01-24", "35.00", "28.00", "+25.0", 7, "35.00", "28.00", "+25.0"),
            ("total", "121.38", "28.00", "+333.5", 14, "121.38", "28.00", "+333.5")],
           ("Z", 14, 14, 14, "121.38", "121.38", "28.00", "+333.5"),
           ("Sun", "Sat", 3, "17.34", "0.00", None),
           ("Sun", None, "+333.5", "+333.5"),
           ["2026-01-04 to 2026-01-10  86.38   0.00                       7          86.38       0.00",
            "2026-01-11 to 2026-01-17  0.00    0.00                       0          0.00        0.00"],
           "Sun                             +333.5                   +333.5",
           "Sun       Sat            3     17.34   0.00",
           [("all days", None, 7, "0.00", "0.00", None), ("all stores", 0, 0, 0, "0.00", "0.00", "0.00", None),
            ("total", "0.00", "0.00", None, 0, "0.00", "0.00", None), ("all days", None, None, None)],
           [("all stores", 0, 0, 0, "0.00", "0.00", "0.00", None)],
           [[], [], [], []]])

    # P sold 400.00 a day a year earlier; Q opened in the report weeks. The
    # amounts are chosen so every growth figure lands on an exact half, with
    # one above zero and one below in each column of queries 02, 04 and 05:
    # -2.05, 4.35, 2.15, -0.15, 0.85, 21.15 and 9.75 percent by weekday with
    # every store, 10.65 and -0.35 by week, and so on.
    p1 = [38260, 40860, 40060, 39940, 40340, 40020, 49900]
    p2 = [38260, 40860, 40060, 39940, 40340, 40020, 37580]
    q1 = [860, 780, 1600, 0, 0, 16880, 320]
    q2 = [980, 980, 0, 0, 0, 0, 0]
    halves = [(d.isoformat(), "P", 40000) for d in days("2025-01-04", "2025-01-18")]
    for k, d in enumerate(days("2026-01-04", "2026-01-17")):
        halves += [(d.isoformat(), "P", (p1 if k < 7 else p2)[weekday(d)]),
                   (d.isoformat(), "Q", (q1 if k < 7 else q2)[weekday(d)])]
    halves = new_db(halves)
    check("every growth figure on a log built for it lands on an exact half and rounds away from zero, above zero "
          "and below in each column of queries 02, 04 and 05, and a store with no day to compare leaves its "
          "growth blank",
          lambda: [q(halves, "02-same-date-naive.sql"), q(halves, "03-comp-stores.sql"),
                   q(halves, "04-weekly-comp.sql"), q(halves, "05-weekday-three-ways.sql")],
          [[("Sun", "Sat", 2, "783.60", "800.00", "-2.1"), ("Mon", "Sun", 2, "834.80", "800.00", "+4.4"),
            ("Tue", "Mon", 2, "817.20", "800.00", "+2.2"), ("Wed", "Tue", 2, "798.80", "800.00", "-0.2"),
            ("Thu", "Wed", 2, "806.80", "800.00", "+0.9"), ("Fri", "Thu", 2, "969.20", "800.00", "+21.2"),
            ("Sat", "Fri", 2, "878.00", "800.00", "+9.8"), ("all days", None, 14, "5888.40", "5600.00", "+5.2")],
           [("P", 14, 14, 14, "5664.40", "5664.40", "5600.00", "+1.2"),
            ("Q", 14, 0, 0, "224.00", "0.00", "0.00", None),
            ("all stores", 28, 14, 14, "5888.40", "5664.40", "5600.00", "+1.2")],
           [("2026-01-04 to 2026-01-10", "3098.20", "2800.00", "+10.7", 7, "2893.80", "2800.00", "+3.4"),
            ("2026-01-11 to 2026-01-17", "2790.20", "2800.00", "-0.4", 7, "2770.60", "2800.00", "-1.1"),
            ("total", "5888.40", "5600.00", "+5.2", 14, "5664.40", "5600.00", "+1.2")],
           [("Sun", "-2.1", "-2.1", "-4.4"), ("Mon", "+4.4", "+4.4", "+2.2"), ("Tue", "+2.2", "+2.2", "+0.2"),
            ("Wed", "-0.2", "-0.2", "-0.2"), ("Thu", "+0.9", "+0.9", "+0.9"), ("Fri", "+21.2", "+21.2", "+0.1"),
            ("Sat", "+9.8", "+9.8", "+9.4"), ("all days", "+5.2", "+5.2", "+1.2")]])

    def agree(conn):
        # The total lines, which each query works out on its own: same-date
        # growth in 02 and 05, all-store growth in 04 and 05, comparable growth
        # in 03, 04 and 05, and comparable sales now and a year earlier in 03
        # and 04.
        s02, s03, s04, s05 = (q(conn, name)[-1] for name in names[1:])
        return [s02[5] == s05[1], s04[3] == s05[2], s03[7] == s04[7] == s05[3], s03[5] == s04[5],
                s03[6] == s04[6]]

    check("the reports agree on the totals they each work out, same-date growth in 02 and 05, all-store growth "
          "in 04 and 05, comparable growth in 03, 04 and 05 and comparable sales in 03 and 04, on the sample and "
          "on the leap-day, shut-store, Sunday-start, empty-week and exact-half logs",
          lambda: [agree(conn) for conn in (db, leap, shut, zero, empty, halves)],
          [[True] * 5] * 6)

    # The costliest log tried within the loader's limits: one store on the
    # first and last day allowed, so the report weeks run from 1971 to 2200,
    # and 99998 stores on one day inside them, 100000 rows in all.
    costly = new_db([(str(FIRST_DAY), "A", 1), (str(LAST_DAY), "A", 1)]
                    + [("1971-02-05", f"S{n}", 100 + n % 97) for n in range(MOST_ROWS - 2)])

    def ends(conn, name):
        rows = q(conn, name)
        return len(rows), rows[0], rows[-1]

    def endless(folder):
        path = Path(folder) / "endless.sql"
        path.write_text("WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) "
                        "SELECT MAX(i) FROM n;", encoding="utf-8")
        try:
            return run_query(db, path)
        except sqlite3.OperationalError as err:
            return str(err)

    with tempfile.TemporaryDirectory() as tmp:
        check("100000 rows spanning 1970-01-01 to 2200-12-31, 99998 of them from different stores on one day, run "
              "through every query inside the step budget, and a query that would run for ever is stopped by it",
              lambda: [ends(costly, name) for name in names] + [endless(tmp)],
              [(99999, ("A", "1970-01-01", "2200-12-31", 2, 84369), ("S99997", "1971-02-05", "1971-02-05", 1, 0)),
               (15, ("Sun", "Sat", 9081, "0.00", "0.00", None),
                ("all days", None, 84000, "147993.08", "147993.08", "0.0")),
               (99999, ("S0", 1, 1, 0, "1.00", "0.00", "0.00", None),
                ("all stores", 99998, 99998, 0, "147993.08", "0.00", "0.00", None)),
               (12001, ("1971-01-03 to 1971-01-09", "0.00", "0.00", None, 0, "0.00", "0.00", None),
                ("total", "147993.08", "147993.08", "0.0", 0, "0.00", "0.00", None)),
               (8, ("Sun", None, None, None), ("all days", "0.0", "0.0", None)),
               f"stopped after {STEP_BUDGET} thousand steps"])

    # The loader, on the included bad file and on small files written here.
    # A crash on one of these files comes back as a value too, so it fails
    # its check like any other wrong answer; files the loader accepts come
    # back with what it loaded.
    def rejection(fn, *args):
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                loaded = fn(*args)
        except SystemExit as stop:
            return stop.code, err.getvalue().strip().splitlines()[-1] if err.getvalue().strip() else ""
        except Exception as crash:
            return f"raised {type(crash).__name__}", str(crash)
        return 0, loaded

    with tempfile.TemporaryDirectory() as tmp:
        def csv_file(name, content):
            path = Path(tmp) / name
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(content)
            return path

        def byte_file(name, data):
            path = Path(tmp) / name
            path.write_bytes(data)
            return path

        head = ",".join(COLUMNS) + "\n"
        # Two rows a year apart make a log with a report week: 371 days from
        # a Sunday.
        small = head + "2025-01-05,KIT,10.00\n2026-01-10,KIT,12.00\n"

        def logs(name, content):
            return rejection(load, csv_file(name, content))

        def sized(result):
            code, loaded = result
            return (code, len(loaded)) if code == 0 else result

        check("the included bad log is refused for 29 February in a year that has none, and a store listed "
              "twice on one day is refused by name",
              lambda: [rejection(load, HERE / "data" / "invalid-sales.csv"),
                       logs("twice.csv", small + "2025-01-05,KIT,3.00\n")],
              [(2, "invalid-sales.csv row 405: sale_date '2025-02-29' is not a calendar date written like "
                   "2025-12-07, from 1970-01-01 to 2200-12-31"),
               (2, "twice.csv row 4: KIT appears twice for 2025-01-05; one row per store and day, with the day's "
                   "sales added together")])

        bad_days = ["2025-02-29", "2025-13-01", "2025-00-10", "2025-04-31", "2025-1-05", "25-01-05", "2025/01/05",
                    "05-01-2025", "20250105", "1969-12-31", "2201-01-01", "", "2025-01-05 09:00",
                    "\uff12\uff10\uff12\uff15-01-05"]
        check("a day that is not on the calendar, written in another form, with a time, in fullwidth digits, "
              "before 1970 or after 2200, or blank is refused, while 1970-01-01, 2200-12-31 and 2024-02-29 load",
              lambda: [logs(f"day{k}.csv", small + f"{raw},KIT,1.00\n") for k, raw in enumerate(bad_days)]
                      + [logs("bounds.csv", head + "1970-01-01,KIT,1.00\n2024-02-29,KIT,2.00\n2200-12-31,KIT,3.00\n")],
              [(2, f"day{k}.csv row 4: sale_date {raw!r} is not a calendar date written like 2025-12-07, "
                   "from 1970-01-01 to 2200-12-31") for k, raw in enumerate(bad_days)]
              + [(0, [("1970-01-01", "KIT", 100), ("2024-02-29", "KIT", 200), ("2200-12-31", "KIT", 300)])])

        codes = [("lower.csv", "kit"), ("space.csv", "KIT 2"), ("double.csv", "KIT--2"), ("edge.csv", "-KIT"),
                 ("trailing.csv", "KIT-"), ("long.csv", "A" * 25), ("blank.csv", ""), ("accent.csv", "CAF\u00c9"),
                 ("fullwidth.csv", "\uff2b\uff29\uff34")]
        bad_amounts = ["-5.00", "5", "5.0", "5.000", "05.00", "1000000.00", "1e3", "", "1,843.20", "$5.00", ".50",
                       "\u0661\u0660.\u0660\u0660", "1\u0660.\u0660\u0660"]
        check("a store code in lower case, with a space, a doubled or outer hyphen, an accent, fullwidth letters, "
              "over 24 characters or blank is refused, and one of exactly 24 characters with two hyphens loads; "
              "an amount that is negative, whole, with one or three decimal places, zero-padded, of seven digits, "
              "in exponent form, blank, with a comma, a dollar sign or no digit before the point, or with "
              "Arabic-Indic digits in it is refused, while 0.00 and 999999.99 load",
              lambda: [logs(name, small + f"2025-01-06,{raw},1.00\n") for name, raw in codes]
                      + [logs("max.csv", small + "2025-01-06,ABCDEFGH-1234567-ABCDEFG,1.00\n")]
                      + [logs(f"amount{k}.csv", small + f'2025-01-06,KIT,"{raw}"\n')
                         for k, raw in enumerate(bad_amounts)]
                      + [logs("extremes.csv", small + "2025-01-06,KIT,0.00\n2025-01-07,KIT,999999.99\n")],
              [(2, f"{name} row 4: store {raw!r} is not a store code: capital letters A to Z and digits 0 to 9, "
                   "joined by single hyphens, at most 24 characters") for name, raw in codes]
              + [(0, [("2025-01-05", "KIT", 1000), ("2026-01-10", "KIT", 1200),
                      ("2025-01-06", "ABCDEFGH-1234567-ABCDEFG", 100)])]
              + [(2, f"amount{k}.csv row 4: sales {raw!r} is not an amount from 0.00 to 999999.99 written like "
                     "1843.20") for k, raw in enumerate(bad_amounts)]
              + [(0, [("2025-01-05", "KIT", 1000), ("2026-01-10", "KIT", 1200), ("2025-01-06", "KIT", 0),
                      ("2025-01-07", "KIT", 99999999)])])

        check("rows are counted past blank lines and a line of spaces, and a stray quote is named by its own row, "
              "in a data row or in the header; rows with too many or too few fields, a line of commas, a tab, "
              "text after a closing quote, a quote left open, a field past the parser's limit, and a bad, renamed "
              "or reordered header, also one found after blank lines, written as one quoted field or with a "
              "trailing comma, are refused, and a long value or header is cut short in the message, by one "
              "character as well as by many",
              lambda: [logs("rows.csv", small + "\n   \n\n2025-01-06,kit,1.00\n"),
                       logs("quote.csv", small + '2025-01-06,"KIT,1.00\n2025-01-07,KIT",1.00\n'),
                       logs("unclosed.csv", small + '2025-01-06,"KIT,1.00\n'),
                       logs("wide.csv", small + "2025-01-06,KIT,1.00,extra\n"),
                       logs("narrow.csv", small + "2025-01-06,KIT\n"),
                       logs("commas.csv", small + ",,\n"),
                       logs("tab.csv", small + "2025-01-06,KIT\t,1.00\n"),
                       logs("after.csv", small + '2025-01-06,"KIT"x,1.00\n'),
                       logs("huge_field.csv", small + "2025-01-06," + "A" * 200000 + ",1.00\n"),
                       logs("header.csv", 'sale_date,"store"x,sales\n2025-01-05,KIT,1.00\n'),
                       logs("open_header.csv", '"sale_date,store,sales\n2025-01-05,KIT,1.00\n'),
                       logs("span_header.csv", '\n\nsale_date,"store,sales\n2025-01-05,KIT",1.00\n'),
                       logs("renamed.csv", "sale_date,shop,sales\n2025-01-05,KIT,1.00\n"),
                       logs("reordered.csv", "store,sale_date,sales\nKIT,2025-01-05,1.00\n"),
                       logs("late_renamed.csv", "\nsale_date,shop,sales\n2025-01-05,KIT,1.00\n"),
                       logs("quoted_header.csv", '"sale_date,store,sales"\n"2025-01-05,KIT,1.00"\n'),
                       logs("trailing_comma.csv", "sale_date,store,sales,\n2025-01-05,KIT,1.00,\n"),
                       logs("long_header.csv", "sale_date,store,sales" + "x" * 100 + "\n2025-01-05,KIT,1.00\n"),
                       logs("long_value.csv", small + "2025-01-06," + "B" * 100 + ",1.00\n"),
                       logs("just_over.csv", small + "2025-01-06," + "C" * 41 + ",1.00\n")],
              [(2, "rows.csv row 7: store 'kit' is not a store code: capital letters A to Z and digits 0 to 9, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "quote.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "unclosed.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "wide.csv row 4: has more fields than the header"),
               (2, "narrow.csv row 4: has fewer fields than the header"),
               (2, "commas.csv row 4: sale_date '' is not a calendar date written like 2025-12-07, "
                   "from 1970-01-01 to 2200-12-31"),
               (2, "tab.csv row 4: store 'KIT\\t' is not a store code: capital letters A to Z and digits 0 to 9, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "after.csv row 4: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "huge_field.csv row 4: has a field over 131072 characters long"),
               (2, "header.csv row 1: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "open_header.csv row 1: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "span_header.csv row 3: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "renamed.csv row 1: expected columns 'sale_date,store,sales', got 'sale_date,shop,sales'"),
               (2, "reordered.csv row 1: expected columns 'sale_date,store,sales', got 'store,sale_date,sales'"),
               (2, "late_renamed.csv row 2: expected columns 'sale_date,store,sales', got 'sale_date,shop,sales'"),
               (2, "quoted_header.csv row 1: expected columns 'sale_date,store,sales', "
                   "got '\"sale_date,store,sales\"'"),
               (2, "trailing_comma.csv row 1: expected columns 'sale_date,store,sales', got 'sale_date,store,sales,'"),
               (2, "long_header.csv row 1: expected columns 'sale_date,store,sales', got 'sale_date,store,sales"
                   + "x" * 19 + "' and 81 more characters"),
               (2, "long_value.csv row 4: store '" + "B" * 40 + "' and 60 more characters is not a store code: "
                   "capital letters A to Z and digits 0 to 9, joined by single hyphens, at most 24 characters"),
               (2, "just_over.csv row 4: store '" + "C" * 40 + "' and 1 more character is not a store code: "
                   "capital letters A to Z and digits 0 to 9, joined by single hyphens, at most 24 characters")])

        class Dropped:
            # A file that gives way partway through, as one on a dropped
            # network share does.
            def __init__(self, text):
                self.lines = io.StringIO(text).readlines()

            def readline(self, size):
                if not self.lines:
                    raise OSError(5, "Input/output error")
                return self.lines.pop(0)

        def dropped(text):
            path = Path(tmp) / "dropped.csv"
            lines, _ = open_csv(path, Dropped(text), COLUMNS)
            return list(records(path, lines, COLUMNS))

        def capped(text):
            return len(list(read_lines(Path(tmp) / "cap.csv", io.StringIO(text))))

        far_down = "".join(f"2025-01-06,C{c},1.00\n" for c in range(20000))
        check("an empty file, one of blank lines, one with only a header, also after a blank line, one that is "
              "not UTF-8 from its first line or only far down, or holds only part of a byte-order mark, a folder, "
              "a read that gives way before the header or partway through, and a line past 1000000 characters "
              "are refused, a line of exactly 1000000 passing; while a byte-order mark, blank lines before the "
              "header, spaces around unquoted fields, in the header too, and a line holding one empty quoted "
              "field, which is passed over like a blank one, load",
              lambda: [logs("empty.csv", ""),
                       logs("blank_only.csv", "\n  \n\n"),
                       logs("bare.csv", head),
                       logs("late_bare.csv", "\n" + head),
                       rejection(load, byte_file("latin1.csv", b"sale_date,store,sales\xc9\n2025-01-05,KIT,1.00\n")),
                       rejection(load, byte_file("late_latin1.csv", (head + far_down).encode("utf-8")
                                                 + b"2025-01-07,CAF\xc9,1.00\n")),
                       rejection(load, byte_file("part_mark.csv", b"\xef\xbb")),
                       rejection(load, Path(tmp)),
                       rejection(dropped, ""),
                       rejection(dropped, small),
                       logs("long_line.csv", small + "," * 1000001 + "\n"),
                       rejection(capped, "x" * 1000001 + "\n"),
                       rejection(capped, "x" * 1000000 + "\r\n"),
                       logs("marked.csv", "\ufeff sale_date , store , sales \n 2025-01-05 , KIT , 10.00 \n"
                            "2026-01-10,KIT,12.00\n"),
                       logs("leading.csv", "\n  \n" + small),
                       logs("quoted_blank.csv", small + '""\n')],
              [(2, "empty.csv: is empty"),
               (2, "blank_only.csv: is empty"),
               (2, "bare.csv row 1: no data rows after the header"),
               (2, "late_bare.csv row 2: no data rows after the header"),
               (2, "latin1.csv: is not UTF-8 text"),
               (2, "late_latin1.csv: is not UTF-8 text"),
               (2, "part_mark.csv: is not UTF-8 text"),
               (2, f"{Path(tmp).name}: is a folder, not a file"),
               (2, "dropped.csv: Input/output error"),
               (2, "dropped.csv: Input/output error"),
               (2, "long_line.csv row 4: runs past 1000000 characters on one line"),
               (2, "cap.csv row 1: runs past 1000000 characters on one line"),
               (0, 1),
               (0, [("2025-01-05", "KIT", 1000), ("2026-01-10", "KIT", 1200)]),
               (0, [("2025-01-05", "KIT", 1000), ("2026-01-10", "KIT", 1200)]),
               (0, [("2025-01-05", "KIT", 1000), ("2026-01-10", "KIT", 1200)])])

        # 100 stores over 1000 days from Sunday 2020-01-05 is exactly the limit.
        spread = head + "".join(f"{datetime.date(2020, 1, 5) + datetime.timedelta(days=n)},S{s},1.00\n"
                                for n in range(1000) for s in range(100))
        check("a log whose weeks never have the same week 52 weeks earlier inside it is refused, at 370 days from "
              "a Sunday and at 376 from a Monday, while 371 days from a Sunday and 377 from a Monday load; and a "
              "log of more than 100000 rows is stopped as it is read, before a bad byte further down, while one "
              "of exactly 100000 loads",
              lambda: [logs("short.csv", head + "2025-01-05,KIT,1.00\n2026-01-09,KIT,1.00\n"),
                       sized(logs("enough.csv", head + "2025-01-05,KIT,1.00\n2026-01-10,KIT,1.00\n")),
                       logs("monday.csv", head + "2025-01-06,KIT,1.00\n2026-01-16,KIT,1.00\n"),
                       sized(logs("monday_enough.csv", head + "2025-01-06,KIT,1.00\n2026-01-17,KIT,1.00\n")),
                       rejection(load, byte_file("too_many.csv", (spread + "2025-01-05,EXTRA,1.00\n"
                                                                  + far_down).encode("utf-8")
                                                 + b"2025-01-07,CAF\xc9,1.00\n")),
                       sized(logs("at_limit.csv", spread))],
              [(2, "short.csv: the log runs from 2025-01-05 to 2026-01-09, and none of its Sunday-to-Saturday "
                   "weeks has the same week 52 weeks earlier in the log as well; that takes at least 371 days"),
               (0, 2),
               (2, "monday.csv: the log runs from 2025-01-06 to 2026-01-16, and none of its Sunday-to-Saturday "
                   "weeks has the same week 52 weeks earlier in the log as well; that takes at least 371 days"),
               (0, 2),
               (2, f"too_many.csv row {MOST_ROWS + 2}: the log runs past 100000 rows"),
               (0, MOST_ROWS)])

        def utf8_check():
            # Output written in the Windows codepage cannot hold these
            # characters; after utf8_output it goes out as UTF-8. stderr
            # keeps its backslashreplace handler, so a file name holding a
            # lone surrogate, which Windows allows, still prints. A stream
            # with no way to switch, as under IDLE, is left as it is.
            saved = sys.stdout, sys.stderr
            out, err = io.BytesIO(), io.BytesIO()
            sys.stdout = io.TextIOWrapper(out, encoding="cp1252", newline="\n")
            sys.stderr = io.TextIOWrapper(err, encoding="cp1252", errors="backslashreplace", newline="\n")
            try:
                utf8_output()
                print("\u6f22\u5b57.csv")
                print("\u6f22\u5b57.csv", file=sys.stderr)
                print("bad" + chr(0xDC80) + ".csv", file=sys.stderr)
                sys.stdout.flush()
                sys.stderr.flush()
                switched = out.getvalue().decode("utf-8"), err.getvalue().decode("utf-8")
                sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
                utf8_output()
                print("\u6f22\u5b57.csv")
                return switched, sys.stdout.getvalue()
            finally:
                sys.stdout, sys.stderr = saved

        other = csv_file("other.csv", SALES_CSV.read_text(encoding="utf-8"))

        def cli(*argv):
            return rejection(settings, [str(a) for a in argv])

        def main_check():
            # main itself, on a file name the Windows codepage cannot hold. It
            # stops at the missing file, and the message has to come out as
            # UTF-8. The command line has no --test, so no suite is started.
            saved = sys.argv, sys.stdout, sys.stderr
            err = io.BytesIO()
            name = "\u6f22\u5b57.csv"
            sys.argv = ["run.py", "--sales", str(Path(tmp) / name)]
            sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="\n")
            sys.stderr = io.TextIOWrapper(err, encoding="cp1252", newline="\n")
            try:
                main()
                return "main returned"
            except SystemExit as stop:
                sys.stderr.flush()
                return stop.code, name in err.getvalue().decode("utf-8")
            finally:
                sys.argv, sys.stdout, sys.stderr = saved

        check("on the command line, a file that is not there, a name with a wildcard in it and a test run on any "
              "file other than the sample are refused, while the sample is picked by default or spelled another "
              "way and a log of your own is taken; output and messages are written as UTF-8 by the helper that "
              "sets them up, which keeps the error handler of a stream it switches, so a lone surrogate in a "
              "name still prints, and leaves alone a stream it cannot switch, and main's own messages come out as "
              "UTF-8",
              lambda: [cli("--sales", Path(tmp) / "not_there.csv"),
                       cli("--sales", Path(tmp) / "data*.csv"),
                       cli("--test", "--sales", other),
                       cli("--test"),
                       cli(),
                       cli("--test", "--sales", HERE / "data" / ".." / "data" / "sales.csv"),
                       cli("--sales", other),
                       utf8_check(),
                       main_check()],
              [(2, f"run.py: error: --sales: '{Path(tmp) / 'not_there.csv'}' is not a file"),
               (2, f"run.py: error: --sales: '{Path(tmp) / 'data*.csv'}' is not a file"),
               (2, "run.py: error: --test checks hand-computed answers for the sample file; "
                   "run it without --sales"),
               (0, (True, SALES_CSV)),
               (0, (False, SALES_CSV)),
               (0, (True, HERE / "data" / ".." / "data" / "sales.csv")),
               (0, (False, other)),
               (("\u6f22\u5b57.csv\n", "\u6f22\u5b57.csv\nbad" + chr(92) + "udc80.csv\n"), "\u6f22\u5b57.csv\n"),
               (2, True)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def settings(argv):
    # Reads the command line and settles which file to load. It never runs a
    # query or the suite, so the suite can check it directly.
    parser = argparse.ArgumentParser(prog="run.py", description="Run the comparable-sales queries against a "
                                                 "daily sales log, the sample by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--sales", type=Path, default=None, help="path to an alternate daily sales CSV")
    args = parser.parse_args(argv)
    path = args.sales or SALES_CSV
    try:
        found = path.is_file()
    except OSError:
        # Python 3.7 raises here for a name Windows cannot hold, such as one
        # with a wildcard in it.
        found = False
    if not found:
        if args.sales is not None:
            parser.error(f"--sales: '{path}' is not a file")
        parser.error(f"the sample file '{path}' is missing")
    if args.test and path.resolve() != SALES_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample file; run it without --sales")
    return args.test, path


def utf8_output():
    # Output is written as UTF-8, since a file name in a message can hold
    # characters that the Windows console codepage cannot print. Each stream
    # keeps its own error handler: stderr's backslashreplace still prints a
    # name holding a lone surrogate. A stream with no way to switch, as under
    # IDLE, is left as it is.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors=stream.errors)


def main():
    utf8_output()
    test, path = settings(sys.argv[1:])
    db = new_db(load(path))
    if test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
