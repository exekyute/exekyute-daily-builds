"""Load the daily metric series into SQLite and run the anomaly queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --metrics data/other.csv          load a different series
"""

import argparse
import csv
import io
import math
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
METRICS_CSV = HERE / "data" / "daily_metrics.csv"
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


def parse_date(path, row_num, raw):
    # Round-trip so non-zero-padded dates are rejected; strptime accepts them
    # but SQLite's date functions return NULL on them.
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
        if parsed.strftime("%Y-%m-%d") != raw:
            raise ValueError
    except (ValueError, TypeError):
        fail(path, row_num, f"metric_date {raw!r} is not YYYY-MM-DD")
    return parsed.date()


def load_metrics(path):
    rows, prev = [], None
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["metric_date", "orders"]:
            fail(path, 1, f"expected columns metric_date,orders, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            if any(v is None for v in row.values()):
                fail(path, i, "has fewer fields than the header")
            day = parse_date(path, i, row["metric_date"])
            # ROWS windows count rows, not days, so the series must be one
            # row per day with no gaps or the 14-row window quietly stops
            # meaning 14 days.
            if prev is not None and day != prev + timedelta(days=1):
                fail(path, i, f"dates must be consecutive; expected {(prev + timedelta(days=1)).isoformat()}")
            prev = day
            raw = (row["orders"] or "").strip()
            if not re.fullmatch(r"[0-9]+", raw):
                fail(path, i, f"orders {row['orders']!r} is not a whole number")
            orders = int(raw)
            # Capped where the squares stay exactly representable as floats:
            # beyond this scale the mean-of-squares variance cancels badly.
            if orders >= 10 ** 7:
                fail(path, i, f"orders {orders} is beyond anything plausible for a daily count")
            rows.append((row["metric_date"], orders))
    if not rows:
        fail(path, 1, "no data rows after the header")
    if len(rows) < 15:
        fail_file(path, f"a 14-day trailing window needs at least 15 days, found {len(rows)}")
    return rows


def build_db(metrics_path):
    metrics = load_metrics(metrics_path)
    db = sqlite3.connect(":memory:")
    try:
        db.execute("SELECT sqrt(1.0)")
    except sqlite3.OperationalError:
        # SQLite built without math functions: supply sqrt from Python with
        # the built-in's exact semantics, NULL in and negative in both give
        # NULL out, because the empty first window feeds it NULL every run.
        def _sqrt(x):
            if x is None or x < 0:
                return None
            return math.sqrt(x)
        db.create_function("sqrt", 1, _sqrt, deterministic=True)
    db.execute("CREATE TABLE daily_metrics (metric_date TEXT PRIMARY KEY, orders INTEGER NOT NULL)")
    db.executemany("INSERT INTO daily_metrics VALUES (?, ?)", metrics)
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

    check("days loaded",
          db.execute("SELECT COUNT(*) FROM daily_metrics").fetchone()[0], 44)

    _, shape = run_query(db, SQL_DIR / "01-series-shape.sql")
    check("extremes with their dates",
          [(r[4], r[5], r[6], r[7]) for r in shape],
          [("2026-08-17", 70, "2026-08-10", 130)])

    _, baseline = run_query(db, SQL_DIR / "02-rolling-baseline.sql")
    check("first day has an empty window",
          [(r[2],) for r in baseline if r[0] == "2026-07-20"], [(0,)])
    check("the alternating stretch gives mean 100 sigma 5",
          [(r[3], r[4]) for r in baseline if r[0] == "2026-08-03"],
          [(100.0, 5.0)])

    _, scores = run_query(db, SQL_DIR / "03-z-scores.sql")
    check("scored days have full windows only", len(scores), 30)
    check("an ordinary day scores minus one",
          [r[4] for r in scores if r[0] == "2026-08-03"], [-1.0])
    check("the spike scores exactly six sigma",
          [(r[4], r[5]) for r in scores if r[0] == "2026-08-10"], [(6.0, "anomaly")])
    check("the drop scores against its contaminated window",
          [(r[4], r[5]) for r in scores if r[0] == "2026-08-17"], [(-3.46, "anomaly")])
    check("the constant fortnight flags flat, not infinite",
          [(r[4], r[5]) for r in scores if r[0] == "2026-09-01"], [(None, "flat baseline")])

    _, anomalies = run_query(db, SQL_DIR / "04-anomalies.sql")
    check("exactly three flagged days",
          [(r[0], r[3]) for r in anomalies],
          [("2026-08-10", "spike"), ("2026-08-17", "drop"), ("2026-09-01", "flat baseline")])

    _, context = run_query(db, SQL_DIR / "05-anomaly-context.sql")
    check("the spike's band and exceedance",
          [(r[2], r[3]) for r in context if r[0] == "2026-08-10"],
          [("90.0 to 110.0", "20.0 above the band")])
    check("the flat day gets no fake band",
          [r[2] for r in context if r[0] == "2026-09-01"],
          ["no band: baseline never moved"])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the anomaly queries against the sample daily series.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--metrics", type=Path, default=METRICS_CSV, help="path to an alternate metrics CSV")
    args = parser.parse_args()

    db = build_db(args.metrics)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
