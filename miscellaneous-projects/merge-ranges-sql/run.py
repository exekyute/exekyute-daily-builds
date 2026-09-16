"""Load the coverage periods into SQLite and run the merge queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --periods data/other.csv          load a different period log
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
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).parent
PERIODS_CSV = HERE / "data" / "periods.csv"
SQL_DIR = HERE / "sql"
PERIOD_COLUMNS = ["period_id", "customer", "starts_on", "ends_on"]
# Dates outside this range are refused, which keeps a year like 0202 or
# 9999 out of the log. A year mistyped inside the range, 2126 for 2026,
# still loads, and shows up as a span or a lapse of about a century.
EARLIEST = date(1970, 1, 1)
LATEST = date(2200, 12, 31)
# Invisible characters that belong in a name: the zero-width joiners that
# Persian and Sinhala spelling needs, and the marks that set writing
# direction around a name in Arabic or Hebrew.
NAME_MARKS = {"\u200c", "\u200d", "\u200e", "\u200f", "\u061c"}


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
            # Cf catches the invisible characters, a zero-width space in a
            # customer name among them, which would split one customer in
            # two without showing anything on the page. The joiners and the
            # direction marks are let through, since names in Persian,
            # Sinhala and Hebrew are spelled with them.
            bad = next((ch for f in fields for ch in f
                        if unicodedata.category(ch) in ("Cc", "Cf") and ch not in NAME_MARKS), None)
            if bad is not None:
                fail(path, start, f"contains the control or invisible character {bad!r}")
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
        fail(path, row_num, f"{name} {raw!r} is not a date like 2026-09-16")
    try:
        value = datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        fail(path, row_num, f"{name} {raw!r} is not a real date")
    if not EARLIEST <= value <= LATEST:
        fail(path, row_num, f"{name} {raw} is outside the dates this log can use, "
                            f"{EARLIEST} to {LATEST}")
    return value


def load_periods(path):
    rows, seen, spellings = [], set(), {}
    reader = read_csv(path, PERIOD_COLUMNS)
    for i, row in records(path, reader, PERIOD_COLUMNS):
        period_id = whole(path, i, "period_id", row["period_id"], 9)
        if period_id in seen:
            fail(path, i, f"period_id {period_id} appears twice; the log holds one row per period")
        seen.add(period_id)
        # NFC first, so a name typed with combining accents matches the same
        # name typed with single characters instead of splitting the customer.
        customer = unicodedata.normalize("NFC", " ".join(row["customer"].split()))
        if not customer:
            fail(path, i, "customer is blank")
        # The queries group by the name as written, so one customer under two
        # spellings comes out as two customers, each covered for part of the
        # time, and the lapse between them never reaches query 05. Spacing
        # and accents are settled above; letter case is not.
        first = spellings.setdefault(customer.casefold(), customer)
        if first != customer:
            fail(path, i, f"customer {customer!r} is also written {first!r}; "
                          "one spelling per customer, or the cover comes out split")
        starts_raw, ends_raw = row["starts_on"], row["ends_on"]
        starts = parse_date(path, i, "starts_on", starts_raw)
        ends = parse_date(path, i, "ends_on", ends_raw)
        # Both ends of a period are covered days, so a period may be one day
        # long, but it cannot end before it starts.
        if ends < starts:
            fail(path, i, f"period {period_id} ends on {ends_raw}, "
                          f"before it starts on {starts_raw}")
        rows.append((period_id, customer, starts_raw, ends_raw))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def new_db(periods):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE periods (period_id INTEGER PRIMARY KEY, customer TEXT NOT NULL, "
               "starts_on TEXT NOT NULL, ends_on TEXT NOT NULL)")
    db.executemany("INSERT INTO periods VALUES (?, ?, ?, ?)", periods)
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
        # got can be a function, so a query that hands back the wrong shape
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

    check("sixteen periods for five customers, running from January 1 to November 30, 807 days added up",
          q(db, "01-period-log-shape.sql"),
          [(5, 16, "2026-01-01", "2026-11-30", 807)])

    naive = q(db, "02-naive-totals.sql")
    check("the two naive totals, each of them right only by accident",
          naive,
          [("Brightside Dental", 3, "2026-01-01", "2026-08-31", 259, 243),
           ("Harbour Freight Co", 2, "2026-01-15", "2026-07-15", 121, 182),
           ("Kestrel Media", 4, "2026-02-01", "2026-11-30", 390, 303),
           ("Northcliff Studio", 6, "2026-03-02", "2026-03-06", 6, 5),
           ("Selkirk Bakery", 1, "2026-07-01", "2026-07-31", 31, 31)])

    blocks = q(db, "03-merged-blocks.sql")
    check("sixteen periods merge into seven blocks, numbered from 1 for each customer",
          blocks,
          [("Brightside Dental", 1, "2026-01-01", "2026-08-31", 3, 243),
           ("Harbour Freight Co", 1, "2026-01-15", "2026-02-28", 1, 45),
           ("Harbour Freight Co", 2, "2026-05-01", "2026-07-15", 1, 76),
           ("Kestrel Media", 1, "2026-02-01", "2026-09-30", 3, 242),
           ("Kestrel Media", 2, "2026-10-05", "2026-11-30", 1, 57),
           ("Northcliff Studio", 1, "2026-03-02", "2026-03-06", 6, 5),
           ("Selkirk Bakery", 1, "2026-07-01", "2026-07-31", 1, 31)])

    coverage = q(db, "04-coverage.sql")
    check("the days covered, with what each naive total got wrong",
          coverage,
          [("Brightside Dental", 3, 1, 259, 243, 16, 0),
           ("Harbour Freight Co", 2, 2, 121, 121, 0, 61),
           ("Kestrel Media", 4, 2, 390, 299, 91, 4),
           ("Northcliff Studio", 6, 1, 6, 5, 1, 0),
           ("Selkirk Bakery", 1, 1, 31, 31, 0, 0)])
    check("the two lapses, dated from the day after cover ends to the day before it resumes",
          q(db, "05-gaps.sql"),
          [("Harbour Freight Co", "2026-03-01", "2026-04-30", 61),
           ("Kestrel Media", "2026-10-01", "2026-10-04", 4)])

    # Logs built for cases the sample does not reach on its own.
    def log(rows):
        return new_db([(n, customer, starts, ends)
                       for n, (customer, starts, ends) in enumerate(rows, 1)])

    touching = log([("Touching", "2026-01-01", "2026-01-31"), ("Touching", "2026-02-01", "2026-02-28"),
                    ("One day short", "2026-01-01", "2026-01-31"), ("One day short", "2026-02-02", "2026-02-28")])
    check("a period starting the day after the last one ends continues the block, one day later opens a new one",
          [q(touching, "03-merged-blocks.sql"), q(touching, "04-coverage.sql"), q(touching, "05-gaps.sql")],
          [[("One day short", 1, "2026-01-01", "2026-01-31", 1, 31),
            ("One day short", 2, "2026-02-02", "2026-02-28", 1, 27),
            ("Touching", 1, "2026-01-01", "2026-02-28", 2, 59)],
           [("One day short", 2, 2, 58, 58, 0, 1), ("Touching", 2, 1, 59, 59, 0, 0)],
           [("One day short", "2026-02-01", "2026-02-01", 1)]])

    # Two short periods inside a long one. Comparing each period with the
    # row before it rather than with the furthest end so far would call the
    # June period a fresh block, since the March period ended in March.
    nested = log([("Nested", "2026-01-01", "2026-12-31"), ("Nested", "2026-03-01", "2026-03-31"),
                  ("Nested", "2026-06-01", "2026-06-30")])
    check("periods held inside a longer one stay in its block, however far apart they are",
          q(nested, "03-merged-blocks.sql"),
          [("Nested", 1, "2026-01-01", "2026-12-31", 3, 365)])

    leap = log([("Leap", "2024-02-01", "2024-02-29"), ("Leap", "2024-03-01", "2024-03-31")])
    check("February 29 counts, and the block runs to the end of March",
          [q(leap, "03-merged-blocks.sql"), q(leap, "04-coverage.sql")],
          [[("Leap", 1, "2024-02-01", "2024-03-31", 2, 60)],
           [("Leap", 2, 1, 60, 60, 0, 0)]])

    year_end = log([("Year end", "2026-12-15", "2027-01-15")])
    check("a period across the year end is 32 days in the blocks and in the totals, not a negative count",
          [q(year_end, "03-merged-blocks.sql"), q(year_end, "04-coverage.sql")],
          [[("Year end", 1, "2026-12-15", "2027-01-15", 1, 32)],
           [("Year end", 1, 1, 32, 32, 0, 0)]])

    # Days counted twice is the surplus the adding up carried, not the days
    # it happened on: three periods over one month put 62 on a 31-day log.
    twins = log([("Twins", "2026-05-01", "2026-05-31"), ("Twins", "2026-05-01", "2026-05-31"),
                 ("Triplets", "2026-05-01", "2026-05-31"), ("Triplets", "2026-05-01", "2026-05-31"),
                 ("Triplets", "2026-05-01", "2026-05-31")])
    check("periods with the same dates cover a month once, and the surplus grows with each one",
          q(twins, "04-coverage.sql"),
          [("Triplets", 3, 1, 93, 31, 62, 0), ("Twins", 2, 1, 62, 31, 31, 0)])

    # Ids that run counter to the dates, and a block of two periods that
    # follows a gap. The merge reads periods in start order, not in the
    # order of the ids, and a gap ends at the earliest start of the block
    # after it, not the latest.
    shuffled = log([("Shuffled", "2026-06-01", "2026-06-30"), ("Shuffled", "2026-01-01", "2026-03-31"),
                    ("Shuffled", "2026-03-20", "2026-05-15"), ("After the gap", "2026-01-01", "2026-01-31"),
                    ("After the gap", "2026-03-01", "2026-03-15"), ("After the gap", "2026-03-10", "2026-03-31")])
    check("periods are read in date order, and a lapse runs to the day before the next block opens",
          [q(shuffled, "03-merged-blocks.sql"), q(shuffled, "05-gaps.sql")],
          [[("After the gap", 1, "2026-01-01", "2026-01-31", 1, 31),
            ("After the gap", 2, "2026-03-01", "2026-03-31", 2, 31),
            ("Shuffled", 1, "2026-01-01", "2026-05-15", 2, 135),
            ("Shuffled", 2, "2026-06-01", "2026-06-30", 1, 30)],
           [("After the gap", "2026-02-01", "2026-02-28", 28),
            ("Shuffled", "2026-05-16", "2026-05-31", 16)]])

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

        def byte_file(name, data):
            path = Path(tmp) / name
            path.write_bytes(data)
            return path

        header = ",".join(PERIOD_COLUMNS) + "\n"
        head = header + "1,Brightside Dental,2026-01-01,2026-03-31\n"
        check("a period that ends before it starts is refused",
              rejection(load_periods, HERE / "data" / "invalid-periods.csv"),
              (2, "invalid-periods.csv row 4: period 3 ends on 2026-06-15, "
                  "before it starts on 2026-08-31"))

        check("rows are counted from where a record starts, past blank lines and a stray quote; text after "
              "a closing quote, a repeated period_id, an id with a leading zero or ten digits, and a date "
              "without its zeroes or on the first data row are refused",
              [rejection(load_periods, csv_file("blank.csv", head + "\n\nx,Kestrel Media,2026-02-01,2026-02-28\n")),
               rejection(load_periods, csv_file("quote.csv", head + '2,"Kestrel Media,2026-02-01,2026-02-28\n'
                                                                   '3,Selkirk Bakery,2026-03-01,2026-03-31"\n')),
               rejection(load_periods, csv_file("after.csv", head + '2,"Kestrel Media"x,2026-02-01,2026-02-28\n')),
               rejection(load_periods, csv_file("twice.csv", head + "1,Kestrel Media,2026-02-01,2026-02-28\n")),
               rejection(load_periods, csv_file("unpadded.csv", head + "2,Kestrel Media,2026-2-1,2026-02-28\n")),
               rejection(load_periods, csv_file("padded_id.csv", head + "007,Kestrel Media,2026-02-01,2026-02-28\n")),
               rejection(load_periods, csv_file("long_id.csv", head + "1234567890,Kestrel Media,2026-02-01,2026-02-28\n")),
               rejection(load_periods, csv_file("first_row.csv", header + "1,Kestrel Media,2026-13-01,2026-02-28\n"))],
              [(2, "blank.csv row 5: period_id 'x' is not a whole number from 1 up, "
                   "at most 9 digits with no leading zero"),
               (2, "quote.csv row 3: a field runs across more than one line; most likely a stray quote"),
               (2, "after.csv row 3: cannot be parsed (',' expected after '\"'); most likely a stray quote"),
               (2, "twice.csv row 3: period_id 1 appears twice; the log holds one row per period"),
               (2, "unpadded.csv row 3: starts_on '2026-2-1' is not a date like 2026-09-16"),
               (2, "padded_id.csv row 3: period_id '007' is not a whole number from 1 up, "
                   "at most 9 digits with no leading zero"),
               (2, "long_id.csv row 3: period_id '1234567890' is not a whole number from 1 up, "
                   "at most 9 digits with no leading zero"),
               (2, "first_row.csv row 2: starts_on '2026-13-01' is not a real date")])

        check("a control character, a zero-width space, rows with too many or too few fields, a renamed "
              "header, dates outside the range, an empty file, one with only a header, and one that is not "
              "UTF-8 are refused, while a byte-order mark is read through",
              [rejection(load_periods, csv_file("tab.csv", head + "2,Kestrel Media,2026-02-01,2026-02-28\t\n")),
               rejection(load_periods, csv_file("zwsp.csv", head + "2,Kestrel\u200b Media,2026-02-01,2026-02-28\n")),
               rejection(load_periods, csv_file("wide.csv", head + "2,Kestrel Media,2026-02-01,2026-02-28,extra\n")),
               rejection(load_periods, csv_file("narrow.csv", head + "2,Kestrel Media,2026-02-01\n")),
               rejection(load_periods, csv_file("renamed.csv", "period,customer,starts_on,ends_on\n")),
               rejection(load_periods, csv_file("range.csv", head + "2,Kestrel Media,9999-12-01,9999-12-31\n")),
               rejection(load_periods, csv_file("early.csv", head + "2,Kestrel Media,1969-12-31,1970-01-31\n")),
               rejection(load_periods, csv_file("bare.csv", header)),
               rejection(load_periods, csv_file("nothing.csv", "")),
               rejection(load_periods, byte_file("latin1.csv", header.encode("utf-8")
                                                 + "1,Caf\xe9 Rivard,2026-01-01,2026-01-31\n".encode("latin-1"))),
               rejection(load_periods, csv_file("bom.csv", "\ufeff" + head)),
               rejection(load_periods, csv_file("edges.csv", header + "1,Kestrel Media,1970-01-01,1970-01-31\n"
                                                             + "2,Kestrel Media,2200-12-01,2200-12-31\n"))],
              [(2, "tab.csv row 3: contains the control or invisible character '\\t'"),
               (2, "zwsp.csv row 3: contains the control or invisible character '\\u200b'"),
               (2, "wide.csv row 3: has more fields than the header"),
               (2, "narrow.csv row 3: has fewer fields than the header"),
               (2, "renamed.csv row 1: expected columns period_id,customer,starts_on,ends_on, "
                   "got ['period', 'customer', 'starts_on', 'ends_on']"),
               (2, "range.csv row 3: starts_on 9999-12-01 is outside the dates this log can use, "
                   "1970-01-01 to 2200-12-31"),
               (2, "early.csv row 3: starts_on 1969-12-31 is outside the dates this log can use, "
                   "1970-01-01 to 2200-12-31"),
               (2, "bare.csv row 1: no data rows after the header"),
               (2, "nothing.csv: is empty"),
               (2, "latin1.csv: is not UTF-8 text"),
               (0, [(1, "Brightside Dental", "2026-01-01", "2026-03-31")]),
               (0, [(1, "Kestrel Media", "1970-01-01", "1970-01-31"),
                    (2, "Kestrel Media", "2200-12-01", "2200-12-31")])])

        check("one customer written two ways is refused, a blank name is refused, spacing and accents are "
              "tidied up, and a name spelled with a joiner is kept as written",
              [rejection(load_periods, csv_file("case.csv", head + "2,brightside dental,2026-05-01,2026-05-31\n")),
               rejection(load_periods, csv_file("noname.csv", head + "2, ,2026-05-01,2026-05-31\n")),
               rejection(load_periods, csv_file("spaced.csv", head + "2,  Brightside   Dental ,2026-05-01,2026-05-31\n")),
               rejection(load_periods, csv_file("accents.csv", header + "1,Cafe\u0301 Rivard,2026-01-01,2026-01-31\n"
                                                               + "2,Caf\u00e9 Rivard,2026-05-01,2026-05-31\n")),
               rejection(load_periods, csv_file("joiner.csv", header + "1,Ali\u200creza Stone,2026-01-01,2026-01-31\n"))],
              [(2, "case.csv row 3: customer 'brightside dental' is also written 'Brightside Dental'; "
                   "one spelling per customer, or the cover comes out split"),
               (2, "noname.csv row 3: customer is blank"),
               (0, [(1, "Brightside Dental", "2026-01-01", "2026-03-31"),
                    (2, "Brightside Dental", "2026-05-01", "2026-05-31")]),
               (0, [(1, "Caf\u00e9 Rivard", "2026-01-01", "2026-01-31"),
                    (2, "Caf\u00e9 Rivard", "2026-05-01", "2026-05-31")]),
               (0, [(1, "Ali\u200creza Stone", "2026-01-01", "2026-01-31")])])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the merge queries against a period log, the sample by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--periods", type=Path, default=None, help="path to an alternate period log CSV")
    args = parser.parse_args()
    # Reports are printed as UTF-8, since output piped or redirected on
    # Windows otherwise falls back to a codepage that cannot print all text.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    given = args.periods is not None
    args.periods = args.periods or PERIODS_CSV
    if not args.periods.is_file():
        if given:
            parser.error(f"--periods: '{args.periods}' is not a file")
        parser.error(f"the sample file '{args.periods}' is missing")
    if args.test and args.periods.resolve() != PERIODS_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample log; run it without --periods")

    db = new_db(load_periods(args.periods))
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
