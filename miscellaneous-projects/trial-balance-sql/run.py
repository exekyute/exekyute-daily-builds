"""Load the chart, journal, and draft journal into SQLite and run the queries.

Usage:
    python run.py                                  run every query in sql/
    python run.py --test                           run the assertion suite
    python run.py --journal data/other.csv         load a different posted journal
    python run.py --draft data/other.csv           check a different draft journal
"""

import argparse
import csv
import io
import re
import sqlite3
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

HERE = Path(__file__).parent
ACCOUNTS_CSV = HERE / "data" / "accounts.csv"
JOURNAL_CSV = HERE / "data" / "journal.csv"
DRAFT_CSV = HERE / "data" / "draft-journal.csv"
SQL_DIR = HERE / "sql"
ACCOUNT_TYPES = ("asset", "liability", "equity", "revenue", "expense")


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


def valid_date(value):
    # Round-trip so non-zero-padded dates are rejected; strptime accepts them
    # but SQLite's date functions return NULL on them.
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") == value
    except (ValueError, TypeError):
        return False


def parse_id(path, row_num, label, raw):
    # Plain ASCII digits only: Python's int() would quietly read '1_0' as 10.
    value = (raw or "").strip()
    if not re.fullmatch(r"[0-9]+", value) or int(value) == 0 or int(value) >= 2 ** 63:
        fail(path, row_num, f"{label} {raw!r} is not a usable id")
    return int(value)


def parse_cents(path, row_num, label, raw):
    # Money loads as integer cents so floats never touch a sum.
    try:
        amount = Decimal(raw)
    except (InvalidOperation, TypeError):
        fail(path, row_num, f"{label} {raw!r} is not a number")
    if not amount.is_finite():
        fail(path, row_num, f"{label} {raw!r} is not a finite number")
    cents = amount.scaleb(2)
    if cents != cents.to_integral_value():
        fail(path, row_num, f"{label} {raw!r} has more than 2 decimal places")
    if amount <= 0:
        fail(path, row_num, f"{label} {raw!r} must be greater than zero")
    if cents > Decimal(10) ** 15:
        fail(path, row_num, f"{label} {raw!r} is beyond any plausible posting")
    return int(cents)


def load_accounts(path):
    rows, seen = [], set()
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != ["account_code", "name", "type"]:
            fail(path, 1, f"expected columns account_code,name,type, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            if any(v is None for v in row.values()):
                fail(path, i, "has fewer fields than the header")
            code = parse_id(path, i, "account_code", row["account_code"])
            if code in seen:
                fail(path, i, f"duplicate account_code {code}")
            seen.add(code)
            if not (row["name"] or "").strip():
                fail(path, i, "name is empty")
            acct_type = (row["type"] or "").strip()
            if acct_type not in ACCOUNT_TYPES:
                fail(path, i, f"type {row['type']!r} is not one of {', '.join(ACCOUNT_TYPES)}")
            rows.append((code, row["name"].strip(), acct_type))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def load_journal(path, known_codes, strict):
    rows, entry_dates = [], {}
    with read_csv(path) as f:
        reader = csv.DictReader(f)
        expected = ["entry_id", "entry_date", "account_code", "debit", "credit", "memo"]
        if reader.fieldnames != expected:
            fail(path, 1, f"expected columns {','.join(expected)}, got {reader.fieldnames}")
        for row in reader:
            i = reader.line_num
            if None in row:
                fail(path, i, "has more fields than the header")
            if any(v is None for v in row.values()):
                fail(path, i, "has fewer fields than the header")
            entry_id = parse_id(path, i, "entry_id", row["entry_id"])
            if not valid_date(row["entry_date"]):
                fail(path, i, f"entry_date {row['entry_date']!r} is not YYYY-MM-DD")
            if entry_dates.setdefault(entry_id, row["entry_date"]) != row["entry_date"]:
                fail(path, i, f"entry {entry_id} carries two different dates")
            code = parse_id(path, i, "account_code", row["account_code"])
            if strict and code not in known_codes:
                fail(path, i, f"account_code {code} is not in the chart")
            debit_raw = (row["debit"] or "").strip()
            credit_raw = (row["credit"] or "").strip()
            if bool(debit_raw) == bool(credit_raw):
                fail(path, i, "a line needs exactly one of debit or credit")
            debit = parse_cents(path, i, "debit", debit_raw) if debit_raw else None
            credit = parse_cents(path, i, "credit", credit_raw) if credit_raw else None
            rows.append((entry_id, row["entry_date"], code, debit, credit, (row["memo"] or "").strip()))
    if not rows:
        fail(path, 1, "no data rows after the header")
    if sum((r[3] or 0) + (r[4] or 0) for r in rows) > 10 ** 15:
        fail_file(path, "totals are beyond anything plausible")
    return rows


def build_db(accounts_path, journal_path, draft_path):
    accounts = load_accounts(accounts_path)
    codes = {a[0] for a in accounts}
    journal = load_journal(journal_path, codes, strict=True)
    draft = load_journal(draft_path, codes, strict=False)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE accounts (account_code INTEGER PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL)")
    for table in ("journal", "draft_journal"):
        db.execute(f"CREATE TABLE {table} (entry_id INTEGER NOT NULL, entry_date TEXT NOT NULL, account_code INTEGER NOT NULL, debit_cents INTEGER, credit_cents INTEGER, memo TEXT)")
    db.executemany("INSERT INTO accounts VALUES (?, ?, ?)", accounts)
    db.executemany("INSERT INTO journal VALUES (?, ?, ?, ?, ?, ?)", journal)
    db.executemany("INSERT INTO draft_journal VALUES (?, ?, ?, ?, ?, ?)", draft)
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

    counts = tuple(db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                   for t in ("accounts", "journal", "draft_journal"))
    check("rows loaded (accounts, journal lines, draft lines)", counts, (10, 25, 7))

    _, chart = run_query(db, SQL_DIR / "01-chart-and-activity.sql")
    check("normal sides derived from type",
          {r[1]: r[3] for r in chart if r[1] in ("Cash", "Sales Revenue", "Rent Expense", "Owner Capital")},
          {"Cash": "debit", "Sales Revenue": "credit", "Rent Expense": "debit", "Owner Capital": "credit"})

    _, entries = run_query(db, SQL_DIR / "02-entry-balance.sql")
    check("twelve entries, all balanced",
          (len(entries), {r[7] for r in entries}), (12, {"balanced"}))
    check("the compound entry posts three lines",
          [r[3] for r in entries if r[0] == 12], [3])

    _, balances = run_query(db, SQL_DIR / "03-account-balances.sql")
    check("key balances land on the right side",
          {r[1]: (r[3], r[4]) for r in balances
           if r[1] in ("Cash", "Inventory", "Accounts Payable", "Sales Revenue")},
          {"Cash": ("7920.00", ""), "Inventory": ("760.00", ""),
           "Accounts Payable": ("", "900.00"), "Sales Revenue": ("", "5290.00")})
    check("no contra balances this month",
          [r[5] for r in balances if r[5] not in ("",)], [])

    _, tb = run_query(db, SQL_DIR / "04-trial-balance.sql")
    check("trial balance rows", len(tb), 11)
    check("the totals row ties",
          [r[2:] for r in tb if r[1] == "TOTAL"],
          [("21190.00", "21190.00", "in balance")])

    _, issues = run_query(db, SQL_DIR / "05-journal-checks.sql")
    check("draft journal issues",
          [(r[0], r[1]) for r in issues],
          [("single-line entry", 4), ("unbalanced entry", 2),
           ("unbalanced entry", 4), ("unknown account", 3)])
    check("the 50.00 gap is named",
          [r[2] for r in issues if r[0] == "unbalanced entry" and r[1] == 2],
          ["debits 500.00 vs credits 450.00"])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the trial balance queries against the sample books.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--accounts", type=Path, default=ACCOUNTS_CSV, help="path to an alternate chart of accounts CSV")
    parser.add_argument("--journal", type=Path, default=JOURNAL_CSV, help="path to an alternate posted journal CSV")
    parser.add_argument("--draft", type=Path, default=DRAFT_CSV, help="path to an alternate draft journal CSV")
    args = parser.parse_args()

    db = build_db(args.accounts, args.journal, args.draft)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
