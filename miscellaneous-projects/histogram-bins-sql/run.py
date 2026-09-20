"""Load a log of delivery times into SQLite and run the histogram queries.

Usage:
    python run.py                          run every query in sql/
    python run.py --test                   run the assertion suite
    python run.py --deliveries log.csv     load a different log
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
DELIVERIES_CSV = HERE / "data" / "deliveries.csv"
SQL_DIR = HERE / "sql"
COLUMNS = ["delivery", "minutes"]
CODE = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")
CODE_LENGTH = 24
# A reading is a whole number of minutes early or late, at most a day either
# way. That keeps the bins the queries build to a few hundred at the
# narrowest width they use, and every count and product well inside SQLite's
# 64-bit integers.
LIMIT_MINUTES = 1440
MOST_READINGS = 100_000
# A line of the file may hold at most this many characters. A real row holds
# a dozen or so.
LINE_CAP = 1_000_000
# A query that runs past this many thousand SQLite steps is stopped. The
# sample takes a handful, and the costliest log the limits above allow takes
# under a tenth of it, on SQLite 3.31 and 3.34 as much as on 3.50, so only
# a query that would run away reaches it.
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
    # Deliveries are named in one plain form: capital letters and digits,
    # joined by single hyphens. A code typed another way would count as a
    # second delivery.
    if len(raw) > CODE_LENGTH or not CODE.fullmatch(raw):
        fail(path, row_num, f"delivery {shown(raw)} is not a delivery code: capital letters and digits, "
                            f"joined by single hyphens, at most {CODE_LENGTH} characters")
    return raw


def minutes_of(path, row_num, raw):
    # Whole minutes, early as a minus and late as a plus, with no plus sign,
    # no leading zero and no fraction.
    match = re.fullmatch(r"0|-?[1-9][0-9]{0,3}", raw)
    if not match or abs(int(raw)) > LIMIT_MINUTES:
        fail(path, row_num, f"minutes {shown(raw)} is not a whole number of minutes from {-LIMIT_MINUTES} "
                            f"to {LIMIT_MINUTES}, written like -15 or 20")
    return int(raw)


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
            delivery = code(path, i, row["delivery"])
            minutes = minutes_of(path, i, row["minutes"])
            if delivery in seen:
                fail(path, i, f"{delivery} appears twice; one row per delivery")
            seen.add(delivery)
            rows.append((delivery, minutes))
            # The file is read a line at a time, so a log far past the limit
            # is never read to the end.
            if len(rows) > MOST_READINGS:
                fail(path, i, f"the log runs past {MOST_READINGS} readings")
    if not rows:
        fail(path, header_line, "no data rows after the header")
    return rows


def new_db(rows):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE deliveries (delivery TEXT PRIMARY KEY, minutes INTEGER NOT NULL)")
    db.executemany("INSERT INTO deliveries VALUES (?, ?)", rows)
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
            raise sqlite3.OperationalError(f"stopped after {STEP_BUDGET * 1000} steps")
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

    check("126 deliveries run from 34 minutes early to 181 late, over 23 bins, 12 of them empty",
          lambda: q(db, "01-log-shape.sql"),
          [(126, -34, 181, 23, 11, 12)])

    check("dividing toward zero puts 86 deliveries in the bin at zero, and the report skips every empty bin",
          lambda: q(db, "02-naive-histogram.sql"),
          [(-3, "-30 to -21", 1), (-2, "-20 to -11", 4), (-1, "-10 to -1", 9), (0, "0 to 9", 86),
           (1, "10 to 19", 15), (2, "20 to 29", 5), (3, "30 to 39", 3), (7, "70 to 79", 1),
           (9, "90 to 99", 1), (18, "180 to 189", 1)])

    check("every bin prints, empty ones included, with a running count, a share to a tenth of a percent and a bar",
          lambda: q(db, "03-histogram.sql"),
          [("-40 to -31", 1, 1, "0.8", "#"),
           ("-30 to -21", 2, 3, "1.6", "##"),
           ("-20 to -11", 8, 11, "6.3", "########"),
           ("-10 to -1", 39, 50, "31.0", "#" * 39),
           ("0 to 9", 50, 100, "39.7", "#" * 50),
           ("10 to 19", 15, 115, "11.9", "#" * 15),
           ("20 to 29", 5, 120, "4.0", "#####"),
           ("30 to 39", 3, 123, "2.4", "###"),
           ("40 to 49", 0, 123, "0.0", ""),
           ("50 to 59", 0, 123, "0.0", ""),
           ("60 to 69", 0, 123, "0.0", ""),
           ("70 to 79", 1, 124, "0.8", "#"),
           ("80 to 89", 0, 124, "0.0", ""),
           ("90 to 99", 1, 125, "0.8", "#"),
           ("100 to 109", 0, 125, "0.0", ""),
           ("110 to 119", 0, 125, "0.0", ""),
           ("120 to 129", 0, 125, "0.0", ""),
           ("130 to 139", 0, 125, "0.0", ""),
           ("140 to 149", 0, 125, "0.0", ""),
           ("150 to 159", 0, 125, "0.0", ""),
           ("160 to 169", 0, 125, "0.0", ""),
           ("170 to 179", 0, 125, "0.0", ""),
           ("180 to 189", 1, 126, "0.8", "#")])

    check("bin by bin, the quick query is 36 too many at zero, 30 short in the bin below it, and silent on "
          "13 bins",
          lambda: q(db, "04-naive-against-true.sql"),
          [("-40 to -31", 1, "", "the quick query leaves this bin out"),
           ("-30 to -21", 2, "1", "1 missing, cut toward zero"),
           ("-20 to -11", 8, "4", "4 missing, cut toward zero"),
           ("-10 to -1", 39, "9", "30 missing, cut toward zero"),
           ("0 to 9", 50, "86", "36 too many, cut toward zero"),
           ("10 to 19", 15, "15", "the same in both"),
           ("20 to 29", 5, "5", "the same in both"),
           ("30 to 39", 3, "3", "the same in both"),
           ("40 to 49", 0, "", "empty, and the quick query leaves it out"),
           ("50 to 59", 0, "", "empty, and the quick query leaves it out"),
           ("60 to 69", 0, "", "empty, and the quick query leaves it out"),
           ("70 to 79", 1, "1", "the same in both"),
           ("80 to 89", 0, "", "empty, and the quick query leaves it out"),
           ("90 to 99", 1, "1", "the same in both"),
           ("100 to 109", 0, "", "empty, and the quick query leaves it out"),
           ("110 to 119", 0, "", "empty, and the quick query leaves it out"),
           ("120 to 129", 0, "", "empty, and the quick query leaves it out"),
           ("130 to 139", 0, "", "empty, and the quick query leaves it out"),
           ("140 to 149", 0, "", "empty, and the quick query leaves it out"),
           ("150 to 159", 0, "", "empty, and the quick query leaves it out"),
           ("160 to 169", 0, "", "empty, and the quick query leaves it out"),
           ("170 to 179", 0, "", "empty, and the quick query leaves it out"),
           ("180 to 189", 1, "1", "the same in both")])

    check("at five minutes a bin the log breaks into 44 bins with a 16-bin gap, at thirty it fits in 9 with the "
          "gap down to 2",
          lambda: q(db, "05-bin-widths.sql"),
          [(5, 44, 18, 26, 16, "0 to 4", 32),
           (10, 23, 11, 12, 8, "0 to 9", 50),
           (30, 9, 7, 2, 2, "0 to 29", 70)])

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
            print_table(["span", "deliveries"], [("0 to 9", 4), ("10 to 19", None)])
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
             "deliveries  earliest  latest  bins  bins_with_readings  empty_bins",
             "----------  --------  ------  ----  ------------------  ----------", 1,
             "126         -34       181     23    11                  12"),
            ("=== 02-naive-histogram.sql ===", "bin  span        deliveries",
             "---  ----------  ----------", 10, "-3   -30 to -21  1"),
            ("=== 03-histogram.sql ===", "span        deliveries  running  share_pct  bar",
             "----------  ----------  -------  ---------  " + "-" * 50, 23,
             "-40 to -31  1           1        0.8        #"),
            ("=== 04-naive-against-true.sql ===", "span        deliveries  naive  note",
             "----------  ----------  -----  " + "-" * 40, 23,
             "-40 to -31  1                  the quick query leaves this bin out"),
            ("=== 05-bin-widths.sql ===",
             "bin_width  bins  bins_with_readings  empty_bins  longest_empty_run  fullest_bin  fullest_count",
             "---------  ----  ------------------  ----------  -----------------  -----------  -------------", 3,
             "5          44    18                  26          16                 0 to 4       32")],
           [(2, '01-broken.sql: did not run: near "SELEC": syntax error'),
            (2, "01-empty.sql: did not run: has no query result to print"),
            (2, "01-ansi.sql: is not UTF-8 text"),
            (2, "01-folder.sql: is a folder, not a query file"),
            (2, "01-gone.sql: No such file or directory")],
           ["span      deliveries", "--------  ----------", "0 to 9    4", "10 to 19"]])

    # Logs built for cases the sample does not reach on its own. None of them
    # goes through the loader.
    def log(values):
        return new_db([(f"D{n:05d}", minutes) for n, minutes in enumerate(values, 1)])

    edges = log([-20, -11, -10, -1, 0, 1, 9, 10])
    check("a reading on a bin's own boundary belongs to the bin that starts there, and -1 belongs to the bin at "
          "-10, where dividing toward zero would put it at 0",
          lambda: [q(edges, "01-log-shape.sql"), q(edges, "02-naive-histogram.sql"), q(edges, "03-histogram.sql"),
                   q(edges, "04-naive-against-true.sql")],
          [[(8, -20, 10, 4, 4, 0)],
           [(-2, "-20 to -11", 1), (-1, "-10 to -1", 2), (0, "0 to 9", 4), (1, "10 to 19", 1)],
           [("-20 to -11", 2, 2, "25.0", "#" * 33),
            ("-10 to -1", 2, 4, "25.0", "#" * 33),
            ("0 to 9", 3, 7, "37.5", "#" * 50),
            ("10 to 19", 1, 8, "12.5", "#" * 16)],
           [("-20 to -11", 2, "1", "1 missing, cut toward zero"),
            ("-10 to -1", 2, "2", "the same in both"),
            ("0 to 9", 3, "4", "1 too many, cut toward zero"),
            ("10 to 19", 1, "1", "the same in both")]])

    early = log([-35, -25, -12])
    check("on a log where every van ran early, the bin the quick query invents above them all still prints, "
          "with nothing of its own in it, and every width still reaches the reading nearest zero",
          lambda: [q(early, "01-log-shape.sql"), q(early, "02-naive-histogram.sql"),
                   q(early, "04-naive-against-true.sql"), q(early, "05-bin-widths.sql")],
          [[(3, -35, -12, 3, 3, 0)],
           [(-3, "-30 to -21", 1), (-2, "-20 to -11", 1), (-1, "-10 to -1", 1)],
           [("-40 to -31", 1, "", "the quick query leaves this bin out"),
            ("-30 to -21", 1, "1", "the same in both"),
            ("-20 to -11", 1, "1", "the same in both"),
            ("-10 to -1", 0, "1", "1 too many, cut toward zero")],
           [(5, 5, 3, 2, 1, "-35 to -31", 1),
            (10, 3, 3, 0, 0, "-40 to -31", 1),
            (30, 2, 2, 0, 0, "-30 to -1", 2)]])

    one = log([7])
    check("a log of one reading gives one bin at 100 percent, and no width finds a gap in it",
          lambda: [q(one, "01-log-shape.sql"), q(one, "03-histogram.sql"), q(one, "05-bin-widths.sql")],
          [[(1, 7, 7, 1, 1, 0)],
           [("0 to 9", 1, 1, "100.0", "#" * 50)],
           [(5, 1, 1, 0, 0, "5 to 9", 1), (10, 1, 1, 0, 0, "0 to 9", 1), (30, 1, 1, 0, 0, "0 to 29", 1)]])

    # 17 readings against 1983 make shares of 0.85 and 99.15 percent, both
    # exact halves in tenths. As a float 0.85 sits just under the half, so
    # printf or ROUND on it gives 0.8 on SQLite 3.50, and rounding half to
    # even gives 0.8 as well; 3.31 and 3.34 happen to give 0.9, and 99.15
    # sits just above the half and rounds up on every version. The bin of 17
    # is too small for a bar of its own against 1983, and still shows one.
    halves = log([0] * 17 + [20] * 1983)
    check("a share that lands on an exact half rounds up in whole numbers, where a float would leave it to "
          "the SQLite version, and the smaller bin still shows a bar",
          lambda: q(halves, "03-histogram.sql"),
          [("0 to 9", 17, 17, "0.9", "#"),
           ("10 to 19", 0, 17, "0.0", ""),
           ("20 to 29", 1983, 2000, "99.2", "#" * 50)])

    # The widest log the loader allows: 100000 readings spread across the
    # whole range, which is 289 bins at ten minutes and 577 at five.
    widest = new_db([(f"D{n:06d}", -1440 + (n * 7) % 2881) for n in range(MOST_READINGS)])

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
        check("100000 readings across the whole range run through every query inside the step budget, and a "
              "query that would run for ever is stopped by it",
              lambda: [ends(widest, "01-log-shape.sql"), ends(widest, "02-naive-histogram.sql"),
                       ends(widest, "03-histogram.sql"), ends(widest, "04-naive-against-true.sql"),
                       ends(widest, "05-bin-widths.sql"), endless(tmp)],
              [(1, (100000, -1440, 1440, 289, 289, 0), (100000, -1440, 1440, 289, 289, 0)),
               (289, (-144, "-1440 to -1431", 35), (144, "1440 to 1449", 35)),
               (289, ("-1440 to -1431", 347, 347, "0.3", "#" * 49), ("1440 to 1449", 35, 100000, "0.0", "#####")),
               (289, ("-1440 to -1431", 347, "35", "312 missing, cut toward zero"),
                ("1440 to 1449", 35, "35", "the same in both")),
               (3, (5, 577, 577, 0, 0, "-1435 to -1431", 174), (30, 97, 97, 0, 0, "-1410 to -1381", 1042)),
               "stopped after 100000000 steps"])

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
        small = head + "D0001,-5\nD0002,12\n"

        def logs(name, content):
            return rejection(load, csv_file(name, content))

        def sized(result):
            code, loaded = result
            return (code, len(loaded)) if code == 0 else result

        check("the included bad log is refused for a reading written with a fraction, and a delivery listed "
              "twice is refused by name",
              lambda: [rejection(load, HERE / "data" / "invalid-deliveries.csv"),
                       logs("twice.csv", small + "D0001,3\n")],
              [(2, "invalid-deliveries.csv row 61: minutes '12.5' is not a whole number of minutes from "
                   "-1440 to 1440, written like -15 or 20"),
               (2, "twice.csv row 4: D0001 appears twice; one row per delivery")])

        bad_minutes = ["12.5", "+5", "007", "-0", "1441", "-1441", "", "1e3", "--5", "five", "\u0661\u0660"]
        check("minutes written with a fraction, a plus sign, a leading zero, as -0, past a day either way, "
              "blank, in exponent form, with two minus signs, as a word or in Arabic-Indic digits are "
              "refused, while 0 and a full day either way load",
              lambda: [logs(f"minutes{k}.csv", head + f'D0001,"{raw}"\n') for k, raw in enumerate(bad_minutes)]
                      + [logs("range.csv", head + "D0001,-1440\nD0002,0\nD0003,1440\n")],
              [(2, f"minutes{k}.csv row 2: minutes {raw!r} is not a whole number of minutes from -1440 to 1440, "
                   "written like -15 or 20") for k, raw in enumerate(bad_minutes)]
              + [(0, [("D0001", -1440), ("D0002", 0), ("D0003", 1440)])])

        codes = [("lower.csv", "d1"), ("space.csv", "D 1"), ("double.csv", "D--1"), ("edge.csv", "-D1"),
                 ("trailing.csv", "D1-"), ("long.csv", "A" * 25), ("blank.csv", ""), ("accent.csv", "CAF\u00c9")]
        check("a delivery code in lower case, with a space, a doubled or outer hyphen, an accent, over 24 "
              "characters or blank is refused, and one of exactly 24 characters with two hyphens loads",
              lambda: [logs(name, head + f"{raw},5\n") for name, raw in codes]
                      + [logs("max.csv", head + "ABCDEFGH-1234567-ABCDEFG,5\n")],
              [(2, f"{name} row 2: delivery {raw!r} is not a delivery code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters") for name, raw in codes]
              + [(0, [("ABCDEFGH-1234567-ABCDEFG", 5)])])

        check("rows are counted past blank lines and a line of spaces, and a stray quote is named by its own row, "
              "in a data row or in the header; rows with too many or too few fields, a line of commas, a tab, "
              "text after a closing quote, a quote left open, a field past the parser's limit, and a bad, renamed "
              "or reordered header, also one written as one quoted field or with a trailing comma, are refused, "
              "and a long value or header is cut short in the message, by one character as well as by many",
              lambda: [logs("rows.csv", small + "\n   \n\nD0003,12.5\n"),
                       logs("quote.csv", small + 'D0003,"5\nD0004,6",7\n'),
                       logs("unclosed.csv", small + 'D0003,"5\n'),
                       logs("wide.csv", small + "D0003,5,extra\n"),
                       logs("narrow.csv", small + "D0003\n"),
                       logs("commas.csv", small + ",\n"),
                       logs("tab.csv", small + "D0003\t,5\n"),
                       logs("after.csv", small + 'D0003,"5"x\n'),
                       logs("huge_field.csv", small + "D0003," + "9" * 200000 + "\n"),
                       logs("header.csv", 'delivery,"minutes"x\nD0001,5\n'),
                       logs("open_header.csv", '"delivery,minutes\nD0001,5\n'),
                       logs("renamed.csv", "delivery,late\nD0001,5\n"),
                       logs("reordered.csv", "minutes,delivery\n5,D0001\n"),
                       logs("late_renamed.csv", "\ndelivery,late\nD0001,5\n"),
                       logs("quoted_header.csv", '"delivery,minutes"\n"D0001,5"\n'),
                       logs("long_header.csv", "delivery,minutes" + "x" * 100 + "\nD0001,5\n"),
                       logs("comma_header.csv", "delivery,minutes,\nD0001,5\n"),
                       logs("long_value.csv", small + "D0003," + "B" * 100 + "\n"),
                       logs("just_over.csv", small + "D0003," + "C" * 41 + "\n")],
              [(2, "rows.csv row 7: minutes '12.5' is not a whole number of minutes from -1440 to 1440, "
                   "written like -15 or 20"),
               (2, "quote.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "unclosed.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "wide.csv row 4: has more fields than the header"),
               (2, "narrow.csv row 4: has fewer fields than the header"),
               (2, "commas.csv row 4: delivery '' is not a delivery code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "tab.csv row 4: delivery 'D0003\\t' is not a delivery code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "after.csv row 4: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "huge_field.csv row 4: has a field over 131072 characters long"),
               (2, "header.csv row 1: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "open_header.csv row 1: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "renamed.csv row 1: expected columns 'delivery,minutes', got 'delivery,late'"),
               (2, "reordered.csv row 1: expected columns 'delivery,minutes', got 'minutes,delivery'"),
               (2, "late_renamed.csv row 2: expected columns 'delivery,minutes', got 'delivery,late'"),
               (2, "quoted_header.csv row 1: expected columns 'delivery,minutes', got '\"delivery,minutes\"'"),
               (2, "long_header.csv row 1: expected columns 'delivery,minutes', got 'delivery,minutes"
                   + "x" * 24 + "' and 76 more characters"),
               (2, "comma_header.csv row 1: expected columns 'delivery,minutes', got 'delivery,minutes,'"),
               (2, "long_value.csv row 4: minutes '" + "B" * 40 + "' and 60 more characters is not a whole number "
                   "of minutes from -1440 to 1440, written like -15 or 20"),
               (2, "just_over.csv row 4: minutes '" + "C" * 40 + "' and 1 more character is not a whole number "
                   "of minutes from -1440 to 1440, written like -15 or 20")])

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

        far_down = "".join(f"D{n:06d},5\n" for n in range(20000))
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
                       rejection(load, byte_file("latin1.csv", b"delivery,minutes\xc9\nD0001,5\n")),
                       rejection(load, byte_file("late_latin1.csv", (head + far_down).encode("utf-8")
                                                 + b"CAF\xc9,5\n")),
                       rejection(load, byte_file("part_mark.csv", b"\xef\xbb")),
                       rejection(load, Path(tmp)),
                       rejection(dropped, ""),
                       rejection(dropped, small),
                       logs("long_line.csv", small + "," * 1000001 + "\n"),
                       rejection(capped, "x" * 1000001 + "\n"),
                       rejection(capped, "x" * 1000000 + "\r\n"),
                       logs("marked.csv", "\ufeff delivery , minutes \n D0001 , -5 \nD0002,12\n"),
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
               (0, [("D0001", -5), ("D0002", 12)]),
               (0, [("D0001", -5), ("D0002", 12)]),
               (0, [("D0001", -5), ("D0002", 12)])])

        spread = head + "".join(f"D{n:06d},{-1440 + (n * 7) % 2881}\n" for n in range(MOST_READINGS))
        check("a log of more than 100000 readings is stopped as it is read, before a bad byte further down, "
              "while one of exactly 100000 loads",
              lambda: [rejection(load, byte_file("too_many.csv", (spread + f"D{MOST_READINGS:06d},5\n"
                                                                  + far_down).encode("utf-8")
                                                 + b"CAF\xc9,5\n")),
                       sized(logs("at_limit.csv", spread))],
              [(2, f"too_many.csv row {MOST_READINGS + 2}: the log runs past 100000 readings"),
               (0, MOST_READINGS)])

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

        other = csv_file("other.csv", DELIVERIES_CSV.read_text(encoding="utf-8"))

        def cli(*argv):
            return rejection(settings, [str(a) for a in argv])

        def main_check():
            # main itself, on a file name the Windows codepage cannot hold. It
            # stops at the missing file, and the message has to come out as
            # UTF-8. The command line has no --test, so no suite is started.
            saved = sys.argv, sys.stdout, sys.stderr
            err = io.BytesIO()
            name = "\u6f22\u5b57.csv"
            sys.argv = ["run.py", "--deliveries", str(Path(tmp) / name)]
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
              lambda: [cli("--deliveries", Path(tmp) / "not_there.csv"),
                       cli("--deliveries", Path(tmp) / "data*.csv"),
                       cli("--test", "--deliveries", other),
                       cli("--test"),
                       cli(),
                       cli("--test", "--deliveries", HERE / "data" / ".." / "data" / "deliveries.csv"),
                       cli("--deliveries", other),
                       utf8_check(),
                       main_check()],
              [(2, f"run.py: error: --deliveries: '{Path(tmp) / 'not_there.csv'}' is not a file"),
               (2, f"run.py: error: --deliveries: '{Path(tmp) / 'data*.csv'}' is not a file"),
               (2, "run.py: error: --test checks hand-computed answers for the sample file; "
                   "run it without --deliveries"),
               (0, (True, DELIVERIES_CSV)),
               (0, (False, DELIVERIES_CSV)),
               (0, (True, HERE / "data" / ".." / "data" / "deliveries.csv")),
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
    parser = argparse.ArgumentParser(prog="run.py", description="Run the histogram queries against a log of "
                                                 "delivery times, the sample by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--deliveries", type=Path, default=None, help="path to an alternate delivery log CSV")
    args = parser.parse_args(argv)
    path = args.deliveries or DELIVERIES_CSV
    try:
        found = path.is_file()
    except OSError:
        # Python 3.7 raises here for a name Windows cannot hold, such as one
        # with a wildcard in it.
        found = False
    if not found:
        if args.deliveries is not None:
            parser.error(f"--deliveries: '{path}' is not a file")
        parser.error(f"the sample file '{path}' is missing")
    if args.test and path.resolve() != DELIVERIES_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample file; run it without --deliveries")
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
