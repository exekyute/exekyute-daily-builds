"""Load a shift log into SQLite and run the weekly overtime queries.

Usage:
    python run.py                     run every query in sql/
    python run.py --test              run the assertion suite
    python run.py --shifts log.csv    load a different log
"""

import argparse
import contextlib
import csv
import io
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
SHIFTS_CSV = HERE / "data" / "shifts.csv"
SQL_DIR = HERE / "sql"
COLUMNS = ["employee", "starts", "ends", "wage"]
CODE = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")
CODE_LENGTH = 24
FIRST_YEAR, LAST_YEAR = 1970, 2200
MINUTE = timedelta(minutes=1)
# A shift runs at most 24 hours, so it crosses at most one boundary between
# weeks, and the queries split a shift at one boundary only.
LONGEST_SHIFT = 1440
# With at most this many shifts of at most 24 hours at a wage of at most
# 999.99, no pay total passes 10**13 cents. Every sum and product the
# queries take stays a whole number well inside SQLite's 64-bit integers,
# and far enough inside that printing cents as a decimal cannot land on the
# wrong cent.
MOST_SHIFTS = 20_000
# A line of the file may hold at most this many characters. A real row holds
# about fifty.
LINE_CAP = 1_000_000
# A query that runs past this many thousand SQLite steps is stopped. The
# sample takes under 30. The costliest log found within the limits above
# takes under a fifth of it, on SQLite 3.31 and 3.34 as on 3.50, so only a
# query that would run away reaches it.
STEP_BUDGET = 100_000


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


def hours(minutes):
    return f"{minutes // 60}:{minutes % 60:02d}"


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


def code(path, row_num, raw):
    # Employees are matched exactly, so a code is held to one plain form:
    # capital letters and digits, joined by single hyphens. One typed another
    # way would split an employee's week in two, and neither half might reach
    # 48 hours.
    if len(raw) > CODE_LENGTH or not CODE.fullmatch(raw):
        fail(path, row_num, f"employee {shown(raw)} is not an employee code: capital letters and digits, "
                            f"joined by single hyphens, at most {CODE_LENGTH} characters")
    return raw


def moment(path, row_num, name, raw):
    # A date and a time to the minute, in the one form the queries read: the
    # SQLite date functions take other forms too, and the seconds of a time
    # written with them would be dropped without a word.
    match = re.fullmatch(r"([0-9]{4})-([0-9]{2})-([0-9]{2}) ([0-9]{2}):([0-9]{2})", raw)
    value = None
    if match and FIRST_YEAR <= int(match.group(1)) <= LAST_YEAR:
        try:
            value = datetime(*(int(part) for part in match.groups()))
        except ValueError:
            value = None
    if value is None:
        fail(path, row_num, f"{name} {shown(raw)} is not a date and time written like 2026-09-14 06:30, "
                            f"from {FIRST_YEAR} to {LAST_YEAR}")
    return value


def wage_of(path, row_num, raw):
    # Dollars and cents an hour, with no sign, no thousands separator and no
    # currency mark.
    match = re.fullmatch(r"(0|[1-9][0-9]{0,2})\.([0-9]{2})", raw)
    if not match or raw == "0.00":
        fail(path, row_num, f"wage {shown(raw)} is not an hourly wage from 0.01 to 999.99 written like 17.35")
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
    rows, spans, wages = [], [], {}
    with handle:
        lines, header_line = open_csv(path, handle, COLUMNS)
        for i, row in records(path, lines, COLUMNS):
            employee = code(path, i, row["employee"])
            starts = moment(path, i, "starts", row["starts"])
            ends = moment(path, i, "ends", row["ends"])
            wage = wage_of(path, i, row["wage"])
            length = (ends - starts) // MINUTE
            if length <= 0:
                fail(path, i, f"ends {row['ends']} is not after starts {row['starts']}")
            if length > LONGEST_SHIFT:
                fail(path, i, f"the shift from {row['starts']} to {row['ends']} runs {hours(length)}; "
                              f"a shift runs at most {hours(LONGEST_SHIFT)}")
            # The rule pays overtime at one and a half times the regular wage,
            # so each employee has one.
            first_wage, first_row = wages.setdefault(employee, (wage, i))
            if wage != first_wage:
                fail(path, i, f"wage {row['wage']} for {employee} is not the "
                              f"{first_wage // 100}.{first_wage % 100:02d} on row {first_row}; "
                              "one regular wage per employee")
            rows.append((employee, row["starts"], row["ends"], wage))
            spans.append((employee, starts, ends, i))
            # The file is read a line at a time, so a log far past the limit
            # is never read to the end.
            if len(rows) > MOST_SHIFTS:
                fail(path, i, f"the log runs past {MOST_SHIFTS} shifts")
    if not rows:
        fail(path, header_line, "no data rows after the header")
    # Minutes worked in two overlapping shifts would count twice. In start
    # order, the first overlap is always between neighbours, so checking each
    # shift against the one before it finds it.
    spans.sort()
    for before, after in zip(spans, spans[1:]):
        if before[0] == after[0] and after[1] < before[2]:
            fail(path, after[3], f"{after[0]}'s shift from {after[1]:%Y-%m-%d %H:%M} overlaps the one on row "
                                 f"{before[3]}, which runs to {before[2]:%Y-%m-%d %H:%M}; one employee's shifts "
                                 "cannot overlap")
    return rows


def new_db(rows):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE shifts (employee TEXT NOT NULL, starts TEXT NOT NULL, ends TEXT NOT NULL, "
               "wage_cents INTEGER NOT NULL, PRIMARY KEY (employee, starts))")
    db.executemany("INSERT INTO shifts VALUES (?, ?, ?, ?)", rows)
    return db


def print_table(headers, rows):
    cells = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h)
              for i, h in enumerate(headers)]
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)).rstrip())
    print("  ".join("-" * w for w in widths))
    for row in cells:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))).rstrip())


def run_query(db, sql_path, most=STEP_BUDGET):
    # SQLite calls budget every thousand steps and stops the query once it
    # returns true, so a query that would run away uses up the budget and
    # stops with an error instead. most is the budget in thousands of steps.
    steps = [0]

    def budget():
        steps[0] += 1
        return steps[0] > most

    db.set_progress_handler(budget, 1000)
    try:
        cursor = db.execute(sql_path.read_text(encoding="utf-8"))
        if cursor.description is None:
            raise sqlite3.ProgrammingError("has no query result to print")
        return [d[0] for d in cursor.description], cursor.fetchall()
    except sqlite3.OperationalError:
        if steps[0] > most:
            raise sqlite3.OperationalError(f"stopped after {most} thousand steps")
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

    check("127 shifts by 5 employees run across 6 Sunday-to-Saturday weeks: 26 run overnight, 2 run into the "
          "next week and 15 days are split, for 957:32 worked",
          lambda: q(db, "01-log-shape.sql"),
          [(127, 5, "2026-08-23 06:30", "2026-09-27 06:30", 6, 26, 2, 15, "957:32")])

    check("counted shift by shift past eight hours, 14 of 25 weeks show overtime; counted by the week each shift "
          "starts in, a Saturday night's hours after midnight land in the week before the one they are worked in",
          lambda: q(db, "02-per-shift-overtime.sql"),
          [("AMARA", "2026-08-23", 5, "47:30", "7:30", "0:00"),
           ("AMARA", "2026-08-30", 6, "54:44", "7:30", "6:44"),
           ("AMARA", "2026-09-06", 4, "38:00", "6:00", "0:00"),
           ("AMARA", "2026-09-13", 5, "47:30", "7:30", "0:00"),
           ("AMARA", "2026-09-20", 4, "38:00", "6:00", "0:00"),
           ("BRODIE", "2026-08-23", 6, "55:00", "7:00", "7:00"),
           ("BRODIE", "2026-08-30", 5, "43:00", "3:00", "0:00"),
           ("BRODIE", "2026-09-06", 5, "45:00", "5:00", "0:00"),
           ("BRODIE", "2026-09-13", 5, "40:00", "0:00", "0:00"),
           ("BRODIE", "2026-09-20", 5, "42:00", "4:00", "0:00"),
           ("CELINE", "2026-08-23", 14, "54:15", "0:00", "6:15"),
           ("CELINE", "2026-08-30", 5, "37:30", "0:00", "0:00"),
           ("CELINE", "2026-09-06", 7, "50:10", "0:00", "2:10"),
           ("CELINE", "2026-09-13", 12, "48:00", "0:00", "0:00"),
           ("CELINE", "2026-09-20", 6, "47:00", "0:00", "0:00"),
           ("DESMOND", "2026-08-23", 5, "48:00", "8:00", "0:00"),
           ("DESMOND", "2026-08-30", 5, "48:01", "8:01", "0:01"),
           ("DESMOND", "2026-09-06", 4, "38:24", "6:24", "0:00"),
           ("DESMOND", "2026-09-13", 6, "62:00", "14:00", "14:00"),
           ("DESMOND", "2026-09-20", 5, "40:58", "0:58", "0:00"),
           ("ELSPETH", "2026-08-23", 2, "8:13", "0:00", "0:00"),
           ("ELSPETH", "2026-08-30", 1, "4:00", "0:00", "0:00"),
           ("ELSPETH", "2026-09-06", 2, "9:07", "0:00", "0:00"),
           ("ELSPETH", "2026-09-13", 2, "8:00", "0:00", "0:00"),
           ("ELSPETH", "2026-09-20", 1, "3:10", "0:00", "0:00")])

    check("split at 00:00 on Sunday, a Saturday night's hours after midnight count in the week they are worked, "
          "a week reached only by them still prints, and six weeks pass 48 hours",
          lambda: q(db, "03-weekly-overtime.sql"),
          [("AMARA", "2026-08-23", 5, "0:00", "47:30", "47:30", "0:00", None),
           ("AMARA", "2026-08-30", 6, "0:00", "54:44", "48:00", "6:44", "2026-09-04 22:30"),
           ("AMARA", "2026-09-06", 4, "0:00", "38:00", "38:00", "0:00", None),
           ("AMARA", "2026-09-13", 5, "0:00", "47:30", "47:30", "0:00", None),
           ("AMARA", "2026-09-20", 4, "0:00", "38:00", "38:00", "0:00", None),
           ("BRODIE", "2026-08-23", 6, "0:00", "48:00", "48:00", "0:00", None),
           ("BRODIE", "2026-08-30", 6, "7:00", "50:00", "48:00", "2:00", "2026-09-04 12:36"),
           ("BRODIE", "2026-09-06", 5, "0:00", "45:00", "45:00", "0:00", None),
           ("BRODIE", "2026-09-13", 5, "0:00", "40:00", "40:00", "0:00", None),
           ("BRODIE", "2026-09-20", 5, "0:00", "42:00", "42:00", "0:00", None),
           ("CELINE", "2026-08-23", 14, "0:00", "54:15", "48:00", "6:15", "2026-08-29 08:00"),
           ("CELINE", "2026-08-30", 5, "0:00", "37:30", "37:30", "0:00", None),
           ("CELINE", "2026-09-06", 7, "0:00", "50:10", "48:00", "2:10", "2026-09-12 11:30"),
           ("CELINE", "2026-09-13", 12, "0:00", "48:00", "48:00", "0:00", None),
           ("CELINE", "2026-09-20", 6, "0:00", "47:00", "47:00", "0:00", None),
           ("DESMOND", "2026-08-23", 5, "0:00", "48:00", "48:00", "0:00", None),
           ("DESMOND", "2026-08-30", 5, "0:00", "48:01", "48:00", "0:01", "2026-09-04 14:36"),
           ("DESMOND", "2026-09-06", 4, "0:00", "38:24", "38:24", "0:00", None),
           ("DESMOND", "2026-09-13", 6, "0:00", "62:00", "48:00", "14:00", "2026-09-18 11:40"),
           ("DESMOND", "2026-09-20", 5, "0:00", "34:28", "34:28", "0:00", None),
           ("DESMOND", "2026-09-27", 1, "6:30", "6:30", "6:30", "0:00", None),
           ("ELSPETH", "2026-08-23", 2, "0:00", "8:13", "8:13", "0:00", None),
           ("ELSPETH", "2026-08-30", 1, "0:00", "4:00", "4:00", "0:00", None),
           ("ELSPETH", "2026-09-06", 2, "0:00", "9:07", "9:07", "0:00", None),
           ("ELSPETH", "2026-09-13", 2, "0:00", "8:00", "8:00", "0:00", None),
           ("ELSPETH", "2026-09-20", 1, "0:00", "3:10", "3:10", "0:00", None)])

    check("pay comes to 19569.98 for the log, with 941.77 of it overtime, and a pay line that lands on half a "
          "cent rounds up",
          lambda: q(db, "04-weekly-pay.sql"),
          [("AMARA", "2026-08-23", "22.45", "47:30", "0:00", "1066.38", "0.00", "1066.38"),
           ("AMARA", "2026-08-30", "22.45", "48:00", "6:44", "1077.60", "226.75", "1304.35"),
           ("AMARA", "2026-09-06", "22.45", "38:00", "0:00", "853.10", "0.00", "853.10"),
           ("AMARA", "2026-09-13", "22.45", "47:30", "0:00", "1066.38", "0.00", "1066.38"),
           ("AMARA", "2026-09-20", "22.45", "38:00", "0:00", "853.10", "0.00", "853.10"),
           ("BRODIE", "2026-08-23", "19.90", "48:00", "0:00", "955.20", "0.00", "955.20"),
           ("BRODIE", "2026-08-30", "19.90", "48:00", "2:00", "955.20", "59.70", "1014.90"),
           ("BRODIE", "2026-09-06", "19.90", "45:00", "0:00", "895.50", "0.00", "895.50"),
           ("BRODIE", "2026-09-13", "19.90", "40:00", "0:00", "796.00", "0.00", "796.00"),
           ("BRODIE", "2026-09-20", "19.90", "42:00", "0:00", "835.80", "0.00", "835.80"),
           ("CELINE", "2026-08-23", "18.35", "48:00", "6:15", "880.80", "172.03", "1052.83"),
           ("CELINE", "2026-08-30", "18.35", "37:30", "0:00", "688.13", "0.00", "688.13"),
           ("CELINE", "2026-09-06", "18.35", "48:00", "2:10", "880.80", "59.64", "940.44"),
           ("CELINE", "2026-09-13", "18.35", "48:00", "0:00", "880.80", "0.00", "880.80"),
           ("CELINE", "2026-09-20", "18.35", "47:00", "0:00", "862.45", "0.00", "862.45"),
           ("DESMOND", "2026-08-23", "20.15", "48:00", "0:00", "967.20", "0.00", "967.20"),
           ("DESMOND", "2026-08-30", "20.15", "48:00", "0:01", "967.20", "0.50", "967.70"),
           ("DESMOND", "2026-09-06", "20.15", "38:24", "0:00", "773.76", "0.00", "773.76"),
           ("DESMOND", "2026-09-13", "20.15", "48:00", "14:00", "967.20", "423.15", "1390.35"),
           ("DESMOND", "2026-09-20", "20.15", "34:28", "0:00", "694.50", "0.00", "694.50"),
           ("DESMOND", "2026-09-27", "20.15", "6:30", "0:00", "130.98", "0.00", "130.98"),
           ("ELSPETH", "2026-08-23", "17.85", "8:13", "0:00", "146.67", "0.00", "146.67"),
           ("ELSPETH", "2026-08-30", "17.85", "4:00", "0:00", "71.40", "0.00", "71.40"),
           ("ELSPETH", "2026-09-06", "17.85", "9:07", "0:00", "162.73", "0.00", "162.73"),
           ("ELSPETH", "2026-09-13", "17.85", "8:00", "0:00", "142.80", "0.00", "142.80"),
           ("ELSPETH", "2026-09-20", "17.85", "3:10", "0:00", "56.53", "0.00", "56.53"),
           ("total", None, None, "926:22", "31:10", "18628.21", "941.77", "19569.98")])

    check("side by side, the per-shift count finds 90:53 of overtime against 31:10 and pays 639.01 over on "
          "balance, and the count by start week moves 7:00 and 6:30 across two week boundaries",
          lambda: q(db, "05-rules-side-by-side.sql"),
          [("AMARA", "2026-08-23", "0:00", "7:30", "0:00", "1066.38", "+84.18", "0.00"),
           ("AMARA", "2026-08-30", "6:44", "7:30", "6:44", "1304.35", "+8.60", "0.00"),
           ("AMARA", "2026-09-06", "0:00", "6:00", "0:00", "853.10", "+67.35", "0.00"),
           ("AMARA", "2026-09-13", "0:00", "7:30", "0:00", "1066.38", "+84.18", "0.00"),
           ("AMARA", "2026-09-20", "0:00", "6:00", "0:00", "853.10", "+67.35", "0.00"),
           ("BRODIE", "2026-08-23", "0:00", "7:00", "7:00", "955.20", "+208.95", "+208.95"),
           ("BRODIE", "2026-08-30", "2:00", "3:00", "0:00", "1014.90", "-129.35", "-159.20"),
           ("BRODIE", "2026-09-06", "0:00", "5:00", "0:00", "895.50", "+49.75", "0.00"),
           ("BRODIE", "2026-09-13", "0:00", "0:00", "0:00", "796.00", "0.00", "0.00"),
           ("BRODIE", "2026-09-20", "0:00", "4:00", "0:00", "835.80", "+39.80", "0.00"),
           ("CELINE", "2026-08-23", "6:15", "0:00", "6:15", "1052.83", "-57.34", "0.00"),
           ("CELINE", "2026-08-30", "0:00", "0:00", "0:00", "688.13", "0.00", "0.00"),
           ("CELINE", "2026-09-06", "2:10", "0:00", "2:10", "940.44", "-19.88", "0.00"),
           ("CELINE", "2026-09-13", "0:00", "0:00", "0:00", "880.80", "0.00", "0.00"),
           ("CELINE", "2026-09-20", "0:00", "0:00", "0:00", "862.45", "0.00", "0.00"),
           ("DESMOND", "2026-08-23", "0:00", "8:00", "0:00", "967.20", "+80.60", "0.00"),
           ("DESMOND", "2026-08-30", "0:01", "8:01", "0:01", "967.70", "+80.60", "0.00"),
           ("DESMOND", "2026-09-06", "0:00", "6:24", "0:00", "773.76", "+64.48", "0.00"),
           ("DESMOND", "2026-09-13", "14:00", "14:00", "14:00", "1390.35", "0.00", "0.00"),
           ("DESMOND", "2026-09-20", "0:00", "0:58", "0:00", "694.50", "+140.72", "+130.98"),
           ("DESMOND", "2026-09-27", "0:00", "0:00", "0:00", "130.98", "-130.98", "-130.98"),
           ("ELSPETH", "2026-08-23", "0:00", "0:00", "0:00", "146.67", "0.00", "0.00"),
           ("ELSPETH", "2026-08-30", "0:00", "0:00", "0:00", "71.40", "0.00", "0.00"),
           ("ELSPETH", "2026-09-06", "0:00", "0:00", "0:00", "162.73", "0.00", "0.00"),
           ("ELSPETH", "2026-09-13", "0:00", "0:00", "0:00", "142.80", "0.00", "0.00"),
           ("ELSPETH", "2026-09-20", "0:00", "0:00", "0:00", "56.53", "0.00", "0.00"),
           ("total", None, "31:10", "90:53", "36:10", "19569.98", "+639.01", "+49.75")])

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

    def total_lines():
        # The last line of the two reports with a total, where the week and
        # the wage are blank.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run_all(db)
        return [line for line in out.getvalue().split("\n") if line.startswith("total")]

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
          "rows each prints and the first of them, with blank cells where a week has no overtime and on the "
          "total lines; and a query file that fails, has no query result, is not UTF-8 or is gone by the time "
          "it is read, or a folder named like one, stops them with a one-line message",
          lambda: [reports(), total_lines(), broken_reports()],
          [[("=== 01-log-shape.sql ===",
             "shifts  employees  first_start       last_end          weeks  overnight  into_next_week  split_days  "
             "worked",
             "------  ---------  ----------------  ----------------  -----  ---------  --------------  ----------  "
             "------", 1,
             "127     5          2026-08-23 06:30  2026-09-27 06:30  6      26         2               15          "
             "957:32"),
            ("=== 02-per-shift-overtime.sql ===",
             "employee  week        shifts  worked  over_8_a_shift  over_48_by_start",
             "--------  ----------  ------  ------  --------------  ----------------", 25,
             "AMARA     2026-08-23  5       47:30   7:30            0:00"),
            ("=== 03-weekly-overtime.sql ===",
             "employee  week        shifts  carried_in  worked  regular  overtime  overtime_from",
             "--------  ----------  ------  ----------  ------  -------  --------  ----------------", 26,
             "AMARA     2026-08-23  5       0:00        47:30   47:30    0:00"),
            ("=== 04-weekly-pay.sql ===",
             "employee  week        wage   regular  overtime  regular_pay  overtime_pay  pay",
             "--------  ----------  -----  -------  --------  -----------  ------------  --------", 27,
             "AMARA     2026-08-23  22.45  47:30    0:00      1066.38      0.00          1066.38"),
            ("=== 05-rules-side-by-side.sql ===",
             "employee  week        overtime  over_8_a_shift  over_48_by_start  pay       over_8_gap  by_start_gap",
             "--------  ----------  --------  --------------  ----------------  --------  ----------  ------------", 27,
             "AMARA     2026-08-23  0:00      7:30            0:00              1066.38   +84.18      0.00")],
           ["total                        926:22   31:10     18628.21     941.77        19569.98",
            "total                 31:10     90:53           36:10             19569.98  +639.01     +49.75"],
           [(2, '01-broken.sql: did not run: near "SELEC": syntax error'),
            (2, "01-empty.sql: did not run: has no query result to print"),
            (2, "01-ansi.sql: is not UTF-8 text"),
            (2, "01-folder.sql: is a folder, not a query file"),
            (2, "01-gone.sql: No such file or directory")]])

    # Logs built for cases the sample does not reach on its own. Only the
    # reversed sample goes through the loader.
    def built(rows):
        return new_db([(e, s, t, w) for e, s, t, w in rows])

    edges = built([("EDGE-A", f"2026-09-{13 + k} 08:00", f"2026-09-{13 + k} 16:00", 2000) for k in range(6)]
                  + [("EDGE-A", "2026-09-19 08:00", "2026-09-19 08:01", 2000),
                     ("EDGE-B", "2026-09-19 16:00", "2026-09-20 00:00", 1850),
                     ("EDGE-B", "2026-09-20 00:00", "2026-09-20 08:00", 1850),
                     ("EDGE-C", "2026-09-19 06:00", "2026-09-20 06:00", 2100)])
    check("a week of exactly 48:00 and then one more minute puts overtime at the start of that minute's shift; a "
          "shift that ends at exactly 00:00 on Sunday stays in its week and is not overnight, the next one "
          "starting then belongs to the new week, and a 24-hour shift splits 18:00 and 6:00",
          lambda: [q(edges, "01-log-shape.sql"), q(edges, "02-per-shift-overtime.sql"),
                   q(edges, "03-weekly-overtime.sql")],
          [[(10, 3, "2026-09-13 08:00", "2026-09-20 08:00", 2, 1, 1, 0, "88:01")],
           [("EDGE-A", "2026-09-13", 7, "48:01", "0:00", "0:01"),
            ("EDGE-B", "2026-09-13", 1, "8:00", "0:00", "0:00"),
            ("EDGE-B", "2026-09-20", 1, "8:00", "0:00", "0:00"),
            ("EDGE-C", "2026-09-13", 1, "24:00", "16:00", "0:00")],
           [("EDGE-A", "2026-09-13", 7, "0:00", "48:01", "48:00", "0:01", "2026-09-19 08:00"),
            ("EDGE-B", "2026-09-13", 1, "0:00", "8:00", "8:00", "0:00", None),
            ("EDGE-B", "2026-09-20", 1, "0:00", "8:00", "8:00", "0:00", None),
            ("EDGE-C", "2026-09-13", 1, "0:00", "18:00", "18:00", "0:00", None),
            ("EDGE-C", "2026-09-20", 1, "6:00", "6:00", "6:00", "0:00", None)]])

    new_year = built([("NY-A", f"{day} 08:00", f"{day} 18:00", 2000)
                      for day in ("2024-12-29", "2024-12-30", "2024-12-31", "2025-01-01", "2025-01-02")]
                     + [("NY-B", "2022-12-31 22:00", "2023-01-01 06:00", 2000),
                        ("NY-C", "2025-01-04 16:00", "2025-01-05 00:00", 2000)])
    check("a week that runs across New Year stays one week and reaches overtime, a Saturday night that ends on "
          "New Year's Day splits at the turn of the year, and a log whose last shift ends at exactly 00:00 on "
          "Sunday does not reach the week after, in any of the queries that split shifts",
          lambda: [q(new_year, "01-log-shape.sql"), q(new_year, "03-weekly-overtime.sql"),
                   q(new_year, "04-weekly-pay.sql"), q(new_year, "05-rules-side-by-side.sql")],
          [[(7, 3, "2022-12-31 22:00", "2025-01-05 00:00", 106, 1, 1, 0, "66:00")],
           [("NY-A", "2024-12-29", 5, "0:00", "50:00", "48:00", "2:00", "2025-01-02 16:00"),
            ("NY-B", "2022-12-25", 1, "0:00", "2:00", "2:00", "0:00", None),
            ("NY-B", "2023-01-01", 1, "6:00", "6:00", "6:00", "0:00", None),
            ("NY-C", "2024-12-29", 1, "0:00", "8:00", "8:00", "0:00", None)],
           [("NY-A", "2024-12-29", "20.00", "48:00", "2:00", "960.00", "60.00", "1020.00"),
            ("NY-B", "2022-12-25", "20.00", "2:00", "0:00", "40.00", "0.00", "40.00"),
            ("NY-B", "2023-01-01", "20.00", "6:00", "0:00", "120.00", "0.00", "120.00"),
            ("NY-C", "2024-12-29", "20.00", "8:00", "0:00", "160.00", "0.00", "160.00"),
            ("total", None, None, "64:00", "2:00", "1280.00", "60.00", "1340.00")],
           [("NY-A", "2024-12-29", "2:00", "10:00", "2:00", "1020.00", "+80.00", "0.00"),
            ("NY-B", "2022-12-25", "0:00", "0:00", "0:00", "40.00", "+120.00", "+120.00"),
            ("NY-B", "2023-01-01", "0:00", "0:00", "0:00", "120.00", "-120.00", "-120.00"),
            ("NY-C", "2024-12-29", "0:00", "0:00", "0:00", "160.00", "0.00", "0.00"),
            ("total", None, "2:00", "10:00", "2:00", "1340.00", "+80.00", "0.00")]])

    nights = built([("NIGHT", f"2026-09-{day:02d} 20:00", f"2026-09-{day + 1:02d} 08:00", 2001)
                    for day in (5, 12, 19)])
    check("on a log of Saturday nights only, the right count runs one week past the last shift's start, a week "
          "that takes in one Saturday night and sends out the next counts 8:00 carried in, and the count by "
          "start week pays the first week too much and the last too little while its total gap comes to nothing",
          lambda: [q(nights, "01-log-shape.sql"), q(nights, "02-per-shift-overtime.sql"),
                   q(nights, "03-weekly-overtime.sql"), q(nights, "05-rules-side-by-side.sql")],
          [[(3, 1, "2026-09-05 20:00", "2026-09-20 08:00", 4, 3, 3, 0, "36:00")],
           [("NIGHT", "2026-08-30", 1, "12:00", "4:00", "0:00"),
            ("NIGHT", "2026-09-06", 1, "12:00", "4:00", "0:00"),
            ("NIGHT", "2026-09-13", 1, "12:00", "4:00", "0:00")],
           [("NIGHT", "2026-08-30", 1, "0:00", "4:00", "4:00", "0:00", None),
            ("NIGHT", "2026-09-06", 2, "8:00", "12:00", "12:00", "0:00", None),
            ("NIGHT", "2026-09-13", 2, "8:00", "12:00", "12:00", "0:00", None),
            ("NIGHT", "2026-09-20", 1, "8:00", "8:00", "8:00", "0:00", None)],
           [("NIGHT", "2026-08-30", "0:00", "4:00", "0:00", "80.04", "+200.10", "+160.08"),
            ("NIGHT", "2026-09-06", "0:00", "4:00", "0:00", "240.12", "+40.02", "0.00"),
            ("NIGHT", "2026-09-13", "0:00", "4:00", "0:00", "240.12", "+40.02", "0.00"),
            ("NIGHT", "2026-09-20", "0:00", "0:00", "0:00", "160.08", "-160.08", "-160.08"),
            ("total", None, "0:00", "12:00", "0:00", "720.36", "+120.06", "0.00")]])

    # At 19.99 an hour, 11 minutes come to 366.48 cents and 30 to 999.5;
    # overtime of 21 minutes comes to 1049.475 cents and 20 to 999.5. Just
    # under a half rounds down and a half rounds up, in both kinds of pay.
    rounding = built([("R1", "2026-09-14 09:00", "2026-09-14 09:11", 1999),
                      ("R2", "2026-09-14 09:00", "2026-09-14 09:30", 1999)]
                     + [(r, f"2026-09-{13 + k} 08:00", f"2026-09-{13 + k} 16:00", 1999)
                        for r in ("R3", "R4") for k in range(6)]
                     + [("R3", "2026-09-19 08:00", "2026-09-19 08:20", 1999),
                        ("R4", "2026-09-19 08:00", "2026-09-19 08:21", 1999)])
    check("regular and overtime pay each round half up to the cent: just under a half rounds down and a half "
          "rounds up",
          lambda: q(rounding, "04-weekly-pay.sql"),
          [("R1", "2026-09-13", "19.99", "0:11", "0:00", "3.66", "0.00", "3.66"),
           ("R2", "2026-09-13", "19.99", "0:30", "0:00", "10.00", "0.00", "10.00"),
           ("R3", "2026-09-13", "19.99", "48:00", "0:20", "959.52", "10.00", "969.52"),
           ("R4", "2026-09-13", "19.99", "48:00", "0:21", "959.52", "10.49", "970.01"),
           ("total", None, None, "96:41", "0:41", "1932.70", "20.49", "1953.19")])

    def reversed_log():
        # The sample again, stored in the opposite order in a table with no
        # key, so nothing hands the rows back in start order unless a query
        # sorts them.
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE shifts (employee TEXT NOT NULL, starts TEXT NOT NULL, ends TEXT NOT NULL, "
                     "wage_cents INTEGER NOT NULL)")
        conn.executemany("INSERT INTO shifts VALUES (?, ?, ?, ?)", list(reversed(load(SHIFTS_CSV))))
        return [q(conn, name) == q(db, name) for name in
                ("01-log-shape.sql", "02-per-shift-overtime.sql", "03-weekly-overtime.sql", "04-weekly-pay.sql",
                 "05-rules-side-by-side.sql")]

    check("the sample stored in the opposite order, in a table with no key to keep it in order, gives the same "
          "five reports",
          reversed_log, [True] * 5)

    # The most shifts the loader allows, each one the longest it allows,
    # running into the next week, for 20000 employees with the longest codes,
    # at the highest wage: the most pieces and weekly lines the queries can be
    # handed, and one of the costliest logs found for the step budget.
    widest = new_db([(f"E{n:023d}", "2026-09-19 20:00", "2026-09-20 20:00", 99999) for n in range(MOST_SHIFTS)])

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

    def counted(folder, most):
        # Counting to 50000 takes about 950 thousand steps.
        path = Path(folder) / "counted.sql"
        path.write_text("WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n WHERE i < 50000) "
                        "SELECT MAX(i) FROM n;", encoding="utf-8")
        try:
            return run_query(db, path, most)[1]
        except sqlite3.OperationalError as err:
            return str(err)

    first, last = "E" + "0" * 23, "E" + "0" * 18 + "19999"
    with tempfile.TemporaryDirectory() as tmp:
        check("20000 shifts of 24 hours at 999.99, each running into the next week, go through every query "
              "inside the step budget, and a query that would run for ever is stopped by it; a query of about 950 "
              "thousand steps is stopped by a budget of 500 thousand and finishes under one of 2000 thousand",
              lambda: [ends(widest, "01-log-shape.sql"), ends(widest, "02-per-shift-overtime.sql"),
                       ends(widest, "03-weekly-overtime.sql"), ends(widest, "04-weekly-pay.sql"),
                       ends(widest, "05-rules-side-by-side.sql"), endless(tmp), counted(tmp, 500),
                       counted(tmp, 2000)],
              [(1, (20000, 20000, "2026-09-19 20:00", "2026-09-20 20:00", 2, 20000, 20000, 0, "480000:00"),
                (20000, 20000, "2026-09-19 20:00", "2026-09-20 20:00", 2, 20000, 20000, 0, "480000:00")),
               (20000, (first, "2026-09-13", 1, "24:00", "16:00", "0:00"),
                (last, "2026-09-13", 1, "24:00", "16:00", "0:00")),
               (40000, (first, "2026-09-13", 1, "0:00", "4:00", "4:00", "0:00", None),
                (last, "2026-09-20", 1, "20:00", "20:00", "20:00", "0:00", None)),
               (40001, (first, "2026-09-13", "999.99", "4:00", "0:00", "3999.96", "0.00", "3999.96"),
                ("total", None, None, "480000:00", "0:00", "479995200.00", "0.00", "479995200.00")),
               (40001, (first, "2026-09-13", "0:00", "16:00", "0:00", "3999.96", "+27999.72", "+19999.80"),
                ("total", None, "0:00", "320000:00", "0:00", "479995200.00", "+159998400.00", "0.00")),
               "stopped after 100000 thousand steps", "stopped after 500 thousand steps", [(50000,)]])

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
        small = head + "A1,2026-09-14 06:00,2026-09-14 14:00,18.35\nB2,2026-09-14 07:00,2026-09-14 15:30,19.90\n"
        small_rows = [("A1", "2026-09-14 06:00", "2026-09-14 14:00", 1835),
                      ("B2", "2026-09-14 07:00", "2026-09-14 15:30", 1990)]

        def logs(name, content):
            return rejection(load, csv_file(name, content))

        def sized(result):
            code_, loaded = result
            return (code_, len(loaded)) if code_ == 0 else result

        check("the included bad log is refused for a shift typed with the wrong end date; overlapping shifts for "
              "one employee are refused naming both rows, in either order in the file and when repeated, while "
              "shifts that touch and two employees on the same hours load",
              lambda: [rejection(load, HERE / "data" / "invalid-shifts.csv"),
                       logs("overlap.csv", small + "A1,2026-09-14 13:00,2026-09-14 18:00,18.35\n"),
                       logs("earlier.csv", head + "A1,2026-09-14 13:00,2026-09-14 18:00,18.35\n"
                                                  "B2,2026-09-14 07:00,2026-09-14 15:30,19.90\n"
                                                  "A1,2026-09-14 06:00,2026-09-14 14:00,18.35\n"),
                       logs("inside.csv", small + "A1,2026-09-14 09:00,2026-09-14 10:00,18.35\n"),
                       logs("repeated.csv", small + "B2,2026-09-14 07:00,2026-09-14 15:30,19.90\n"),
                       logs("touching.csv", small + "A1,2026-09-14 14:00,2026-09-14 16:00,18.35\n"
                                                    "A2,2026-09-14 06:00,2026-09-14 14:00,18.35\n")],
              [(2, "invalid-shifts.csv row 75: the shift from 2026-09-12 06:30 to 2026-09-21 13:40 runs 223:10; "
                   "a shift runs at most 24:00"),
               (2, "overlap.csv row 4: A1's shift from 2026-09-14 13:00 overlaps the one on row 2, which runs to "
                   "2026-09-14 14:00; one employee's shifts cannot overlap"),
               (2, "earlier.csv row 2: A1's shift from 2026-09-14 13:00 overlaps the one on row 4, which runs to "
                   "2026-09-14 14:00; one employee's shifts cannot overlap"),
               (2, "inside.csv row 4: A1's shift from 2026-09-14 09:00 overlaps the one on row 2, which runs to "
                   "2026-09-14 14:00; one employee's shifts cannot overlap"),
               (2, "repeated.csv row 4: B2's shift from 2026-09-14 07:00 overlaps the one on row 3, which runs to "
                   "2026-09-14 15:30; one employee's shifts cannot overlap"),
               (0, small_rows + [("A1", "2026-09-14 14:00", "2026-09-14 16:00", 1835),
                                 ("A2", "2026-09-14 06:00", "2026-09-14 14:00", 1835)])])

        bad_moments = ["2026-09-14T06:00", "2026-09-14 06:00:00", "2026-09-14 24:00", "2026-02-29 06:00",
                       "2026-9-14 06:00", "2026-09-14 6:00", "2026-09-14  06:00", "1969-12-31 23:59",
                       "2201-01-01 00:00", "", "14/09/2026 06:00", "2026-09-14 06:00Z",
                       "\uff12\uff10\uff12\uff16-09-14 06:00", "2026-09-14"]
        check("a start written with a T, seconds, 24:00, a day the month does not have, a missing leading zero, a "
              "doubled space, outside 1970 to 2200, blank, day first, with a zone, in fullwidth digits or without a "
              "time is refused, as a start and as an end; a shift that ends when it starts or before is refused, as "
              "over 24 hours, while one of a minute, one of exactly 24 hours, a leap day and both ends of the range "
              "load",
              lambda: [logs(f"moment{k}.csv", head + f"A1,{raw},2026-09-14 14:00,18.35\n")
                       for k, raw in enumerate(bad_moments)]
                      + [logs(f"end{k}.csv", head + f"A1,2026-09-14 06:00,{raw},18.35\n")
                         for k, raw in enumerate(bad_moments)]
                      + [
                         logs("same.csv", head + "A1,2026-09-14 06:00,2026-09-14 06:00,18.35\n"),
                         logs("before.csv", head + "A1,2026-09-14 06:00,2026-09-13 22:00,18.35\n"),
                         logs("long.csv", head + "A1,2026-09-14 06:00,2026-09-15 06:01,18.35\n"),
                         logs("edges.csv", head + "A1,2026-09-14 06:00,2026-09-14 06:01,18.35\n"
                                                  "A1,2026-09-19 06:00,2026-09-20 06:00,18.35\n"
                                                  "A1,2028-02-29 23:00,2028-03-01 07:00,18.35\n"
                                                  "B2,1970-01-01 00:00,1970-01-01 08:00,19.90\n"
                                                  "B2,2200-12-31 16:00,2200-12-31 23:59,19.90\n")],
              [(2, f"moment{k}.csv row 2: starts {raw!r} is not a date and time written like 2026-09-14 06:30, "
                   "from 1970 to 2200") for k, raw in enumerate(bad_moments)]
              + [(2, f"end{k}.csv row 2: ends {raw!r} is not a date and time written like 2026-09-14 06:30, "
                     "from 1970 to 2200") for k, raw in enumerate(bad_moments)]
              + [
                 (2, "same.csv row 2: ends 2026-09-14 06:00 is not after starts 2026-09-14 06:00"),
                 (2, "before.csv row 2: ends 2026-09-13 22:00 is not after starts 2026-09-14 06:00"),
                 (2, "long.csv row 2: the shift from 2026-09-14 06:00 to 2026-09-15 06:01 runs 24:01; "
                     "a shift runs at most 24:00"),
                 (0, [("A1", "2026-09-14 06:00", "2026-09-14 06:01", 1835),
                      ("A1", "2026-09-19 06:00", "2026-09-20 06:00", 1835),
                      ("A1", "2028-02-29 23:00", "2028-03-01 07:00", 1835),
                      ("B2", "1970-01-01 00:00", "1970-01-01 08:00", 1990),
                      ("B2", "2200-12-31 16:00", "2200-12-31 23:59", 1990)])])

        codes = [("lower.csv", "a1"), ("space.csv", "A 1"), ("double.csv", "A--1"), ("edge.csv", "-A1"),
                 ("trailing.csv", "A1-"), ("long.csv", "A" * 25), ("blank.csv", ""), ("accent.csv", "\u00c9LODIE")]
        bad_wages = ["17.5", "17", "17.355", "-17.35", "+17.35", "$17.35", "17,35", "1,017.35", "1000.00", "017.35",
                     ".35", "0.00", "", "1e1", "\u0661\u0667.35"]
        check("an employee code in lower case, with a space, a doubled or outer hyphen, an accent, over 24 "
              "characters or blank is refused, and one of exactly 24 characters loads; a wage with one or three "
              "decimal places or none, a sign, a dollar sign, a comma, past 999.99, a leading zero, no digit before "
              "the point, of 0.00, blank, in exponent form or in Arabic-Indic digits is refused, and so is a second "
              "wage for one employee, while 0.01 and 999.99 load",
              lambda: [logs(name, head + f"{raw},2026-09-14 06:00,2026-09-14 14:00,18.35\n") for name, raw in codes]
                      + [logs("max.csv", head + "ABCDEFGH-1234567-ABCDEFG,2026-09-14 06:00,2026-09-14 14:00,18.35\n")]
                      + [logs(f"wage{k}.csv", head + f'A1,2026-09-14 06:00,2026-09-14 14:00,"{raw}"\n')
                         for k, raw in enumerate(bad_wages)]
                      + [logs("raise.csv", small + "A1,2026-09-15 06:00,2026-09-15 14:00,18.50\n"),
                         logs("wages.csv", head + "A1,2026-09-14 06:00,2026-09-14 14:00,0.01\n"
                                                  "B2,2026-09-14 06:00,2026-09-14 14:00,999.99\n")],
              [(2, f"{name} row 2: employee {raw!r} is not an employee code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters") for name, raw in codes]
              + [(0, [("ABCDEFGH-1234567-ABCDEFG", "2026-09-14 06:00", "2026-09-14 14:00", 1835)])]
              + [(2, f"wage{k}.csv row 2: wage {raw!r} is not an hourly wage from 0.01 to 999.99 written like 17.35")
                 for k, raw in enumerate(bad_wages)]
              + [(2, "raise.csv row 4: wage 18.50 for A1 is not the 18.35 on row 2; one regular wage per employee"),
                 (0, [("A1", "2026-09-14 06:00", "2026-09-14 14:00", 1),
                      ("B2", "2026-09-14 06:00", "2026-09-14 14:00", 99999)])])

        wage_msg = "is not an hourly wage from 0.01 to 999.99 written like 17.35"
        check("rows are counted past blank lines and a line of spaces, and a stray quote is named by its own row, "
              "in a data row or in the header; rows with too many or too few fields, a line of commas, a tab, "
              "text after a closing quote, a quote left open, a field past the parser's limit, and a bad, renamed "
              "or reordered header, also one written as one quoted field or with a trailing comma, are refused, "
              "and a long value or header is cut short in the message, by one character as well as by many, "
              "while a value of exactly 40 characters shows whole",
              lambda: [logs("rows.csv", small + "\n   \n\nC3,2026-09-14 06:00,2026-09-14 14:00,17\n"),
                       logs("quote.csv", small + 'C3,"2026-09-14 06:00\nC4,x",y,z,w\n'),
                       logs("unclosed.csv", small + 'C3,2026-09-14 06:00,2026-09-14 14:00,"17.35\n'),
                       logs("wide.csv", small + "C3,2026-09-14 06:00,2026-09-14 14:00,17.35,extra\n"),
                       logs("narrow.csv", small + "C3,2026-09-14 06:00,2026-09-14 14:00\n"),
                       logs("commas.csv", small + ",,,\n"),
                       logs("tab.csv", small + "C3\t,2026-09-14 06:00,2026-09-14 14:00,17.35\n"),
                       logs("after.csv", small + 'C3,2026-09-14 06:00,2026-09-14 14:00,"17.35"x\n'),
                       logs("huge_field.csv", small + "C3,2026-09-14 06:00,2026-09-14 14:00," + "9" * 200000 + "\n"),
                       logs("header.csv", 'employee,starts,ends,"wage"x\nA1,2026-09-14 06:00,2026-09-14 14:00,1.00\n'),
                       logs("open_header.csv", '"employee,starts,ends,wage\nA1,2026-09-14 06:00,2026-09-14 14:00,'
                                               '1.00\n'),
                       logs("renamed.csv", "employee,start,end,wage\nA1,2026-09-14 06:00,2026-09-14 14:00,1.00\n"),
                       logs("reordered.csv", "employee,ends,starts,wage\nA1,2026-09-14 06:00,2026-09-14 14:00,1.00\n"),
                       logs("late_renamed.csv", "\nemployee,start,end,wage\nA1,2026-09-14 06:00,2026-09-14 14:00,"
                                                "1.00\n"),
                       logs("quoted_header.csv", '"employee,starts,ends,wage"\nA1,2026-09-14 06:00,2026-09-14 '
                                                 '14:00,1.00\n'),
                       logs("long_header.csv", "employee,starts,ends,wage" + "x" * 100 + "\n"),
                       logs("header_over.csv", "employee,starts,ends,wage" + "x" * 16 + "\n"),
                       logs("comma_header.csv", "employee,starts,ends,wage,\nA1,2026-09-14 06:00,2026-09-14 14:00,"
                                                "1.00\n"),
                       logs("long_value.csv", small + "C3,2026-09-14 06:00,2026-09-14 14:00," + "B" * 100 + "\n"),
                       logs("just_over.csv", small + "C3,2026-09-14 06:00,2026-09-14 14:00," + "C" * 41 + "\n"),
                       logs("forty.csv", small + "C3,2026-09-14 06:00,2026-09-14 14:00," + "D" * 40 + "\n")],
              [(2, f"rows.csv row 7: wage '17' {wage_msg}"),
               (2, "quote.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "unclosed.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "wide.csv row 4: has more fields than the header"),
               (2, "narrow.csv row 4: has fewer fields than the header"),
               (2, "commas.csv row 4: employee '' is not an employee code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "tab.csv row 4: employee 'C3\\t' is not an employee code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "after.csv row 4: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "huge_field.csv row 4: has a field over 131072 characters long"),
               (2, "header.csv row 1: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "open_header.csv row 1: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "renamed.csv row 1: expected columns 'employee,starts,ends,wage', got 'employee,start,end,wage'"),
               (2, "reordered.csv row 1: expected columns 'employee,starts,ends,wage', got 'employee,ends,starts,"
                   "wage'"),
               (2, "late_renamed.csv row 2: expected columns 'employee,starts,ends,wage', got "
                   "'employee,start,end,wage'"),
               (2, "quoted_header.csv row 1: expected columns 'employee,starts,ends,wage', got "
                   "'\"employee,starts,ends,wage\"'"),
               (2, "long_header.csv row 1: expected columns 'employee,starts,ends,wage', got 'employee,starts,"
                   "ends,wage" + "x" * 15 + "' and 85 more characters"),
               (2, "header_over.csv row 1: expected columns 'employee,starts,ends,wage', got 'employee,starts,"
                   "ends,wage" + "x" * 15 + "' and 1 more character"),
               (2, "comma_header.csv row 1: expected columns 'employee,starts,ends,wage', got "
                   "'employee,starts,ends,wage,'"),
               (2, "long_value.csv row 4: wage '" + "B" * 40 + f"' and 60 more characters {wage_msg}"),
               (2, "just_over.csv row 4: wage '" + "C" * 40 + f"' and 1 more character {wage_msg}"),
               (2, "forty.csv row 4: wage '" + "D" * 40 + f"' {wage_msg}")])

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

        far_down = "".join(f"F{n},2026-09-14 06:00,2026-09-14 14:00,18.35\n" for n in range(5000))
        check("an empty file, one of blank lines, one with only a header, also after a blank line, one that is "
              "not UTF-8 from its first line or only far down, or holds only part of a byte-order mark, a folder, "
              "a read that gives way before the header or partway through, and a line past 1000000 characters "
              "are refused, a line of exactly 1000000 passing; while a byte-order mark, blank lines before the "
              "header, spaces around unquoted fields, in the header too, and a line holding one empty quoted field, "
              "which is passed over like a blank one, load",
              lambda: [logs("empty.csv", ""),
                       logs("blank_only.csv", "\n  \n\n"),
                       logs("bare.csv", head),
                       logs("late_bare.csv", "\n" + head),
                       rejection(load, byte_file("latin1.csv", b"employee,starts,ends,wage\xc9\n")),
                       rejection(load, byte_file("late_latin1.csv", (head + far_down).encode("utf-8")
                                                 + b"CAF\xc9,2026-09-14 06:00,2026-09-14 14:00,18.35\n")),
                       rejection(load, byte_file("part_mark.csv", b"\xef\xbb")),
                       rejection(load, Path(tmp)),
                       rejection(dropped, ""),
                       rejection(dropped, small),
                       logs("long_line.csv", small + "," * 1000001 + "\n"),
                       rejection(capped, "x" * 1000001 + "\n"),
                       rejection(capped, "x" * 1000000 + "\r\n"),
                       logs("marked.csv", "\ufeff employee , starts , ends , wage \n A1 , 2026-09-14 06:00 , "
                                          "2026-09-14 14:00 , 18.35 \nB2,2026-09-14 07:00,2026-09-14 15:30,19.90\n"),
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
               (0, small_rows),
               (0, small_rows),
               (0, small_rows)])

        spread = head + "".join(f"S{n},2026-09-19 20:00,2026-09-20 20:00,999.99\n" for n in range(MOST_SHIFTS))
        check("a log of more than 20000 shifts is stopped as it is read, before a bad byte further down, while one "
              "of exactly 20000 loads",
              lambda: [rejection(load, byte_file("too_many.csv", (spread + f"S{MOST_SHIFTS},2026-09-14 06:00,"
                                                                  "2026-09-14 14:00,18.35\n" + far_down)
                                                 .encode("utf-8") + b"CAF\xc9,2026-09-14 06:00\n")),
                       sized(logs("at_limit.csv", spread))],
              [(2, f"too_many.csv row {MOST_SHIFTS + 2}: the log runs past 20000 shifts"),
               (0, MOST_SHIFTS)])

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

        other = csv_file("other.csv", SHIFTS_CSV.read_text(encoding="utf-8"))

        def cli(*argv):
            return rejection(settings, [str(a) for a in argv])

        def main_check():
            # main itself, on a file name the Windows codepage cannot hold. It
            # stops at the missing file, and the message has to come out as
            # UTF-8. The command line has no --test, so no suite is started.
            saved = sys.argv, sys.stdout, sys.stderr
            err = io.BytesIO()
            name = "\u6f22\u5b57.csv"
            sys.argv = ["run.py", "--shifts", str(Path(tmp) / name)]
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
              lambda: [cli("--shifts", Path(tmp) / "not_there.csv"),
                       cli("--shifts", Path(tmp) / "data*.csv"),
                       cli("--test", "--shifts", other),
                       cli("--test"),
                       cli(),
                       cli("--test", "--shifts", HERE / "data" / ".." / "data" / "shifts.csv"),
                       cli("--shifts", other),
                       utf8_check(),
                       main_check()],
              [(2, f"run.py: error: --shifts: '{Path(tmp) / 'not_there.csv'}' is not a file"),
               (2, f"run.py: error: --shifts: '{Path(tmp) / 'data*.csv'}' is not a file"),
               (2, "run.py: error: --test checks hand-computed answers for the sample file; "
                   "run it without --shifts"),
               (0, (True, SHIFTS_CSV)),
               (0, (False, SHIFTS_CSV)),
               (0, (True, HERE / "data" / ".." / "data" / "shifts.csv")),
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
    parser = argparse.ArgumentParser(prog="run.py", description="Run the weekly overtime queries against a shift "
                                                 "log, the sample by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--shifts", type=Path, default=None, help="path to an alternate shift log CSV")
    args = parser.parse_args(argv)
    path = args.shifts or SHIFTS_CSV
    try:
        found = path.is_file()
    except OSError:
        # Python 3.7 raises here for a name Windows cannot hold, such as one
        # with a wildcard in it.
        found = False
    if not found:
        if args.shifts is not None:
            parser.error(f"--shifts: '{path}' is not a file")
        parser.error(f"the sample file '{path}' is missing")
    if args.test and path.resolve() != SHIFTS_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample file; run it without --shifts")
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
