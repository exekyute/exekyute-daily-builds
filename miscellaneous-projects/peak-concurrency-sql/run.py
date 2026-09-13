"""Load the help desk call log into SQLite and run the concurrency queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --calls data/other.csv            load a different call log
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
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
CALLS_CSV = HERE / "data" / "calls.csv"
SQL_DIR = HERE / "sql"
COLUMNS = ["call_id", "started_at", "ended_at"]


def fail(path, row_num, message):
    print(f"{path.name} row {row_num}: {message}", file=sys.stderr)
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
            yield start, dict(zip(columns, fields))
            start = reader.line_num + 1
    except csv.Error as err:
        fail(path, start, f"cannot be parsed ({err}); most likely a stray quote")


def parse_stamp(path, row_num, name, raw):
    # Shape first, since the queries compare times as text and only a fixed
    # YYYY-MM-DD HH:MM sorts in time order; then whether it is a real time.
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}", raw):
        fail(path, row_num, f"{name} {raw!r} is not YYYY-MM-DD HH:MM")
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M")
    except ValueError:
        fail(path, row_num, f"{name} {raw!r} is not a real date and time")


def load_calls(path):
    rows, seen = [], set()
    reader = read_csv(path, COLUMNS)
    for i, row in records(path, reader, COLUMNS):
        raw_id = row["call_id"].strip()
        if not re.fullmatch(r"[1-9][0-9]{0,17}", raw_id):
            fail(path, i, f"call_id {raw_id!r} is not a call id: 1 to 18 digits, 0 to 9, no leading zero")
        call_id = int(raw_id)
        if call_id in seen:
            fail(path, i, f"call_id {call_id} appears twice; the log holds one row per call")
        seen.add(call_id)
        started_raw = row["started_at"].strip()
        ended_raw = row["ended_at"].strip()
        started = parse_stamp(path, i, "started_at", started_raw)
        ended = parse_stamp(path, i, "ended_at", ended_raw)
        # ended_at is the first minute the line was free, so a call has to
        # end at least a minute after it starts to have held a line at all.
        if ended < started:
            fail(path, i, f"call {call_id} ends at {ended_raw}, before it starts at {started_raw}")
        if ended == started:
            fail(path, i, f"call {call_id} ends the minute it starts, so it never held a line")
        if ended - started > timedelta(days=1):
            fail(path, i, f"call {call_id} runs longer than a day; most likely a mistyped date")
        rows.append((call_id, started_raw, ended_raw))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def new_db(rows):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE calls (call_id INTEGER PRIMARY KEY, "
               "started_at TEXT NOT NULL, ended_at TEXT NOT NULL)")
    db.executemany("INSERT INTO calls VALUES (?, ?, ?)", rows)
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

    day = "2026-09-08 "
    check("twenty calls loaded",
          db.execute("SELECT COUNT(*) FROM calls").fetchone()[0], 20)

    _, shape = run_query(db, SQL_DIR / "01-call-log-shape.sql")
    check("seven hours from first call to last hang-up, 525 call minutes",
          shape, [(20, day + "09:05", day + "16:05", 420, 525)])

    _, naive = run_query(db, SQL_DIR / "02-naive-peak.sql")
    check("the naive sweep peaks at six, on the 10:25 handoff",
          lambda: max(naive, key=lambda r: r[4]), (10, day + "10:25", "start", 108, 6))
    check("the naive sweep puts a caller on hold at 13:30",
          [r for r in naive if r[1] == day + "13:30"], [(26, day + "13:30", "start", 115, 4)])

    _, timeline = run_query(db, SQL_DIR / "03-timeline.sql")
    check("the true peak is five", lambda: max(r[2] for r in timeline), 5)
    check("both handoff minutes net to zero and drop out of the timeline",
          [r for r in timeline if r[0] in (day + "10:25", day + "13:30")], [])
    check("two calls starting in the same minute raise the count by two in one row",
          lambda: [(r[0], r[2]) for r in timeline if day + "10:52" <= r[0] <= day + "11:05"],
          [(day + "10:52", 0), (day + "11:05", 2)])
    check("the timeline covers the whole span and ends at 0",
          lambda: (sum(r[3] for r in timeline[:-1]), timeline[-1]),
          (420, (day + "16:05", None, 0, None)))

    _, load = run_query(db, SQL_DIR / "04-average-load.sql")
    check("averaging the timeline's rows overstates the load against the clock",
          load, [(34, "1.74", "1.25", "1.25")])

    _, over = run_query(db, SQL_DIR / "05-over-capacity.sql")
    check("two stretches over three agents, the first peaking at five",
          over, [(day + "10:12", day + "10:36", 24, 5, 36), (day + "14:52", day + "15:00", 8, 4, 8)])

    # Logs built for cases the sample does not reach on its own.
    def log(calls):
        return new_db([(n, start, end) for n, (start, end) in enumerate(calls, 1)])

    chain = log([(day + "09:00", day + "09:30"), (day + "09:30", day + "10:00"),
                 (day + "10:00", day + "10:30")])
    check("three back-to-back calls keep one line busy for 90 minutes",
          run_query(chain, SQL_DIR / "03-timeline.sql")[1],
          [(day + "09:00", day + "10:30", 1, 90), (day + "10:30", None, 0, None)])

    # Over three, back to exactly three, then over again: two stretches. Its
    # time-weighted average, 380 minutes over 120, does not come out even
    # the way the sample's 1.25 does, so both minute columns must round it.
    dip = log([(day + "09:00", day + "11:00")] * 3
              + [(day + "09:10", day + "09:20"), (day + "09:30", day + "09:40")])
    check("a dip to exactly three between two busy spells keeps them as two stretches",
          run_query(dip, SQL_DIR / "05-over-capacity.sql")[1],
          [(day + "09:10", day + "09:20", 10, 4, 10), (day + "09:30", day + "09:40", 10, 4, 10)])
    check("both time-weighted columns give 380 minutes over 120 as 3.17",
          run_query(dip, SQL_DIR / "04-average-load.sql")[1], [(5, "3.40", "3.17", "3.17")])

    # Five live, then two end and one starts in the same minute. Netted, the
    # count steps from five to four and the stretch stays whole; taken one
    # event at a time with ends first, it would pass through three.
    mixed = log([(day + "09:00", day + "10:00")] * 3 + [(day + "09:05", day + "09:30")] * 2
                + [(day + "09:30", day + "10:00")])
    check("two ends and a start in one minute leave the stretch whole",
          run_query(mixed, SQL_DIR / "05-over-capacity.sql")[1],
          [(day + "09:05", day + "10:00", 55, 5, 80)])

    # 201 call minutes over a 200-minute span is exactly 1.005, and the float
    # for it sits just below the half, so printf alone would print 1.00.
    half = log([(day + "09:00", day + "12:20"), (day + "10:00", day + "10:01")])
    check("both time-weighted columns round an exact 1.005 up to 1.01",
          run_query(half, SQL_DIR / "04-average-load.sql")[1], [(3, "1.33", "1.01", "1.01")])

    # Queries 01, 03, 04, and 05 each work out minutes on their own, so each
    # runs across midnight. The timeline needs rows at different counts for
    # 04's weighting to show a wrong length: with a single row, any nonzero
    # length gives the same average.
    night = log([("2026-09-08 23:30", "2026-09-09 00:30")] + [("2026-09-08 23:50", "2026-09-09 00:20")] * 4)
    check("calls across midnight keep their lengths in queries 01, 03, 04, and 05",
          [run_query(night, SQL_DIR / name)[1] for name in
           ("01-call-log-shape.sql", "03-timeline.sql", "04-average-load.sql", "05-over-capacity.sql")],
          [[(5, "2026-09-08 23:30", "2026-09-09 00:30", 60, 180)],
           [("2026-09-08 23:30", "2026-09-08 23:50", 1, 20), ("2026-09-08 23:50", "2026-09-09 00:20", 5, 30),
            ("2026-09-09 00:20", "2026-09-09 00:30", 1, 10), ("2026-09-09 00:30", None, 0, None)],
           [(3, "2.33", "3.00", "3.00")],
           [("2026-09-08 23:50", "2026-09-09 00:20", 30, 5, 60)]])

    # The loader, on the included bad file and on a stray quote that closes a
    # line later: that record starts on row 3, though the csv reader is on
    # line 4 by the time it hands the record over.
    def rejection(path):
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                load_calls(path)
        except SystemExit as stop:
            return stop.code, err.getvalue().strip()
        return 0, ""

    check("the bad sample file is refused at row 18",
          rejection(HERE / "data" / "invalid-calls.csv"),
          (2, "invalid-calls.csv row 18: call 111 ends at 2026-09-08 11:40, "
              "before it starts at 2026-09-08 12:06"))
    with tempfile.TemporaryDirectory() as tmp:
        stray = Path(tmp) / "stray-quote.csv"
        with open(stray, "w", encoding="utf-8", newline="") as f:
            f.write("call_id,started_at,ended_at\n"
                    "1,2026-09-08 09:00,2026-09-08 09:30\n"
                    '2,"2026-09-08 09:10,2026-09-08 09:40\n'
                    '3,2026-09-08 09:20,2026-09-08 09:50"\n')
        check("a stray quote is reported on the row where its record starts",
              rejection(stray),
              (2, "stray-quote.csv row 3: a field runs across more than one line; "
                  "most likely a stray quote"))

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the concurrency queries against a call log, the sample by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--calls", type=Path, default=CALLS_CSV, help="path to an alternate call log CSV")
    args = parser.parse_args()
    # Reports are printed as UTF-8, since output piped or redirected on
    # Windows otherwise falls back to a codepage that cannot print all text.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if not args.calls.is_file():
        parser.error(f"--calls: '{args.calls}' is not a file")
    if args.test and args.calls.resolve() != CALLS_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample log; run it without --calls")

    db = new_db(load_calls(args.calls))
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
