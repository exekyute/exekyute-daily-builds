"""Load a parts list and a daily usage log into SQLite and run the reorder-point queries.

Usage:
    python run.py                                        run every query in sql/
    python run.py --test                                 run the assertion suite
    python run.py --parts parts.csv --usage usage.csv    load a different parts list and log
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
PARTS_CSV = HERE / "data" / "parts.csv"
USAGE_CSV = HERE / "data" / "usage.csv"
SQL_DIR = HERE / "sql"
PART_COLUMNS = ["part", "lead_days"]
USAGE_COLUMNS = ["day", "part", "units"]
CODE = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")
CODE_LENGTH = 24
FIRST_DAY, LAST_DAY = datetime.date(1970, 1, 1), datetime.date(2200, 12, 31)
# A part is used at most 999 units a day, over a log of at most 1000 days,
# with a lead time of at most 90 days. The queries square the usage and
# multiply the spread by the lead time and by z x z x 10000, 54289 at the 99
# percent level; with these limits no product passes 1.3 x 10**18, well
# inside SQLite's 64-bit integers, so every step stays exact and none turns
# into a float.
MOST_UNITS = 999
MOST_DAYS = 1000
MOST_LEAD_DAYS = 90
MOST_PARTS = 1000
MOST_ROWS = 100_000
# A line of the file may hold at most this many characters. A real row holds
# a few dozen.
LINE_CAP = 1_000_000
# A query that runs past this many thousand SQLite steps is stopped. The
# sample takes under a hundred, and the costliest logs found within the
# limits above take about a quarter of it, on SQLite 3.31, 3.34 and 3.50
# alike, so only a query that would run away reaches it.
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
    # No field of these files runs across lines, so a quote left open is
    # caught on its own row and nothing is held past the end of a line.
    # strict, because the lenient parser folds text that follows a closing
    # quote back into the field and hands over a garbled row without a word.
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


def opened(path):
    path = Path(path)
    try:
        folder = path.is_dir()
    except OSError:
        # Python 3.7 raises here for a name Windows cannot hold.
        folder = False
    if folder:
        fail_file(path, "is a folder, not a file")
    try:
        return open(path, encoding="utf-8", newline="")
    except OSError as err:
        fail_file(path, err.strerror or "cannot be read")


def code(path, row_num, raw):
    # Parts are matched exactly between the two files, so a code is held to
    # one plain form: capital letters and digits, joined by single hyphens.
    # One typed another way would be a different part.
    if len(raw) > CODE_LENGTH or not CODE.fullmatch(raw):
        fail(path, row_num, f"part {shown(raw)} is not a part code: capital letters and digits, "
                            f"joined by single hyphens, at most {CODE_LENGTH} characters")
    return raw


def lead_days_of(path, row_num, raw):
    # Whole days, with no sign, no leading zero and no fraction.
    if not re.fullmatch(r"[1-9][0-9]?", raw) or int(raw) > MOST_LEAD_DAYS:
        fail(path, row_num, f"lead_days {shown(raw)} is not a whole number of days from 1 to {MOST_LEAD_DAYS}, "
                            "written like 7")
    return int(raw)


def day_of(path, row_num, raw):
    # One form, so the queries can compare days as text and count them apart
    # with julianday.
    match = re.fullmatch(r"([0-9]{4})-([0-9]{2})-([0-9]{2})", raw)
    day = None
    if match:
        try:
            day = datetime.date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            day = None
    if day is None or not FIRST_DAY <= day <= LAST_DAY:
        fail(path, row_num, f"day {shown(raw)} is not a date written like 2026-01-31, "
                            f"from {FIRST_DAY} to {LAST_DAY}")
    return day


def units_of(path, row_num, raw):
    # Whole units used that day, with no sign, no leading zero and no
    # fraction. A part put back on the shelf is not negative usage.
    if not re.fullmatch(r"0|[1-9][0-9]{0,2}", raw):
        fail(path, row_num, f"units {shown(raw)} is not a whole number of units from 0 to {MOST_UNITS}, "
                            "written like 4")
    return int(raw)


def load_parts(path):
    rows, seen = [], set()
    with opened(path) as handle:
        lines, header_line = open_csv(path, handle, PART_COLUMNS)
        for i, row in records(path, lines, PART_COLUMNS):
            part = code(path, i, row["part"])
            lead_days = lead_days_of(path, i, row["lead_days"])
            if part in seen:
                fail(path, i, f"{part} appears twice; one row per part")
            seen.add(part)
            rows.append((part, lead_days))
            if len(rows) > MOST_PARTS:
                fail(path, i, f"the list runs past {MOST_PARTS} parts")
    if not rows:
        fail(path, header_line, "no data rows after the header")
    return rows


def load_usage(path, parts, parts_path):
    known = {part for part, _ in parts}
    rows, seen, days = [], set(), {}
    with opened(path) as handle:
        lines, header_line = open_csv(path, handle, USAGE_COLUMNS)
        for i, row in records(path, lines, USAGE_COLUMNS):
            day = day_of(path, i, row["day"])
            part = code(path, i, row["part"])
            if part not in known:
                fail(path, i, f"{part} is not in {Path(parts_path).name}, so it has no lead time")
            units = units_of(path, i, row["units"])
            if (part, day) in seen:
                fail(path, i, f"{part} appears twice for {day}; one row per part and day, "
                              "with the units added together")
            seen.add((part, day))
            days.setdefault(part, set()).add(day)
            rows.append((day.isoformat(), part, units))
            # The file is read a line at a time, so a log far past the limit
            # is never read to the end.
            if len(rows) > MOST_ROWS:
                fail(path, i, f"the log runs past {MOST_ROWS} rows")
    if not rows:
        fail(path, header_line, "no data rows after the header")
    first = min(min(have) for have in days.values())
    last = max(max(have) for have in days.values())
    span = (last - first).days + 1
    if span > MOST_DAYS:
        fail_file(path, f"the log runs from {first} to {last}, {span} days, more than the {MOST_DAYS} it may cover")
    if span < 2:
        fail_file(path, f"the log covers only {first}; a standard deviation needs at least two days")
    # Every part has a row for every day, so a day nothing was used is a 0
    # the averages and the spread count, and every part's stretches start
    # on the same first day.
    for part, _ in parts:
        have = days.get(part, set())
        if len(have) < span:
            missing = next(day for day in (first + datetime.timedelta(days=k) for k in range(span))
                           if day not in have)
            fail_file(path, f"{part} has no row for {missing}; every part needs a row for every day from "
                            f"{first} to {last}, with 0 on a day none was used")
    return rows


def new_db(parts, usage):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE parts (part TEXT PRIMARY KEY, lead_days INTEGER NOT NULL)")
    db.execute("CREATE TABLE usage (day TEXT NOT NULL, part TEXT NOT NULL, units INTEGER NOT NULL, "
               "PRIMARY KEY (part, day))")
    db.executemany("INSERT INTO parts VALUES (?, ?)", parts)
    db.executemany("INSERT INTO usage VALUES (?, ?, ?)", usage)
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

    check("the log runs from 2026-01-01 to 2026-04-30, 120 days for 8 parts on 960 rows, 13221 units in all, "
          "with 69 rows where a part was not used",
          lambda: q(db, "01-log-shape.sql"),
          [("2026-01-01", "2026-04-30", 120, 8, 960, 13221, 69)])

    check("reordering at the average lead-time demand runs out in 77 of 161 cycles, 48 percent, and in at least "
          "half of them for four of the eight parts",
          lambda: q(db, "02-average-rule.sql"),
          [("BATTERY-AA", 3, 27, 40, 19, 48),
           ("DUCT-TAPE-2IN", 6, 12, 20, 11, 55),
           ("FILTER-20X25", 10, 37, 12, 4, 33),
           ("FUSE-15A", 14, 16, 8, 5, 63),
           ("GLOVE-NITRILE-L", 5, 121, 24, 12, 50),
           ("LED-TUBE-4FT", 12, 70, 10, 3, 30),
           ("SHOP-TOWEL", 7, 415, 17, 9, 53),
           ("ZIP-TIE-8IN", 4, 20, 30, 14, 47),
           ("all parts", None, None, 161, 77, 48)])

    check("safety stock at z = 1.65 comes from the exact spread through whole-number square roots, and "
          "FILTER-20X25's average of 3.65 and lead-time demand of 36.5 both round half up",
          lambda: q(db, "03-reorder-point.sql"),
          [("BATTERY-AA", 3, "9.1", "3.0", 27, 9, 36),
           ("DUCT-TAPE-2IN", 6, "2.0", "1.3", 12, 6, 18),
           ("FILTER-20X25", 10, "3.7", "2.1", 37, 11, 48),
           ("FUSE-15A", 14, "1.1", "1.0", 16, 7, 23),
           ("GLOVE-NITRILE-L", 5, "24.1", "6.1", 121, 23, 144),
           ("LED-TUBE-4FT", 12, "5.8", "2.4", 70, 14, 84),
           ("SHOP-TOWEL", 7, "59.2", "14.4", 415, 64, 479),
           ("ZIP-TIE-8IN", 4, "5.1", "2.1", 20, 7, 27)])

    check("with safety stock the same cycles run out 6 times instead of 77, and the units asked for at an empty "
          "shelf fall from 642 to 21; GLOVE-NITRILE-L's first cycle uses exactly its 144 and does not run out",
          lambda: q(db, "04-rules-side-by-side.sql"),
          [("BATTERY-AA", 40, 27, 19, 100, 36, 2, 5),
           ("DUCT-TAPE-2IN", 20, 12, 11, 31, 18, 0, 0),
           ("FILTER-20X25", 12, 37, 4, 24, 48, 1, 6),
           ("FUSE-15A", 8, 16, 5, 12, 23, 0, 0),
           ("GLOVE-NITRILE-L", 24, 121, 12, 144, 144, 1, 4),
           ("LED-TUBE-4FT", 10, 70, 3, 28, 84, 1, 5),
           ("SHOP-TOWEL", 17, 415, 9, 254, 479, 0, 0),
           ("ZIP-TIE-8IN", 30, 20, 14, 49, 27, 1, 1),
           ("all parts", 161, None, 77, 642, None, 6, 21)])

    check("holding 110, 141 and 198 units of safety stock across the parts cuts the run-outs from 77 to 15, 6 "
          "and 1 at 90, 95 and 99 percent",
          lambda: q(db, "05-service-levels.sql"),
          [(50, "0.00", 0, 161, 77, 48),
           (90, "1.28", 110, 161, 15, 9),
           (95, "1.65", 141, 161, 6, 4),
           (99, "2.33", 198, 161, 1, 1)])

    def agree(conn):
        # The reports share their numbers: 02's reorder points are 03's
        # lead-time demand and 04's average rule, 03's reorder points are
        # 04's safety rule, 04's cycles and average run-outs are 02's, every
        # level of 05 replays the same cycles, and 05's rows at 50 and 95
        # percent are the totals of 02 and 04 with the safety stock of 03.
        r02, r03, r04, r05 = (q(conn, name) for name in ("02-average-rule.sql", "03-reorder-point.sql",
                                                          "04-rules-side-by-side.sql", "05-service-levels.sql"))
        return [[(r[0], r[1], r[2]) for r in r02[:-1]] == [(r[0], r[1], r[4]) for r in r03],
                [(r[0], r[2], r[5]) for r in r04[:-1]] == [(r[0], r[4], r[6]) for r in r03],
                [(r[0], r[3], r[4]) for r in r02] == [(r[0], r[1], r[3]) for r in r04],
                [r[3] for r in r05] == [r02[-1][3]] * 4,
                r05[0][2:] == (0,) + r02[-1][3:],
                r05[2][2:5] == (sum(r[5] for r in r03), r04[-1][1], r04[-1][6])]

    def reversed_log():
        # The sample again, stored in the opposite order in tables with no
        # key, so nothing hands the rows back in day or part order unless a
        # query sorts them.
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE parts (part TEXT NOT NULL, lead_days INTEGER NOT NULL)")
        conn.execute("CREATE TABLE usage (day TEXT NOT NULL, part TEXT NOT NULL, units INTEGER NOT NULL)")
        parts = load_parts(PARTS_CSV)
        conn.executemany("INSERT INTO parts VALUES (?, ?)", list(reversed(parts)))
        conn.executemany("INSERT INTO usage VALUES (?, ?, ?)", list(reversed(load_usage(USAGE_CSV, parts,
                                                                                         PARTS_CSV))))
        return [q(conn, name) == q(db, name) for name in
                ("01-log-shape.sql", "02-average-rule.sql", "03-reorder-point.sql", "04-rules-side-by-side.sql",
                 "05-service-levels.sql")]

    check("the five reports agree with each other wherever they share a number, and the sample stored in the "
          "opposite order, in tables with no key, gives the same five reports",
          lambda: [agree(db), reversed_log()],
          [[True] * 6, [True] * 5])

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
          "rows each prints and the first and last of them, the total lines leaving blank the columns that have "
          "no total; and a query file that fails, has no query result, is not UTF-8 or is gone by the time it "
          "is read, or a folder named like one, stops them with a one-line message",
          lambda: [reports(), broken_reports()],
          [[("=== 01-log-shape.sql ===",
             "first_day   last_day    days  parts  usage_rows  units_used  idle_rows",
             "----------  ----------  ----  -----  ----------  ----------  ---------", 1,
             "2026-01-01  2026-04-30  120   8      960         13221       69",
             "2026-01-01  2026-04-30  120   8      960         13221       69"),
            ("=== 02-average-rule.sql ===",
             "part             lead_days  reorder_point  cycles  ran_out  ran_out_pct",
             "---------------  ---------  -------------  ------  -------  -----------", 9,
             "BATTERY-AA       3          27             40      19       48",
             "all parts                                  161     77       48"),
            ("=== 03-reorder-point.sql ===",
             "part             lead_days  avg_daily  sd_daily  lead_demand  safety_stock  reorder_point",
             "---------------  ---------  ---------  --------  -----------  ------------  -------------", 8,
             "BATTERY-AA       3          9.1        3.0       27           9             36",
             "ZIP-TIE-8IN      4          5.1        2.1       20           7             27"),
            ("=== 04-rules-side-by-side.sql ===",
             "part             cycles  average_point  average_ran_out  average_units_short  safety_point  "
             "safety_ran_out  safety_units_short",
             "---------------  ------  -------------  ---------------  -------------------  ------------  "
             "--------------  ------------------", 9,
             "BATTERY-AA       40      27             19               100                  36            "
             "2               5",
             "all parts        161                    77               642                                "
             "6               21"),
            ("=== 05-service-levels.sql ===",
             "service_pct  z     safety_stock  cycles  ran_out  ran_out_pct",
             "-----------  ----  ------------  ------  -------  -----------", 4,
             "50           0.00  0             161     77       48",
             "99           2.33  198           161     1        1")],
           [(2, '01-broken.sql: did not run: near "SELEC": syntax error'),
            (2, "01-empty.sql: did not run: has no query result to print"),
            (2, "01-ansi.sql: is not UTF-8 text"),
            (2, "01-folder.sql: is a folder, not a query file"),
            (2, "01-gone.sql: No such file or directory")]])

    # Logs built for cases the sample does not reach on its own. None of them
    # goes through the loader.
    def built(series, first=datetime.date(2027, 12, 30)):
        parts = [(part, lead) for part, (lead, _) in series.items()]
        usage = [((first + datetime.timedelta(days=k)).isoformat(), part, units)
                 for part, (_, used) in series.items() for k, units in enumerate(used)]
        return new_db(parts, usage)

    def printed(conn, name):
        # The rows of a report as print_table lays them out, below the rule.
        headers, rows = run_query(conn, SQL_DIR / name)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            print_table(headers, rows)
        return out.getvalue().splitlines()[2:]

    # Four days across a year end. EXACT's days use exactly its reorder
    # point under each rule, and one day uses one more than the average;
    # HALF's average and lead-time demand land on exact halves, and its first
    # stretch uses exactly the 3 that 2.5 rounds up to, so rounding half
    # down would call it a run-out; SQUARE's safety stock is exactly 33, where
    # 1.65 x 20.0 is a whole number, and ABOVE's squared is 841.03, just past
    # 29 x 29, so it rounds up to 30, where 27224 in place of 27225 would
    # give 29;
    # SWING's Newton steps swing between 3 and 4; LONG's lead time is longer
    # than the log; FLAT and IDLE have no spread; and LEFTOVER's heavy last
    # day falls in a stretch the end of the log cuts short.
    edges = built({"EXACT": (1, [1, 1, 1, 2]), "HALF": (2, [1, 2, 0, 2]), "SQUARE": (1, [40, 40, 0, 40]),
                   "ABOVE": (1, [0, 8, 37, 0]), "SWING": (1, [0, 0, 4, 4]), "LONG": (5, [3, 1, 4, 1]),
                   "FLAT": (2, [3, 3, 3, 3]), "IDLE": (3, [0, 0, 0, 0]), "LEFTOVER": (3, [0, 0, 0, 12])})
    check("a stretch that uses exactly the reorder point does not run out and one unit more does; averages and "
          "lead-time demand on an exact half round up; a safety stock that is exactly a whole number is not "
          "rounded up, and one whose square lands just past a perfect square is; Newton steps that swing "
          "between two values stop; a part with no spread gets no safety stock; a lead time longer than the log "
          "gives no cycles and a blank share, in the printed report too; and a stretch cut short by the end of "
          "the log is left out, across a year end",
          lambda: [q(edges, "01-log-shape.sql"), q(edges, "02-average-rule.sql"), q(edges, "03-reorder-point.sql"),
                   q(edges, "04-rules-side-by-side.sql"), q(edges, "05-service-levels.sql"),
                   printed(edges, "02-average-rule.sql")[6]],
          [[("2027-12-30", "2028-01-02", 4, 9, 36, 216, 13)],
           [("ABOVE", 1, 11, 4, 1, 25), ("EXACT", 1, 1, 4, 1, 25), ("FLAT", 2, 6, 2, 0, 0), ("HALF", 2, 3, 2, 0, 0),
            ("IDLE", 3, 0, 1, 0, 0), ("LEFTOVER", 3, 9, 1, 0, 0), ("LONG", 5, 11, 0, 0, None),
            ("SQUARE", 1, 30, 4, 3, 75), ("SWING", 1, 2, 4, 2, 50), ("all parts", None, None, 22, 7, 32)],
           [("ABOVE", 1, "11.3", "17.6", 11, 30, 41),
            ("EXACT", 1, "1.3", "0.5", 1, 1, 2), ("FLAT", 2, "3.0", "0.0", 6, 0, 6),
            ("HALF", 2, "1.3", "1.0", 3, 3, 6), ("IDLE", 3, "0.0", "0.0", 0, 0, 0),
            ("LEFTOVER", 3, "3.0", "6.0", 9, 18, 27), ("LONG", 5, "2.3", "1.5", 11, 6, 17),
            ("SQUARE", 1, "30.0", "20.0", 30, 33, 63), ("SWING", 1, "2.0", "2.3", 2, 4, 6)],
           [("ABOVE", 4, 11, 1, 26, 41, 0, 0),
            ("EXACT", 4, 1, 1, 1, 2, 0, 0), ("FLAT", 2, 6, 0, 0, 6, 0, 0), ("HALF", 2, 3, 0, 0, 6, 0, 0),
            ("IDLE", 1, 0, 0, 0, 0, 0, 0), ("LEFTOVER", 1, 9, 0, 0, 27, 0, 0), ("LONG", 0, 11, 0, 0, 17, 0, 0),
            ("SQUARE", 4, 30, 3, 30, 63, 0, 0), ("SWING", 4, 2, 2, 4, 6, 0, 0),
            ("all parts", 22, None, 7, 61, None, 0, 0)],
           [(50, "0.00", 0, 22, 7, 32), (90, "1.28", 74, 22, 1, 5), (95, "1.65", 95, 22, 0, 0),
            (99, "2.33", 133, 22, 0, 0)],
           "LONG       5          11             0       0"])

    # Twenty days. BURST uses nothing but 20 units on one day, and DIP 5 a
    # day but for two days of nothing, both at a lead time of two. LATE uses
    # nothing for its one whole stretch of 11 days, then 100 a day for the 9
    # days the end of the log cuts short, more than either reorder point.
    burst = [0] * 9 + [20] + [0] * 10
    dip = [5] * 3 + [0] + [5] * 10 + [0] + [5] * 5
    late = [0] * 11 + [100] * 9
    skewed = built({"BURST": (2, burst), "DIP": (2, dip), "LATE": (11, late)})
    burst_alone = built({"BURST": (2, burst)})
    check("about half holds only when a stretch is as likely to run over the average as under it: a part used in "
          "one burst runs out in 1 of 10 cycles under the average rule and still 1 at every service level, "
          "shown on its own too, and one that dips now and then runs out in 8 of 10; and 900 units in a stretch "
          "the end of the log cuts short count against neither rule",
          lambda: [q(skewed, "02-average-rule.sql"), q(skewed, "03-reorder-point.sql"),
                   q(skewed, "04-rules-side-by-side.sql"), q(skewed, "05-service-levels.sql"),
                   q(burst_alone, "05-service-levels.sql")],
          [[("BURST", 2, 2, 10, 1, 10), ("DIP", 2, 9, 10, 8, 80), ("LATE", 11, 495, 1, 0, 0),
            ("all parts", None, None, 21, 9, 43)],
           [("BURST", 2, "1.0", "4.5", 2, 11, 13), ("DIP", 2, "4.5", "1.5", 9, 4, 13),
            ("LATE", 11, "45.0", "51.0", 495, 280, 775)],
           [("BURST", 10, 2, 1, 18, 13, 1, 7), ("DIP", 10, 9, 8, 8, 13, 0, 0), ("LATE", 1, 495, 0, 0, 775, 0, 0),
            ("all parts", 21, None, 9, 26, None, 1, 7)],
           [(50, "0.00", 0, 21, 9, 43), (90, "1.28", 229, 21, 1, 5), (95, "1.65", 295, 21, 1, 5),
            (99, "2.33", 416, 21, 1, 5)],
           [(50, "0.00", 0, 10, 1, 10), (90, "1.28", 9, 10, 1, 10), (95, "1.65", 11, 10, 1, 10),
            (99, "2.33", 15, 10, 1, 10)]])

    # ONCE uses 4 units on the last of eight days at a lead time of one:
    # half a unit a day, and a standard deviation of the square root of 2.
    # SPARE uses one unit on the first of 400 days, a standard deviation of
    # exactly 0.05, where twenty times it squared is 1 and its root is 1.
    # TRACE uses one unit on the first of 50 days: twenty times its standard
    # deviation squared rounds down to 8, whose Newton steps swing between 2
    # and 3; stopping at 2 prints 0.1, where 3 would print 0.2.
    once = built({"ONCE": (1, [0] * 7 + [4])})
    spare = built({"SPARE": (7, [1] + [0] * 399)})
    trace = built({"TRACE": (1, [1] + [0] * 49)})
    check("a part used on one day in eight runs out in 1 of 8 cycles at 50 and 90 percent, a share of 12.5 that "
          "rounds up to 13, and not at 95 percent, where its one busy day uses exactly the reorder point of 4; "
          "a part used once in 400 days has a standard deviation of exactly 0.05, which prints as 0.1, and keeps "
          "one on the shelf; and one used once in 50 days prints 0.1, its Newton steps settling on the lower of "
          "the two values they swing between",
          lambda: [q(once, "02-average-rule.sql"), q(once, "03-reorder-point.sql"),
                   q(once, "04-rules-side-by-side.sql"), q(once, "05-service-levels.sql"),
                   q(spare, "02-average-rule.sql"), q(spare, "03-reorder-point.sql"),
                   q(spare, "05-service-levels.sql"), q(trace, "03-reorder-point.sql")],
          [[("ONCE", 1, 1, 8, 1, 13), ("all parts", None, None, 8, 1, 13)],
           [("ONCE", 1, "0.5", "1.4", 1, 3, 4)],
           [("ONCE", 8, 1, 1, 3, 4, 0, 0), ("all parts", 8, None, 1, 3, None, 0, 0)],
           [(50, "0.00", 0, 8, 1, 13), (90, "1.28", 2, 8, 1, 13), (95, "1.65", 3, 8, 0, 0), (99, "2.33", 4, 8, 0, 0)],
           [("SPARE", 7, 0, 57, 1, 2), ("all parts", None, None, 57, 1, 2)],
           [("SPARE", 7, "0.0", "0.1", 0, 1, 1)],
           [(50, "0.00", 0, 57, 1, 2), (90, "1.28", 1, 57, 0, 0), (95, "1.65", 1, 57, 0, 0),
            (99, "2.33", 1, 57, 0, 0)],
           [("TRACE", 1, "0.0", "0.1", 0, 1, 1)]])

    # One of the costliest logs found within the loader's limits: 1000 parts
    # over 100 days at a lead time of one day, each part using 0 and 999 on
    # alternate days. Then 100 parts over 1000 days at a lead time of 90, the
    # longest log and lead time with the widest spread the limits allow,
    # where the largest products are formed.
    def alternating(parts, days, lead):
        return built({f"P{p:04d}": (lead, [999 * ((p + d) % 2) for d in range(days)]) for p in range(parts)},
                     datetime.date(1970, 1, 1))

    costly = alternating(1000, 100, 1)
    largest = alternating(100, 1000, 90)

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

    names = ("01-log-shape.sql", "02-average-rule.sql", "03-reorder-point.sql", "04-rules-side-by-side.sql",
             "05-service-levels.sql")
    with tempfile.TemporaryDirectory() as tmp:
        check("1000 parts over 100 days and 100 parts over 1000 days, at the loader's limits, run through every "
              "query inside the step budget with their largest numbers exact, and a query that would run for "
              "ever is stopped by it",
              lambda: [[ends(costly, name) for name in names], [ends(largest, name) for name in names],
                       endless(tmp)],
              [[(1, ("1970-01-01", "1970-04-10", 100, 1000, 100000, 49950000, 50000),
                 ("1970-01-01", "1970-04-10", 100, 1000, 100000, 49950000, 50000)),
                (1001, ("P0000", 1, 500, 100, 50, 50), ("all parts", None, None, 100000, 50000, 50)),
                (1000, ("P0000", 1, "499.5", "502.0", 500, 829, 1329), ("P0999", 1, "499.5", "502.0", 500, 829, 1329)),
                (1001, ("P0000", 100, 500, 50, 24950, 1329, 0, 0), ("all parts", 100000, None, 50000, 24950000,
                                                                     None, 0, 0)),
                (4, (50, "0.00", 0, 100000, 50000, 50), (99, "2.33", 1170000, 100000, 0, 0))],
               [(1, ("1970-01-01", "1972-09-26", 1000, 100, 100000, 49950000, 50000),
                 ("1970-01-01", "1972-09-26", 1000, 100, 100000, 49950000, 50000)),
                (101, ("P0000", 90, 44955, 11, 0, 0), ("all parts", None, None, 1100, 0, 0)),
                (100, ("P0000", 90, "499.5", "499.7", 44955, 7823, 52778),
                 ("P0099", 90, "499.5", "499.7", 44955, 7823, 52778)),
                (101, ("P0000", 11, 44955, 0, 0, 52778, 0, 0), ("all parts", 1100, None, 0, 0, None, 0, 0)),
                (4, (50, "0.00", 0, 1100, 0, 0), (99, "2.33", 1104700, 1100, 0, 0))],
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

        parts_head = ",".join(PART_COLUMNS) + "\n"
        head = ",".join(USAGE_COLUMNS) + "\n"
        two_parts = csv_file("two_parts.csv", parts_head + "BOLT,3\nNUT,5\n")
        pair = [("BOLT", 3), ("NUT", 5)]
        small = head + "2026-03-01,BOLT,4\n2026-03-01,NUT,2\n2026-03-02,BOLT,6\n2026-03-02,NUT,0\n"

        def logs(name, content, parts=pair):
            return rejection(load_usage, csv_file(name, content), parts, two_parts)

        def lists(name, content):
            return rejection(load_parts, csv_file(name, content))

        def sized(result):
            code, loaded = result
            return (code, len(loaded)) if code == 0 else result

        check("the included bad log is refused for a part put back on the shelf written as usage of -2, and a "
              "part listed twice for one day is refused by name",
              lambda: [rejection(load_usage, HERE / "data" / "invalid-usage.csv", load_parts(PARTS_CSV), PARTS_CSV),
                       logs("twice.csv", small + "2026-03-01,NUT,3\n")],
              [(2, "invalid-usage.csv row 412: units '-2' is not a whole number of units from 0 to 999, "
                   "written like 4"),
               (2, "twice.csv row 6: NUT appears twice for 2026-03-01; one row per part and day, "
                   "with the units added together")])

        bad_units = ["-2", "1000", "4.0", "+4", "04", "-0", "", "1e2", "four", "\u0664"]
        bad_leads = ["0", "91", "7.5", "+7", "07", "-7", "", "\uff17", "1\u0660"]
        check("units written as a minus, past 999, with a fraction, a plus sign or a leading zero, as -0, blank, "
              "in exponent form, as a word or in Arabic-Indic digits are refused, as are lead times of 0 or past "
              "90 days, with a fraction, a sign or a leading zero, blank, or in fullwidth or Arabic-Indic digits, "
              "even after a plain first digit, and a part listed twice; while 0 and 999 units and lead times of "
              "1 and 90 days load",
              lambda: [logs(f"units{k}.csv", small + f'2026-03-03,BOLT,"{raw}"\n') for k, raw in enumerate(bad_units)]
                      + [lists(f"lead{k}.csv", parts_head + f'BOLT,"{raw}"\n') for k, raw in enumerate(bad_leads)]
                      + [lists("repeat.csv", parts_head + "BOLT,3\nNUT,5\nBOLT,4\n"),
                         logs("unit_bounds.csv", head + "2026-03-01,BOLT,0\n2026-03-01,NUT,999\n"
                                                        "2026-03-02,BOLT,999\n2026-03-02,NUT,0\n"),
                         lists("lead_bounds.csv", parts_head + "BOLT,1\nNUT,90\n")],
              [(2, f"units{k}.csv row 6: units {raw!r} is not a whole number of units from 0 to 999, written like 4")
               for k, raw in enumerate(bad_units)]
              + [(2, f"lead{k}.csv row 2: lead_days {raw!r} is not a whole number of days from 1 to 90, "
                     "written like 7") for k, raw in enumerate(bad_leads)]
              + [(2, "repeat.csv row 4: BOLT appears twice; one row per part"),
                 (0, [("2026-03-01", "BOLT", 0), ("2026-03-01", "NUT", 999), ("2026-03-02", "BOLT", 999),
                      ("2026-03-02", "NUT", 0)]),
                 (0, [("BOLT", 1), ("NUT", 90)])])

        codes = [("lower.csv", "bolt"), ("space.csv", "BOLT 2"), ("double.csv", "BOLT--2"), ("edge.csv", "-BOLT"),
                 ("trailing.csv", "BOLT-"), ("long.csv", "A" * 25), ("blank.csv", ""), ("accent.csv", "CAF\u00c9"),
                 ("fullwidth.csv", "\uff22\uff2f\uff2c\uff34")]
        bad_days = ["2026-02-30", "2026-13-01", "2026-3-01", "26-03-01", "2026/03/01", "20260301", "1969-12-31",
                    "2201-01-01", "0000-01-01", "", "2026-03-01T00:00", "\uff12\uff10\uff12\uff16-03-01"]
        check("a part code in lower case, with a space, a doubled or outer hyphen, an accent or fullwidth letters, "
              "over 24 characters or blank is refused in either file, and one of exactly 24 characters with two "
              "hyphens loads; a day that is not on the calendar, written in another form, before 1970 or after "
              "2200, blank, with a time or in fullwidth digits is refused, while the first and last days allowed "
              "load",
              lambda: [lists(name, parts_head + f"{raw},3\n") for name, raw in codes]
                      + [logs("u" + name, head + f"2026-03-01,{raw},1\n") for name, raw in codes]
                      + [lists("max.csv", parts_head + "ABCDEFGH-1234567-ABCDEFG,3\n")]
                      + [logs(f"day{k}.csv", head + f"{raw},BOLT,1\n") for k, raw in enumerate(bad_days)]
                      + [logs("earliest.csv", head + "1970-01-01,BOLT,1\n1970-01-02,BOLT,2\n", [("BOLT", 3)]),
                         logs("latest.csv", head + "2200-12-30,BOLT,1\n2200-12-31,BOLT,2\n", [("BOLT", 3)])],
              [(2, f"{name} row 2: part {raw!r} is not a part code: capital letters and digits, joined by single "
                   "hyphens, at most 24 characters") for name, raw in codes]
              + [(2, f"u{name} row 2: part {raw!r} is not a part code: capital letters and digits, joined by single "
                     "hyphens, at most 24 characters") for name, raw in codes]
              + [(0, [("ABCDEFGH-1234567-ABCDEFG", 3)])]
              + [(2, f"day{k}.csv row 2: day {raw!r} is not a date written like 2026-01-31, from 1970-01-01 to "
                     "2200-12-31") for k, raw in enumerate(bad_days)]
              + [(0, [("1970-01-01", "BOLT", 1), ("1970-01-02", "BOLT", 2)]),
                 (0, [("2200-12-30", "BOLT", 1), ("2200-12-31", "BOLT", 2)])])

        # 1000 days from 2026-01-01 end on 2028-09-26.
        def run_of(days, parts=("BOLT",)):
            start = datetime.date(2026, 1, 1)
            return head + "".join(f"{start + datetime.timedelta(days=k)},{part},1\n"
                                  for k in range(days) for part in parts)

        many = [(f"P{p:04d}", 1) for p in range(1000)]
        check("a part missing from the parts list, a day missing from the middle of one part's log, a part in "
              "the list with no rows at all, a log of one day and one over 1000 days are refused, as is a parts "
              "list past 1000 parts; while a log of exactly 1000 days, and 1000 parts over two days, load",
              lambda: [logs("unknown.csv", small + "2026-03-01,WASHER,1\n"),
                       logs("gap.csv", head + "2026-03-01,BOLT,1\n2026-03-01,NUT,1\n2026-03-03,BOLT,1\n"
                                              "2026-03-02,NUT,1\n2026-03-03,NUT,1\n"),
                       logs("no_rows.csv", head + "2026-03-01,BOLT,1\n2026-03-02,BOLT,1\n"),
                       logs("one_day.csv", head + "2026-03-01,BOLT,1\n2026-03-01,NUT,1\n"),
                       logs("too_long.csv", run_of(1001), [("BOLT", 3)]),
                       lists("too_many.csv", parts_head + "".join(f"P{p:04d},1\n" for p in range(1001))),
                       sized(logs("longest.csv", run_of(1000), [("BOLT", 3)])),
                       sized(lists("most.csv", parts_head + "".join(f"P{p:04d},1\n" for p in range(1000)))),
                       sized(logs("most_usage.csv", run_of(2, [p for p, _ in many]), many))],
              [(2, "unknown.csv row 6: WASHER is not in two_parts.csv, so it has no lead time"),
               (2, "gap.csv: BOLT has no row for 2026-03-02; every part needs a row for every day from 2026-03-01 "
                   "to 2026-03-03, with 0 on a day none was used"),
               (2, "no_rows.csv: NUT has no row for 2026-03-01; every part needs a row for every day from "
                   "2026-03-01 to 2026-03-02, with 0 on a day none was used"),
               (2, "one_day.csv: the log covers only 2026-03-01; a standard deviation needs at least two days"),
               (2, "too_long.csv: the log runs from 2026-01-01 to 2028-09-27, 1001 days, more than the 1000 it "
                   "may cover"),
               (2, "too_many.csv row 1002: the list runs past 1000 parts"),
               (0, 1000),
               (0, 1000),
               (0, 2000)])

        check("rows are counted past blank lines and a line of spaces, and a stray quote is named by its own row, "
              "in a data row or in the header; rows with too many or too few fields, a line of commas, a tab, "
              "text after a closing quote, a quote left open, a field past the parser's limit, and a bad, renamed "
              "or reordered header in either file, also one written as one quoted field or with a trailing comma, "
              "are refused, and a long value or header is cut short in the message, by one character as well as "
              "by many, while a value of exactly 40 characters shows whole",
              lambda: [logs("rows.csv", small + "\n   \n\n2026-03-03,BOLT,4.5\n"),
                       logs("quote.csv", small + '2026-03-03,"BOLT,4\n2026-03-03,NUT",4\n'),
                       logs("unclosed.csv", small + '2026-03-03,"BOLT,4\n'),
                       logs("wide.csv", small + "2026-03-03,BOLT,4,extra\n"),
                       logs("narrow.csv", small + "2026-03-03,BOLT\n"),
                       logs("commas.csv", small + ",,\n"),
                       logs("tab.csv", small + "2026-03-03,BOLT\t,4\n"),
                       logs("after.csv", small + '2026-03-03,"BOLT"x,4\n'),
                       logs("huge_field.csv", small + "2026-03-03,BOLT," + "9" * 200000 + "\n"),
                       logs("header.csv", 'day,"part"x,units\n2026-03-01,BOLT,4\n'),
                       logs("open_header.csv", '"day,part,units\n2026-03-01,BOLT,4\n'),
                       logs("renamed.csv", "day,part,used\n2026-03-01,BOLT,4\n"),
                       logs("reordered.csv", "part,day,units\nBOLT,2026-03-01,4\n"),
                       logs("late_renamed.csv", "\nday,part,used\n2026-03-01,BOLT,4\n"),
                       logs("quoted_header.csv", '"day,part,units"\n"2026-03-01,BOLT,4"\n'),
                       logs("comma_header.csv", "day,part,units,\n2026-03-01,BOLT,4\n"),
                       lists("parts_header.csv", 'part,"lead_days"x\nBOLT,3\n'),
                       lists("parts_renamed.csv", "part,lead_time\nBOLT,3\n"),
                       lists("parts_reordered.csv", "lead_days,part\n3,BOLT\n"),
                       logs("long_header.csv", "day,part,units" + "x" * 100 + "\n2026-03-01,BOLT,4\n"),
                       logs("long_value.csv", small + "2026-03-03,BOLT," + "B" * 100 + "\n"),
                       logs("just_over.csv", small + "2026-03-03,BOLT," + "C" * 41 + "\n"),
                       logs("just_fits.csv", small + "2026-03-03,BOLT," + "D" * 40 + "\n")],
              [(2, "rows.csv row 9: units '4.5' is not a whole number of units from 0 to 999, written like 4"),
               (2, "quote.csv row 6: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "unclosed.csv row 6: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "wide.csv row 6: has more fields than the header"),
               (2, "narrow.csv row 6: has fewer fields than the header"),
               (2, "commas.csv row 6: day '' is not a date written like 2026-01-31, from 1970-01-01 to 2200-12-31"),
               (2, "tab.csv row 6: part 'BOLT\\t' is not a part code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "after.csv row 6: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "huge_field.csv row 6: has a field over 131072 characters long"),
               (2, "header.csv row 1: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "open_header.csv row 1: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "renamed.csv row 1: expected columns 'day,part,units', got 'day,part,used'"),
               (2, "reordered.csv row 1: expected columns 'day,part,units', got 'part,day,units'"),
               (2, "late_renamed.csv row 2: expected columns 'day,part,units', got 'day,part,used'"),
               (2, "quoted_header.csv row 1: expected columns 'day,part,units', got '\"day,part,units\"'"),
               (2, "comma_header.csv row 1: expected columns 'day,part,units', got 'day,part,units,'"),
               (2, "parts_header.csv row 1: cannot be parsed (',' expected after '\"'); a quoted field has to end "
                   "at its closing quote"),
               (2, "parts_renamed.csv row 1: expected columns 'part,lead_days', got 'part,lead_time'"),
               (2, "parts_reordered.csv row 1: expected columns 'part,lead_days', got 'lead_days,part'"),
               (2, "long_header.csv row 1: expected columns 'day,part,units', got 'day,part,units"
                   + "x" * 26 + "' and 74 more characters"),
               (2, "long_value.csv row 6: units '" + "B" * 40 + "' and 60 more characters is not a whole number "
                   "of units from 0 to 999, written like 4"),
               (2, "just_over.csv row 6: units '" + "C" * 40 + "' and 1 more character is not a whole number "
                   "of units from 0 to 999, written like 4"),
               (2, "just_fits.csv row 6: units '" + "D" * 40 + "' is not a whole number of units from 0 to 999, "
                   "written like 4")])

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
            lines, _ = open_csv(path, Dropped(text), USAGE_COLUMNS)
            return list(records(path, lines, USAGE_COLUMNS))

        def capped(text):
            return len(list(read_lines(Path(tmp) / "cap.csv", io.StringIO(text))))

        # 20000 good rows for the two parts, one day apart from 1970-01-01, so
        # the bad byte after them is the first thing wrong.
        far_down = "".join(f"{datetime.date(1970, 1, 1) + datetime.timedelta(days=k)},{part},1\n"
                           for k in range(10000) for part in ("BOLT", "NUT"))
        check("an empty file, one of blank lines, one with only a header, also after a blank line, in either "
              "file, one that is not UTF-8 from its first line or only far down, or holds only part of a "
              "byte-order mark, a folder, a read that gives way before the header or partway through, and a line "
              "past 1000000 characters are refused, a line of exactly 1000000 passing; while a byte-order mark, "
              "blank lines before the header, spaces around unquoted fields, in the header too, and a line "
              "holding one empty quoted field, which is passed over like a blank one, load",
              lambda: [logs("empty.csv", ""),
                       logs("blank_only.csv", "\n  \n\n"),
                       logs("bare.csv", head),
                       logs("late_bare.csv", "\n" + head),
                       lists("bare_parts.csv", parts_head),
                       lists("empty_parts.csv", ""),
                       rejection(load_usage, byte_file("latin1.csv", b"day,part,units\xc9\n2026-03-01,BOLT,1\n"),
                                 pair, two_parts),
                       rejection(load_usage, byte_file("late_latin1.csv", (head + far_down).encode("utf-8")
                                                       + b"2026-03-03,CAF\xc9,1\n"), pair, two_parts),
                       rejection(load_parts, byte_file("part_mark.csv", b"\xef\xbb")),
                       rejection(load_parts, Path(tmp)),
                       rejection(dropped, ""),
                       rejection(dropped, small),
                       logs("long_line.csv", small + "," * 1000001 + "\n"),
                       rejection(capped, "x" * 1000001 + "\n"),
                       rejection(capped, "x" * 1000000 + "\r\n"),
                       logs("marked.csv", "\ufeff day , part , units \n 2026-03-01 , BOLT , 4 \n"
                                          "2026-03-01,NUT,2\n2026-03-02,BOLT,6\n2026-03-02,NUT,0\n"),
                       logs("leading.csv", "\n  \n" + small),
                       logs("quoted_blank.csv", small + '""\n')],
              [(2, "empty.csv: is empty"),
               (2, "blank_only.csv: is empty"),
               (2, "bare.csv row 1: no data rows after the header"),
               (2, "late_bare.csv row 2: no data rows after the header"),
               (2, "bare_parts.csv row 1: no data rows after the header"),
               (2, "empty_parts.csv: is empty"),
               (2, "latin1.csv: is not UTF-8 text"),
               (2, "late_latin1.csv: is not UTF-8 text"),
               (2, "part_mark.csv: is not UTF-8 text"),
               (2, f"{Path(tmp).name}: is a folder, not a file"),
               (2, "dropped.csv: Input/output error"),
               (2, "dropped.csv: Input/output error"),
               (2, "long_line.csv row 6: runs past 1000000 characters on one line"),
               (2, "cap.csv row 1: runs past 1000000 characters on one line"),
               (0, 1),
               (0, [("2026-03-01", "BOLT", 4), ("2026-03-01", "NUT", 2), ("2026-03-02", "BOLT", 6),
                    ("2026-03-02", "NUT", 0)]),
               (0, [("2026-03-01", "BOLT", 4), ("2026-03-01", "NUT", 2), ("2026-03-02", "BOLT", 6),
                    ("2026-03-02", "NUT", 0)]),
               (0, [("2026-03-01", "BOLT", 4), ("2026-03-01", "NUT", 2), ("2026-03-02", "BOLT", 6),
                    ("2026-03-02", "NUT", 0)])])

        # 1000 parts over 101 days is 101000 rows; over 100 days it is exactly
        # the limit.
        grid = [(f"P{n:05d}", 1) for n in range(1000)]
        rows_of = (lambda days: head + "".join(f"{datetime.date(2026, 1, 1) + datetime.timedelta(days=k)},{part},1\n"
                                               for k in range(days) for part, _ in grid))
        check("a log of more than 100000 rows is stopped as it is read, before a bad byte further down, while "
              "one of exactly 100000 loads",
              lambda: [rejection(load_usage, byte_file("too_many_rows.csv", (rows_of(101) + far_down).encode("utf-8")
                                                       + b"2026-03-03,CAF\xc9,1\n"), grid, two_parts),
                       sized(rejection(load_usage, csv_file("at_limit.csv", rows_of(100)), grid, two_parts))],
              [(2, f"too_many_rows.csv row {MOST_ROWS + 2}: the log runs past 100000 rows"),
               (0, MOST_ROWS)])

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

        other_parts = csv_file("other_parts.csv", PARTS_CSV.read_text(encoding="utf-8"))
        other_usage = csv_file("other_usage.csv", USAGE_CSV.read_text(encoding="utf-8"))

        def cli(*argv):
            return rejection(settings, [str(a) for a in argv])

        def main_check():
            # main itself, on a file name the Windows codepage cannot hold. It
            # stops at the missing file, and the message has to come out as
            # UTF-8. The command line has no --test, so no suite is started.
            saved = sys.argv, sys.stdout, sys.stderr
            err = io.BytesIO()
            name = "\u6f22\u5b57.csv"
            sys.argv = ["run.py", "--parts", str(PARTS_CSV), "--usage", str(Path(tmp) / name)]
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

        def main_message(*argv):
            # main itself on files of your own, where the usage log names a
            # part the parts list lacks: the message has to name the parts
            # file given on the command line. It stops while loading, before
            # main picks between the suite and the reports.
            saved = sys.argv, sys.stdout, sys.stderr
            err = io.BytesIO()
            wrapped_out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="\n")
            wrapped_err = io.TextIOWrapper(err, encoding="cp1252", newline="\n")
            sys.argv = ["run.py"] + [str(a) for a in argv]
            sys.stdout, sys.stderr = wrapped_out, wrapped_err
            try:
                main()
                return "main returned"
            except SystemExit as stop:
                wrapped_err.flush()
                return stop.code, err.getvalue().decode("utf-8").strip()
            finally:
                sys.argv, sys.stdout, sys.stderr = saved

        stray = csv_file("stray_usage.csv", head + "2026-03-01,WASHER,1\n")
        spelled = HERE / "data" / ".." / "data"
        check("on the command line, a file that is not there, a name with a wildcard in it, one of the two files "
              "given without the other, and a test run on any file other than the samples are refused, while the "
              "samples are picked by default or spelled another way and files of your own are taken; output and "
              "messages are written as UTF-8 by the helper that sets them up, which leaves alone a stream it "
              "cannot switch, and main's own messages come out as UTF-8 and name the parts file given on the "
              "command line",
              lambda: [cli("--parts", Path(tmp) / "not_there.csv", "--usage", other_usage),
                       cli("--parts", other_parts, "--usage", Path(tmp) / "data*.csv"),
                       cli("--usage", other_usage),
                       cli("--parts", other_parts),
                       cli("--test", "--parts", other_parts, "--usage", other_usage),
                       cli("--test", "--parts", PARTS_CSV, "--usage", other_usage),
                       cli("--test"),
                       cli(),
                       cli("--test", "--parts", spelled / "parts.csv", "--usage", spelled / "usage.csv"),
                       cli("--parts", other_parts, "--usage", other_usage),
                       utf8_check(),
                       main_check(),
                       main_message("--parts", other_parts, "--usage", stray)],
              [(2, f"run.py: error: --parts: '{Path(tmp) / 'not_there.csv'}' is not a file"),
               (2, f"run.py: error: --usage: '{Path(tmp) / 'data*.csv'}' is not a file"),
               (2, "run.py: error: --parts and --usage go together: give both, or neither for the samples"),
               (2, "run.py: error: --parts and --usage go together: give both, or neither for the samples"),
               (2, "run.py: error: --test checks hand-computed answers for the sample files; "
                   "run it without --parts and --usage"),
               (2, "run.py: error: --test checks hand-computed answers for the sample files; "
                   "run it without --parts and --usage"),
               (0, (True, PARTS_CSV, USAGE_CSV)),
               (0, (False, PARTS_CSV, USAGE_CSV)),
               (0, (True, spelled / "parts.csv", spelled / "usage.csv")),
               (0, (False, other_parts, other_usage)),
               (("\u6f22\u5b57.csv\n", "\u6f22\u5b57.csv\n"), "\u6f22\u5b57.csv\n"),
               (2, True),
               (2, "stray_usage.csv row 2: WASHER is not in other_parts.csv, so it has no lead time")])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def settings(argv):
    # Reads the command line and settles which files to load. It never runs
    # a query or the suite, so the suite can check it directly.
    parser = argparse.ArgumentParser(prog="run.py", description="Run the reorder-point queries against a parts "
                                                 "list and a daily usage log, the samples by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--parts", type=Path, default=None, help="path to a parts CSV: part,lead_days")
    parser.add_argument("--usage", type=Path, default=None, help="path to a daily usage CSV: day,part,units")
    args = parser.parse_args(argv)
    # The two files are read together: a usage log is checked against the
    # parts list beside it, so one of your own is never paired with a sample.
    if (args.parts is None) != (args.usage is None):
        parser.error("--parts and --usage go together: give both, or neither for the samples")
    paths = []
    for flag, given, sample in (("--parts", args.parts, PARTS_CSV), ("--usage", args.usage, USAGE_CSV)):
        path = given or sample
        try:
            found = path.is_file()
        except OSError:
            # Python 3.7 raises here for a name Windows cannot hold, such as
            # one with a wildcard in it.
            found = False
        if not found:
            if given is not None:
                parser.error(f"{flag}: '{path}' is not a file")
            parser.error(f"the sample file '{path}' is missing")
        paths.append(path)
    if args.test and (paths[0].resolve() != PARTS_CSV.resolve() or paths[1].resolve() != USAGE_CSV.resolve()):
        parser.error("--test checks hand-computed answers for the sample files; run it without --parts and --usage")
    return args.test, paths[0], paths[1]


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
    test, parts_path, usage_path = settings(sys.argv[1:])
    parts = load_parts(parts_path)
    db = new_db(parts, load_usage(usage_path, parts, parts_path))
    if test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
