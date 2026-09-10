"""Load the sensor list and reading log into SQLite and run the forward-fill queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --sensors data/other.csv          load a different sensor list
    python run.py --readings data/other.csv         load a different reading log
"""

import argparse
import csv
import io
import re
import sqlite3
import sys
import unicodedata
from datetime import datetime
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent
SENSORS_CSV = HERE / "data" / "sensors.csv"
READINGS_CSV = HERE / "data" / "readings.csv"
SQL_DIR = HERE / "sql"


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
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if reader.fieldnames is None:
        fail_file(path, "is empty")
    if reader.fieldnames != columns:
        fail(path, 1, f"expected columns {','.join(columns)}, got {reader.fieldnames}")
    return reader


def records(path, reader):
    # Yields each record with the line it STARTED on. reader.line_num is where
    # a record ended, which for a stray quote is the end of the file, so an
    # error would otherwise point at the wrong line and quote everything after.
    start = reader.line_num + 1
    try:
        for row in reader:
            yield start, row
            start = reader.line_num + 1
    except csv.Error as err:
        fail(path, start, f"cannot be parsed ({err}); most likely a quote that never closes")


def cell(path, row_num, row, column, required=True):
    if None in row:
        fail(path, row_num, "has more fields than the header")
    if any(v is None for v in row.values()):
        fail(path, row_num, "has fewer fields than the header")
    # A field spanning lines is almost always an unclosed quote that has
    # swallowed the rows after it, so it is refused rather than joined up.
    if any(ch in row[column] for ch in "\r\n"):
        fail(path, row_num, f"{column} runs across more than one line; "
                            "most likely a quote that never closes")
    value = unicodedata.normalize("NFC", " ".join(row[column].split()))
    if required and not value:
        fail(path, row_num, f"{column} is empty")
    return value


def parse_tenths(path, row_num, column, raw):
    # Held as integer tenths of a degree so no comparison against a limit
    # ever depends on how a float happened to round.
    if not re.fullmatch(r"-?[0-9]+(\.[0-9])?", raw):
        fail(path, row_num, f"{column} {raw!r} is not a temperature to one decimal place")
    tenths = int(Decimal(raw) * 10)
    if abs(tenths) >= 10000:
        fail(path, row_num, f"{column} {raw!r} is beyond anything a cold-chain sensor reports")
    return tenths


def load_sensors(path):
    rows, seen = [], {}
    reader = read_csv(path, ["sensor_id", "location", "max_celsius"])
    for i, row in records(path, reader):
        sensor = cell(path, i, row, "sensor_id")
        # Readings match sensor ids exactly, so two ids differing only by
        # case would load as two sensors and split one sensor's readings
        # between them; refuse the second spelling rather than guess.
        first = seen.get(sensor.casefold())
        if first == sensor:
            fail(path, i, f"sensor_id {sensor!r} appears twice")
        if first is not None:
            fail(path, i, f"sensor_id {sensor!r} matches {first!r} apart from letter case")
        seen[sensor.casefold()] = sensor
        location = cell(path, i, row, "location")
        limit = parse_tenths(path, i, "max_celsius", cell(path, i, row, "max_celsius"))
        rows.append((sensor, location, limit))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def load_readings(path, sensor_ids):
    rows, seen = [], set()
    reader = read_csv(path, ["sensor_id", "reading_at", "celsius"])
    for i, row in records(path, reader):
        sensor = cell(path, i, row, "sensor_id")
        if sensor not in sensor_ids:
            fail(path, i, f"sensor_id {sensor!r} is not in the sensor list")
        stamp = cell(path, i, row, "reading_at")
        # The shape is checked first so a stamp missing its zero padding is
        # refused: it would sort out of place as text and strftime would
        # return NULL. A stamp with the right shape can still name a moment
        # that never existed, which is a different complaint.
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}", stamp):
            fail(path, i, f"reading_at {stamp!r} is not YYYY-MM-DD HH:MM")
        try:
            datetime.strptime(stamp, "%Y-%m-%d %H:%M")
        except ValueError:
            fail(path, i, f"reading_at {stamp!r} is not a real date and time")
        # Two rows at one instant make "the last reading before now" mean two
        # different values, so a sensor gets at most one row per moment.
        if (sensor, stamp) in seen:
            fail(path, i, f"{sensor} already has a row at {stamp}; "
                          "the last reading before any later moment would be ambiguous")
        seen.add((sensor, stamp))
        # A blank temperature is the point of the log, a moment the sensor
        # was polled and reported nothing, so it loads as NULL.
        raw = cell(path, i, row, "celsius", required=False)
        tenths = parse_tenths(path, i, "celsius", raw) if raw else None
        rows.append((sensor, stamp, tenths))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def build_db(sensors_path, readings_path):
    sensors = load_sensors(sensors_path)
    readings = load_readings(readings_path, {s for s, _, _ in sensors})
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE sensors (sensor_id TEXT PRIMARY KEY, location TEXT NOT NULL, "
               "max_tenths INTEGER NOT NULL)")
    db.execute("CREATE TABLE readings (sensor_id TEXT NOT NULL, reading_at TEXT NOT NULL, "
               "tenths INTEGER, PRIMARY KEY (sensor_id, reading_at))")
    db.executemany("INSERT INTO sensors VALUES (?, ?, ?)", sensors)
    db.executemany("INSERT INTO readings VALUES (?, ?, ?)", readings)
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
        nonlocal failures
        if got == want:
            print(f"PASS  {label}")
        else:
            failures += 1
            print(f"FAIL  {label}\n      got:  {got!r}\n      want: {want!r}")

    def at(hour):
        return f"2026-09-09 {hour:02d}:00"

    check("both tables loaded",
          (db.execute("SELECT COUNT(*) FROM sensors").fetchone()[0],
           db.execute("SELECT COUNT(*) FROM readings").fetchone()[0]),
          (2, 24))

    _, shape = run_query(db, SQL_DIR / "01-log-shape.sql")
    check("twelve rows a sensor, the cooler missing eight of them",
          shape,
          [("CLR-1", "Cooler bay", "4.0", 12, 4, 8, at(0), at(11)),
           ("FRZ-1", "Freezer bay", "-15.0", 12, 6, 6, at(0), at(11))])

    _, lag = run_query(db, SQL_DIR / "02-lag-falls-short.sql")
    check("LAG fills four of the twelve fillable gaps and leaves eight blank",
          (len(lag), sum(r[4] == "filled" for r in lag), sum(r[4] == "left blank" for r in lag)),
          (12, 4, 8))
    check("LAG is never wrong, only short: every value it fills is the right one",
          [r for r in lag if r[4] == "filled" and r[2] != r[3]], [])

    _, fill = run_query(db, SQL_DIR / "03-forward-fill.sql")
    check("every row of the log comes back", len(fill), 24)
    check("the counter advances only on real readings",
          [r[3] for r in fill if r[0] == "FRZ-1"],
          [1, 2, 2, 3, 3, 3, 3, 4, 5, 5, 5, 6])
    check("a run of three carries the reading before it, and ages as it goes",
          [(r[1], r[4], r[5], r[6]) for r in fill if r[0] == "FRZ-1" and r[1] in (at(4), at(5), at(6))],
          [(at(4), "-17.9", at(3), 60), (at(5), "-17.9", at(3), 120), (at(6), "-17.9", at(3), 180)])
    check("rows before a sensor's first reading have nothing to carry",
          [(r[1], r[4], r[6]) for r in fill if r[0] == "CLR-1" and r[3] == 0],
          [(at(0), "", None), (at(1), "", None)])
    check("the one-pass fill agrees with the correlated answer on every fillable gap",
          sorted((r[0], r[1], r[4]) for r in fill if r[2] == "" and r[4] != ""),
          sorted((r[0], r[1], r[3]) for r in lag))

    _, cap = run_query(db, SQL_DIR / "04-staleness-cap.sql")
    check("a two-hour cap splits the log four ways and the four add up",
          cap,
          [("CLR-1", 4, 2, 4, 2, 12),
           ("FRZ-1", 6, 5, 1, 0, 12)])

    _, blind = run_query(db, SQL_DIR / "05-blind-spots.sql")
    check("three blind spots, and the cooler came back from one over its limit",
          [(r[0], r[2], r[3], r[4], r[5], r[6], r[8], r[10]) for r in blind],
          [("CLR-1", "dark start", at(0), at(1), 2, "", "3.4", "within limit"),
           ("CLR-1", "too stale", at(6), at(9), 4, "3.5", "6.8", "breach"),
           ("FRZ-1", "too stale", at(6), at(6), 1, "-17.9", "-17.6", "within limit")])

    # The sample is polled hourly, so on it the age of a carried reading is
    # always sixty minutes a row and a clock cap cannot be told from a row
    # cap. This log is uneven on purpose: the row at 03:20 is only the second
    # after its reading and is still too stale, because 200 minutes have gone.
    uneven = sqlite3.connect(":memory:")
    uneven.execute("CREATE TABLE sensors (sensor_id TEXT PRIMARY KEY, location TEXT NOT NULL, "
                   "max_tenths INTEGER NOT NULL)")
    uneven.execute("CREATE TABLE readings (sensor_id TEXT NOT NULL, reading_at TEXT NOT NULL, "
                   "tenths INTEGER, PRIMARY KEY (sensor_id, reading_at))")
    uneven.execute("INSERT INTO sensors VALUES ('S-1', 'Test bay', 40)")
    uneven.executemany("INSERT INTO readings VALUES (?, ?, ?)",
                       [("S-1", "2026-09-09 00:00", 30),
                        ("S-1", "2026-09-09 00:20", None),
                        ("S-1", "2026-09-09 03:20", None)])
    _, clock = run_query(uneven, SQL_DIR / "04-staleness-cap.sql")
    check("the cap is measured on the clock: two rows after a reading can already be too stale",
          clock, [("S-1", 1, 1, 1, 0, 3)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the forward-fill queries against the sample log.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--sensors", type=Path, default=SENSORS_CSV, help="path to the sensor list")
    parser.add_argument("--readings", type=Path, default=READINGS_CSV, help="path to the reading log")
    args = parser.parse_args()
    # The loader accepts any UTF-8 text, so the reports have to be able to
    # print it. Output piped or redirected on Windows falls back to a
    # codepage that cannot, even where the console itself would manage.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    given = (args.sensors, args.readings)
    for flag, path in zip(("sensors", "readings"), given):
        if not path.is_file():
            parser.error(f"--{flag}: '{path}' is not a file")
    if args.test and any(g.resolve() != d.resolve() for g, d in zip(given, (SENSORS_CSV, READINGS_CSV))):
        parser.error("--test checks hand-computed answers for the sample log; run it without a file override")

    db = build_db(*given)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
