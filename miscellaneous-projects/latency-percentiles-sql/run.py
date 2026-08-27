"""Load the sample request log into SQLite and run the percentile queries.

Usage:
    python run.py                                    run every query in sql/
    python run.py --test                             run the assertion suite
    python run.py --requests data/other.csv          load a different log
"""

import argparse
import csv
import io
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
REQUESTS_CSV = HERE / "data" / "requests.csv"
SQL_DIR = HERE / "sql"


def fail(path, row_num, message):
    print(f"{path.name} row {row_num}: {message}", file=sys.stderr)
    sys.exit(2)


def fail_file(path, message):
    print(f"{Path(path).name}: {message}", file=sys.stderr)
    sys.exit(2)


def read_csv(path):
    # utf-8-sig strips the byte-order mark that Excel puts on its CSV exports.
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except OSError as err:
        fail_file(path, err.strerror or "cannot be read")
    except UnicodeDecodeError:
        fail_file(path, "is not UTF-8 text")
    return io.StringIO(text, newline="")


def valid_timestamp(value):
    # Round-trip so non-zero-padded parts like 8:05:00 are rejected;
    # strptime accepts them but SQLite's date functions return NULL on them.
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        return datetime.strptime(value, fmt).strftime(fmt) == value
    except (ValueError, TypeError):
        return False


def load_requests(path):
    rows = []
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["endpoint", "request_ts", "duration_ms"]:
            fail(path, 1, f"expected columns endpoint,request_ts,duration_ms, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            endpoint = (row["endpoint"] or "").strip()
            if not endpoint.startswith("/"):
                fail(path, i, f"endpoint {row['endpoint']!r} must start with /")
            if not valid_timestamp(row["request_ts"]):
                fail(path, i, f"request_ts {row['request_ts']!r} is not YYYY-MM-DD HH:MM:SS")
            try:
                duration = int(row["duration_ms"])
            except (ValueError, TypeError):
                fail(path, i, f"duration_ms {row['duration_ms']!r} is not an integer")
            if not 0 < duration < 10 ** 9:
                fail(path, i, f"duration_ms {duration} is out of range")
            rows.append((endpoint, row["request_ts"], duration))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(requests_path):
    requests = load_requests(requests_path)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE requests (endpoint TEXT NOT NULL, request_ts TEXT NOT NULL, duration_ms INTEGER NOT NULL)")
    db.executemany("INSERT INTO requests VALUES (?, ?, ?)", requests)
    return db


def print_table(headers, rows):
    cells = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) if cells else len(h)
              for i, h in enumerate(headers)]
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print("  ".join("-" * w for w in widths))
    for row in cells:
        print("  ".join(row[i].ljust(widths[i]) for i in range(len(headers))))


def run_query(db, sql_path):
    cursor = db.execute(sql_path.read_text(encoding="utf-8"))
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
        nonlocal failures
        if got == want:
            print(f"PASS  {label}")
        else:
            failures += 1
            print(f"FAIL  {label}\n      got:  {got!r}\n      want: {want!r}")

    check("requests loaded",
          db.execute("SELECT COUNT(*) FROM requests").fetchone()[0], 36)

    _, summary = run_query(db, SQL_DIR / "01-endpoint-summary.sql")
    check("endpoint summaries",
          summary,
          [("/api/export", 4, 1200, 1550.0, 2000),
           ("/api/login", 11, 30, 58.36, 250),
           ("/api/search", 21, 40, 133.52, 900)])

    _, ranked = run_query(db, SQL_DIR / "02-ranked-durations.sql")
    check("search median rank sits on the tie",
          [r[1] for r in ranked if r[0] == "/api/search" and r[2] in (10, 11)],
          [80, 80])

    _, math = run_query(db, SQL_DIR / "03-percentile-math.sql")
    check("percentile rows", len(math), 9)
    check("search p99 blends 400 and 900 at 0.8",
          [(r[2], r[3], r[4], r[5]) for r in math if r[0] == "/api/search" and r[1] == "p99"],
          [(400, 900, 0.8, 800.0)])
    check("login p99 blends 50 and 250 at 0.9",
          [(r[4], r[5]) for r in math if r[0] == "/api/login" and r[1] == "p99"],
          [(0.9, 230.0)])
    check("export p50 is the midpoint of a tiny sample",
          [(r[4], r[5]) for r in math if r[0] == "/api/export" and r[1] == "p50"],
          [(0.5, 1500.0)])

    _, grid = run_query(db, SQL_DIR / "04-percentile-grid.sql")
    check("percentile grid",
          grid,
          [("/api/export", 4, "1550.0", "1500.0", "1880.0", "1988.0"),
           ("/api/login", 11, "58.4", "40.0", "50.0", "230.0"),
           ("/api/search", 21, "133.5", "80.0", "150.0", "800.0")])

    _, slowest = run_query(db, SQL_DIR / "05-slowest-requests.sql")
    check("top three slowest per endpoint",
          [(r[0], r[1], r[2]) for r in slowest],
          [("/api/export", 1, 2000), ("/api/export", 2, 1600), ("/api/export", 3, 1400),
           ("/api/login", 1, 250), ("/api/login", 2, 50), ("/api/login", 3, 46),
           ("/api/search", 1, 900), ("/api/search", 2, 400), ("/api/search", 3, 150)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the percentile queries against the sample request log.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--requests", type=Path, default=REQUESTS_CSV, help="path to an alternate request CSV")
    args = parser.parse_args()

    db = build_db(args.requests)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
