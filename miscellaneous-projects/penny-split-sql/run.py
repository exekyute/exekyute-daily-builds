"""Load the shared bills into SQLite and run the split queries.

Usage:
    python run.py                                              run every query in sql/
    python run.py --test                                       run the assertion suite
    python run.py --bills data/b.csv --splits data/s.csv       load a different bill log
"""

import argparse
import contextlib
import csv
import io
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
BILLS_CSV = HERE / "data" / "bills.csv"
SPLITS_CSV = HERE / "data" / "splits.csv"
SQL_DIR = HERE / "sql"
# Set on the copies of this script that the test run starts to check the
# command line, so that none of them can start the test run again.
CLI_CHECK_MARK = "PENNY_SPLIT_CLI_CHECK"
BILL_COLUMNS = ["bill_id", "bill", "amount"]
SPLIT_COLUMNS = ["bill_id", "department", "weight"]
# A bill runs up to 9999999.99 and its weights add up to at most 1000000,
# so an amount in cents times a weight stays under 10**15. That keeps the
# whole-number arithmetic in the queries exact, and keeps the floating-point
# share that queries 02 and 04 round exact enough to round the same way.
MOST_WEIGHT = 1_000_000
# Invisible characters that belong in a name: the zero-width joiner and
# non-joiner that Persian and Sinhala spelling needs, and the marks that set
# writing direction around a name in Arabic or Hebrew.
NAME_MARKS = {"\u200c", "\u200d", "\u200e", "\u200f", "\u061c"}
# Invisible characters outside the control and format categories that the
# loader refuses as well: the combining grapheme joiner, the Hangul fillers,
# and the Khmer inherent vowels.
BLANK_MARKS = {"\u034f", "\u115f", "\u1160", "\u17b4", "\u17b5", "\u3164", "\uffa0"}


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
    # skipinitialspace, so a space after a comma does not turn the quote
    # that follows into part of the field.
    reader = csv.reader(io.StringIO(text, newline=""), strict=True, skipinitialspace=True)
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
            # A line holding nothing but spaces is as blank as an empty one.
            if len(fields) <= 1 and not "".join(fields).strip(" "):
                start = reader.line_num + 1
                continue
            if any(ch in f for f in fields for ch in "\r\n"):
                fail(path, start, "a field runs across more than one line; "
                                  "most likely a stray quote")
            # An invisible character in a department name, a zero-width
            # space among them, would split one department in two without
            # showing anything on the page. Cf holds most of them, and
            # BLANK_MARKS a few that sit in other categories. The joiners
            # and the direction marks are let through, since names in
            # Persian, Sinhala and Hebrew are spelled with them.
            bad = next((ch for f in fields for ch in f
                        if (unicodedata.category(ch) in ("Cc", "Cf") and ch not in NAME_MARKS)
                        or ch in BLANK_MARKS), None)
            if bad is not None:
                fail(path, start, f"contains the control or invisible character U+{ord(bad):04X}")
            if len(fields) > len(columns):
                fail(path, start, "has more fields than the header")
            if len(fields) < len(columns):
                fail(path, start, "has fewer fields than the header")
            yield start, {k: v.strip() for k, v in zip(columns, fields)}
            start = reader.line_num + 1
    except csv.Error as err:
        fail(path, start, f"cannot be parsed ({err}); most likely a stray quote")


def whole_id(path, row_num, raw):
    if not re.fullmatch(r"[1-9][0-9]{0,8}", raw):
        fail(path, row_num, f"bill_id {raw!r} is not a whole number from 1 up, "
                            "at most 9 digits with no leading zero")
    return int(raw)


def name_field(path, row_num, name, raw):
    # Runs of spaces collapsed, then NFC, so a name typed with combining
    # accents matches the same name typed with single characters.
    value = unicodedata.normalize("NFC", " ".join(raw.split()))
    # A name made of nothing but joiners and direction marks is as blank as
    # an empty one.
    if not value.translate(dict.fromkeys(map(ord, NAME_MARKS))).strip():
        fail(path, row_num, f"{name} is blank")
    return value


def cents(path, row_num, raw):
    # Two decimal places, no sign, no thousands separator, no currency mark.
    match = re.fullmatch(r"(0|[1-9][0-9]{0,6})\.([0-9]{2})", raw)
    value = int(match.group(1)) * 100 + int(match.group(2)) if match else 0
    if value == 0:
        fail(path, row_num, f"amount {raw!r} is not an amount from 0.01 to 9999999.99 "
                            "written like 1025.00")
    return value


def weight_of(path, row_num, raw):
    if not re.fullmatch(r"[1-9][0-9]{0,6}", raw) or int(raw) > MOST_WEIGHT:
        fail(path, row_num, f"weight {raw!r} is not a whole number from 1 to {MOST_WEIGHT}")
    return int(raw)


def load_bills(path):
    rows, lines = [], {}
    reader = read_csv(path, BILL_COLUMNS)
    for i, row in records(path, reader, BILL_COLUMNS):
        bill_id = whole_id(path, i, row["bill_id"])
        if bill_id in lines:
            fail(path, i, f"bill_id {bill_id} appears twice; the file holds one row per bill")
        lines[bill_id] = i
        rows.append((bill_id, name_field(path, i, "bill", row["bill"]), cents(path, i, row["amount"])))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows, lines


def load_splits(path, bills_path, bill_lines):
    rows, pairs, totals, spellings = [], set(), {}, {}
    reader = read_csv(path, SPLIT_COLUMNS)
    for i, row in records(path, reader, SPLIT_COLUMNS):
        bill_id = whole_id(path, i, row["bill_id"])
        if bill_id not in bill_lines:
            fail(path, i, f"bill_id {bill_id} is not in {Path(bills_path).name}")
        department = name_field(path, i, "department", row["department"])
        # The queries group by the name as written, so one department under
        # two spellings comes out as two departments in query 05, its charges
        # split between them. Spacing and the encoding of accents are settled
        # above; letter case is not. casefold can undo NFC, so the key is
        # normalised again.
        key = unicodedata.normalize("NFC", department.casefold())
        first = spellings.setdefault(key, department)
        if first != department:
            fail(path, i, f"department {department!r} is also written {first!r}; "
                          "one spelling per department, or its charges come out split")
        if (bill_id, department) in pairs:
            fail(path, i, f"department {department!r} appears twice on bill {bill_id}; "
                          "one row per department per bill")
        pairs.add((bill_id, department))
        weight = weight_of(path, i, row["weight"])
        totals[bill_id] = totals.get(bill_id, 0) + weight
        if totals[bill_id] > MOST_WEIGHT:
            fail(path, i, f"the weights on bill {bill_id} add up to more than {MOST_WEIGHT}")
        rows.append((bill_id, department, weight))
    if not rows:
        fail(path, 1, "no data rows after the header")
    # A bill with no split rows drops out of every join, so nobody would be
    # charged for it while query 01 still counts it in the total billed.
    for bill_id, line in bill_lines.items():
        if bill_id not in totals:
            fail(bills_path, line, f"bill {bill_id} has no rows in {Path(path).name}; "
                                   "every bill needs at least one department to charge")
    return rows


def load(bills_path, splits_path):
    bills, lines = load_bills(bills_path)
    return bills, load_splits(splits_path, bills_path, lines)


def new_db(bills, splits):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE bills (bill_id INTEGER PRIMARY KEY, bill TEXT NOT NULL, "
               "amount_cents INTEGER NOT NULL)")
    db.execute("CREATE TABLE splits (bill_id INTEGER NOT NULL REFERENCES bills, "
               "department TEXT NOT NULL, weight INTEGER NOT NULL, "
               "PRIMARY KEY (bill_id, department))")
    db.executemany("INSERT INTO bills VALUES (?, ?, ?)", bills)
    db.executemany("INSERT INTO splits VALUES (?, ?, ?)", splits)
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
    cursor = db.execute(sql_path.read_text(encoding="utf-8"))
    if cursor.description is None:
        raise sqlite3.ProgrammingError("has no query result to print")
    return [d[0] for d in cursor.description], cursor.fetchall()


def run_all(db, sql_dir=SQL_DIR):
    for sql_path in sorted(sql_dir.glob("*.sql")):
        try:
            headers, rows = run_query(db, sql_path)
        except (sqlite3.Error, sqlite3.Warning) as err:
            fail_file(sql_path, f"did not run: {err}")
        except UnicodeDecodeError:
            fail_file(sql_path, "is not UTF-8 text")
        print(f"=== {sql_path.name} ===")
        print_table(headers, rows)
        print()


def run_tests(db):
    failures = 0

    def check(label, got, want):
        # got is a function, so a query that does not run fails its own
        # check instead of stopping the suite. SystemExit is caught as well,
        # since the reports stop the run when a query fails.
        nonlocal failures
        try:
            got = got()
        except (Exception, SystemExit) as err:
            got = f"raised {type(err).__name__}: {err}"
        if got == want:
            print(f"PASS  {label}")
        else:
            failures += 1
            print(f"FAIL  {label}\n      got:  {got!r}\n      want: {want!r}")

    def q(conn, name):
        return run_query(conn, SQL_DIR / name)[1]

    check("seven bills split across six departments in 36 rows, 9940.25 billed",
          lambda: q(db, "01-bill-log-shape.sql"),
          [(7, 6, 36, "9940.25")])

    check("rounding each share on its own misses six of the seven bills, by up to two cents either way",
          lambda: q(db, "02-rounded-shares.sql"),
          [(1, "Office rent, July", "8025.00", 6, "8025.00", 0),
           (2, "Internet, July", "100.00", 6, "100.02", 2),
           (3, "Design software, July", "1025.00", 4, "1025.01", 1),
           (4, "Parking, July", "245.25", 2, "245.26", 1),
           (5, "Internet, August", "100.00", 6, "100.02", 2),
           (6, "Coffee and kitchen, August", "50.00", 6, "49.98", -2),
           (7, "Cleaning, September", "395.00", 6, "394.99", -1)])

    check("the leftover cents go one each to the largest remainders, and a tie goes to the name that sorts first",
          lambda: q(db, "03-largest-remainder.sql"),
          [(1, "Design", 620, "1309.34", "800/3800", 5, 0, "1309.34"),
           (1, "Engineering", 1480, "3125.52", "2400/3800", 3, 1, "3125.53"),
           (1, "Finance", 310, "654.67", "400/3800", 6, 0, "654.67"),
           (1, "Operations", 540, "1140.39", "1800/3800", 4, 0, "1140.39"),
           (1, "Sales", 450, "950.32", "3400/3800", 1, 1, "950.33"),
           (1, "Support", 400, "844.73", "2600/3800", 2, 1, "844.74"),
           (2, "Design", 1, "16.66", "4/6", 1, 1, "16.67"),
           (2, "Engineering", 1, "16.66", "4/6", 2, 1, "16.67"),
           (2, "Finance", 1, "16.66", "4/6", 3, 1, "16.67"),
           (2, "Operations", 1, "16.66", "4/6", 4, 1, "16.67"),
           (2, "Sales", 1, "16.66", "4/6", 5, 0, "16.66"),
           (2, "Support", 1, "16.66", "4/6", 6, 0, "16.66"),
           (3, "Design", 7, "275.96", "4/26", 4, 0, "275.96"),
           (3, "Engineering", 12, "473.07", "18/26", 1, 1, "473.08"),
           (3, "Operations", 2, "78.84", "16/26", 2, 1, "78.85"),
           (3, "Sales", 5, "197.11", "14/26", 3, 0, "197.11"),
           (4, "Operations", 1, "122.62", "1/2", 1, 1, "122.63"),
           (4, "Sales", 1, "122.62", "1/2", 2, 0, "122.62"),
           (5, "Design", 1, "16.66", "4/6", 1, 1, "16.67"),
           (5, "Engineering", 1, "16.66", "4/6", 2, 1, "16.67"),
           (5, "Finance", 1, "16.66", "4/6", 3, 1, "16.67"),
           (5, "Operations", 1, "16.66", "4/6", 4, 1, "16.67"),
           (5, "Sales", 1, "16.66", "4/6", 5, 0, "16.66"),
           (5, "Support", 1, "16.66", "4/6", 6, 0, "16.66"),
           (6, "Design", 1, "8.33", "2/6", 1, 1, "8.34"),
           (6, "Engineering", 1, "8.33", "2/6", 2, 1, "8.34"),
           (6, "Finance", 1, "8.33", "2/6", 3, 0, "8.33"),
           (6, "Operations", 1, "8.33", "2/6", 4, 0, "8.33"),
           (6, "Sales", 1, "8.33", "2/6", 5, 0, "8.33"),
           (6, "Support", 1, "8.33", "2/6", 6, 0, "8.33"),
           (7, "Design", 4, "54.48", "8/29", 4, 0, "54.48"),
           (7, "Engineering", 9, "122.58", "18/29", 1, 1, "122.59"),
           (7, "Finance", 2, "27.24", "4/29", 6, 0, "27.24"),
           (7, "Operations", 3, "40.86", "6/29", 5, 0, "40.86"),
           (7, "Sales", 6, "81.72", "12/29", 2, 1, "81.73"),
           (7, "Support", 5, "68.10", "10/29", 3, 0, "68.10")])

    check("the plug balances every bill and leaves a department a cent or more out on four; the split never does",
          lambda: q(db, "04-plug-versus-split.sql"),
          [(1, "Office rent, July", 0, None, 0, "0.473", 0, "0.473"),
           (2, "Internet, July", 2, "Design", 0, "1.666", 0, "0.666"),
           (3, "Design software, July", 1, "Engineering", 0, "0.692", 0, "0.538"),
           (4, "Parking, July", 1, "Operations", 0, "0.500", 0, "0.500"),
           (5, "Internet, August", 2, "Design", 0, "1.666", 0, "0.666"),
           (6, "Coffee and kitchen, August", -2, "Design", 0, "1.666", 0, "0.666"),
           (7, "Cleaning, September", -1, "Engineering", 0, "1.379", 0, "0.586")])

    check("tied cents went to Design, Engineering, Finance and Operations, and Sales and Support won none",
          lambda: q(db, "05-tied-cents.sql"),
          [("Design", 6, 3, 3, 0, "1681.46"),
           ("Engineering", 6, 6, 3, 0, "3762.88"),
           ("Finance", 5, 2, 2, 1, "723.58"),
           ("Operations", 7, 4, 3, 1, "1424.40"),
           ("Sales", 7, 2, 0, 4, "1393.44"),
           ("Support", 5, 1, 0, 3, "954.49")])

    def reports():
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            run_all(db)
        lines = out.getvalue().split("\n")
        at = lines.index("=== 04-plug-versus-split.sql ===")
        return lines[:5] + lines[at + 3:at + 5]

    check("the reports print as tables, with a blank where no plug was needed",
          reports,
          ["=== 01-bill-log-shape.sql ===",
           "bills  departments  splits  billed",
           "-----  -----------  ------  -------",
           "7      6            36      9940.25",
           "",
           "1        Office rent, July           0                             0            0.473"
           "            0             0.473",
           "2        Internet, July              2               Design        0            1.666"
           "            0             0.666"])

    # Bill logs built for cases the sample does not reach on its own. Each
    # bill is numbered from 1 in the order given, with its split rows.
    def log(bills):
        bill_rows, split_rows = [], []
        for n, (label, amount_cents, parts) in enumerate(bills, 1):
            bill_rows.append((n, label, amount_cents))
            split_rows += [(n, department, weight) for department, weight in parts]
        return new_db(bill_rows, split_rows)

    five_ways = [("Ash", 1), ("Birch", 1), ("Cedar", 1), ("Elm", 1), ("Fir", 1)]
    tiny = log([("Stamps", 3, five_ways)])
    check("on a 0.03 bill split five ways, rounding charges 0.05 and the plug lands 1.6 cents out",
          lambda: [q(tiny, "01-bill-log-shape.sql"), q(tiny, "02-rounded-shares.sql"),
                   q(tiny, "03-largest-remainder.sql"), q(tiny, "04-plug-versus-split.sql")],
          [[(1, 5, 5, "0.03")],
           [(1, "Stamps", "0.03", 5, "0.05", 2)],
           [(1, "Ash", 1, "0.00", "3/5", 1, 1, "0.01"), (1, "Birch", 1, "0.00", "3/5", 2, 1, "0.01"),
            (1, "Cedar", 1, "0.00", "3/5", 3, 1, "0.01"), (1, "Elm", 1, "0.00", "3/5", 4, 0, "0.00"),
            (1, "Fir", 1, "0.00", "3/5", 5, 0, "0.00")],
           [(1, "Stamps", 2, "Ash", 0, "1.600", 0, "0.600")]])

    whole_cents = log([("Printer lease", 90000, [("Birch", 2), ("Ash", 1)]), ("Van hire", 12345, [("Cedar", 7)])])
    check("a bill that splits into whole cents hands out no extra cent, needs no plug and has no ties, "
          "and a bill with one department charges it the lot",
          lambda: [q(whole_cents, "03-largest-remainder.sql"), q(whole_cents, "04-plug-versus-split.sql"),
                   q(whole_cents, "05-tied-cents.sql")],
          [[(1, "Ash", 1, "300.00", "0/3", 1, 0, "300.00"), (1, "Birch", 2, "600.00", "0/3", 2, 0, "600.00"),
            (2, "Cedar", 7, "123.45", "0/7", 1, 0, "123.45")],
           [(1, "Printer lease", 0, None, 0, "0.000", 0, "0.000"), (2, "Van hire", 0, None, 0, "0.000", 0, "0.000")],
           [("Ash", 1, 0, 0, 0, "300.00"), ("Birch", 1, 0, 0, 0, "600.00"), ("Cedar", 1, 0, 0, 0, "123.45")]])

    # Three shares each cut by a third of a cent. As whole numbers the
    # remainders are equal and the cent goes to the first name; worked out in
    # floating point as the share in cents less its whole cents, the middle
    # share's comes out a hair larger.
    thirds = log([("Courier run", 1050, [("Archive", 2), ("Bindery", 5), ("Courier", 2)])])
    check("equal remainders are equal even when the shares differ in size, so the cent goes by the name",
          lambda: [q(thirds, "03-largest-remainder.sql"), q(thirds, "05-tied-cents.sql")],
          [[(1, "Archive", 2, "2.33", "3/9", 1, 1, "2.34"), (1, "Bindery", 5, "5.83", "3/9", 2, 0, "5.83"),
            (1, "Courier", 2, "2.33", "3/9", 3, 0, "2.33")],
           [("Archive", 1, 1, 1, 0, "2.34"), ("Bindery", 1, 0, 0, 1, "5.83"), ("Courier", 1, 0, 0, 1, "2.33")]])

    # Two departments that tie among the ones that missed out, and two that
    # tie among the ones that got a cent. Neither pair straddles the cut, so
    # neither counts as a tie in query 05.
    one_side = log([("Lamp", 1, [("Ash", 1), ("Birch", 1), ("Cedar", 2)]),
                    ("Kettle", 2, [("Ash", 2), ("Birch", 2), ("Cedar", 1)])])
    check("a tie counts only when it sits across the cut, not among the departments on one side of it",
          lambda: [q(one_side, "03-largest-remainder.sql"), q(one_side, "05-tied-cents.sql")],
          [[(1, "Ash", 1, "0.00", "1/4", 2, 0, "0.00"), (1, "Birch", 1, "0.00", "1/4", 3, 0, "0.00"),
            (1, "Cedar", 2, "0.00", "2/4", 1, 1, "0.01"), (2, "Ash", 2, "0.00", "4/5", 1, 1, "0.01"),
            (2, "Birch", 2, "0.00", "4/5", 2, 1, "0.01"), (2, "Cedar", 1, "0.00", "2/5", 3, 0, "0.00")],
           [("Ash", 2, 1, 0, 0, "0.01"), ("Birch", 2, 1, 0, 0, "0.01"), ("Cedar", 2, 1, 0, 0, "0.01")]])

    cased = log([("Postage", 1, [("archive", 1), ("Bindery", 1)])])
    check("names sort in byte order in all three queries, so a plain capital letter comes before any lower-case one",
          lambda: [q(cased, "03-largest-remainder.sql"), q(cased, "04-plug-versus-split.sql"),
                   q(cased, "05-tied-cents.sql")],
          [[(1, "Bindery", 1, "0.00", "1/2", 1, 1, "0.01"), (1, "archive", 1, "0.00", "1/2", 2, 0, "0.00")],
           [(1, "Postage", 1, "Bindery", 0, "0.500", 0, "0.500")],
           [("Bindery", 1, 1, 1, 0, "0.01"), ("archive", 1, 0, 0, 1, "0.00")]])

    # The largest amount and total weight the loader takes, including two
    # shares a millionth of a cent either side of a half.
    top = 999999999
    caps = log([("Lease, north tower", top, [("Ash", 333333), ("Birch", 333333), ("Cedar", 333334)]),
                ("Lease, south tower", top, [("Ash", 1), ("Birch", 999999)]),
                ("Lease, annex", top, [("Ash", 499999), ("Birch", 500001)])])
    check("at the largest amount and total weight the loader accepts, every share still comes out exact",
          lambda: [q(caps, "01-bill-log-shape.sql"), q(caps, "02-rounded-shares.sql"),
                   q(caps, "03-largest-remainder.sql"), q(caps, "04-plug-versus-split.sql"),
                   q(caps, "05-tied-cents.sql")],
          [[(3, 3, 7, "29999999.97")],
           [(1, "Lease, north tower", "9999999.99", 3, "10000000.00", 1),
            (2, "Lease, south tower", "9999999.99", 2, "9999999.99", 0),
            (3, "Lease, annex", "9999999.99", 2, "9999999.99", 0)],
           [(1, "Ash", 333333, "3333329.99", "666667/1000000", 1, 1, "3333330.00"),
            (1, "Birch", 333333, "3333329.99", "666667/1000000", 2, 1, "3333330.00"),
            (1, "Cedar", 333334, "3333339.99", "666666/1000000", 3, 0, "3333339.99"),
            (2, "Ash", 1, "9.99", "999999/1000000", 1, 1, "10.00"),
            (2, "Birch", 999999, "9999989.99", "1/1000000", 2, 0, "9999989.99"),
            (3, "Ash", 499999, "4999989.99", "500001/1000000", 1, 1, "4999990.00"),
            (3, "Birch", 500001, "5000009.99", "499999/1000000", 2, 0, "5000009.99")],
           [(1, "Lease, north tower", 1, "Cedar", 0, "0.666", 0, "0.666"),
            (2, "Lease, south tower", 0, None, 0, "0.000", 0, "0.000"),
            (3, "Lease, annex", 0, None, 0, "0.499", 0, "0.499")],
           [("Ash", 3, 3, 0, 0, "8333330.00"), ("Birch", 3, 1, 0, 0, "18333329.98"),
            ("Cedar", 1, 0, 0, 0, "3333339.99")]])

    # Fleet fuel: the largest share is exactly 5.01, so it needed no rounding,
    # and the plug moves it a whole cent. Postage and stationery: the largest
    # weight ties both other departments for the largest rounded share on the
    # postage, and ties Elm for the largest cut share on the stationery, and
    # those names sort first, so the plug would go to one of them if it went
    # by share. Printer toner and water cooler: misses of exactly 0.510 and
    # 0.514 of a cent, which binary floating point cannot hold.
    plugs = log([("Fleet fuel", 1002, [("Ash", 1), ("Birch", 2), ("Cedar", 1)]),
                 ("Postage", 11, [("Fir", 342), ("Elm", 328), ("Ash", 340)]),
                 ("Stationery", 320, [("Elm", 224), ("Oak", 191), ("Fir", 225)]),
                 ("Printer toner", 2374, [("Cedar", 219), ("Fir", 208), ("Ash", 173)]),
                 ("Water cooler", 2307, [("Cedar", 89), ("Birch", 351), ("Oak", 60)])])
    check("the plug goes to the largest weight when another share ties it, lands a whole cent out on a share "
          "that was already exact, "
          "and its misses are worked out in whole numbers",
          lambda: q(plugs, "04-plug-versus-split.sql"),
          [(1, "Fleet fuel", 1, "Birch", 0, "1.000", 0, "0.500"),
           (2, "Postage", 1, "Fir", 0, "0.724", 0, "0.572"),
           (3, "Stationery", 1, "Fir", 0, "0.500", 0, "0.500"),
           (4, "Printer toner", 1, "Cedar", 0, "0.510", 0, "0.503"),
           (5, "Water cooler", 1, "Birch", 0, "0.514", 0, "0.514")])

    # The loader, on the included bad file and on small files written here.
    # A crash on one of these files comes back as a value too, so it fails
    # its check like any other wrong answer; a pair of files the loader
    # accepts comes back with what it loaded.
    def rejection(load_pair, *args):
        err = io.StringIO()
        try:
            with contextlib.redirect_stderr(err):
                loaded = load_pair(*args)
        except SystemExit as stop:
            return stop.code, err.getvalue().strip()
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

        bill_head = ",".join(BILL_COLUMNS) + "\n"
        split_head = ",".join(SPLIT_COLUMNS) + "\n"
        one_bill = bill_head + "1,Rent,100.00\n"
        one_split = csv_file("one_split.csv", split_head + "1,Design,1\n")
        two_bills = csv_file("two_bills.csv", one_bill + "2,Internet,50.00\n")

        def bills(name, content):
            return rejection(load, csv_file(name, content), one_split)

        def splits(name, content):
            return rejection(load, two_bills, csv_file(name, split_head + "1,Design,1\n" + content))

        def refused_amount(name, raw):
            return bills(name, one_bill + f"2,Internet,{raw}\n")

        def amount_message(name, raw):
            return (2, f"{name} row 3: amount {raw!r} is not an amount from 0.01 to 9999999.99 "
                       "written like 1025.00")

        check("a bill with no split rows is refused, since nobody would be charged for it",
              lambda: rejection(load, HERE / "data" / "invalid-bills.csv", SPLITS_CSV),
              (2, "invalid-bills.csv row 9: bill 8 has no rows in splits.csv; "
                  "every bill needs at least one department to charge"))

        check("in the bills file, rows are counted past blank lines, a line of spaces and a stray quote; a "
              "bad header, text after a closing quote, a repeated bill_id, an id with a leading zero, ten "
              "digits or trailing text, a bill that is blank or only joiners or direction marks, and a line of "
              "commas are refused",
              lambda: [bills("blank.csv", one_bill + "\n   \n\nx,Internet,50.00\n"),
                       bills("quote.csv", one_bill + '2,"Internet,50.00\n3,Parking,20.00"\n'),
                       bills("spans.csv", one_bill + '2,"Inter\nnet"x,50.00\n'),
                       bills("after.csv", one_bill + '2,"Internet"x,50.00\n'),
                       bills("header.csv", 'bill_id,"bill"x,amount\n1,Rent,100.00\n'),
                       bills("twice.csv", one_bill + "1,Internet,50.00\n"),
                       bills("padded_id.csv", one_bill + "007,Internet,50.00\n"),
                       bills("long_id.csv", one_bill + "1234567890,Internet,50.00\n"),
                       bills("text_id.csv", one_bill + "12a,Internet,50.00\n"),
                       bills("noname.csv", one_bill + "2, ,50.00\n"),
                       bills("joiner_only.csv", one_bill + "2,\u200d,50.00\n"),
                       bills("marks_only.csv", one_bill + "2,\u200f\u061c,50.00\n"),
                       bills("commas.csv", one_bill + ",,\n")],
              [(2, "blank.csv row 6: bill_id 'x' is not a whole number from 1 up, "
                   "at most 9 digits with no leading zero"),
               (2, "quote.csv row 3: a field runs across more than one line; most likely a stray quote"),
               (2, "spans.csv row 3: cannot be parsed (',' expected after '\"'); most likely a stray quote"),
               (2, "after.csv row 3: cannot be parsed (',' expected after '\"'); most likely a stray quote"),
               (2, "header.csv row 1: cannot be parsed (',' expected after '\"')"),
               (2, "twice.csv row 3: bill_id 1 appears twice; the file holds one row per bill"),
               (2, "padded_id.csv row 3: bill_id '007' is not a whole number from 1 up, "
                   "at most 9 digits with no leading zero"),
               (2, "long_id.csv row 3: bill_id '1234567890' is not a whole number from 1 up, "
                   "at most 9 digits with no leading zero"),
               (2, "text_id.csv row 3: bill_id '12a' is not a whole number from 1 up, "
                   "at most 9 digits with no leading zero"),
               (2, "noname.csv row 3: bill is blank"),
               (2, "joiner_only.csv row 3: bill is blank"),
               (2, "marks_only.csv row 3: bill is blank"),
               (2, "commas.csv row 3: bill_id '' is not a whole number from 1 up, "
                   "at most 9 digits with no leading zero")])

        amounts = [("thousands.csv", '"1,025.00"', "1,025.00"), ("no_decimals.csv", "1025", "1025"),
                   ("one_decimal.csv", "1025.5", "1025.5"), ("three_decimals.csv", "1025.500", "1025.500"),
                   ("trailing.csv", "5.00x", "5.00x"), ("negative.csv", "-5.00", "-5.00"),
                   ("currency.csv", "$5.00", "$5.00"), ("leading_zero.csv", "05.00", "05.00"),
                   ("zero.csv", "0.00", "0.00"), ("too_much.csv", "10000000.00", "10000000.00")]
        check("an amount with a thousands separator, no decimals, one or three decimals, trailing text, a "
              "sign, a currency mark, a leading zero, nothing to charge, or more than the largest is refused",
              lambda: [refused_amount(name, written) for name, written, raw in amounts],
              [amount_message(name, raw) for name, written, raw in amounts])

        check("in the splits file, a bill that is not in the bills file, a department twice on one bill or "
              "written in another case, a blank department, a weight of zero, a fraction, a leading zero or "
              "over the limit, weights that add up past the limit, a bad id on the first row, and a file "
              "with only a header are refused",
              lambda: [splits("unknown.csv", "3,Design,1\n"),
                       splits("dupe.csv", "1,Design,2\n"),
                       splits("case.csv", "2,design,1\n"),
                       splits("sharp_s.csv", "1,Stra\u00dfe,1\n2,STRASSE,1\n"),
                       splits("greek.csv", "1,\u0390,1\n2,\u03aa\u0301,1\n"),
                       splits("nodept.csv", "2, ,1\n"),
                       splits("zero_weight.csv", "2,Sales,0\n"),
                       splits("fraction.csv", "2,Sales,2.5\n"),
                       splits("padded_weight.csv", "2,Sales,07\n"),
                       splits("heavy.csv", "2,Sales,1000001\n"),
                       splits("adds_up.csv", "1,Sales,999999\n2,Sales,5\n1,Support,1\n"),
                       rejection(load, two_bills, csv_file("first_row.csv", split_head + "0,Design,1\n")),
                       rejection(load, two_bills, csv_file("bare_splits.csv", split_head))],
              [(2, "unknown.csv row 3: bill_id 3 is not in two_bills.csv"),
               (2, "dupe.csv row 3: department 'Design' appears twice on bill 1; one row per department per bill"),
               (2, "case.csv row 3: department 'design' is also written 'Design'; "
                   "one spelling per department, or its charges come out split"),
               (2, "sharp_s.csv row 4: department 'STRASSE' is also written 'Stra\u00dfe'; "
                   "one spelling per department, or its charges come out split"),
               (2, "greek.csv row 4: department '\u03aa\u0301' is also written '\u0390'; "
                   "one spelling per department, or its charges come out split"),
               (2, "nodept.csv row 3: department is blank"),
               (2, "zero_weight.csv row 3: weight '0' is not a whole number from 1 to 1000000"),
               (2, "fraction.csv row 3: weight '2.5' is not a whole number from 1 to 1000000"),
               (2, "padded_weight.csv row 3: weight '07' is not a whole number from 1 to 1000000"),
               (2, "heavy.csv row 3: weight '1000001' is not a whole number from 1 to 1000000"),
               (2, "adds_up.csv row 5: the weights on bill 1 add up to more than 1000000"),
               (2, "first_row.csv row 2: bill_id '0' is not a whole number from 1 up, "
                   "at most 9 digits with no leading zero"),
               (2, "bare_splits.csv row 1: no data rows after the header")])

        check("a control character, a line holding only a tab, a zero-width space, the combining grapheme "
              "joiner, the Hangul fillers and the Khmer inherent vowels, rows with too many or too few fields, a "
              "renamed header, an empty file, one with only a header, one that is not UTF-8, and a folder in "
              "place of a file are refused",
              lambda: [bills("tab.csv", one_bill + "2,Internet\t,50.00\n"),
                       splits("zwsp.csv", "2,Sa\u200bles,1\n"),
                       splits("tab_line.csv", "\t\n2,Sales,1\n"),
                       *[splits(f"mark_{mark:04x}.csv", f"2,Sa{chr(mark)}les,1\n")
                         for mark in (0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x3164, 0xFFA0)],
                       splits("wide.csv", "2,Sales,1,extra\n"),
                       bills("narrow.csv", one_bill + "2,Internet\n"),
                       rejection(load, csv_file("renamed.csv", "id,bill,amount\n"), one_split),
                       rejection(load, csv_file("bare.csv", bill_head), one_split),
                       rejection(load, two_bills, csv_file("nothing.csv", "")),
                       rejection(load, byte_file("latin1.csv", bill_head.encode("utf-8")
                                                 + "1,Caf\xe9 rent,100.00\n".encode("latin-1")), one_split),
                       (lambda code, message: (code, message.startswith(Path(tmp).name + ": ")))(
                           *rejection(load, Path(tmp), one_split))],
              [(2, "tab.csv row 3: contains the control or invisible character U+0009"),
               (2, "zwsp.csv row 3: contains the control or invisible character U+200B"),
               (2, "tab_line.csv row 3: contains the control or invisible character U+0009"),
               *[(2, f"mark_{mark:04x}.csv row 3: contains the control or invisible character U+{mark:04X}")
                 for mark in (0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x3164, 0xFFA0)],
               (2, "wide.csv row 3: has more fields than the header"),
               (2, "narrow.csv row 3: has fewer fields than the header"),
               (2, "renamed.csv row 1: expected columns bill_id,bill,amount, got ['id', 'bill', 'amount']"),
               (2, "bare.csv row 1: no data rows after the header"),
               (2, "nothing.csv: is empty"),
               (2, "latin1.csv: is not UTF-8 text"),
               (2, True)])

        check("a byte-order mark is read through; spaces around fields and before a quote, untidy spacing "
              "and accents are settled; the joiners and direction marks are kept; and a nine-digit id, the "
              "smallest and largest amounts, and a single weight of 1000000 load",
              lambda: [rejection(load, csv_file("bom.csv", "\ufeff" + one_bill), one_split),
                       rejection(load, csv_file("tidy.csv", bill_head + " 1 ,  Office   rent , 0.01 \n"
                                                + '999999999, "Caf\u00e9 lunch",9999999.99\n'
                                                + "3,Lease,5000.00\n"),
                                 csv_file("tidy_splits.csv", split_head + '1, "Cafe\u0301 staff", 1 \n'
                                          + "999999999,Caf\u00e9 staff,999995\n"
                                          + "999999999,Ali\u200creza Stone,1\n"
                                          + "999999999,Mina\u200d Rao,1\n"
                                          + "999999999,\u200fLev Adler,1\n"
                                          + "999999999,Nour\u061c Haddad,1\n"
                                          + "999999999,\u200eOren Katz,1\n"
                                          + "3,Head office,1000000\n"))],
              [(0, ([(1, "Rent", 10000)], [(1, "Design", 1)])),
               (0, ([(1, "Office rent", 1), (999999999, "Caf\u00e9 lunch", 999999999), (3, "Lease", 500000)],
                    [(1, "Caf\u00e9 staff", 1), (999999999, "Caf\u00e9 staff", 999995),
                     (999999999, "Ali\u200creza Stone", 1), (999999999, "Mina\u200d Rao", 1),
                     (999999999, "\u200fLev Adler", 1), (999999999, "Nour\u061c Haddad", 1),
                     (999999999, "\u200eOren Katz", 1), (3, "Head office", 1000000)]))])

        # Absolute paths, since Python 3.7 and 3.8 can leave __file__ relative.
        # Each copy started here carries CLI_CHECK_MARK, which stops it from
        # running the suite even if the rule against --test on other files is
        # broken, and the timeout stops a copy that hangs.
        script, folder = str(Path(__file__).resolve()), str(HERE.resolve())
        child_env = dict(os.environ, **{CLI_CHECK_MARK: "1"})

        def run_cli(*argv):
            return subprocess.run([sys.executable, "-B", script, *argv], cwd=folder, env=child_env,
                                  capture_output=True, timeout=120)

        def cli(*argv):
            done = run_cli(*argv)
            lines = done.stderr.decode("utf-8", "replace").strip().splitlines()
            return done.returncode, lines[-1] if lines else ""

        def piped_names():
            # Reports piped to a file or another program on Windows would
            # otherwise be written in a codepage that cannot hold these names.
            names = "Caf\u00e9 staff", "\u05de\u05d7\u05dc\u05e7\u05d4"
            done = run_cli("--bills", str(csv_file("named_bills.csv", bill_head + "1,Rent,100.00\n")),
                           "--splits", str(csv_file("named_splits.csv", split_head
                                                    + "".join(f"1,{name},1\n" for name in names))))
            return done.returncode, all(name in done.stdout.decode("utf-8", "replace") for name in names)

        def sql_folder(name, data):
            folder = Path(tmp) / name
            folder.mkdir()
            (folder / f"01-{name}.sql").write_bytes(data)
            return folder

        other_bills = csv_file("other_bills.csv", BILLS_CSV.read_text(encoding="utf-8"))
        other_splits = csv_file("other_splits.csv", SPLITS_CSV.read_text(encoding="utf-8"))
        check("on the command line, a bills file without its splits file or the other way round, a file "
              "that is not there, and the test run on either file other than the sample are refused; reports "
              "piped out with names that are not plain ASCII print; and a query file that fails, has no query result, "
              "or is not UTF-8 stops the reports with a one-line message",
              lambda: [cli("--bills", str(other_bills)),
                       cli("--splits", str(other_splits)),
                       cli("--bills", "missing.csv", "--splits", str(other_splits)),
                       cli("--test", "--bills", str(other_bills), "--splits", str(other_splits)),
                       cli("--test", "--bills", str(BILLS_CSV.resolve()), "--splits", str(other_splits)),
                       cli("--test", "--bills", str(other_bills), "--splits", str(SPLITS_CSV.resolve())),
                       piped_names(),
                       rejection(run_all, db, sql_folder("broken", b"SELEC 1;")),
                       rejection(run_all, db, sql_folder("empty", b"")),
                       rejection(run_all, db, sql_folder("ansi", "-- caf\xe9\nSELECT 1;".encode("latin-1")))],
              [(2, "run.py: error: --bills and --splits go together; give both or neither"),
               (2, "run.py: error: --bills and --splits go together; give both or neither"),
               (2, "run.py: error: --bills: 'missing.csv' is not a file"),
               (2, "run.py: error: --test checks hand-computed answers for the sample bills; "
                   "run it without --bills and --splits"),
               (2, "run.py: error: --test checks hand-computed answers for the sample bills; "
                   "run it without --bills and --splits"),
               (2, "run.py: error: --test checks hand-computed answers for the sample bills; "
                   "run it without --bills and --splits"),
               (0, True),
               (2, '01-broken.sql: did not run: near "SELEC": syntax error'),
               (2, "01-empty.sql: did not run: has no query result to print"),
               (2, "01-ansi.sql: is not UTF-8 text")])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the split queries against a bill log, the sample by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--bills", type=Path, default=None, help="path to an alternate bills CSV")
    parser.add_argument("--splits", type=Path, default=None, help="path to the splits CSV for those bills")
    args = parser.parse_args()
    # Reports are printed as UTF-8, since output piped or redirected on
    # Windows otherwise falls back to a codepage that cannot print all text.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    # The two files only make sense as a pair, so a bills file of your own
    # never picks up the sample splits, or the other way round.
    if (args.bills is None) != (args.splits is None):
        parser.error("--bills and --splits go together; give both or neither")
    given = args.bills is not None
    for flag, value, sample in (("--bills", args.bills, BILLS_CSV), ("--splits", args.splits, SPLITS_CSV)):
        path = value or sample
        if not path.is_file():
            if given:
                parser.error(f"{flag}: '{path}' is not a file")
            parser.error(f"the sample file '{path}' is missing")
    bills_path, splits_path = args.bills or BILLS_CSV, args.splits or SPLITS_CSV
    if args.test and (bills_path.resolve() != BILLS_CSV.resolve()
                      or splits_path.resolve() != SPLITS_CSV.resolve()):
        parser.error("--test checks hand-computed answers for the sample bills; "
                     "run it without --bills and --splits")
    # A copy started by the test run's own command-line check never runs the
    # suite, so a broken rule above fails that check once instead of starting
    # the suite over and over.
    if args.test and os.environ.get(CLI_CHECK_MARK):
        parser.error("--test does not run inside the test run's own command-line check")

    db = new_db(*load(bills_path, splits_path))
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
