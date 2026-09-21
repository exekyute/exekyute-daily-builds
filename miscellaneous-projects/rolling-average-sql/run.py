"""Load a daily sales log into SQLite and run the rolling-average queries.

Usage:
    python run.py                   run every query in sql/
    python run.py --test            run the assertion suite
    python run.py --sales log.csv   load a different log
"""

import argparse
import contextlib
import csv
import io
import re
import sqlite3
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).parent
SALES_CSV = HERE / "data" / "sales.csv"
SQL_DIR = HERE / "sql"
COLUMNS = ["day", "sales"]
# The days a log may hold. A day appears at most once, so a log holds at
# most the 84371 days from the first to the last, and with at most 999999.99
# a day no total passes 10**13 cents: every sum, and twice every sum, which
# the rounding takes, stays a whole number well inside SQLite's 64-bit
# integers.
EARLIEST = date(1970, 1, 1)
LATEST = date(2200, 12, 31)
# A line of the file may hold at most this many characters. A real row holds
# a couple of dozen.
LINE_CAP = 1_000_000
# A query that runs past this many thousand SQLite steps is stopped. The
# sample takes at most 13, and a log of every day the loader allows takes
# about a tenth of it, on SQLite 3.31 and 3.34 as much as on 3.50, so only a
# query that would run away reaches it.
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


def day_of(path, row_num, raw):
    # The shape first, since query 02 orders the days as text and only a fixed
    # YYYY-MM-DD sorts in date order. Then whether it is a real date: julianday
    # rolls 2025-11-31 over to 1 December without a word, which would give two
    # rows the same day number.
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
        fail(path, row_num, f"day {shown(raw)} is not a date written like 2025-11-04")
    try:
        value = date(int(raw[:4]), int(raw[5:7]), int(raw[8:]))
    except ValueError:
        fail(path, row_num, f"day {raw} is not a real date")
    if not EARLIEST <= value <= LATEST:
        fail(path, row_num, f"day {raw} is outside the days a log can hold, {EARLIEST} to {LATEST}")
    return raw


def cents(path, row_num, raw):
    # Two decimal places, no sign, no thousands separator and no currency
    # mark. A day the shop opened and sold nothing is 0.00, and counts as a
    # day logged; a day it stayed shut is left out of the log.
    match = re.fullmatch(r"(0|[1-9][0-9]{0,5})\.([0-9]{2})", raw)
    if not match:
        fail(path, row_num, f"sales {shown(raw)} is not an amount from 0.00 to 999999.99 written like 412.50")
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
            day = day_of(path, i, row["day"])
            amount = cents(path, i, row["sales"])
            # The file is read a line at a time and a day can appear only
            # once, so a file longer than the days allowed stops at its first
            # repeat and is never read to the end.
            if day in seen:
                fail(path, i, f"{day} appears twice; one row per day, with the day's sales added together")
            seen.add(day)
            rows.append((day, amount))
    if not rows:
        fail(path, header_line, "no data rows after the header")
    return rows


def new_db(rows):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE daily_sales (day TEXT PRIMARY KEY, sales_cents INTEGER NOT NULL)")
    db.executemany("INSERT INTO daily_sales VALUES (?, ?)", rows)
    return db


def print_table(headers, rows):
    cells = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h)
              for i, h in enumerate(headers)]
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip())
    print("  ".join("-" * w for w in widths))
    for row in cells:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))).rstrip())


def run_query(db, sql_path, text=None):
    # SQLite calls budget every thousand steps and stops the query once it
    # returns true, so a query that would run away uses up the budget and
    # stops with an error instead.
    steps = [0]

    def budget():
        steps[0] += 1
        return steps[0] > STEP_BUDGET

    db.set_progress_handler(budget, 1000)
    try:
        cursor = db.execute(sql_path.read_text(encoding="utf-8") if text is None else text)
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

    partial = "partial: the window starts before the log"

    check("the log runs 69 days from 2025-11-04 to 2026-01-11 with 54 of them logged; 9 of the 15 missing days "
          "are Mondays, the longest gap is 5 days, and sales come to 45147.60",
          lambda: q(db, "01-log-shape.sql"),
          [("2025-11-04", "2026-01-11", 69, 54, 15, 9, 6, 5, "45147.60")])

    check("the last seven rows span 8 calendar days over a closed Monday, 10 over a missing Saturday and two "
          "Mondays, and 13 across the Christmas closure, where the average reads 1333.94 on New Year's Day",
          lambda: q(db, "02-rows-frame.sql"),
          [("2025-11-04", "498.25", "2025-11-04", 1, "498.25"), ("2025-11-05", "561.40", "2025-11-04", 2, "529.83"),
           ("2025-11-06", "603.15", "2025-11-04", 3, "554.27"), ("2025-11-07", "772.80", "2025-11-04", 4, "608.90"),
           ("2025-11-08", "1134.55", "2025-11-04", 5, "714.03"), ("2025-11-09", "846.90", "2025-11-04", 6, "736.18"),
           ("2025-11-11", "517.35", "2025-11-04", 8, "704.91"), ("2025-11-12", "548.70", "2025-11-05", 8, "712.12"),
           ("2025-11-13", "621.05", "2025-11-06", 8, "720.64"), ("2025-11-14", "794.10", "2025-11-07", 8, "747.92"),
           ("2025-11-15", "1187.45", "2025-11-08", 8, "807.16"), ("2025-11-16", "859.20", "2025-11-09", 8, "767.82"),
           ("2025-11-18", "506.60", "2025-11-11", 8, "719.21"), ("2025-11-19", "572.95", "2025-11-12", 8, "727.15"),
           ("2025-11-20", "634.40", "2025-11-13", 8, "739.39"), ("2025-11-21", "808.75", "2025-11-14", 8, "766.21"),
           ("2025-11-23", "891.15", "2025-11-15", 9, "780.07"), ("2025-11-25", "529.80", "2025-11-16", 10, "686.12"),
           ("2025-11-26", "583.25", "2025-11-18", 9, "646.70"), ("2025-11-27", "617.90", "2025-11-19", 9, "662.60"),
           ("2025-11-28", "846.35", "2025-11-20", 9, "701.66"), ("2025-11-29", "1226.70", "2025-11-21", 9, "786.27"),
           ("2025-11-30", "902.45", "2025-11-23", 8, "799.66"), ("2025-12-02", "541.10", "2025-11-25", 8, "749.65"),
           ("2025-12-03", "596.85", "2025-11-26", 8, "759.23"), ("2025-12-04", "652.30", "2025-11-27", 8, "769.09"),
           ("2025-12-05", "871.95", "2025-11-28", 8, "805.39"), ("2025-12-06", "1268.20", "2025-11-29", 8, "865.65"),
           ("2025-12-07", "934.65", "2025-11-30", 8, "823.93"), ("2025-12-09", "568.40", "2025-12-02", 8, "776.21"),
           ("2025-12-10", "614.75", "2025-12-03", 8, "786.73"), ("2025-12-11", "689.10", "2025-12-04", 8, "799.91"),
           ("2025-12-12", "917.55", "2025-12-05", 8, "837.80"), ("2025-12-13", "1342.80", "2025-12-06", 8, "905.06"),
           ("2025-12-14", "978.25", "2025-12-07", 8, "863.64"), ("2025-12-16", "612.95", "2025-12-09", 8, "817.69"),
           ("2025-12-17", "671.30", "2025-12-10", 8, "832.39"), ("2025-12-18", "758.65", "2025-12-11", 8, "852.94"),
           ("2025-12-19", "1086.40", "2025-12-12", 8, "909.70"),
           ("2025-12-20", "1655.15", "2025-12-13", 8, "1015.07"),
           ("2025-12-21", "1204.90", "2025-12-14", 8, "995.37"),
           ("2025-12-23", "1873.60", "2025-12-16", 8, "1123.28"),
           ("2025-12-24", "2418.35", "2025-12-17", 8, "1381.19"),
           ("2025-12-30", "734.20", "2025-12-18", 13, "1390.18"),
           ("2025-12-31", "1062.85", "2025-12-19", 13, "1433.64"),
           ("2026-01-01", "388.50", "2025-12-20", 13, "1333.94"),
           ("2026-01-02", "571.95", "2025-12-21", 13, "1179.19"),
           ("2026-01-03", "903.15", "2025-12-23", 12, "1136.09"),
           ("2026-01-04", "716.05", "2025-12-24", 12, "970.72"), ("2026-01-06", "462.30", "2025-12-30", 8, "691.29"),
           ("2026-01-07", "498.65", "2025-12-31", 8, "657.64"), ("2026-01-09", "683.20", "2026-01-01", 9, "603.40"),
           ("2026-01-10", "1015.75", "2026-01-02", 9, "693.01"), ("2026-01-11", "788.60", "2026-01-03", 9, "723.96")])

    # Eleven of these averages land on an exact half cent. Four of them,
    # 736.175, 743.775, 782.525 and 898.525, sit just under the half as a
    # float of dollars, so printf or ROUND on one prints a cent low on
    # SQLite 3.50 and not on 3.31 or 3.34; in whole cents they round up on
    # every version.
    check("seven calendar days hold six days logged in a week with a closed Monday and two after the Christmas "
          "closure, the average reads 728.52 on New Year's Day, and every exact half cent rounds up",
          lambda: q(db, "03-range-frame.sql"),
          [("2025-11-04", "498.25", "2025-10-29", 1, "498.25", "498.25"),
           ("2025-11-05", "561.40", "2025-10-30", 2, "1059.65", "529.83"),
           ("2025-11-06", "603.15", "2025-10-31", 3, "1662.80", "554.27"),
           ("2025-11-07", "772.80", "2025-11-01", 4, "2435.60", "608.90"),
           ("2025-11-08", "1134.55", "2025-11-02", 5, "3570.15", "714.03"),
           ("2025-11-09", "846.90", "2025-11-03", 6, "4417.05", "736.18"),
           ("2025-11-11", "517.35", "2025-11-05", 6, "4436.15", "739.36"),
           ("2025-11-12", "548.70", "2025-11-06", 6, "4423.45", "737.24"),
           ("2025-11-13", "621.05", "2025-11-07", 6, "4441.35", "740.23"),
           ("2025-11-14", "794.10", "2025-11-08", 6, "4462.65", "743.78"),
           ("2025-11-15", "1187.45", "2025-11-09", 6, "4515.55", "752.59"),
           ("2025-11-16", "859.20", "2025-11-10", 6, "4527.85", "754.64"),
           ("2025-11-18", "506.60", "2025-11-12", 6, "4517.10", "752.85"),
           ("2025-11-19", "572.95", "2025-11-13", 6, "4541.35", "756.89"),
           ("2025-11-20", "634.40", "2025-11-14", 6, "4554.70", "759.12"),
           ("2025-11-21", "808.75", "2025-11-15", 6, "4569.35", "761.56"),
           ("2025-11-23", "891.15", "2025-11-17", 5, "3413.85", "682.77"),
           ("2025-11-25", "529.80", "2025-11-19", 5, "3437.05", "687.41"),
           ("2025-11-26", "583.25", "2025-11-20", 5, "3447.35", "689.47"),
           ("2025-11-27", "617.90", "2025-11-21", 5, "3430.85", "686.17"),
           ("2025-11-28", "846.35", "2025-11-22", 5, "3468.45", "693.69"),
           ("2025-11-29", "1226.70", "2025-11-23", 6, "4695.15", "782.53"),
           ("2025-11-30", "902.45", "2025-11-24", 6, "4706.45", "784.41"),
           ("2025-12-02", "541.10", "2025-11-26", 6, "4717.75", "786.29"),
           ("2025-12-03", "596.85", "2025-11-27", 6, "4731.35", "788.56"),
           ("2025-12-04", "652.30", "2025-11-28", 6, "4765.75", "794.29"),
           ("2025-12-05", "871.95", "2025-11-29", 6, "4791.35", "798.56"),
           ("2025-12-06", "1268.20", "2025-11-30", 6, "4832.85", "805.48"),
           ("2025-12-07", "934.65", "2025-12-01", 6, "4865.05", "810.84"),
           ("2025-12-09", "568.40", "2025-12-03", 6, "4892.35", "815.39"),
           ("2025-12-10", "614.75", "2025-12-04", 6, "4910.25", "818.38"),
           ("2025-12-11", "689.10", "2025-12-05", 6, "4947.05", "824.51"),
           ("2025-12-12", "917.55", "2025-12-06", 6, "4992.65", "832.11"),
           ("2025-12-13", "1342.80", "2025-12-07", 6, "5067.25", "844.54"),
           ("2025-12-14", "978.25", "2025-12-08", 6, "5110.85", "851.81"),
           ("2025-12-16", "612.95", "2025-12-10", 6, "5155.40", "859.23"),
           ("2025-12-17", "671.30", "2025-12-11", 6, "5211.95", "868.66"),
           ("2025-12-18", "758.65", "2025-12-12", 6, "5281.50", "880.25"),
           ("2025-12-19", "1086.40", "2025-12-13", 6, "5450.35", "908.39"),
           ("2025-12-20", "1655.15", "2025-12-14", 6, "5762.70", "960.45"),
           ("2025-12-21", "1204.90", "2025-12-15", 6, "5989.35", "998.23"),
           ("2025-12-23", "1873.60", "2025-12-17", 6, "7250.00", "1208.33"),
           ("2025-12-24", "2418.35", "2025-12-18", 6, "8997.05", "1499.51"),
           ("2025-12-30", "734.20", "2025-12-24", 2, "3152.55", "1576.28"),
           ("2025-12-31", "1062.85", "2025-12-25", 2, "1797.05", "898.53"),
           ("2026-01-01", "388.50", "2025-12-26", 3, "2185.55", "728.52"),
           ("2026-01-02", "571.95", "2025-12-27", 4, "2757.50", "689.38"),
           ("2026-01-03", "903.15", "2025-12-28", 5, "3660.65", "732.13"),
           ("2026-01-04", "716.05", "2025-12-29", 6, "4376.70", "729.45"),
           ("2026-01-06", "462.30", "2025-12-31", 6, "4104.80", "684.13"),
           ("2026-01-07", "498.65", "2026-01-01", 6, "3540.60", "590.10"),
           ("2026-01-09", "683.20", "2026-01-03", 5, "3263.35", "652.67"),
           ("2026-01-10", "1015.75", "2026-01-04", 5, "3375.95", "675.19"),
           ("2026-01-11", "788.60", "2026-01-05", 5, "3448.50", "689.70")])

    check("by the span of the ROWS frame, the two frames agree on the first six days and differ on each of the "
          "other 48, most at 13 days, where ROWS reads 605.42 too high on New Year's Day",
          lambda: q(db, "04-rows-against-range.sql"),
          [(1, 1, 0, "0.00", "2025-11-04", "498.25", "498.25"), (2, 1, 0, "0.00", "2025-11-05", "529.83", "529.83"),
           (3, 1, 0, "0.00", "2025-11-06", "554.27", "554.27"), (4, 1, 0, "0.00", "2025-11-07", "608.90", "608.90"),
           (5, 1, 0, "0.00", "2025-11-08", "714.03", "714.03"), (6, 1, 0, "0.00", "2025-11-09", "736.18", "736.18"),
           (8, 33, 33, "-118.32", "2025-12-24", "1381.19", "1499.51"),
           (9, 8, 8, "97.30", "2025-11-23", "780.07", "682.77"),
           (10, 1, 1, "-1.29", "2025-11-25", "686.12", "687.41"),
           (12, 2, 2, "403.96", "2026-01-03", "1136.09", "732.13"),
           (13, 4, 4, "605.42", "2026-01-01", "1333.94", "728.52")])

    check("read as zero sales, the average drops to 450.36 on 2025-12-30 against 1576.28 read as unknown, and "
          "the first six days are flagged as partial windows",
          lambda: q(db, "05-zero-or-unknown.sql"),
          [("2025-11-04", 1, "71.18", "498.25", "427.07", partial),
           ("2025-11-05", 2, "151.38", "529.83", "378.45", partial),
           ("2025-11-06", 3, "237.54", "554.27", "316.73", partial),
           ("2025-11-07", 4, "347.94", "608.90", "260.96", partial),
           ("2025-11-08", 5, "510.02", "714.03", "204.01", partial),
           ("2025-11-09", 6, "631.01", "736.18", "105.17", partial),
           ("2025-11-11", 6, "633.74", "739.36", "105.62", ""), ("2025-11-12", 6, "631.92", "737.24", "105.32", ""),
           ("2025-11-13", 6, "634.48", "740.23", "105.75", ""), ("2025-11-14", 6, "637.52", "743.78", "106.26", ""),
           ("2025-11-15", 6, "645.08", "752.59", "107.51", ""), ("2025-11-16", 6, "646.84", "754.64", "107.80", ""),
           ("2025-11-18", 6, "645.30", "752.85", "107.55", ""), ("2025-11-19", 6, "648.76", "756.89", "108.13", ""),
           ("2025-11-20", 6, "650.67", "759.12", "108.45", ""), ("2025-11-21", 6, "652.76", "761.56", "108.80", ""),
           ("2025-11-23", 5, "487.69", "682.77", "195.08", ""), ("2025-11-25", 5, "491.01", "687.41", "196.40", ""),
           ("2025-11-26", 5, "492.48", "689.47", "196.99", ""), ("2025-11-27", 5, "490.12", "686.17", "196.05", ""),
           ("2025-11-28", 5, "495.49", "693.69", "198.20", ""), ("2025-11-29", 6, "670.74", "782.53", "111.79", ""),
           ("2025-11-30", 6, "672.35", "784.41", "112.06", ""), ("2025-12-02", 6, "673.96", "786.29", "112.33", ""),
           ("2025-12-03", 6, "675.91", "788.56", "112.65", ""), ("2025-12-04", 6, "680.82", "794.29", "113.47", ""),
           ("2025-12-05", 6, "684.48", "798.56", "114.08", ""), ("2025-12-06", 6, "690.41", "805.48", "115.07", ""),
           ("2025-12-07", 6, "695.01", "810.84", "115.83", ""), ("2025-12-09", 6, "698.91", "815.39", "116.48", ""),
           ("2025-12-10", 6, "701.46", "818.38", "116.92", ""), ("2025-12-11", 6, "706.72", "824.51", "117.79", ""),
           ("2025-12-12", 6, "713.24", "832.11", "118.87", ""), ("2025-12-13", 6, "723.89", "844.54", "120.65", ""),
           ("2025-12-14", 6, "730.12", "851.81", "121.69", ""), ("2025-12-16", 6, "736.49", "859.23", "122.74", ""),
           ("2025-12-17", 6, "744.56", "868.66", "124.10", ""), ("2025-12-18", 6, "754.50", "880.25", "125.75", ""),
           ("2025-12-19", 6, "778.62", "908.39", "129.77", ""), ("2025-12-20", 6, "823.24", "960.45", "137.21", ""),
           ("2025-12-21", 6, "855.62", "998.23", "142.61", ""),
           ("2025-12-23", 6, "1035.71", "1208.33", "172.62", ""),
           ("2025-12-24", 6, "1285.29", "1499.51", "214.22", ""),
           ("2025-12-30", 2, "450.36", "1576.28", "1125.92", ""),
           ("2025-12-31", 2, "256.72", "898.53", "641.81", ""), ("2026-01-01", 3, "312.22", "728.52", "416.30", ""),
           ("2026-01-02", 4, "393.93", "689.38", "295.45", ""), ("2026-01-03", 5, "522.95", "732.13", "209.18", ""),
           ("2026-01-04", 6, "625.24", "729.45", "104.21", ""), ("2026-01-06", 6, "586.40", "684.13", "97.73", ""),
           ("2026-01-07", 6, "505.80", "590.10", "84.30", ""), ("2026-01-09", 5, "466.19", "652.67", "186.48", ""),
           ("2026-01-10", 5, "482.28", "675.19", "192.91", ""), ("2026-01-11", 5, "492.64", "689.70", "197.06", "")])

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

    def blank_cell():
        # No query here ever returns NULL, so the printer's own handling
        # of one is checked directly.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            print_table(["day", "sales"], [("2025-11-04", "498.25"), ("2025-11-05", None)])
        return out.getvalue().splitlines()

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
          "rows each prints and the first of them, and a query file that fails, has no query result, is not "
          "UTF-8 or is gone by the time it is read, or a folder named like one, stops them with a one-line "
          "message; a value the printer is handed as nothing prints as a blank cell",
          lambda: [reports(), broken_reports(), blank_cell()],
          [[("=== 01-log-shape.sql ===",
             "first_day   last_day    calendar_days  days_logged  days_missing  mondays_missing  other_days_missing  "
             "longest_gap  total_sales",
             "----------  ----------  -------------  -----------  ------------  ---------------  ------------------  "
             "-----------  -----------", 1,
             "2025-11-04  2026-01-11  69             54           15            9                6                   "
             "5            45147.60"),
            ("=== 02-rows-frame.sql ===", "day         sales    window_from  calendar_days  avg_7",
             "----------  -------  -----------  -------------  -------", 54,
             "2025-11-04  498.25   2025-11-04   1              498.25"),
            ("=== 03-range-frame.sql ===", "day         sales    window_from  days_logged  window_sales  avg_7",
             "----------  -------  -----------  -----------  ------------  -------", 54,
             "2025-11-04  498.25   2025-10-29   1            498.25        498.25"),
            ("=== 04-rows-against-range.sql ===",
             "calendar_days  days  days_differing  largest_drift  on_day      rows_avg  range_avg",
             "-------------  ----  --------------  -------------  ----------  --------  ---------", 11,
             "1              1     0               0.00           2025-11-04  498.25    498.25"),
            ("=== 05-zero-or-unknown.sql ===", "day         days_logged  as_zero  as_unknown  gap      note",
             "----------  -----------  -------  ----------  -------  " + "-" * len(partial), 54,
             "2025-11-04  1            71.18    498.25      427.07   " + partial)],
           [(2, '01-broken.sql: did not run: near "SELEC": syntax error'),
            (2, "01-empty.sql: did not run: has no query result to print"),
            (2, "01-ansi.sql: is not UTF-8 text"),
            (2, "01-folder.sql: is a folder, not a query file"),
            (2, "01-gone.sql: No such file or directory")],
           ["day         sales", "----------  ------", "2025-11-04  498.25", "2025-11-05"]])

    # Logs built for cases the sample does not reach on its own. None of the
    # logs made here goes through the loader.
    def log(pairs):
        return new_db(pairs)

    # Nine days in a row across a leap day, one of them logged at 0.00.
    every_day = [("2024-02-24", 35025), ("2024-02-25", 41280), ("2024-02-26", 0), ("2024-02-27", 29815),
                 ("2024-02-28", 33460), ("2024-02-29", 38705), ("2024-03-01", 45190), ("2024-03-02", 52335),
                 ("2024-03-03", 40050)]
    full = log(every_day)
    no_zero = log([pair for pair in every_day if pair[1] != 0])
    check("with no day missing, across a leap day, the seven rows are the seven days, so the two frames agree "
          "and a full window reads the same as zero or unknown; a day logged at 0.00 counts as a day in both "
          "readings, and left out it moves only the unknown one",
          lambda: [q(full, "02-rows-frame.sql"), q(full, "03-range-frame.sql"), q(full, "04-rows-against-range.sql"),
                   q(full, "05-zero-or-unknown.sql"), q(no_zero, "01-log-shape.sql"),
                   q(no_zero, "05-zero-or-unknown.sql")],
          [[("2024-02-24", "350.25", "2024-02-24", 1, "350.25"), ("2024-02-25", "412.80", "2024-02-24", 2, "381.53"),
            ("2024-02-26", "0.00", "2024-02-24", 3, "254.35"), ("2024-02-27", "298.15", "2024-02-24", 4, "265.30"),
            ("2024-02-28", "334.60", "2024-02-24", 5, "279.16"), ("2024-02-29", "387.05", "2024-02-24", 6, "297.14"),
            ("2024-03-01", "451.90", "2024-02-24", 7, "319.25"), ("2024-03-02", "523.35", "2024-02-25", 7, "343.98"),
            ("2024-03-03", "400.50", "2024-02-26", 7, "342.22")],
           [("2024-02-24", "350.25", "2024-02-18", 1, "350.25", "350.25"),
            ("2024-02-25", "412.80", "2024-02-19", 2, "763.05", "381.53"),
            ("2024-02-26", "0.00", "2024-02-20", 3, "763.05", "254.35"),
            ("2024-02-27", "298.15", "2024-02-21", 4, "1061.20", "265.30"),
            ("2024-02-28", "334.60", "2024-02-22", 5, "1395.80", "279.16"),
            ("2024-02-29", "387.05", "2024-02-23", 6, "1782.85", "297.14"),
            ("2024-03-01", "451.90", "2024-02-24", 7, "2234.75", "319.25"),
            ("2024-03-02", "523.35", "2024-02-25", 7, "2407.85", "343.98"),
            ("2024-03-03", "400.50", "2024-02-26", 7, "2395.55", "342.22")],
           [(1, 1, 0, "0.00", "2024-02-24", "350.25", "350.25"), (2, 1, 0, "0.00", "2024-02-25", "381.53", "381.53"),
            (3, 1, 0, "0.00", "2024-02-26", "254.35", "254.35"), (4, 1, 0, "0.00", "2024-02-27", "265.30", "265.30"),
            (5, 1, 0, "0.00", "2024-02-28", "279.16", "279.16"), (6, 1, 0, "0.00", "2024-02-29", "297.14", "297.14"),
            (7, 3, 0, "0.00", "2024-03-01", "319.25", "319.25")],
           [("2024-02-24", 1, "50.04", "350.25", "300.21", partial),
            ("2024-02-25", 2, "109.01", "381.53", "272.52", partial),
            ("2024-02-26", 3, "109.01", "254.35", "145.34", partial),
            ("2024-02-27", 4, "151.60", "265.30", "113.70", partial),
            ("2024-02-28", 5, "199.40", "279.16", "79.76", partial),
            ("2024-02-29", 6, "254.69", "297.14", "42.45", partial),
            ("2024-03-01", 7, "319.25", "319.25", "0.00", ""), ("2024-03-02", 7, "343.98", "343.98", "0.00", ""),
            ("2024-03-03", 7, "342.22", "342.22", "0.00", "")],
           [("2024-02-24", "2024-03-03", 9, 8, 1, 1, 0, 1, "3158.60")],
           [("2024-02-24", 1, "50.04", "350.25", "300.21", partial),
            ("2024-02-25", 2, "109.01", "381.53", "272.52", partial),
            ("2024-02-27", 3, "151.60", "353.73", "202.13", partial),
            ("2024-02-28", 4, "199.40", "348.95", "149.55", partial),
            ("2024-02-29", 5, "254.69", "356.57", "101.88", partial),
            ("2024-03-01", 6, "319.25", "372.46", "53.21", ""), ("2024-03-02", 6, "343.98", "401.31", "57.33", ""),
            ("2024-03-03", 6, "342.22", "399.26", "57.04", "")]])

    sparse = log([("2026-03-01", 10000), ("2026-03-07", 20000), ("2026-03-08", 40000), ("2026-03-15", 80000)])

    def text_ordered():
        # Query 03 with its frame ordered by the date text instead of the day
        # number: it runs, and every day's frame holds that day alone.
        text = (SQL_DIR / "03-range-frame.sql").read_text(encoding="utf-8")
        changed = text.replace("ORDER BY day_no RANGE", "ORDER BY day RANGE")
        rows = run_query(db, None, changed)[1]
        return changed != text, len(rows), sum(1 for r in rows if r[3] == 1 and r[5] == r[1])

    check("a day six days back is inside the seven-day frame and one seven back is not; on a log this sparse "
          "the ROWS frame reaches across 15 days and averages 375.00 where the only day in the week sold 800.00; "
          "a day six days after the first has a full window; and ordered by the date text, the RANGE frame "
          "still runs and holds each day alone",
          lambda: [q(sparse, "01-log-shape.sql"), q(sparse, "02-rows-frame.sql"), q(sparse, "03-range-frame.sql"),
                   q(sparse, "04-rows-against-range.sql"), q(sparse, "05-zero-or-unknown.sql"), text_ordered()],
          [[("2026-03-01", "2026-03-15", 15, 4, 11, 2, 9, 6, "1500.00")],
           [("2026-03-01", "100.00", "2026-03-01", 1, "100.00"), ("2026-03-07", "200.00", "2026-03-01", 7, "150.00"),
            ("2026-03-08", "400.00", "2026-03-01", 8, "233.33"), ("2026-03-15", "800.00", "2026-03-01", 15, "375.00")],
           [("2026-03-01", "100.00", "2026-02-23", 1, "100.00", "100.00"),
            ("2026-03-07", "200.00", "2026-03-01", 2, "300.00", "150.00"),
            ("2026-03-08", "400.00", "2026-03-02", 2, "600.00", "300.00"),
            ("2026-03-15", "800.00", "2026-03-09", 1, "800.00", "800.00")],
           [(1, 1, 0, "0.00", "2026-03-01", "100.00", "100.00"), (7, 1, 0, "0.00", "2026-03-07", "150.00", "150.00"),
            (8, 1, 1, "-66.67", "2026-03-08", "233.33", "300.00"),
            (15, 1, 1, "-425.00", "2026-03-15", "375.00", "800.00")],
           [("2026-03-01", 1, "14.29", "100.00", "85.71", partial), ("2026-03-07", 2, "42.86", "150.00", "107.14", ""),
            ("2026-03-08", 2, "85.71", "300.00", "214.29", ""), ("2026-03-15", 1, "114.29", "800.00", "685.71", "")],
           (True, 54, 54)])

    # Two tied logs. In the ten-day span of the first, the three days drift
    # by -28.57, -37.14 and 37.14 in date order; in the eight-day span of the
    # second, by -4.76, 19.04 and -19.04. The tie goes to the middle day both
    # times, and the earlier day of the pair drifts down in one and up in the
    # other, so neither the order of the days alone, nor a tie sent to the
    # later day, nor one settled by the sign of the drift picks it in both.
    # On these SQLite versions the tied days also reach query 04's ROW_NUMBER
    # in date order, so a query with no tiebreak at all would pass as well;
    # the day in its ORDER BY is what makes the earlier day sure to win.
    tied = log([("2026-03-03", 60000), ("2026-03-04", 30000), ("2026-03-07", 60000), ("2026-03-08", 30000),
                ("2026-03-09", 40000), ("2026-03-11", 70000), ("2026-03-14", 50000), ("2026-03-15", 40000),
                ("2026-03-16", 40000), ("2026-03-17", 40000), ("2026-03-18", 40000)])
    tied_up = log([("2026-03-03", 30000), ("2026-03-05", 50000), ("2026-03-06", 30000), ("2026-03-07", 10000),
                   ("2026-03-08", 40000), ("2026-03-09", 40000), ("2026-03-10", 30000), ("2026-03-12", 70000),
                   ("2026-03-13", 70000), ("2026-03-15", 30000), ("2026-03-18", 10000)])
    # A day on a Monday, and a Sunday and a Monday, so a calendar that starts
    # or ends a day out would miss a Monday that is logged.
    one = log([("2026-02-16", 99999999)])
    weekend = log([("2026-03-22", 1), ("2026-03-23", 2)])
    check("when two days in one span drift equally far, one each way, the report names the earlier of them, "
          "whether it drifts up or down; a log of one day, a Monday, gives each report one row, at the largest "
          "amount a day may hold, and read as zero that day is a seventh of itself; and a logged Monday at "
          "either end of a log is not counted missing",
          lambda: [q(tied, "04-rows-against-range.sql"), q(tied_up, "04-rows-against-range.sql"),
                   q(one, "01-log-shape.sql"), q(one, "02-rows-frame.sql"), q(one, "03-range-frame.sql"),
                   q(one, "04-rows-against-range.sql"), q(one, "05-zero-or-unknown.sql"),
                   q(weekend, "01-log-shape.sql")],
          [[(1, 1, 0, "0.00", "2026-03-03", "600.00", "600.00"), (2, 1, 0, "0.00", "2026-03-04", "450.00", "450.00"),
            (5, 1, 0, "0.00", "2026-03-07", "500.00", "500.00"), (6, 1, 0, "0.00", "2026-03-08", "450.00", "450.00"),
            (7, 1, 0, "0.00", "2026-03-09", "440.00", "440.00"), (9, 1, 1, "-16.67", "2026-03-11", "483.33", "500.00"),
            (10, 3, 3, "-37.14", "2026-03-17", "442.86", "480.00"),
            (12, 2, 2, "-42.86", "2026-03-15", "457.14", "500.00")],
           [(1, 1, 0, "0.00", "2026-03-03", "300.00", "300.00"), (3, 1, 0, "0.00", "2026-03-05", "400.00", "400.00"),
            (4, 1, 0, "0.00", "2026-03-06", "366.67", "366.67"), (5, 1, 0, "0.00", "2026-03-07", "300.00", "300.00"),
            (6, 1, 0, "0.00", "2026-03-08", "320.00", "320.00"), (7, 1, 0, "0.00", "2026-03-09", "333.33", "333.33"),
            (8, 3, 3, "19.04", "2026-03-12", "385.71", "366.67"),
            (9, 1, 1, "-65.71", "2026-03-15", "414.29", "480.00"),
            (11, 1, 1, "-35.71", "2026-03-18", "414.29", "450.00")],
           [("2026-02-16", "2026-02-16", 1, 1, 0, 0, 0, 0, "999999.99")],
           [("2026-02-16", "999999.99", "2026-02-16", 1, "999999.99")],
           [("2026-02-16", "999999.99", "2026-02-10", 1, "999999.99", "999999.99")],
           [(1, 1, 0, "0.00", "2026-02-16", "999999.99", "999999.99")],
           [("2026-02-16", 1, "142857.14", "999999.99", "857142.85", partial)],
           [("2026-03-22", "2026-03-23", 2, 2, 0, 0, 0, 0, "0.03")]])

    def reversed_log():
        # The sample again, stored in the opposite order in a table with no
        # key, so nothing hands the rows back in date order unless a query
        # sorts them.
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE daily_sales (day TEXT NOT NULL, sales_cents INTEGER NOT NULL)")
        conn.executemany("INSERT INTO daily_sales VALUES (?, ?)", list(reversed(load(SALES_CSV))))
        return [q(conn, name) == q(db, name) for name in
                ("01-log-shape.sql", "02-rows-frame.sql", "03-range-frame.sql", "04-rows-against-range.sql",
                 "05-zero-or-unknown.sql")]

    check("the sample stored in the opposite order, in a table with no key to keep it in order, gives the same "
          "five reports",
          reversed_log, [True] * 5)

    # Every day the loader allows, 1970-01-01 to 2200-12-31, each near the
    # largest amount a day may hold; and two days, one at each end, which
    # leaves query 01 a calendar of 84371 days to walk with nothing in it.
    whole_range = log([((EARLIEST + timedelta(days=k)).isoformat(), 99999999 - (k * 7919) % 1000)
                       for k in range(84371)])
    two_ends = log([("1970-01-01", 5), ("2200-12-31", 7)])

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
        check("every day from 1970-01-01 to 2200-12-31 near the largest amount, and two days, one at each end, "
              "run through every query inside the step budget, totals print in full to the cent, and a query "
              "that would run for ever is stopped by the budget",
              lambda: [ends(whole_range, "01-log-shape.sql"), ends(whole_range, "02-rows-frame.sql"),
                       ends(whole_range, "03-range-frame.sql"), ends(whole_range, "04-rows-against-range.sql"),
                       ends(whole_range, "05-zero-or-unknown.sql"), q(two_ends, "01-log-shape.sql"),
                       q(two_ends, "02-rows-frame.sql"), q(two_ends, "03-range-frame.sql"),
                       q(two_ends, "04-rows-against-range.sql"), q(two_ends, "05-zero-or-unknown.sql"),
                       endless(tmp)],
              [(1, ("1970-01-01", "2200-12-31", 84371, 84371, 0, 0, 0, 0, "84370577730.64"),
                ("1970-01-01", "2200-12-31", 84371, 84371, 0, 0, 0, 0, "84370577730.64")),
               (84371, ("1970-01-01", "999999.99", "1970-01-01", 1, "999999.99"),
                ("2200-12-31", "999999.69", "2200-12-25", 7, "999997.26")),
               (84371, ("1970-01-01", "999999.99", "1969-12-26", 1, "999999.99", "999999.99"),
                ("2200-12-31", "999999.69", "2200-12-25", 7, "6999980.82", "999997.26")),
               (7, (1, 1, 0, "0.00", "1970-01-01", "999999.99", "999999.99"),
                (7, 84365, 0, "0.00", "1970-01-07", "999993.85", "999993.85")),
               (84371, ("1970-01-01", 1, "142857.14", "999999.99", "857142.85", partial),
                ("2200-12-31", 7, "999997.26", "999997.26", "0.00", "")),
               [("1970-01-01", "2200-12-31", 84371, 2, 84369, 12053, 72316, 84369, "0.12")],
               [("1970-01-01", "0.05", "1970-01-01", 1, "0.05"), ("2200-12-31", "0.07", "1970-01-01", 84371, "0.06")],
               [("1970-01-01", "0.05", "1969-12-26", 1, "0.05", "0.05"),
                ("2200-12-31", "0.07", "2200-12-25", 1, "0.07", "0.07")],
               [(1, 1, 0, "0.00", "1970-01-01", "0.05", "0.05"), (84371, 1, 1, "-0.01", "2200-12-31", "0.06", "0.07")],
               [("1970-01-01", 1, "0.01", "0.05", "0.04", partial), ("2200-12-31", 1, "0.01", "0.07", "0.06", "")],
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
        small = head + "2025-11-04,412.50\n2025-11-05,398.15\n"

        def logs(name, content):
            return rejection(load, csv_file(name, content))

        def sized(result):
            code, loaded = result
            return (code, len(loaded)) if code == 0 else result

        check("the included bad log is refused for an amount written with a thousands separator, and a day "
              "listed twice is refused by name",
              lambda: [rejection(load, HERE / "data" / "invalid-sales.csv"),
                       logs("twice.csv", small + "2025-11-04,3.00\n")],
              [(2, "invalid-sales.csv row 46: sales '1,062.85' is not an amount from 0.00 to 999999.99 "
                   "written like 412.50"),
               (2, "twice.csv row 4: 2025-11-04 appears twice; one row per day, with the day's sales added "
                   "together")])

        bad_shapes = ["2025-1-04", "25-11-04", "2025/11/04", "2025-11-04T09:00", "04/11/2025", "",
                      "\uff12\uff10\uff12\uff15-11-04", "2025-11-4", "Nov 4 2025"]
        not_real = ["2025-11-31", "2025-02-29", "2025-13-01", "2025-00-10", "2025-11-00", "0000-01-01"]
        check("a day written without its leading zeros, with a two-digit year, slashes, a time, day first, "
              "blank, in fullwidth digits or as words is refused, as is the 31st of November, the 29th of "
              "February 2025, a month 13, a month or day 00, a year 0000, and a day before 1970 or after 2200; "
              "1970-01-01, 2024-02-29 and 2200-12-31 in one log load",
              lambda: [logs(f"shape{k}.csv", head + f"{raw},5.00\n") for k, raw in enumerate(bad_shapes)]
                      + [logs(f"real{k}.csv", head + f"{raw},5.00\n") for k, raw in enumerate(not_real)]
                      + [logs("early.csv", head + "1969-12-31,5.00\n"), logs("late.csv", head + "2201-01-01,5.00\n"),
                         logs("bounds.csv", head + "2200-12-31,1.00\n1970-01-01,2.00\n2024-02-29,3.00\n")],
              [(2, f"shape{k}.csv row 2: day {raw!r} is not a date written like 2025-11-04")
               for k, raw in enumerate(bad_shapes)]
              + [(2, f"real{k}.csv row 2: day {raw} is not a real date") for k, raw in enumerate(not_real)]
              + [(2, "early.csv row 2: day 1969-12-31 is outside the days a log can hold, 1970-01-01 to 2200-12-31"),
                 (2, "late.csv row 2: day 2201-01-01 is outside the days a log can hold, 1970-01-01 to 2200-12-31"),
                 (0, [("2200-12-31", 100), ("1970-01-01", 200), ("2024-02-29", 300)])])

        bad_amounts = ["-5.00", "5", "5.0", "5.000", "05.00", "1000000.00", "1e3", "", "5,00", "$5.00", ".50",
                       "1,062.85", "\u0661\u0660.\u0660\u0660", "1\u0660.\u0660\u0660"]
        check("a negative, whole, one-place, three-place, zero-padded, seven-digit, exponent, blank, comma, "
              "dollar-sign or thousands-separated amount, one with no digit before the point, or one with "
              "Arabic-Indic digits in it, even after a plain first digit, is refused; 0.00 and 999999.99 load",
              lambda: [logs(f"amount{k}.csv", small + f'2025-11-06,"{raw}"\n') for k, raw in enumerate(bad_amounts)]
                      + [logs("extremes.csv", head + "2025-11-04,0.00\n2025-11-05,999999.99\n")],
              [(2, f"amount{k}.csv row 4: sales {raw!r} is not an amount from 0.00 to 999999.99 written like 412.50")
               for k, raw in enumerate(bad_amounts)]
              + [(0, [("2025-11-04", 0), ("2025-11-05", 99999999)])])

        check("rows are counted past blank lines and a line of spaces, and a stray quote is named by its own row, "
              "in a data row or in the header; rows with too many or too few fields, a line of commas, a tab, "
              "text after a closing quote, a quote left open, a field past the parser's limit, and a bad, renamed "
              "or reordered header, also one found after blank lines, written as one quoted field or with a "
              "trailing comma, are refused, and a long value or header is cut short in the message, by one "
              "character as well as by many, while a value of exactly 40 characters is shown whole",
              lambda: [logs("rows.csv", small + "\n   \n\n2025-11-06,12.5\n"),
                       logs("quote.csv", small + '2025-11-06,"5.00\n2025-11-07,6.00",7\n'),
                       logs("unclosed.csv", small + '2025-11-06,"5.00\n'),
                       logs("wide.csv", small + "2025-11-06,5.00,extra\n"),
                       logs("narrow.csv", small + "2025-11-06\n"),
                       logs("commas.csv", small + ",\n"),
                       logs("tab.csv", small + "2025-11-06\t,5.00\n"),
                       logs("after.csv", small + '2025-11-06,"5.00"x\n'),
                       logs("huge_field.csv", small + "2025-11-06," + "9" * 200000 + "\n"),
                       logs("header.csv", 'day,"sales"x\n2025-11-04,5.00\n'),
                       logs("open_header.csv", '"day,sales\n2025-11-04,5.00\n'),
                       logs("renamed.csv", "day,amount\n2025-11-04,5.00\n"),
                       logs("reordered.csv", "sales,day\n5.00,2025-11-04\n"),
                       logs("late_renamed.csv", "\n\nday,amount\n2025-11-04,5.00\n"),
                       logs("quoted_header.csv", '"day,sales"\n"2025-11-04,5.00"\n'),
                       logs("long_header.csv", "day,sales" + "x" * 100 + "\n2025-11-04,5.00\n"),
                       logs("comma_header.csv", "day,sales,\n2025-11-04,5.00\n"),
                       logs("long_value.csv", small + "2025-11-06," + "B" * 100 + "\n"),
                       logs("just_over.csv", small + "2025-11-06," + "C" * 41 + "\n"),
                       logs("exactly_40.csv", small + "2025-11-06," + "D" * 40 + "\n")],
              [(2, "rows.csv row 7: sales '12.5' is not an amount from 0.00 to 999999.99 written like 412.50"),
               (2, "quote.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "unclosed.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "wide.csv row 4: has more fields than the header"),
               (2, "narrow.csv row 4: has fewer fields than the header"),
               (2, "commas.csv row 4: day '' is not a date written like 2025-11-04"),
               (2, "tab.csv row 4: day '2025-11-06\\t' is not a date written like 2025-11-04"),
               (2, "after.csv row 4: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "huge_field.csv row 4: has a field over 131072 characters long"),
               (2, "header.csv row 1: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "open_header.csv row 1: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "renamed.csv row 1: expected columns 'day,sales', got 'day,amount'"),
               (2, "reordered.csv row 1: expected columns 'day,sales', got 'sales,day'"),
               (2, "late_renamed.csv row 3: expected columns 'day,sales', got 'day,amount'"),
               (2, "quoted_header.csv row 1: expected columns 'day,sales', got '\"day,sales\"'"),
               (2, "long_header.csv row 1: expected columns 'day,sales', got 'day,sales"
                   + "x" * 31 + "' and 69 more characters"),
               (2, "comma_header.csv row 1: expected columns 'day,sales', got 'day,sales,'"),
               (2, "long_value.csv row 4: sales '" + "B" * 40 + "' and 60 more characters is not an amount "
                   "from 0.00 to 999999.99 written like 412.50"),
               (2, "just_over.csv row 4: sales '" + "C" * 40 + "' and 1 more character is not an amount "
                   "from 0.00 to 999999.99 written like 412.50"),
               (2, "exactly_40.csv row 4: sales '" + "D" * 40 + "' is not an amount from 0.00 to 999999.99 "
                   "written like 412.50")])

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
            return len(list(read_lines(Path(tmp) / "endless.csv", Endless())))

        all_days = "".join(f"{(EARLIEST + timedelta(days=k)).isoformat()},1.00\n" for k in range(84371))
        far_down = all_days[:20000 * 16]
        check("an empty file, one of blank lines, one with only a header, also after a blank line, one that is "
              "not UTF-8 from its first line or only far down, or holds only part of a byte-order mark, a folder, "
              "a read that gives way before the header or partway through, and a line past 1000000 characters "
              "are refused, a line of exactly 1000000 passing the cap and a line that never ends being cut off at it "
              "rather than read whole; while a byte-order mark, blank lines before the "
              "header, spaces around unquoted fields, in the header too, and a line holding one empty quoted field, "
              "which is passed over like a blank one, load",
              lambda: [logs("empty.csv", ""),
                       logs("blank_only.csv", "\n  \n\n"),
                       logs("bare.csv", head),
                       logs("late_bare.csv", "\n" + head),
                       rejection(load, byte_file("latin1.csv", b"day,sales\xc9\n2025-11-04,5.00\n")),
                       rejection(load, byte_file("late_latin1.csv", (head + far_down).encode("utf-8")
                                                 + b"2025-11-04,5.00\xc9\n")),
                       rejection(load, byte_file("part_mark.csv", b"\xef\xbb")),
                       rejection(load, Path(tmp)),
                       rejection(dropped, ""),
                       rejection(dropped, small),
                       logs("long_line.csv", small + "," * 1000001 + "\n"),
                       rejection(capped, "x" * 1000001 + "\n"),
                       rejection(capped, "x" * 1000000 + "\r\n"),
                       rejection(endless_line),
                       logs("marked.csv", "\ufeff day , sales \n 2025-11-04 , 412.50 \n2025-11-05,398.15\n"),
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
               (0, [("2025-11-04", 41250), ("2025-11-05", 39815)]),
               (0, [("2025-11-04", 41250), ("2025-11-05", 39815)]),
               (0, [("2025-11-04", 41250), ("2025-11-05", 39815)])])

        check("a log of every day from 1970-01-01 to 2200-12-31, 84371 rows, loads, and one row more, which can "
              "only repeat a day, is stopped as it is read, before a bad byte further down",
              lambda: [sized(logs("every_day.csv", head + all_days)),
                       rejection(load, byte_file("one_more.csv", (head + all_days + "2025-11-04,1.00\n"
                                                                  + far_down).encode("utf-8") + b"\xc9\n"))],
              [(0, 84371),
               (2, "one_more.csv row 84373: 2025-11-04 appears twice; one row per day, with the day's sales "
                   "added together")])

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
              "sets them up, which leaves alone a stream it cannot switch, and main's own messages come out as "
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
    parser = argparse.ArgumentParser(prog="run.py", description="Run the rolling-average queries against a "
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
