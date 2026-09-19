"""Load a monthly recurring revenue log into SQLite and run the bridge queries.

Usage:
    python run.py                  run every query in sql/
    python run.py --test           run the assertion suite
    python run.py --mrr log.csv    load a different log
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
MRR_CSV = HERE / "data" / "mrr.csv"
SQL_DIR = HERE / "sql"
MRR_COLUMNS = ["month", "customer", "mrr"]
CODE = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")
CODE_LENGTH = 24
FIRST_YEAR, LAST_YEAR = 1970, 2200
# The queries give every customer a row in every month of the log, so the
# customers times the months is the number of rows they work through. With
# at most 999999.99 a row, no total passes 10**13 cents, which keeps every
# sum, and every product the rates take, a whole number well inside SQLite's
# 64-bit integers, and far enough inside that printing cents as a decimal
# cannot land on the wrong cent.
MOST_CELLS = 100_000
# A query that runs past this many thousand SQLite steps is stopped. The
# sample takes a few dozen. The costliest log found within the limits above
# takes about a quarter of it on SQLite 3.50 and about a third on 3.31 and
# 3.34, so only a query that would run away reaches it.
STEP_BUDGET = 100_000
# A line of the file may hold at most this many characters. A real row
# holds a few dozen.
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
    return repr(raw) if len(raw) <= 40 else f"{raw[:40]!r} and {len(raw) - 40} more characters"


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


def month_of(path, row_num, raw):
    # The queries match months as text, so a month is held to one form.
    match = re.fullmatch(r"([0-9]{4})-([0-9]{2})", raw)
    if not match or not FIRST_YEAR <= int(match.group(1)) <= LAST_YEAR or not 1 <= int(match.group(2)) <= 12:
        fail(path, row_num, f"month {shown(raw)} is not a month written like 2025-04, "
                            f"from {FIRST_YEAR}-01 to {LAST_YEAR}-12")
    return raw


def month_no(month):
    # The same count of months the queries use: years times twelve, plus the
    # month counted from zero.
    return int(month[:4]) * 12 + int(month[5:]) - 1


def code(path, row_num, raw):
    # Customers are matched exactly, so a code is held to one plain form:
    # capital letters and digits, joined by single hyphens. One typed in
    # lower case, or with a stray character, would otherwise be a new
    # customer, and the real one would read as churned.
    if len(raw) > CODE_LENGTH or not CODE.fullmatch(raw):
        fail(path, row_num, f"customer {shown(raw)} is not a customer code: capital letters and digits, "
                            f"joined by single hyphens, at most {CODE_LENGTH} characters")
    return raw


def cents(path, row_num, raw):
    # Two decimal places, no sign, no thousands separator, no currency mark.
    match = re.fullmatch(r"(0|[1-9][0-9]{0,5})\.([0-9]{2})", raw)
    if not match:
        fail(path, row_num, f"mrr {shown(raw)} is not an amount from 0.01 to 999999.99 written like 249.00")
    value = int(match.group(1)) * 100 + int(match.group(2))
    if value == 0:
        fail(path, row_num, "mrr is 0.00; a month the customer paid nothing for is left out of the log")
    return value


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
        lines, header_line = open_csv(path, handle, MRR_COLUMNS)
        for i, row in records(path, lines, MRR_COLUMNS):
            month = month_of(path, i, row["month"])
            customer = code(path, i, row["customer"])
            amount = cents(path, i, row["mrr"])
            if (month, customer) in seen:
                fail(path, i, f"{customer} appears twice for {month}; one row per customer and month, "
                              "with the amounts added together")
            seen.add((month, customer))
            rows.append((month, customer, amount))
            # Each row is a different customer and month, so a log past the
            # limit in rows is past it in customer-months too. The file is read
            # a line at a time, so a log far past the limit is never read to
            # the end.
            if len(rows) > MOST_CELLS:
                fail(path, i, f"the log runs past {MOST_CELLS} rows, and each row is a customer-month "
                              "the queries fill in")
    if not rows:
        fail(path, header_line, "no data rows after the header")
    numbers = [month_no(month) for month, _, _ in rows]
    first, last = min(numbers), max(numbers)
    if first == last:
        fail_file(path, f"the log covers only {rows[0][0]}; the bridge compares each month with "
                        "the one before, so it needs at least two")
    customers = len({customer for _, customer, _ in rows})
    span = last - first + 1
    if customers * span > MOST_CELLS:
        fail_file(path, f"{customers} customers over {span} months make {customers * span} customer-months, "
                        f"more than the {MOST_CELLS} the queries fill in")
    return rows


def new_db(rows):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE mrr (month TEXT NOT NULL, customer TEXT NOT NULL, mrr_cents INTEGER NOT NULL, "
               "PRIMARY KEY (month, customer))")
    db.executemany("INSERT INTO mrr VALUES (?, ?, ?)", rows)
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

    check("the log runs from 2025-01 to 2025-12 with 14 customers on 107 rows, and 12 months are skipped "
          "between a customer's first payment and their last",
          lambda: q(db, "01-log-shape.sql"),
          [("2025-01", "2025-12", 12, 14, 107, 12)])

    check("LAG over the rows never sees a churn or a return: the movements leave money unexplained in eight "
          "of eleven months, and in June a churn and a return cancel so the gap reads zero",
          lambda: q(db, "02-lag-by-row.sql"),
          [("2025-02", "1790.25", "115.00", "0.00", "0.00", "1905.25", "0.00"),
           ("2025-03", "1905.25", "199.00", "0.00", "-30.00", "1915.25", "-159.00"),
           ("2025-04", "1915.25", "0.00", "0.00", "0.00", "1725.75", "-189.50"),
           ("2025-05", "1725.75", "0.00", "0.00", "0.00", "1610.75", "-115.00"),
           ("2025-06", "1610.75", "139.00", "0.00", "0.00", "1749.75", "0.00"),
           ("2025-07", "1749.75", "0.00", "50.00", "0.00", "1700.75", "-99.00"),
           ("2025-08", "1700.75", "0.00", "100.00", "0.00", "1725.75", "-75.00"),
           ("2025-09", "1725.75", "89.00", "0.00", "-105.00", "1709.75", "0.00"),
           ("2025-10", "1709.75", "0.00", "50.00", "0.00", "1858.75", "99.00"),
           ("2025-11", "1858.75", "0.00", "50.00", "-16.00", "2007.75", "115.00"),
           ("2025-12", "2007.75", "219.00", "0.00", "0.00", "2137.75", "-89.00")])

    check("with a row for every customer in every month, each change is named: five new, three "
          "reactivations, three expansions, two contractions and seven churns",
          lambda: q(db, "03-movements.sql"),
          [("2025-02", "LUNENBURG-DENTAL", "new", "0.00", "115.00", "115.00"),
           ("2025-03", "DARTMOUTH-CHIRO", "churn", "159.00", "0.00", "-159.00"),
           ("2025-03", "FAIRVIEW-FAMILY-MED", "contraction", "310.75", "280.75", "-30.00"),
           ("2025-03", "KEMPT-ROAD-CLINIC", "new", "0.00", "199.00", "199.00"),
           ("2025-04", "NORTH-END-VET", "churn", "189.50", "0.00", "-189.50"),
           ("2025-05", "LUNENBURG-DENTAL", "churn", "115.00", "0.00", "-115.00"),
           ("2025-06", "ANNAPOLIS-EYE-CARE", "churn", "159.00", "0.00", "-159.00"),
           ("2025-06", "BEDFORD-PEDIATRICS", "new", "0.00", "139.00", "139.00"),
           ("2025-06", "DARTMOUTH-CHIRO", "reactivation", "0.00", "159.00", "159.00"),
           ("2025-07", "CITADEL-OPTICAL", "churn", "99.00", "0.00", "-99.00"),
           ("2025-07", "KEMPT-ROAD-CLINIC", "expansion", "199.00", "249.00", "50.00"),
           ("2025-08", "HARBOUR-DENTAL", "expansion", "249.00", "349.00", "100.00"),
           ("2025-08", "MAPLE-LEAF-AUDIOLOGY", "churn", "75.00", "0.00", "-75.00"),
           ("2025-09", "SOUTH-SHORE-DERM", "contraction", "420.00", "315.00", "-105.00"),
           ("2025-09", "WOLFVILLE-WELLNESS", "new", "0.00", "89.00", "89.00"),
           ("2025-10", "CITADEL-OPTICAL", "reactivation", "0.00", "149.00", "149.00"),
           ("2025-11", "FAIRVIEW-FAMILY-MED", "expansion", "280.75", "330.75", "50.00"),
           ("2025-11", "LUNENBURG-DENTAL", "reactivation", "0.00", "99.00", "99.00"),
           ("2025-12", "TRURO-MEDICAL", "new", "0.00", "219.00", "219.00"),
           ("2025-12", "WOLFVILLE-WELLNESS", "churn", "89.00", "0.00", "-89.00")])

    check("every month's bridge adds up, and the year runs from 1790.25 to 2137.75 through 761.00 new, "
          "407.00 back again, 200.00 expansion, 135.00 contraction and 885.50 churn",
          lambda: q(db, "04-bridge.sql"),
          [("2025-02", "1790.25", "115.00", "0.00", "0.00", "0.00", "0.00", "1905.25", "yes"),
           ("2025-03", "1905.25", "199.00", "0.00", "0.00", "-30.00", "-159.00", "1915.25", "yes"),
           ("2025-04", "1915.25", "0.00", "0.00", "0.00", "0.00", "-189.50", "1725.75", "yes"),
           ("2025-05", "1725.75", "0.00", "0.00", "0.00", "0.00", "-115.00", "1610.75", "yes"),
           ("2025-06", "1610.75", "139.00", "159.00", "0.00", "0.00", "-159.00", "1749.75", "yes"),
           ("2025-07", "1749.75", "0.00", "0.00", "50.00", "0.00", "-99.00", "1700.75", "yes"),
           ("2025-08", "1700.75", "0.00", "0.00", "100.00", "0.00", "-75.00", "1725.75", "yes"),
           ("2025-09", "1725.75", "89.00", "0.00", "0.00", "-105.00", "0.00", "1709.75", "yes"),
           ("2025-10", "1709.75", "0.00", "149.00", "0.00", "0.00", "0.00", "1858.75", "yes"),
           ("2025-11", "1858.75", "0.00", "99.00", "50.00", "0.00", "0.00", "2007.75", "yes"),
           ("2025-12", "2007.75", "219.00", "0.00", "0.00", "0.00", "-89.00", "2137.75", "yes"),
           ("total", "1790.25", "761.00", "407.00", "200.00", "-135.00", "-885.50", "2137.75", "yes")])

    check("customers won and lost add up month by month, and net retention passes 100 percent in August "
          "and November while gross stays at or under it",
          lambda: q(db, "05-retention.sql"),
          [("2025-02", 9, 0, 1, 10, "100.0", "100.0"),
           ("2025-03", 10, 1, 1, 10, "90.1", "90.1"),
           ("2025-04", 10, 1, 0, 9, "90.1", "90.1"),
           ("2025-05", 9, 1, 0, 8, "93.3", "93.3"),
           ("2025-06", 8, 1, 2, 9, "90.1", "90.1"),
           ("2025-07", 9, 1, 0, 8, "94.3", "97.2"),
           ("2025-08", 8, 1, 0, 7, "95.6", "101.5"),
           ("2025-09", 7, 0, 1, 8, "93.9", "93.9"),
           ("2025-10", 8, 0, 1, 9, "100.0", "100.0"),
           ("2025-11", 9, 0, 1, 10, "100.0", "102.7"),
           ("2025-12", 10, 1, 1, 10, "95.6", "95.6")])

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
          "rows each prints and the first of them, and a query file that fails, has no query result, is not UTF-8 "
          "or is gone by the time it is read, or a folder named like one, stops them with a one-line message",
          lambda: [reports(), broken_reports()],
          [[("=== 01-log-shape.sql ===",
             "first_month  last_month  months  customers  paying_rows  skipped_months",
             "-----------  ----------  ------  ---------  -----------  --------------", 1,
             "2025-01      2025-12     12      14         107          12"),
            ("=== 02-lag-by-row.sql ===", "month    opening  new     expansion  contraction  closing  unexplained",
             "-------  -------  ------  ---------  -----------  -------  -----------", 11,
             "2025-02  1790.25  115.00  0.00       0.00         1905.25  0.00"),
            ("=== 03-movements.sql ===", "month    customer              movement      mrr_before  mrr_after  change",
             "-------  --------------------  ------------  ----------  ---------  -------", 20,
             "2025-02  LUNENBURG-DENTAL      new           0.00        115.00     115.00"),
            ("=== 04-bridge.sql ===",
             "month    opening  new     reactivation  expansion  contraction  churn    closing  adds_up",
             "-------  -------  ------  ------------  ---------  -----------  -------  -------  -------", 12,
             "2025-02  1790.25  115.00  0.00          0.00       0.00         0.00     1905.25  yes"),
            ("=== 05-retention.sql ===",
             "month    paying_at_open  lost  won  paying_at_close  grr_pct  nrr_pct",
             "-------  --------------  ----  ---  ---------------  -------  -------", 11,
             "2025-02  9               0     1    10               100.0    100.0")],
           [(2, '01-broken.sql: did not run: near "SELEC": syntax error'),
            (2, "01-empty.sql: did not run: has no query result to print"),
            (2, "01-ansi.sql: is not UTF-8 text"),
            (2, "01-folder.sql: is a folder, not a query file"),
            (2, "01-gone.sql: No such file or directory")]])

    # Logs built for cases the sample does not reach on its own. Only the
    # reversed sample goes through the loader.
    gap = new_db([("2024-11", "A", 10000), ("2024-12", "A", 10000), ("2025-02", "A", 12000),
                  ("2025-03", "A", 12000), ("2025-04", "A", 12000),
                  ("2024-11", "B", 5000), ("2025-03", "B", 5000), ("2025-04", "B", 5000),
                  ("2025-02", "C", 3000), ("2025-03", "C", 3000), ("2025-04", "C", 3000)])
    check("a month nobody paid for still gets its row, across a change of year; a customer seen only in the "
          "first month comes back as a reactivation, not new; a month with no change shows zeros; and a month "
          "that opens with nobody paying leaves its rates blank, in the printed report too",
          lambda: [q(gap, "01-log-shape.sql"), q(gap, "02-lag-by-row.sql"), q(gap, "03-movements.sql"),
                   q(gap, "04-bridge.sql"), q(gap, "05-retention.sql"), printed(gap, "05-retention.sql")[2]],
          [[("2024-11", "2025-04", 6, 3, 11, 4)],
           [("2024-12", "150.00", "0.00", "0.00", "0.00", "100.00", "-50.00"),
            ("2025-01", "100.00", "0.00", "0.00", "0.00", "0.00", "-100.00"),
            ("2025-02", "0.00", "30.00", "20.00", "0.00", "150.00", "100.00"),
            ("2025-03", "150.00", "0.00", "0.00", "0.00", "200.00", "50.00"),
            ("2025-04", "200.00", "0.00", "0.00", "0.00", "200.00", "0.00")],
           [("2024-12", "B", "churn", "50.00", "0.00", "-50.00"),
            ("2025-01", "A", "churn", "100.00", "0.00", "-100.00"),
            ("2025-02", "A", "reactivation", "0.00", "120.00", "120.00"),
            ("2025-02", "C", "new", "0.00", "30.00", "30.00"),
            ("2025-03", "B", "reactivation", "0.00", "50.00", "50.00")],
           [("2024-12", "150.00", "0.00", "0.00", "0.00", "0.00", "-50.00", "100.00", "yes"),
            ("2025-01", "100.00", "0.00", "0.00", "0.00", "0.00", "-100.00", "0.00", "yes"),
            ("2025-02", "0.00", "30.00", "120.00", "0.00", "0.00", "0.00", "150.00", "yes"),
            ("2025-03", "150.00", "0.00", "50.00", "0.00", "0.00", "0.00", "200.00", "yes"),
            ("2025-04", "200.00", "0.00", "0.00", "0.00", "0.00", "0.00", "200.00", "yes"),
            ("total", "150.00", "30.00", "170.00", "0.00", "0.00", "-150.00", "200.00", "yes")],
           [("2024-12", 2, 1, 0, 1, "66.7", "66.7"),
            ("2025-01", 1, 1, 0, 0, "0.0", "0.0"),
            ("2025-02", 0, 0, 2, 2, None, None),
            ("2025-03", 2, 0, 1, 3, "100.0", "100.0"),
            ("2025-04", 3, 0, 0, 3, "100.0", "100.0")],
           "2025-02  0               0     2    2"])

    # 400.00 opens the month. 19.80 of contraction and a 20.00 churn keep
    # 360.20, 90.05 percent; 12.00 of expansion brings net to 372.20, 93.05
    # percent. As floating point both sit just under the half: printf or
    # ROUND on the float gives 90.0 and 93.0 on SQLite 3.50 but 90.1 and 93.1
    # on 3.31 and 3.34, and rounding half to even gives 90.0 and 93.0. The
    # 10.00 new customer counts in neither.
    halves = new_db([("2025-01", "P", 28000), ("2025-01", "Q", 5000), ("2025-01", "R", 5000),
                     ("2025-01", "T", 2000),
                     ("2025-02", "P", 26020), ("2025-02", "Q", 6200), ("2025-02", "R", 5000),
                     ("2025-02", "S", 1000)])
    check("rates that land on an exact half round up, where rounding half to even would round down and printf "
          "or ROUND on a float changes with the SQLite version, and a new customer counts in neither rate",
          lambda: [q(halves, "04-bridge.sql"), q(halves, "05-retention.sql")],
          [[("2025-02", "400.00", "10.00", "0.00", "12.00", "-19.80", "-20.00", "382.20", "yes"),
            ("total", "400.00", "10.00", "0.00", "12.00", "-19.80", "-20.00", "382.20", "yes")],
           [("2025-02", 4, 1, 1, 4, "90.1", "93.1")]])

    def reversed_log():
        # The sample again, stored in the opposite order in a table with no
        # key, so nothing hands the rows back in month order unless a query
        # sorts them.
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE mrr (month TEXT NOT NULL, customer TEXT NOT NULL, mrr_cents INTEGER NOT NULL)")
        conn.executemany("INSERT INTO mrr VALUES (?, ?, ?)", list(reversed(load(MRR_CSV))))
        return [q(conn, name) == q(db, name) for name in
                ("01-log-shape.sql", "02-lag-by-row.sql", "03-movements.sql", "04-bridge.sql", "05-retention.sql")]

    check("the sample stored in the opposite order, in a table with no key to keep it in order, gives the same "
          "five reports",
          reversed_log, [True] * 5)

    # 36 customers from 1970-01 to 2200-12, every one paying 0.07 more each
    # month after the first: 99792 customer-months, near the most the loader
    # allows, both ends of the months it allows, and one of the costliest
    # logs found for the step budget. Then 50000 customers over two months at
    # the largest amount, one of them dropping to 0.01, for totals near the
    # largest the limits allow.
    growing = new_db([(f"{n // 12:04d}-{n % 12 + 1:02d}", f"C{c}", 100 + 7 * (n - 23640) + c)
                      for c in range(36) for n in range(23640, 26412)])
    largest = new_db([("2025-01", f"C{c}", 99999999) for c in range(50000)]
                     + [("2025-02", f"C{c}", 1 if c == 0 else 99999999) for c in range(50000)])

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
        check("36 customers from 1970-01 to 2200-12, nearly the most customer-months the loader allows, each "
              "changing every month after the first, run through each query inside the step budget; totals near "
              "the largest the limits allow print in full, to the cent; and a query that would run for ever is "
              "stopped by the step budget",
              lambda: [ends(growing, "01-log-shape.sql"), ends(growing, "02-lag-by-row.sql"),
                       ends(growing, "03-movements.sql"), ends(growing, "04-bridge.sql"),
                       ends(growing, "05-retention.sql"), q(largest, "04-bridge.sql"),
                       q(largest, "05-retention.sql"), endless(tmp)],
              [(1, ("1970-01", "2200-12", 2772, 36, 99792, 0), ("1970-01", "2200-12", 2772, 36, 99792, 0)),
               (2771, ("1970-02", "42.30", "0.00", "2.52", "0.00", "44.82", "0.00"),
                ("2200-12", "7022.70", "0.00", "2.52", "0.00", "7025.22", "0.00")),
               (99756, ("1970-02", "C0", "expansion", "1.00", "1.07", "0.07"),
                ("2200-12", "C9", "expansion", "194.99", "195.06", "0.07")),
               (2772, ("1970-02", "42.30", "0.00", "0.00", "2.52", "0.00", "0.00", "44.82", "yes"),
                ("total", "42.30", "0.00", "0.00", "6982.92", "0.00", "0.00", "7025.22", "yes")),
               (2771, ("1970-02", 36, 0, 0, 36, "100.0", "106.0"), ("2200-12", 36, 0, 0, 36, "100.0", "100.0")),
               [("2025-02", "49999999500.00", "0.00", "0.00", "0.00", "-999999.98", "0.00", "49998999500.02", "yes"),
                ("total", "49999999500.00", "0.00", "0.00", "0.00", "-999999.98", "0.00", "49998999500.02", "yes")],
               [("2025-02", 50000, 0, 0, 50000, "100.0", "100.0")],
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

        head = ",".join(MRR_COLUMNS) + "\n"
        small = head + "2025-01,KIT,10.00\n2025-02,KIT,12.00\n"

        def logs(name, content):
            return rejection(load, csv_file(name, content))

        def sized(result):
            code, loaded = result
            return (code, len(loaded)) if code == 0 else result

        check("a customer listed twice in one month is refused, naming the row",
              lambda: [rejection(load, HERE / "data" / "invalid-mrr.csv"),
                       logs("twice.csv", small + "2025-01,KIT,3.00\n")],
              [(2, "invalid-mrr.csv row 63: KEMPT-ROAD-CLINIC appears twice for 2025-07; one row per customer "
                   "and month, with the amounts added together"),
               (2, "twice.csv row 4: KIT appears twice for 2025-01; one row per customer and month, "
                   "with the amounts added together")])

        bad_months = ["2025-13", "2025-00", "2025-1", "25-01", "2025/01", "1969-12", "2201-01", "", "2025-01-01",
                      "Jan-2025", "\uff12\uff10\uff12\uff15-\uff10\uff11"]
        check("a month past 12 or at 00, written without its leading zero, with a two-digit year, a slash, a "
              "day, a month name or fullwidth digits, before 1970 or after 2200, or blank is refused, while "
              "1970-01 and 2200-12 in one log load",
              lambda: [logs(f"month{k}.csv", head + f"{raw},KIT,1.00\n2025-02,KIT,1.00\n")
                       for k, raw in enumerate(bad_months)]
                      + [logs("bounds.csv", head + "1970-01,KIT,1.00\n2200-12,KIT,1.00\n")],
              [(2, f"month{k}.csv row 2: month {raw!r} is not a month written like 2025-04, from 1970-01 to 2200-12")
               for k, raw in enumerate(bad_months)]
              + [(0, [("1970-01", "KIT", 100), ("2200-12", "KIT", 100)])])

        codes = [("lower.csv", "kit"), ("space.csv", "KIT 2"), ("double.csv", "KIT--2"), ("edge.csv", "-KIT"),
                 ("trailing.csv", "KIT-"), ("long.csv", "A" * 25), ("blank.csv", ""), ("accent.csv", "CAF\u00c9"),
                 ("fullwidth.csv", "\uff2b\uff29\uff34")]
        check("a customer code in lower case, with a space, a doubled or outer hyphen, an accent, fullwidth "
              "letters, over 24 characters, or blank is refused, and a code of exactly 24 characters with two "
              "hyphens loads",
              lambda: [logs(name, head + f"2025-01,{raw},1.00\n2025-02,KIT,1.00\n") for name, raw in codes]
                      + [logs("max.csv", head + "2025-01,ABCDEFGH-1234567-ABCDEFG,1.00\n2025-02,KIT,1.00\n")],
              [(2, f"{name} row 2: customer {raw!r} is not a customer code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters") for name, raw in codes]
              + [(0, [("2025-01", "ABCDEFGH-1234567-ABCDEFG", 100), ("2025-02", "KIT", 100)])])

        bad_amounts = ["-5.00", "5", "5.0", "5.000", "05.00", "1000000.00", "1e3", "", "5,00", "$5.00", ".50",
                       "\u0661\u0660.\u0660\u0660", "1\u0660.\u0660\u0660"]
        check("an amount of 0.00 is refused as a month to leave out; a negative, whole, one-place, three-place, "
              "zero-padded, seven-digit, exponent, blank, comma or dollar-sign amount, one with no digit before the "
              "point, or one with "
              "Arabic-Indic digits in it, even after a plain first digit, is refused; and 0.01 and 999999.99 load",
              lambda: [logs("zero.csv", small + "2025-03,KIT,0.00\n")]
                      + [logs(f"amount{k}.csv", small + f'2025-03,KIT,"{raw}"\n') for k, raw in enumerate(bad_amounts)]
                      + [logs("extremes.csv", head + "2025-01,KIT,0.01\n2025-02,KIT,999999.99\n")],
              [(2, "zero.csv row 4: mrr is 0.00; a month the customer paid nothing for is left out of the log")]
              + [(2, f"amount{k}.csv row 4: mrr {raw!r} is not an amount from 0.01 to 999999.99 written like 249.00")
                 for k, raw in enumerate(bad_amounts)]
              + [(0, [("2025-01", "KIT", 1), ("2025-02", "KIT", 99999999)])])

        check("rows are counted past blank lines and a line of spaces, and a stray quote is named by its own row, "
              "in a data row or in the header; rows with too many or too few fields, a line of commas, a tab, text "
              "after a closing quote, a quote left open, a field past the parser's limit, and a bad, renamed or "
              "reordered header, also one found after blank lines, written as one quoted field or with a trailing "
              "comma, are refused, and "
              "a long value or header is cut short in the message",
              lambda: [logs("rows.csv", small + "\n   \n\n2025-03,kit,1.00\n"),
                       logs("quote.csv", small + '2025-03,"KIT,1.00\n2025-04,KIT",1.00\n'),
                       logs("unclosed.csv", small + '2025-03,"KIT,1.00\n'),
                       logs("wide.csv", small + "2025-03,KIT,1.00,extra\n"),
                       logs("narrow.csv", small + "2025-03,KIT\n"),
                       logs("commas.csv", small + ",,\n"),
                       logs("tab.csv", small + "2025-03,KIT\t,1.00\n"),
                       logs("after.csv", small + '2025-03,"KIT"x,1.00\n'),
                       logs("huge_field.csv", small + "2025-03," + "A" * 200000 + ",1.00\n"),
                       logs("header.csv", 'month,"customer"x,mrr\n2025-01,KIT,1.00\n'),
                       logs("open_header.csv", '"month,customer,mrr\n2025-01,KIT,1.00\n2025-02,KIT,1.00\n'),
                       logs("span_header.csv", '\n\nmonth,"customer,mrr\n2025-01,KIT",1.00\n2025-02,KIT,1.00\n'),
                       logs("renamed.csv", "month,account,mrr\n2025-01,KIT,1.00\n"),
                       logs("reordered.csv", "customer,month,mrr\nKIT,2025-01,1.00\n"),
                       logs("late_renamed.csv", "\nmonth,account,mrr\n2025-01,KIT,1.00\n"),
                       logs("quoted_header.csv", '"month,customer,mrr"\n"2025-01,KIT,10.00"\n'),
                       logs("trailing_comma.csv", "month,customer,mrr,\n2025-01,KIT,1.00,\n"),
                       logs("long_header.csv", "month,customer,mrr" + "x" * 100 + "\n2025-01,KIT,1.00\n"),
                       logs("long_value.csv", small + "2025-03," + "B" * 100 + ",1.00\n")],
              [(2, "rows.csv row 7: customer 'kit' is not a customer code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "quote.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "unclosed.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "wide.csv row 4: has more fields than the header"),
               (2, "narrow.csv row 4: has fewer fields than the header"),
               (2, "commas.csv row 4: month '' is not a month written like 2025-04, from 1970-01 to 2200-12"),
               (2, "tab.csv row 4: customer 'KIT\\t' is not a customer code: capital letters and digits, "
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
               (2, "renamed.csv row 1: expected columns 'month,customer,mrr', got 'month,account,mrr'"),
               (2, "reordered.csv row 1: expected columns 'month,customer,mrr', got 'customer,month,mrr'"),
               (2, "late_renamed.csv row 2: expected columns 'month,customer,mrr', got 'month,account,mrr'"),
               (2, "quoted_header.csv row 1: expected columns 'month,customer,mrr', got '\"month,customer,mrr\"'"),
               (2, "trailing_comma.csv row 1: expected columns 'month,customer,mrr', got 'month,customer,mrr,'"),
               (2, "long_header.csv row 1: expected columns 'month,customer,mrr', got 'month,customer,mrr"
                   + "x" * 22 + "' and 78 more characters"),
               (2, "long_value.csv row 4: customer '" + "B" * 40 + "' and 60 more characters is not a customer "
                   "code: capital letters and digits, joined by single hyphens, at most 24 characters")])

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
            lines, _ = open_csv(path, Dropped(text), MRR_COLUMNS)
            return list(records(path, lines, MRR_COLUMNS))

        def capped(text):
            return len(list(read_lines(Path(tmp) / "cap.csv", io.StringIO(text))))

        far_down = "".join(f"2025-01,C{c},1.00\n" for c in range(20000))
        check("an empty file, one of blank lines, one with only a header, also after a blank line, one that is not "
              "UTF-8 from its first line or only far down, or holds only part of a byte-order mark, a folder, a "
              "read that gives way before the header or partway through, and a line past 1000000 characters are "
              "refused, a line of exactly 1000000 passing; while a byte-order mark, blank lines before the header "
              "and spaces around unquoted fields, in the header too, load",
              lambda: [logs("empty.csv", ""),
                       logs("blank_only.csv", "\n  \n\n"),
                       logs("bare.csv", head),
                       logs("late_bare.csv", "\n" + head),
                       rejection(load, byte_file("latin1.csv", b"month,customer,mrr\xc9\n2025-01,KIT,1.00\n")),
                       rejection(load, byte_file("late_latin1.csv", (head + far_down).encode("utf-8")
                                                 + b"2025-02,CAF\xc9,1.00\n")),
                       rejection(load, byte_file("part_mark.csv", b"\xef\xbb")),
                       rejection(load, Path(tmp)),
                       rejection(dropped, ""),
                       rejection(dropped, small),
                       logs("long_line.csv", small + "," * 1000001 + "\n"),
                       rejection(capped, "x" * 1000001 + "\n"),
                       rejection(capped, "x" * 1000000 + "\r\n"),
                       logs("marked.csv", "\ufeff month , customer , mrr \n 2025-01 , KIT , 10.00 \n"
                            "2025-02,KIT,12.00\n"),
                       logs("leading.csv", "\n  \n" + small)],
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
               (0, [("2025-01", "KIT", 1000), ("2025-02", "KIT", 1200)]),
               (0, [("2025-01", "KIT", 1000), ("2025-02", "KIT", 1200)])])

        # 1000 customers over 100 months, each paying in the first month and
        # the last, is exactly the limit; one more customer is 100 over. 50001
        # customers over two months, all but one paying in the first month
        # only, is under the limit in rows and over it in customer-months, and
        # 50001 customers paying in both months runs past it in rows.
        def spread(customers, last):
            return head + "".join(f"2025-01,C{c},1.00\n{last},C{c},1.00\n" for c in range(customers))

        check("a log of one month is refused, as is one whose customers times its months pass 100000, by one "
              "customer or with fewer rows than that, and one that runs past 100000 rows is stopped as it is read, "
              "before it reaches a bad byte further down, while a log of exactly 100000 customer-months loads",
              lambda: [logs("one_month.csv", head + "2025-01,KIT,1.00\n2025-01,BOX,2.00\n"),
                       logs("one_over.csv", spread(1001, "2033-04")),
                       logs("sparse.csv", head + "".join(f"2025-01,C{c},1.00\n" for c in range(50001))
                            + "2025-02,C0,1.00\n"),
                       rejection(load, byte_file("too_many_rows.csv",
                                                 (spread(50001, "2025-02") + far_down).encode("utf-8")
                                                 + b"2025-03,CAF\xc9,1.00\n")),
                       sized(logs("at_limit.csv", spread(1000, "2033-04")))],
              [(2, "one_month.csv: the log covers only 2025-01; the bridge compares each month with the one before, "
                   "so it needs at least two"),
               (2, "one_over.csv: 1001 customers over 100 months make 100100 customer-months, more than the "
                   "100000 the queries fill in"),
               (2, "sparse.csv: 50001 customers over 2 months make 100002 customer-months, more than the "
                   "100000 the queries fill in"),
               (2, "too_many_rows.csv row 100002: the log runs past 100000 rows, and each row is a customer-month "
                   "the queries fill in"),
               (0, 2000)])

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

        other = csv_file("other.csv", MRR_CSV.read_text(encoding="utf-8"))

        def cli(*argv):
            return rejection(settings, [str(a) for a in argv])

        def main_check():
            # main itself, on a file name the Windows codepage cannot hold. It
            # stops at the missing file, and the message has to come out as
            # UTF-8. The command line has no --test, so no suite is started.
            saved = sys.argv, sys.stdout, sys.stderr
            err = io.BytesIO()
            name = "\u6f22\u5b57.csv"
            sys.argv = ["run.py", "--mrr", str(Path(tmp) / name)]
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

        check("on the command line, a file that is not there, a name with a wildcard in it, and a test run on any "
              "file other than the sample "
              "are refused, while the sample is picked by default or spelled another way and a log of your own "
              "is taken; output and messages are written as UTF-8 by the helper that sets them up, which leaves "
              "alone a stream it cannot switch, and main's own messages come out as UTF-8",
              lambda: [cli("--mrr", Path(tmp) / "not_there.csv"),
                       cli("--mrr", Path(tmp) / "data*.csv"),
                       cli("--test", "--mrr", other),
                       cli("--test"),
                       cli(),
                       cli("--test", "--mrr", HERE / "data" / ".." / "data" / "mrr.csv"),
                       cli("--mrr", other),
                       utf8_check(),
                       main_check()],
              [(2, f"run.py: error: --mrr: '{Path(tmp) / 'not_there.csv'}' is not a file"),
               (2, f"run.py: error: --mrr: '{Path(tmp) / 'data*.csv'}' is not a file"),
               (2, "run.py: error: --test checks hand-computed answers for the sample file; run it without --mrr"),
               (0, (True, MRR_CSV)),
               (0, (False, MRR_CSV)),
               (0, (True, HERE / "data" / ".." / "data" / "mrr.csv")),
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
    parser = argparse.ArgumentParser(prog="run.py", description="Run the bridge queries against a monthly "
                                                 "recurring revenue log, the sample by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--mrr", type=Path, default=None, help="path to an alternate MRR log CSV")
    args = parser.parse_args(argv)
    path = args.mrr or MRR_CSV
    try:
        found = path.is_file()
    except OSError:
        # Python 3.7 raises here for a name Windows cannot hold, such as one
        # with a wildcard in it.
        found = False
    if not found:
        if args.mrr is not None:
            parser.error(f"--mrr: '{path}' is not a file")
        parser.error(f"the sample file '{path}' is missing")
    if args.test and path.resolve() != MRR_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample file; run it without --mrr")
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
