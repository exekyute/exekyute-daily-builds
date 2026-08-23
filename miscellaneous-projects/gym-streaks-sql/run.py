"""Load the sample gym data into SQLite and run the streak queries.

Usage:
    python run.py                                  run every query in sql/
    python run.py --test                           run the assertion suite
    python run.py --checkins data/other.csv        load a different check-in file
"""

import argparse
import csv
import io
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
MEMBERS_CSV = HERE / "data" / "members.csv"
CHECKINS_CSV = HERE / "data" / "checkins.csv"
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


def valid_datetime(value, fmt):
    # Round-trip so non-zero-padded parts like 2026-8-1 are rejected;
    # strptime accepts them but SQLite's DATE() returns NULL on them.
    try:
        return datetime.strptime(value, fmt).strftime(fmt) == value
    except (ValueError, TypeError):
        return False


def load_members(path):
    members = []
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["member_id", "name", "joined_date"]:
            fail(path, 1, f"expected columns member_id,name,joined_date, got {reader.fieldnames}")
        seen = set()
        for row in reader:
            i = reader.line_num
            try:
                member_id = int(row["member_id"])
            except (ValueError, TypeError):
                fail(path, i, f"member_id {row['member_id']!r} is not an integer")
            if member_id in seen:
                fail(path, i, f"duplicate member_id {member_id}")
            seen.add(member_id)
            if not (row["name"] or "").strip():
                fail(path, i, "name is empty")
            if not valid_datetime(row["joined_date"], "%Y-%m-%d"):
                fail(path, i, f"joined_date {row['joined_date']!r} is not YYYY-MM-DD")
            members.append((member_id, row["name"].strip(), row["joined_date"]))
    if not members:
        fail(path, 1, "no data rows after the header")
    return members


def load_checkins(path, known_ids):
    checkins = []
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["member_id", "checkin_ts"]:
            fail(path, 1, f"expected columns member_id,checkin_ts, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            try:
                member_id = int(row["member_id"])
            except (ValueError, TypeError):
                fail(path, i, f"member_id {row['member_id']!r} is not an integer")
            if member_id not in known_ids:
                fail(path, i, f"member_id {member_id} has no row in members.csv")
            if not valid_datetime(row["checkin_ts"], "%Y-%m-%d %H:%M"):
                fail(path, i, f"checkin_ts {row['checkin_ts']!r} is not YYYY-MM-DD HH:MM")
            checkins.append((member_id, row["checkin_ts"]))
    if not checkins:
        fail(path, 1, "no data rows after the header")
    return checkins


def build_db(checkins_path):
    members = load_members(MEMBERS_CSV)
    checkins = load_checkins(checkins_path, {m[0] for m in members})
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE members (member_id INTEGER PRIMARY KEY, name TEXT, joined_date TEXT)")
    db.execute("CREATE TABLE checkins (member_id INTEGER REFERENCES members, checkin_ts TEXT)")
    db.executemany("INSERT INTO members VALUES (?, ?, ?)", members)
    db.executemany("INSERT INTO checkins VALUES (?, ?)", checkins)
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

    check("check-in rows loaded",
          db.execute("SELECT COUNT(*) FROM checkins").fetchone()[0], 49)
    check("distinct member-days",
          db.execute("SELECT COUNT(*) FROM (SELECT DISTINCT member_id, DATE(checkin_ts) FROM checkins)").fetchone()[0], 48)

    _, islands = run_query(db, SQL_DIR / "02-streak-islands.sql")
    check("total streak islands", len(islands), 15)
    check("Mara Voss islands",
          [r for r in islands if r[0] == "Mara Voss"],
          [("Mara Voss", "2026-07-20", "2026-08-02", 14),
           ("Mara Voss", "2026-08-15", "2026-08-19", 5)])
    check("Dev Okafor duplicate day counted once",
          [r for r in islands if r[0] == "Dev Okafor" and r[1] == "2026-08-10"],
          [("Dev Okafor", "2026-08-10", "2026-08-14", 5)])

    _, longest = run_query(db, SQL_DIR / "03-longest-streaks.sql")
    check("longest streak per member",
          {name: days for name, _, _, days in longest},
          {"Mara Voss": 14, "Dev Okafor": 5, "Tomas Rehn": 5,
           "Aiko Tanaka": 4, "June Park": 1, "Priya Nair": 1})

    _, current = run_query(db, SQL_DIR / "04-current-streaks.sql")
    check("current streaks on 2026-08-19",
          [(name, days) for name, _, days in current],
          [("Mara Voss", 5), ("Aiko Tanaka", 3)])

    _, lapsed = run_query(db, SQL_DIR / "05-lapsed-members.sql")
    check("lapsed members",
          [(name, days) for name, _, _, days in lapsed],
          [("Noor Haddad", None), ("Priya Nair", 50), ("Tomas Rehn", 42)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the gym streak queries against the sample data.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--checkins", type=Path, default=CHECKINS_CSV, help="path to an alternate check-ins CSV")
    args = parser.parse_args()

    db = build_db(args.checkins)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
