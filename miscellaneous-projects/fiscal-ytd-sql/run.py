"""Load a monthly revenue log into SQLite and run the fiscal year-to-date queries.

Usage:
    python run.py                     run every query in sql/
    python run.py --test              run the assertion suite
    python run.py --revenue log.csv   load a different log
"""

import argparse
import contextlib
import csv
import io
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
REVENUE_CSV = HERE / "data" / "revenue.csv"
SQL_DIR = HERE / "sql"
COLUMNS = ["month", "revenue"]
# Months run from 1970-01 to 2200-12 and each appears once, so a log holds
# at most 2772 rows, and a longer one is refused at the first row that
# repeats a month or falls outside the range. A month's revenue is at most
# 99999999.99, so no total the queries keep, twelve months at most, passes
# 1.2 * 10**11 cents, and the growth arithmetic stays well inside SQLite's
# 64-bit integers.
FIRST_YEAR, LAST_YEAR = 1970, 2200
# A query that runs past this many thousand SQLite steps is stopped. The
# sample takes under ten for each query. The costliest log the limits above
# allow, every month at the largest amount, takes under a twentieth of it on
# SQLite 3.50, 3.34 and 3.31 alike, so only a query that would run away
# reaches it.
STEP_BUDGET = 20_000
# A line of the file may hold at most this many characters. A real row
# holds a dozen or so.
LINE_CAP = 1_000_000


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
    # A longer line is refused, so one enormous line is never held in memory
    # whole. The byte-order mark that Excel puts on its CSV exports is
    # dropped here.
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


def month_of(path, row_num, raw):
    # The queries match months as text and read the year and month out of
    # fixed places, so a month is held to one form.
    match = re.fullmatch(r"([0-9]{4})-([0-9]{2})", raw)
    if not match or not FIRST_YEAR <= int(match.group(1)) <= LAST_YEAR or not 1 <= int(match.group(2)) <= 12:
        fail(path, row_num, f"month {shown(raw)} is not a month written like 2025-04, "
                            f"from {FIRST_YEAR}-01 to {LAST_YEAR}-12")
    return raw


def cents(path, row_num, raw):
    # Two decimal places, no sign, no thousands separator, no currency mark.
    # 0.00 is a month that brought in nothing, which is not the same as a
    # month with no row: the queries read a missing month as unknown.
    match = re.fullmatch(r"(0|[1-9][0-9]{0,7})\.([0-9]{2})", raw)
    if not match:
        fail(path, row_num, f"revenue {shown(raw)} is not an amount from 0.00 to 99999999.99 written like 1250.00")
    return int(match.group(1)) * 100 + int(match.group(2))


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
            month = month_of(path, i, row["month"])
            amount = cents(path, i, row["revenue"])
            if month in seen:
                fail(path, i, f"{month} appears twice; one row per month, with the amounts added together")
            seen.add(month)
            rows.append((month, amount))
    if not rows:
        fail(path, header_line, "no data rows after the header")
    return rows


def new_db(rows):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE revenue (month TEXT PRIMARY KEY, revenue_cents INTEGER NOT NULL)")
    db.executemany("INSERT INTO revenue VALUES (?, ?)", rows)
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

    def pick(rows, *months):
        # The rows of a report for the months named, in report order.
        return [row for row in rows if row[0] in months]

    def printed(conn, name):
        # The rows of a report as print_table lays them out, below the rule.
        headers, rows = run_query(conn, SQL_DIR / name)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            print_table(headers, rows)
        return out.getvalue().splitlines()[2:]

    check("the log runs from 2024-04 to 2026-08 on 28 rows, with one month missing and one at zero, across "
          "fiscal years 2024-25 to 2026-27, and ends in the fifth month of the last",
          lambda: q(db, "01-log-shape.sql"),
          [("2024-04", "2026-08", 28, 1, 1, "2024-25", "2026-27", 5)])

    check("the calendar running total starts again each January, so 2025-01 and 2026-01 count one month, and "
          "set against last year's calendar months it reads 4 percent up at 2026-08",
          lambda: q(db, "02-calendar-ytd.sql"),
          [("2024-04", 1, "161347.20", None, None),
           ("2024-05", 2, "404665.97", None, None),
           ("2024-06", 3, "817349.90", None, None),
           ("2024-07", 4, "1418902.08", None, None),
           ("2024-08", 5, "2049676.54", None, None),
           ("2024-09", 6, "2434806.19", None, None),
           ("2024-10", 7, "2674272.71", None, None),
           ("2024-11", 8, "2674272.71", None, None),
           ("2025-01", 1, "92877.14", None, None),
           ("2025-02", 2, "169192.53", None, None),
           ("2025-03", 3, "284633.51", None, None),
           ("2025-04", 4, "466149.11", "161347.20", 189),
           ("2025-05", 5, "728551.51", "404665.97", 80),
           ("2025-06", 6, "1154293.80", "817349.90", 41),
           ("2025-07", 7, "1775899.60", "1418902.08", 25),
           ("2025-08", 8, "2414247.11", "2049676.54", 18),
           ("2025-09", 9, "2794918.69", "2434806.19", 15),
           ("2025-10", 10, "3031111.58", "2674272.71", 13),
           ("2025-11", 11, "3148779.58", "2674272.71", 18),
           ("2025-12", 12, "3307553.00", None, None),
           ("2026-01", 1, "143955.28", "92877.14", 55),
           ("2026-02", 2, "264789.43", "169192.53", 57),
           ("2026-03", 3, "434180.04", "284633.51", 53),
           ("2026-04", 4, "620233.53", "466149.11", 33),
           ("2026-05", 5, "875878.45", "728551.51", 20),
           ("2026-06", 6, "1291665.09", "1154293.80", 12),
           ("2026-07", 7, "1897112.07", "1775899.60", 7),
           ("2026-08", 8, "2510553.30", "2414247.11", 4)])

    check("the fiscal running total starts again each April, a month at 0.00 adds nothing, and the missing "
          "2024-12 leaves 2024-25 without a total from there to March",
          lambda: q(db, "03-fiscal-ytd.sql"),
          [("2024-04", "2024-25", 1, "161347.20", "161347.20", None),
           ("2024-05", "2024-25", 2, "243318.77", "404665.97", None),
           ("2024-06", "2024-25", 3, "412683.93", "817349.90", None),
           ("2024-07", "2024-25", 4, "601552.18", "1418902.08", None),
           ("2024-08", "2024-25", 5, "630774.46", "2049676.54", None),
           ("2024-09", "2024-25", 6, "385129.65", "2434806.19", None),
           ("2024-10", "2024-25", 7, "239466.52", "2674272.71", None),
           ("2024-11", "2024-25", 8, "0.00", "2674272.71", None),
           ("2024-12", "2024-25", 9, None, None, "2024-12"),
           ("2025-01", "2024-25", 10, "92877.14", None, "2024-12"),
           ("2025-02", "2024-25", 11, "76315.39", None, "2024-12"),
           ("2025-03", "2024-25", 12, "115440.98", None, "2024-12"),
           ("2025-04", "2025-26", 1, "181515.60", "181515.60", None),
           ("2025-05", "2025-26", 2, "262402.40", "443918.00", None),
           ("2025-06", "2025-26", 3, "425742.29", "869660.29", None),
           ("2025-07", "2025-26", 4, "621605.80", "1491266.09", None),
           ("2025-08", "2025-26", 5, "638347.51", "2129613.60", None),
           ("2025-09", "2025-26", 6, "380671.58", "2510285.18", None),
           ("2025-10", "2025-26", 7, "236192.89", "2746478.07", None),
           ("2025-11", "2025-26", 8, "117668.00", "2864146.07", None),
           ("2025-12", "2025-26", 9, "158773.42", "3022919.49", None),
           ("2026-01", "2025-26", 10, "143955.28", "3166874.77", None),
           ("2026-02", "2025-26", 11, "120834.15", "3287708.92", None),
           ("2026-03", "2025-26", 12, "169390.61", "3457099.53", None),
           ("2026-04", "2026-27", 1, "186053.49", "186053.49", None),
           ("2026-05", "2026-27", 2, "255644.92", "441698.41", None),
           ("2026-06", "2026-27", 3, "415786.64", "857485.05", None),
           ("2026-07", "2026-27", 4, "605446.98", "1462932.03", None),
           ("2026-08", "2026-27", 5, "613441.23", "2076373.26", None)])

    check("against last year to the same fiscal month, 2026-27 goes from 3 percent up in April to 3 percent "
          "down in August while the calendar growth stays above zero, and the months that lean on the missing "
          "2024-12 have no growth",
          lambda: q(db, "04-fiscal-growth.sql"),
          [("2025-04", "2025-26", 1, "181515.60", "161347.20", 13, 189),
           ("2025-05", "2025-26", 2, "443918.00", "404665.97", 10, 80),
           ("2025-06", "2025-26", 3, "869660.29", "817349.90", 6, 41),
           ("2025-07", "2025-26", 4, "1491266.09", "1418902.08", 5, 25),
           ("2025-08", "2025-26", 5, "2129613.60", "2049676.54", 4, 18),
           ("2025-09", "2025-26", 6, "2510285.18", "2434806.19", 3, 15),
           ("2025-10", "2025-26", 7, "2746478.07", "2674272.71", 3, 13),
           ("2025-11", "2025-26", 8, "2864146.07", "2674272.71", 7, 18),
           ("2025-12", "2025-26", 9, "3022919.49", None, None, None),
           ("2026-01", "2025-26", 10, "3166874.77", None, None, 55),
           ("2026-02", "2025-26", 11, "3287708.92", None, None, 57),
           ("2026-03", "2025-26", 12, "3457099.53", None, None, 53),
           ("2026-04", "2026-27", 1, "186053.49", "181515.60", 3, 33),
           ("2026-05", "2026-27", 2, "441698.41", "443918.00", -1, 20),
           ("2026-06", "2026-27", 3, "857485.05", "869660.29", -1, 12),
           ("2026-07", "2026-27", 4, "1462932.03", "1491266.09", -2, 7),
           ("2026-08", "2026-27", 5, "2076373.26", "2129613.60", -3, 4)])

    check("2024-25 has no total, 2025-26 has a total and nothing to set it against, and 2026-27 is set against "
          "the same five months of 2025-26, with the whole of 2025-26 beside it",
          lambda: q(db, "05-year-summary.sql"),
          [("2024-25", "2025-03", 12, 1, None, None, None, None),
           ("2025-26", "2026-03", 12, 0, "3457099.53", None, None, None),
           ("2026-27", "2026-08", 5, 0, "2076373.26", "2129613.60", -3, "3457099.53")])

    def reports():
        # For each report: its heading, column names, the rule under them, how
        # many rows it prints, and the first of them.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run_all(db)
        lines = out.getvalue().split("\n")
        heads = [n for n, line in enumerate(lines) if line.startswith("===")]
        sections = []
        for k, at in enumerate(heads):
            end = heads[k + 1] if k + 1 < len(heads) else len(lines)
            rows = [line for line in lines[at + 3:end] if line]
            sections.append((lines[at], lines[at + 1], lines[at + 2], len(rows), rows[0]))
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
          "rows each prints and the first of them, and a missing month prints with blank cells; a query file "
          "that fails, has no query result, is not UTF-8 or is gone by the time it is read, or a folder named "
          "like one, stops them with a one-line message",
          lambda: [reports(), printed(db, "03-fiscal-ytd.sql")[7:9], broken_reports()],
          [[("=== 01-log-shape.sql ===",
             "first_month  last_month  logged  missing  at_zero  first_fiscal_year  last_fiscal_year  "
             "last_fiscal_month",
             "-----------  ----------  ------  -------  -------  -----------------  ----------------  "
             "-----------------", 1,
             "2024-04      2026-08     28      1        1        2024-25            2026-27           5"),
            ("=== 02-calendar-ytd.sql ===", "month    ytd_months  calendar_ytd  last_year_ytd  growth_pct",
             "-------  ----------  ------------  -------------  ----------", 28,
             "2024-04  1           161347.20"),
            ("=== 03-fiscal-ytd.sql ===", "month    fiscal_year  fiscal_month  revenue    fiscal_ytd  unknown_from",
             "-------  -----------  ------------  ---------  ----------  ------------", 29,
             "2024-04  2024-25      1             161347.20  161347.20"),
            ("=== 04-fiscal-growth.sql ===",
             "month    fiscal_year  fiscal_month  fiscal_ytd  last_year_ytd  growth_pct  calendar_growth_pct",
             "-------  -----------  ------------  ----------  -------------  ----------  -------------------", 17,
             "2025-04  2025-26      1             181515.60   161347.20      13          189"),
            ("=== 05-year-summary.sql ===",
             "fiscal_year  through  months  missing  revenue     same_months_last_year  growth_pct  "
             "full_year_last_year",
             "-----------  -------  ------  -------  ----------  ---------------------  ----------  "
             "-------------------", 3,
             "2024-25      2025-03  12      1")],
           ["2024-11  2024-25      8             0.00       2674272.71",
            "2024-12  2024-25      9                                    2024-12"],
           [(2, '01-broken.sql: did not run: near "SELEC": syntax error'),
            (2, "01-empty.sql: did not run: has no query result to print"),
            (2, "01-ansi.sql: is not UTF-8 text"),
            (2, "01-folder.sql: is a folder, not a query file"),
            (2, "01-gone.sql: No such file or directory")]])

    # Logs built for cases the sample does not reach on its own. Only the
    # reversed sample goes through the loader, inside the checks that use it.
    def span(first, last, amount):
        # Every month from first to last, each given amount(k, year, month)
        # cents, k counting from zero.
        rows, (year, month), k = [], first, 0
        while (year, month) <= last:
            rows.append((f"{year:04d}-{month:02d}", amount(k, year, month)))
            k += 1
            year, month = (year + 1, 1) if month == 12 else (year, month + 1)
        return rows

    def agree(conn):
        # Query 04's calendar growth is query 02's growth on each month both
        # print; query 05's revenue is query 03's total at the month each
        # year runs to, and its figure for last year and its growth are
        # query 04's at that month.
        calendar = {row[0]: row[4] for row in q(conn, "02-calendar-ytd.sql")}
        totals = {row[0]: row[4] for row in q(conn, "03-fiscal-ytd.sql")}
        growth = {row[0]: (row[4], row[5]) for row in q(conn, "04-fiscal-growth.sql")}
        years = q(conn, "05-year-summary.sql")
        return [all(row[6] == calendar.get(row[0]) for row in q(conn, "04-fiscal-growth.sql")),
                all(row[4] == totals[row[1]] for row in years),
                all((row[5], row[6]) == growth.get(row[1], (None, None)) for row in years)]

    february = new_db(span((2025, 2), (2026, 4), lambda k, y, m: 100000 + 10001 * k))
    century = new_db(span((2198, 4), (2200, 4), lambda k, y, m: 100000 + 10001 * k))
    gaps = new_db([("2024-04", 10000), ("2024-06", 30000), ("2026-05", 5000)])
    # 400.00, then 402.00, 0.5 percent up, then 391.95, 2.5 percent down,
    # then nothing; every other month 0.00. Rounded half away from zero these
    # are 1 and -3, where rounding half to even gives 0 and -2 and rounding
    # half up gives -2 for the second.
    halves = new_db(span((2024, 4), (2027, 4),
                         lambda k, y, m: {(2024, 4): 40000, (2025, 4): 40200, (2026, 4): 39195}.get((y, m), 0)))
    one_2099 = new_db([("2099-04", 5000)])
    one_1970 = new_db([("1970-01", 5000)])
    one_march = new_db([("2025-03", 5000)])
    march_start = new_db(span((2025, 3), (2026, 4), lambda k, y, m: 100000 + 10001 * k))
    one_2200 = new_db([("2200-04", 5000)])
    # Every month the loader allows, each at the largest amount, is the
    # costliest log for every query; two rows, at the first and last months
    # allowed, give the longest calendar with the least to fill it.
    biggest = new_db(span((1970, 1), (2200, 12), lambda k, y, m: 9999999999))
    sparse = new_db([("1970-01", 1), ("2200-12", 9999999999)])

    def backwards():
        # The sample again, stored in the opposite order in a table with no
        # key, so nothing hands the rows back in month order unless a query
        # sorts them.
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE revenue (month TEXT NOT NULL, revenue_cents INTEGER NOT NULL)")
        conn.executemany("INSERT INTO revenue VALUES (?, ?)", list(reversed(load(REVENUE_CSV))))
        return conn

    check("the reports agree with each other on the sample and on every log the suite builds: the calendar "
          "growth in query 04 is query 02's, and in query 05 each fiscal year's revenue, last year's figure for "
          "the same months and growth are queries 03's and 04's at the month the year runs to",
          lambda: [agree(conn) for conn in (db, february, century, gaps, halves, one_2099, one_1970, one_march,
                                            march_start, one_2200, biggest, sparse, backwards())],
          [[True, True, True]] * 13)

    check("fiscal months run from 1 in April to 12 in March across a change of calendar year; a log that starts "
          "in February, and one that starts in March, count the months before them in their first fiscal year "
          "as missing, so that year has no total; a fiscal year is named for the two years it spans, with the "
          "second written in full where a century turns and with a leading zero in 2200-01; a log of one month "
          "in 2025-03 belongs to 2024-25; and a log of one month in 1970-01 reaches back to 1969-04",
          lambda: [q(february, "01-log-shape.sql"),
                   pick(q(february, "03-fiscal-ytd.sql"), "2024-04", "2025-01", "2025-02", "2025-03", "2025-04",
                        "2025-12", "2026-01", "2026-03", "2026-04"),
                   pick(q(february, "04-fiscal-growth.sql"), "2025-04", "2026-02", "2026-04"),
                   q(february, "05-year-summary.sql"),
                   q(century, "01-log-shape.sql"),
                   pick(q(century, "03-fiscal-ytd.sql"), "2199-03", "2199-04", "2200-03", "2200-04"),
                   pick(q(century, "04-fiscal-growth.sql"), "2199-04", "2200-03", "2200-04"),
                   q(century, "05-year-summary.sql"),
                   q(march_start, "01-log-shape.sql"),
                   pick(q(march_start, "03-fiscal-ytd.sql"), "2024-04", "2025-03", "2025-04", "2026-03"),
                   pick(q(march_start, "04-fiscal-growth.sql"), "2025-04", "2026-03", "2026-04"),
                   q(march_start, "05-year-summary.sql"),
                   q(one_2200, "01-log-shape.sql"),
                   q(one_2099, "01-log-shape.sql"),
                   q(one_march, "01-log-shape.sql"),
                   q(one_1970, "01-log-shape.sql"),
                   q(one_1970, "05-year-summary.sql")],
          [[("2025-02", "2026-04", 15, 10, 0, "2024-25", "2026-27", 1)],
           [("2024-04", "2024-25", 1, None, None, "2024-04"),
            ("2025-01", "2024-25", 10, None, None, "2024-04"),
            ("2025-02", "2024-25", 11, "1000.00", None, "2024-04"),
            ("2025-03", "2024-25", 12, "1100.01", None, "2024-04"),
            ("2025-04", "2025-26", 1, "1200.02", "1200.02", None),
            ("2025-12", "2025-26", 9, "2000.10", "14400.54", None),
            ("2026-01", "2025-26", 10, "2100.11", "16500.65", None),
            ("2026-03", "2025-26", 12, "2300.13", "21000.90", None),
            ("2026-04", "2026-27", 1, "2400.14", "2400.14", None)],
           [("2025-04", "2025-26", 1, "1200.02", None, None, None),
            ("2026-02", "2025-26", 11, "18700.77", None, None, 330),
            ("2026-04", "2026-27", 1, "2400.14", "1200.02", 100, 173)],
           [("2024-25", "2025-03", 12, 10, None, None, None, None),
            ("2025-26", "2026-03", 12, 0, "21000.90", None, None, None),
            ("2026-27", "2026-04", 1, 0, "2400.14", "1200.02", 100, "21000.90")],
           [("2198-04", "2200-04", 25, 0, 0, "2198-99", "2200-01", 1)],
           [("2199-03", "2198-99", 12, "2100.11", "18600.66", None),
            ("2199-04", "2199-2200", 1, "2200.12", "2200.12", None),
            ("2200-03", "2199-2200", 12, "3300.23", "33002.10", None),
            ("2200-04", "2200-01", 1, "3400.24", "3400.24", None)],
           [("2199-04", "2199-2200", 1, "2200.12", "1000.00", 120, 720),
            ("2200-03", "2199-2200", 12, "33002.10", "18600.66", 77, 60),
            ("2200-04", "2200-01", 1, "3400.24", "2200.12", 55, 59)],
           [("2198-99", "2199-03", 12, 0, "18600.66", None, None, None),
            ("2199-2200", "2200-03", 12, 0, "33002.10", "18600.66", 77, "18600.66"),
            ("2200-01", "2200-04", 1, 0, "3400.24", "2200.12", 55, "33002.10")],
           [("2025-03", "2026-04", 14, 11, 0, "2024-25", "2026-27", 1)],
           [("2024-04", "2024-25", 1, None, None, "2024-04"),
            ("2025-03", "2024-25", 12, "1000.00", None, "2024-04"),
            ("2025-04", "2025-26", 1, "1100.01", "1100.01", None),
            ("2026-03", "2025-26", 12, "2200.12", "19800.78", None)],
           [("2025-04", "2025-26", 1, "1100.01", None, None, None),
            ("2026-03", "2025-26", 12, "19800.78", None, None, 530),
            ("2026-04", "2026-27", 1, "2300.13", "1100.01", 109, 310)],
           [("2024-25", "2025-03", 12, 11, None, None, None, None),
            ("2025-26", "2026-03", 12, 0, "19800.78", None, None, None),
            ("2026-27", "2026-04", 1, 0, "2300.13", "1100.01", 109, "19800.78")],
           [("2200-04", "2200-04", 1, 0, 0, "2200-01", "2200-01", 1)],
           [("2099-04", "2099-04", 1, 0, 0, "2099-2100", "2099-2100", 1)],
           [("2025-03", "2025-03", 1, 11, 0, "2024-25", "2024-25", 12)],
           [("1970-01", "1970-01", 1, 9, 0, "1969-70", "1969-70", 10)],
           [("1969-70", "1970-01", 10, 9, None, None, None, None)]])

    check("a missing month blanks its fiscal year from there on, the first one missing is the one named even "
          "after a second, a fiscal year with no rows at all is twelve months missing, and any growth that "
          "leans on a blank total is blank too, while the calendar total goes on over the gap",
          lambda: [q(gaps, "01-log-shape.sql"), q(gaps, "02-calendar-ytd.sql"),
                   pick(q(gaps, "03-fiscal-ytd.sql"), "2024-04", "2024-05", "2024-06", "2024-07", "2025-04",
                        "2026-04", "2026-05"),
                   pick(q(gaps, "04-fiscal-growth.sql"), "2025-04", "2026-05"),
                   q(gaps, "05-year-summary.sql")],
          [[("2024-04", "2026-05", 3, 23, 0, "2024-25", "2026-27", 2)],
           [("2024-04", 1, "100.00", None, None), ("2024-06", 2, "400.00", None, None),
            ("2026-05", 1, "50.00", None, None)],
           [("2024-04", "2024-25", 1, "100.00", "100.00", None),
            ("2024-05", "2024-25", 2, None, None, "2024-05"),
            ("2024-06", "2024-25", 3, "300.00", None, "2024-05"),
            ("2024-07", "2024-25", 4, None, None, "2024-05"),
            ("2025-04", "2025-26", 1, None, None, "2025-04"),
            ("2026-04", "2026-27", 1, None, None, "2026-04"),
            ("2026-05", "2026-27", 2, "50.00", None, "2026-04")],
           [("2025-04", "2025-26", 1, None, "100.00", None, None),
            ("2026-05", "2026-27", 2, None, None, None, None)],
           [("2024-25", "2025-03", 12, 10, None, None, None, None),
            ("2025-26", "2026-03", 12, 12, None, None, None, None),
            ("2026-27", "2026-05", 2, 1, None, None, None, None)]])

    check("growth that lands on an exact half rounds away from zero in every query that prints it, 0.5 up to "
          "1 and 2.5 down to -3, where rounding half to even gives 0 and -2; growth against a zero is blank, "
          "and a year that falls to zero reads -100",
          lambda: [pick(q(halves, "02-calendar-ytd.sql"), "2025-04", "2026-01", "2026-04", "2027-04"),
                   pick(q(halves, "04-fiscal-growth.sql"), "2025-04", "2026-01", "2026-04", "2027-04"),
                   q(halves, "05-year-summary.sql")],
          [[("2025-04", 4, "402.00", "400.00", 1), ("2026-01", 1, "0.00", "0.00", None),
            ("2026-04", 4, "391.95", "402.00", -3), ("2027-04", 4, "0.00", "391.95", -100)],
           [("2025-04", "2025-26", 1, "402.00", "400.00", 1, 1),
            ("2026-01", "2025-26", 10, "402.00", "400.00", 1, None),
            ("2026-04", "2026-27", 1, "391.95", "402.00", -3, -3),
            ("2027-04", "2027-28", 1, "0.00", "391.95", -100, -100)],
           [("2024-25", "2025-03", 12, 0, "400.00", None, None, None),
            ("2025-26", "2026-03", 12, 0, "402.00", "400.00", 1, "400.00"),
            ("2026-27", "2027-03", 12, 0, "391.95", "402.00", -3, "402.00"),
            ("2027-28", "2027-04", 1, 0, "0.00", "391.95", -100, "391.95")]])

    names = ("01-log-shape.sql", "02-calendar-ytd.sql", "03-fiscal-ytd.sql", "04-fiscal-growth.sql",
             "05-year-summary.sql")

    def reversed_log():
        conn = backwards()
        return [q(conn, name) == q(db, name) for name in names]

    check("the sample stored in the opposite order, in a table with no key to keep it in order, gives the same "
          "five reports",
          reversed_log, [True] * 5)

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
        check("every month from 1970-01 to 2200-12 at the largest amount, and a log of only those two months, "
              "run through each query inside the step budget, with twelve months at the largest amount printed "
              "in full, to the cent; and a query that would run for ever is stopped by the step budget",
              lambda: [[ends(biggest, name) for name in names], [ends(sparse, name) for name in names],
                       endless(tmp)],
              [[(1, ("1970-01", "2200-12", 2772, 9, 0, "1969-70", "2200-01", 9),
                 ("1970-01", "2200-12", 2772, 9, 0, "1969-70", "2200-01", 9)),
                (2772, ("1970-01", 1, "99999999.99", None, None),
                 ("2200-12", 12, "1199999999.88", "1199999999.88", 0)),
                (2781, ("1969-04", "1969-70", 1, None, None, "1969-04"),
                 ("2200-12", "2200-01", 9, "99999999.99", "899999999.91", None)),
                (2769, ("1970-04", "1970-71", 1, "99999999.99", None, None, None),
                 ("2200-12", "2200-01", 9, "899999999.91", "899999999.91", 0, 0)),
                (232, ("1969-70", "1970-03", 12, 9, None, None, None, None),
                 ("2200-01", "2200-12", 9, 0, "899999999.91", "899999999.91", 0, "1199999999.88"))],
               [(1, ("1970-01", "2200-12", 2, 2779, 0, "1969-70", "2200-01", 9),
                 ("1970-01", "2200-12", 2, 2779, 0, "1969-70", "2200-01", 9)),
                (2, ("1970-01", 1, "0.01", None, None), ("2200-12", 1, "99999999.99", None, None)),
                (2781, ("1969-04", "1969-70", 1, None, None, "1969-04"),
                 ("2200-12", "2200-01", 9, "99999999.99", None, "2200-04")),
                (2769, ("1970-04", "1970-71", 1, None, None, None, None),
                 ("2200-12", "2200-01", 9, None, None, None, None)),
                (232, ("1969-70", "1970-03", 12, 11, None, None, None, None),
                 ("2200-01", "2200-12", 9, 8, None, None, None, None))],
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
        small = head + "2025-01,10.00\n2025-02,12.00\n"

        def logs(name, content):
            return rejection(load, csv_file(name, content))

        def sized(result):
            code, loaded = result
            return (code, len(loaded)) if code == 0 else result

        every = head + "".join(f"{y:04d}-{m:02d},1.00\n" for y in range(1970, 2201) for m in range(1, 13))
        # Over 35000 characters of rows, far more than the text decoder
        # reads ahead, so a byte that is not UTF-8 after them is not reached
        # before the row above them is refused.
        far_down = "".join(f"{y:04d}-{m:02d},1.00\n" for y in range(1971, 2201) for m in range(1, 13))
        check("the included bad log is refused for a month listed twice, naming the row; a log of every month "
              "from 1970-01 to 2200-12 loads all 2772, and a row past them is refused, since it can only repeat "
              "a month or fall outside the range, as it is read and before a byte that is not UTF-8 further down",
              lambda: [rejection(load, HERE / "data" / "invalid-revenue.csv"),
                       sized(logs("every.csv", every)),
                       rejection(load, byte_file("repeat.csv", (every + "2025-07,3.00\n" + far_down).encode("utf-8")
                                                 + b"2026-02,1\xc9.00\n")),
                       rejection(load, byte_file("beyond.csv", (every + "2201-01,3.00\n" + far_down).encode("utf-8")
                                                 + b"2026-02,1\xc9.00\n"))],
              [(2, "invalid-revenue.csv row 17: 2025-07 appears twice; one row per month, with the amounts "
                   "added together"),
               (0, 2772),
               (2, "repeat.csv row 2774: 2025-07 appears twice; one row per month, with the amounts added together"),
               (2, "beyond.csv row 2774: month '2201-01' is not a month written like 2025-04, "
                   "from 1970-01 to 2200-12")])

        bad_months = ["2025-13", "2025-00", "2025-1", "25-01", "2025/01", "1969-12", "2201-01", "", "2025-01-01",
                      "Jan-2025", "2025-26", "\uff12\uff10\uff12\uff15-\uff10\uff11"]
        check("a month past 12 or at 00, written without its leading zero, with a two-digit year, a slash, a "
              "day, a month name, as a fiscal year like 2025-26 or in fullwidth digits, before 1970 or after "
              "2200, or blank is refused, while 1970-01 and 2200-12 in one log load",
              lambda: [logs(f"month{k}.csv", head + f"{raw},1.00\n2025-02,1.00\n")
                       for k, raw in enumerate(bad_months)]
                      + [logs("bounds.csv", head + "1970-01,1.00\n2200-12,1.00\n")],
              [(2, f"month{k}.csv row 2: month {raw!r} is not a month written like 2025-04, from 1970-01 to 2200-12")
               for k, raw in enumerate(bad_months)]
              + [(0, [("1970-01", 100), ("2200-12", 100)])])

        bad_amounts = ["-5.00", "5", "5.0", "5.000", "05.00", "100000000.00", "1e3", "", "5,00", "$5.00", ".50",
                       "1,250.00", "\u0661\u0660.\u0660\u0660", "1\u0660.\u0660\u0660"]
        check("a negative, whole, one-place, three-place, zero-padded, nine-digit, exponent, blank, comma, "
              "dollar-sign or thousands-separated amount, one with no digit before the point, or one with "
              "Arabic-Indic digits in it, even after a plain first digit, is refused; and 0.00, 0.01 and "
              "99999999.99 load",
              lambda: [logs(f"amount{k}.csv", small + f'2025-03,"{raw}"\n') for k, raw in enumerate(bad_amounts)]
                      + [logs("extremes.csv", head + "2025-01,0.00\n2025-02,0.01\n2025-03,99999999.99\n")],
              [(2, f"amount{k}.csv row 4: revenue {raw!r} is not an amount from 0.00 to 99999999.99 written like "
                   "1250.00") for k, raw in enumerate(bad_amounts)]
              + [(0, [("2025-01", 0), ("2025-02", 1), ("2025-03", 9999999999)])])

        check("rows are counted past blank lines and a line of spaces, and a stray quote is named by its own row, "
              "in a data row or in the header; rows with too many or too few fields, a line of one comma or of "
              "three, a tab, text after a closing quote, a quote left open, a field past the parser's limit, and "
              "a bad, renamed or reordered header, also one found after blank lines, written as one quoted field "
              "or with a trailing comma, are refused, and a long value or header is cut short in the message, by "
              "one character as well as by many, while a value of exactly 40 characters is shown whole",
              lambda: [logs("rows.csv", small + "\n   \n\n2025-3,1.00\n"),
                       logs("quote.csv", small + '2025-03,"1.00\n2025-04,1.00",\n'),
                       logs("unclosed.csv", small + '2025-03,"1.00\n'),
                       logs("wide.csv", small + "2025-03,1.00,extra\n"),
                       logs("narrow.csv", small + "2025-03\n"),
                       logs("commas.csv", small + ",\n"),
                       logs("more_commas.csv", small + ",,,\n"),
                       logs("tab.csv", small + "2025-03\t,1.00\n"),
                       logs("after.csv", small + '2025-03,"1.00"x\n'),
                       logs("huge_field.csv", small + "2025-03," + "9" * 200000 + "\n"),
                       logs("header.csv", 'month,"revenue"x\n2025-01,1.00\n'),
                       logs("open_header.csv", '"month,revenue\n2025-01,1.00\n2025-02,1.00\n'),
                       logs("renamed.csv", "month,amount\n2025-01,1.00\n"),
                       logs("reordered.csv", "revenue,month\n1.00,2025-01\n"),
                       logs("late_renamed.csv", "\nmonth,amount\n2025-01,1.00\n"),
                       logs("quoted_header.csv", '"month,revenue"\n"2025-01,10.00"\n'),
                       logs("trailing_comma.csv", "month,revenue,\n2025-01,1.00,\n"),
                       logs("long_header.csv", "month,revenue" + "x" * 100 + "\n2025-01,1.00\n"),
                       logs("long_value.csv", small + "2025-03," + "B" * 100 + "\n"),
                       logs("just_over.csv", small + "2025-03," + "C" * 41 + "\n"),
                       logs("exactly_40.csv", small + "2025-03," + "D" * 40 + "\n")],
              [(2, "rows.csv row 7: month '2025-3' is not a month written like 2025-04, from 1970-01 to 2200-12"),
               (2, "quote.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "unclosed.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "wide.csv row 4: has more fields than the header"),
               (2, "narrow.csv row 4: has fewer fields than the header"),
               (2, "commas.csv row 4: month '' is not a month written like 2025-04, from 1970-01 to 2200-12"),
               (2, "more_commas.csv row 4: has more fields than the header"),
               (2, "tab.csv row 4: month '2025-03\\t' is not a month written like 2025-04, from 1970-01 to 2200-12"),
               (2, "after.csv row 4: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "huge_field.csv row 4: has a field over 131072 characters long"),
               (2, "header.csv row 1: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "open_header.csv row 1: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "renamed.csv row 1: expected columns 'month,revenue', got 'month,amount'"),
               (2, "reordered.csv row 1: expected columns 'month,revenue', got 'revenue,month'"),
               (2, "late_renamed.csv row 2: expected columns 'month,revenue', got 'month,amount'"),
               (2, "quoted_header.csv row 1: expected columns 'month,revenue', got '\"month,revenue\"'"),
               (2, "trailing_comma.csv row 1: expected columns 'month,revenue', got 'month,revenue,'"),
               (2, "long_header.csv row 1: expected columns 'month,revenue', got 'month,revenue"
                   + "x" * 27 + "' and 73 more characters"),
               (2, "long_value.csv row 4: revenue '" + "B" * 40 + "' and 60 more characters is not an amount "
                   "from 0.00 to 99999999.99 written like 1250.00"),
               (2, "just_over.csv row 4: revenue '" + "C" * 40 + "' and 1 more character is not an amount "
                   "from 0.00 to 99999999.99 written like 1250.00"),
               (2, "exactly_40.csv row 4: revenue '" + "D" * 40 + "' is not an amount "
                   "from 0.00 to 99999999.99 written like 1250.00")])

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

        class Endless:
            # A file whose one line never ends. Asked for a set number of
            # characters it hands them over; asked for the whole line it
            # cannot, and says so.
            def readline(self, size=-1):
                if size is None or size < 0:
                    raise MemoryError("asked for the whole of a line that never ends")
                return "x" * size

        def endless_line():
            # At most three lines are taken, so a reader that never refuses
            # the line fails this check instead of filling memory.
            count = 0
            for _ in read_lines(Path(tmp) / "endless.csv", Endless()):
                count += 1
                if count == 3:
                    break
            return count

        check("an empty file, one of blank lines, one with only a header, also after a blank line, one that is "
              "not UTF-8 from its first line or only far down, or holds only part of a byte-order mark, a folder, "
              "a read that gives way before the header or partway through, a line past 1000000 characters, and a "
              "line that never ends, which is read only up to the cap, are refused, a line of exactly 1000000 "
              "passing the line cap; while a byte-order mark, blank lines before the header, spaces around "
              "unquoted fields, in the header too, and a line holding one empty quoted field, which is passed over "
              "like a blank one, load",
              lambda: [logs("empty.csv", ""),
                       logs("blank_only.csv", "\n  \n\n"),
                       logs("bare.csv", head),
                       logs("late_bare.csv", "\n" + head),
                       rejection(load, byte_file("latin1.csv", b"month,revenue\xc9\n2025-01,1.00\n")),
                       rejection(load, byte_file("late_latin1.csv", (head + far_down).encode("utf-8")
                                                 + b"1970-01,1\xc9.00\n")),
                       rejection(load, byte_file("part_mark.csv", b"\xef\xbb")),
                       rejection(load, Path(tmp)),
                       rejection(dropped, ""),
                       rejection(dropped, small),
                       logs("long_line.csv", small + "," * 1000001 + "\n"),
                       rejection(capped, "x" * 1000001 + "\n"),
                       rejection(capped, "x" * 1000000 + "\r\n"),
                       rejection(endless_line),
                       logs("marked.csv", "\ufeff month , revenue \n 2025-01 , 10.00 \n2025-02,12.00\n"),
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
               (2, "endless.csv row 1: runs past 1000000 characters on one line"),
               (0, [("2025-01", 1000), ("2025-02", 1200)]),
               (0, [("2025-01", 1000), ("2025-02", 1200)]),
               (0, [("2025-01", 1000), ("2025-02", 1200)])])

        def utf8_check():
            # Output written in the Windows codepage cannot hold these
            # characters; after utf8_output it goes out as UTF-8. A stream
            # with no way to switch, as under IDLE, is left as it is.
            saved = sys.stdout, sys.stderr
            out, err = io.BytesIO(), io.BytesIO()
            sys.stdout = io.TextIOWrapper(out, encoding="cp1252", newline="\n")
            sys.stderr = io.TextIOWrapper(err, encoding="cp1252", newline="\n")
            try:
                utf8_output()
                print("\u6f22\u5b57.csv")
                print("\u6f22\u5b57.csv", file=sys.stderr)
                sys.stdout.flush()
                sys.stderr.flush()
                switched = out.getvalue().decode("utf-8"), err.getvalue().decode("utf-8")
                sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
                utf8_output()
                print("\u6f22\u5b57.csv")
                return switched, sys.stdout.getvalue()
            finally:
                sys.stdout, sys.stderr = saved

        other = csv_file("other.csv", REVENUE_CSV.read_text(encoding="utf-8"))

        def cli(*argv):
            return rejection(settings, [str(a) for a in argv])

        def main_check():
            # main itself, on a file name the Windows codepage cannot hold. It
            # stops at the missing file, and the message has to come out as
            # UTF-8. The command line has no --test, so no suite is started.
            saved = sys.argv, sys.stdout, sys.stderr
            err = io.BytesIO()
            name = "\u6f22\u5b57.csv"
            sys.argv = ["run.py", "--revenue", str(Path(tmp) / name)]
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
              "sets them up, which leaves alone a stream it cannot switch, and main's own messages come out as "
              "UTF-8",
              lambda: [cli("--revenue", Path(tmp) / "not_there.csv"),
                       cli("--revenue", Path(tmp) / "data*.csv"),
                       cli("--test", "--revenue", other),
                       cli("--test"),
                       cli(),
                       cli("--test", "--revenue", HERE / "data" / ".." / "data" / "revenue.csv"),
                       cli("--revenue", other),
                       utf8_check(),
                       main_check()],
              [(2, f"run.py: error: --revenue: '{Path(tmp) / 'not_there.csv'}' is not a file"),
               (2, f"run.py: error: --revenue: '{Path(tmp) / 'data*.csv'}' is not a file"),
               (2, "run.py: error: --test checks hand-computed answers for the sample file; "
                   "run it without --revenue"),
               (0, (True, REVENUE_CSV)),
               (0, (False, REVENUE_CSV)),
               (0, (True, HERE / "data" / ".." / "data" / "revenue.csv")),
               (0, (False, other)),
               (("\u6f22\u5b57.csv\n", "\u6f22\u5b57.csv\n"), "\u6f22\u5b57.csv\n"),
               (2, True)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def settings(argv):
    # Reads the command line and settles which file to load. It never runs a
    # query or the suite, so the suite can check it directly.
    parser = argparse.ArgumentParser(prog="run.py", description="Run the fiscal year-to-date queries against a "
                                                 "monthly revenue log, the sample by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--revenue", type=Path, default=None, help="path to an alternate monthly revenue CSV")
    args = parser.parse_args(argv)
    path = args.revenue or REVENUE_CSV
    try:
        found = path.is_file()
    except OSError:
        # Python 3.7 raises here for a name Windows cannot hold, such as one
        # with a wildcard in it.
        found = False
    if not found:
        if args.revenue is not None:
            parser.error(f"--revenue: '{path}' is not a file")
        parser.error(f"the sample file '{path}' is missing")
    if args.test and path.resolve() != REVENUE_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample file; run it without --revenue")
    return args.test, path


def utf8_output():
    # Output is written as UTF-8, since a file name in a message can hold
    # characters that the Windows console codepage cannot print. A stream
    # with no way to switch, as under IDLE, is left as it is.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")


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
