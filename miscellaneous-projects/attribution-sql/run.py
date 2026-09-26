"""Load a marketing touch log and a conversions log into SQLite and run the attribution queries.

Usage:
    python run.py                                                  run every query in sql/
    python run.py --test                                           run the assertion suite
    python run.py --touches t.csv --conversions c.csv              load a different pair of logs
"""

import argparse
import contextlib
import csv
import io
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

HERE = Path(__file__).parent
TOUCHES_CSV = HERE / "data" / "touches.csv"
CONVERSIONS_CSV = HERE / "data" / "conversions.csv"
SQL_DIR = HERE / "sql"
TOUCH_COLUMNS = ["touch_id", "customer", "channel", "touched_at"]
CONVERSION_COLUMNS = ["conversion_id", "customer", "converted_at", "revenue"]
CUSTOMER = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")
CHANNEL = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
NAME_LENGTH = 24
FIRST_YEAR, LAST_YEAR = 1970, 2200
MOMENT = "%Y-%m-%d %H:%M"
# Each log holds at most this many rows. Every touch is paired with every
# conversion by the same customer before the window sorts them, so the pairs
# are capped as well: a customer with 300 touches and 300 conversions makes
# 90000. With at most 999999.99 a conversion, no total the queries add up,
# the join's included, passes 10**13 cents, which keeps every sum and every
# product in the linear split a whole number well inside SQLite's 64-bit
# integers.
MOST_TOUCHES = 50_000
MOST_CONVERSIONS = 50_000
MOST_PAIRS = 100_000
# A line of the file may hold at most this many characters. A real row holds
# a few dozen.
LINE_CAP = 1_000_000
# A query that runs past this many thousand SQLite steps is stopped. The
# sample takes about twenty. The costliest logs found within the limits above
# take under a third of it, on SQLite 3.31 and 3.34 as much as on 3.50, so
# only a query that would run away reaches it.
STEP_BUDGET = 200_000


def fail(path, row_num, message):
    print(f"{Path(path).name} row {row_num}: {message}", file=sys.stderr)
    sys.exit(2)


def fail_file(path, message):
    print(f"{Path(path).name}: {message}", file=sys.stderr)
    sys.exit(2)


def shown(raw, keep=40):
    # A value is cut short in a message, so one enormous field cannot flood
    # the screen.
    if len(raw) <= keep:
        return repr(raw)
    over = len(raw) - keep
    return f"{raw[:keep]!r} and {over} more character" + ("" if over == 1 else "s")


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
        # trailing one still shows, and to twice the length of a value, since
        # the conversions header alone runs past 40 characters.
        got = line.rstrip("\r\n")
        fail(path, number, f"expected columns '{','.join(columns)}', got {shown(got, 80)}")
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


def whole_id(path, row_num, name, raw):
    if not re.fullmatch(r"[1-9][0-9]{0,8}", raw):
        fail(path, row_num, f"{name} {shown(raw)} is not a whole number from 1 to 999999999 "
                            "with no leading zero")
    return int(raw)


def customer_of(path, row_num, raw):
    # Customers are matched exactly across the two logs, so a code is held to
    # one plain form. One typed in lower case, or with a stray character,
    # would be a different customer, and its touches would credit nothing.
    if len(raw) > NAME_LENGTH or not CUSTOMER.fullmatch(raw):
        fail(path, row_num, f"customer {shown(raw)} is not a customer code: capital letters and digits, "
                            f"joined by single hyphens, at most {NAME_LENGTH} characters")
    return raw


def channel_of(path, row_num, raw):
    # The queries group on the channel as written, so Email and email would
    # split one channel's credit in two. Channels are held to small letters.
    if len(raw) > NAME_LENGTH or not CHANNEL.fullmatch(raw):
        fail(path, row_num, f"channel {shown(raw)} is not a channel name: small letters and digits, "
                            f"joined by single hyphens, at most {NAME_LENGTH} characters")
    return raw


def moment_of(path, row_num, name, raw):
    # The queries compare moments as text, which puts them in time order only
    # while every one is written the same way, to the minute. The date has to
    # exist, and the years are held to 1970 to 2200, so a mistyped year is
    # refused rather than read as a date centuries away.
    ok = False
    match = re.fullmatch(r"([0-9]{4})-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}", raw)
    if match and FIRST_YEAR <= int(match.group(1)) <= LAST_YEAR:
        try:
            ok = datetime.strptime(raw, MOMENT).strftime(MOMENT) == raw
        except ValueError:
            ok = False
    if not ok:
        fail(path, row_num, f"{name} {shown(raw)} is not a date and time written like 2026-04-15 14:00, "
                            f"from {FIRST_YEAR}-01-01 00:00 to {LAST_YEAR}-12-31 23:59")
    return raw


def cents(path, row_num, raw):
    # Two decimal places, no sign, no thousands separator, no currency mark.
    match = re.fullmatch(r"(0|[1-9][0-9]{0,5})\.([0-9]{2})", raw)
    if not match:
        fail(path, row_num, f"revenue {shown(raw)} is not an amount from 0.00 to 999999.99 written like 149.99")
    return int(match.group(1)) * 100 + int(match.group(2))


def opened(path):
    path = Path(path)
    try:
        folder = path.is_dir()
    except OSError:
        # Python 3.7 raises here for a name Windows cannot hold.
        folder = False
    if folder:
        fail_file(path, "is a folder, not a file")
    try:
        return open(path, encoding="utf-8", newline="")
    except OSError as err:
        fail_file(path, err.strerror or "cannot be read")


def load_touches(path):
    rows, ids, seen = [], set(), {}
    with opened(path) as handle:
        lines, header_line = open_csv(path, handle, TOUCH_COLUMNS)
        for i, row in records(path, lines, TOUCH_COLUMNS):
            touch_id = whole_id(path, i, "touch_id", row["touch_id"])
            customer = customer_of(path, i, row["customer"])
            channel = channel_of(path, i, row["channel"])
            touched_at = moment_of(path, i, "touched_at", row["touched_at"])
            if touch_id in ids:
                fail(path, i, f"touch_id {touch_id} appears twice; one row per touch")
            ids.add(touch_id)
            # The same customer, channel and minute twice is one touch logged
            # twice, and linear credit would count it twice.
            first = seen.setdefault((customer, channel, touched_at), touch_id)
            if first != touch_id:
                fail(path, i, f"touch {touch_id} repeats touch {first} ({customer}, {channel}, {touched_at}); "
                              "a touch logged twice would be credited twice")
            rows.append((touch_id, customer, channel, touched_at))
            # The file is read a line at a time, so a log far past the limit
            # is never read to the end.
            if len(rows) > MOST_TOUCHES:
                fail(path, i, f"the log runs past {MOST_TOUCHES} touches")
    if not rows:
        fail(path, header_line, "no data rows after the header")
    return rows


def load_conversions(path):
    rows, ids, seen = [], set(), {}
    with opened(path) as handle:
        lines, header_line = open_csv(path, handle, CONVERSION_COLUMNS)
        for i, row in records(path, lines, CONVERSION_COLUMNS):
            conversion_id = whole_id(path, i, "conversion_id", row["conversion_id"])
            customer = customer_of(path, i, row["customer"])
            converted_at = moment_of(path, i, "converted_at", row["converted_at"])
            revenue = cents(path, i, row["revenue"])
            if conversion_id in ids:
                fail(path, i, f"conversion_id {conversion_id} appears twice; one row per conversion")
            ids.add(conversion_id)
            # The window runs from the previous conversion, so two at the same
            # minute would leave the second one no window at all.
            first = seen.setdefault((customer, converted_at), conversion_id)
            if first != conversion_id:
                fail(path, i, f"{customer} converts twice at {converted_at}, as conversions {first} and "
                              f"{conversion_id}; one conversion per customer per minute, with the revenue "
                              "added together")
            rows.append((conversion_id, customer, converted_at, revenue))
            if len(rows) > MOST_CONVERSIONS:
                fail(path, i, f"the log runs past {MOST_CONVERSIONS} conversions")
    if not rows:
        fail(path, header_line, "no data rows after the header")
    return rows


def load(touches_path, conversions_path):
    touches = load_touches(touches_path)
    conversions = load_conversions(conversions_path)
    counts = {}
    for _, customer, _, _ in touches:
        counts[customer] = counts.get(customer, 0) + 1
    pairs = sum(counts.get(customer, 0) for _, customer, _, _ in conversions)
    if pairs > MOST_PAIRS:
        fail_file(conversions_path, f"these conversions and the touches in {Path(touches_path).name} pair up "
                                    f"{pairs} times by customer, more than the {MOST_PAIRS} the queries work "
                                    "through")
    return touches, conversions


def new_db(touches, conversions):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE touches (touch_id INTEGER PRIMARY KEY, customer TEXT NOT NULL, "
               "channel TEXT NOT NULL, touched_at TEXT NOT NULL)")
    db.execute("CREATE TABLE conversions (conversion_id INTEGER PRIMARY KEY, customer TEXT NOT NULL, "
               "converted_at TEXT NOT NULL, revenue_cents INTEGER NOT NULL)")
    # The queries join the two logs on the customer and look for touches in a
    # stretch of time, so both are indexed that way.
    db.execute("CREATE INDEX touches_by_customer ON touches (customer, touched_at)")
    db.execute("CREATE INDEX conversions_by_customer ON conversions (customer, converted_at)")
    db.executemany("INSERT INTO touches VALUES (?, ?, ?, ?)", touches)
    db.executemany("INSERT INTO conversions VALUES (?, ?, ?, ?)", conversions)
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
    sql_paths = sorted(sql_dir.glob("*.sql"))
    if not sql_paths:
        fail_file(sql_dir, "holds no query files")
    for sql_path in sql_paths:
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

    check("40 touches across 7 channels by 11 customers, and 15 conversions by 11 customers worth 2628.07",
          lambda: q(db, "01-log-shape.sql"),
          [(40, 7, 11, 15, 11, "2628.07")])

    check("joining every touch to every conversion by customer makes 55 pairs over 14 conversions and credits "
          "6459.74",
          lambda: q(db, "02-naive-join.sql"),
          [("affiliate", 4, 4, "462.34"),
           ("display", 4, 4, "367.25"),
           ("email", 18, 12, "1682.66"),
           ("organic", 5, 5, "589.60"),
           ("paid-search", 10, 10, "888.09"),
           ("referral", 4, 4, "1444.97"),
           ("social", 10, 9, "1024.83"),
           ("(total)", 55, 14, "6459.74")])

    check("32 of the 55 pairs fall in a window; the other 23 come after the conversion (9), at or before the "
          "previous one (9) or more than 30 days before (5), and three conversions are left with none",
          lambda: q(db, "03-touch-windows.sql"),
          [(1, "CU-1001", "2026-03-10 14:30", None, "2026-02-08 14:30", 3, 3, 0, 0, "email", "paid-search"),
           (2, "CU-1002", "2026-03-14 11:00", None, "2026-02-12 11:00", 2, 4, 0, 0, "organic", "email"),
           (3, "CU-1007", "2026-03-18 12:00", None, "2026-02-16 12:00", 0, 0, 0, 2, None, None),
           (4, "CU-1006", "2026-03-22 15:10", None, "2026-02-20 15:10", 0, 0, 0, 0, None, None),
           (5, "CU-1010", "2026-03-28 20:00", None, "2026-02-26 20:00", 2, 0, 0, 0, "referral", "email"),
           (6, "CU-1002", "2026-04-03 16:30", "2026-03-14 11:00", "2026-03-04 16:30", 3, 1, 2, 0,
            "paid-search", "email"),
           (7, "CU-1005", "2026-04-04 09:00", None, "2026-03-05 09:00", 2, 0, 0, 0, "email", "paid-search"),
           (8, "CU-1005", "2026-04-06 17:45", "2026-04-04 09:00", "2026-03-07 17:45", 0, 0, 2, 0, None, None),
           (9, "CU-1012", "2026-04-08 16:20", None, "2026-03-09 16:20", 2, 1, 0, 0, "social", "email"),
           (10, "CU-1003", "2026-04-15 14:00", None, "2026-03-16 14:00", 3, 0, 0, 2, "email", "paid-search"),
           (11, "CU-1012", "2026-04-20 11:00", "2026-04-08 16:20", "2026-03-21 11:00", 1, 0, 2, 0,
            "paid-search", "paid-search"),
           (12, "CU-1009", "2026-04-26 10:05", None, "2026-03-27 10:05", 1, 0, 0, 0, "referral", "referral"),
           (13, "CU-1004", "2026-05-08 10:15", None, "2026-04-08 10:15", 7, 0, 0, 0, "paid-search", "organic"),
           (14, "CU-1011", "2026-05-16 09:40", None, "2026-04-16 09:40", 4, 0, 0, 0, "email", "referral"),
           (15, "CU-1001", "2026-05-20 11:00", "2026-03-10 14:30", "2026-04-20 11:00", 2, 0, 3, 1,
            "email", "organic")])

    check("each conversion's revenue goes to the first channel, the last channel, or by touch to the cent, a "
          "leftover cent going to the largest remainder and a tie to the name that sorts first",
          lambda: q(db, "04-credit-by-conversion.sql"),
          [(1, "100.00", "email", 1, 3, "100.00", "0.00", "33.34"),
           (1, "100.00", "paid-search", 1, 3, "0.00", "100.00", "33.33"),
           (1, "100.00", "social", 1, 3, "0.00", "0.00", "33.33"),
           (2, "240.00", "email", 1, 2, "0.00", "240.00", "120.00"),
           (2, "240.00", "organic", 1, 2, "240.00", "0.00", "120.00"),
           (3, "75.00", "(unattributed)", 0, 0, "75.00", "75.00", "75.00"),
           (4, "310.00", "(unattributed)", 0, 0, "310.00", "310.00", "310.00"),
           (5, "4.99", "email", 1, 2, "0.00", "4.99", "2.50"),
           (5, "4.99", "referral", 1, 2, "4.99", "0.00", "2.49"),
           (6, "57.35", "email", 1, 3, "0.00", "57.35", "19.12"),
           (6, "57.35", "paid-search", 1, 3, "57.35", "0.00", "19.12"),
           (6, "57.35", "social", 1, 3, "0.00", "0.00", "19.11"),
           (7, "49.50", "email", 1, 2, "49.50", "0.00", "24.75"),
           (7, "49.50", "paid-search", 1, 2, "0.00", "49.50", "24.75"),
           (8, "64.00", "(unattributed)", 0, 0, "64.00", "64.00", "64.00"),
           (9, "60.00", "email", 1, 2, "0.00", "60.00", "30.00"),
           (9, "60.00", "social", 1, 2, "60.00", "0.00", "30.00"),
           (10, "89.99", "email", 1, 3, "89.99", "0.00", "30.00"),
           (10, "89.99", "paid-search", 1, 3, "0.00", "89.99", "30.00"),
           (10, "89.99", "social", 1, 3, "0.00", "0.00", "29.99"),
           (11, "35.00", "paid-search", 1, 1, "35.00", "35.00", "35.00"),
           (12, "1250.00", "referral", 1, 1, "1250.00", "1250.00", "1250.00"),
           (13, "150.25", "display", 1, 7, "0.00", "0.00", "21.47"),
           (13, "150.25", "email", 2, 7, "0.00", "0.00", "42.93"),
           (13, "150.25", "organic", 1, 7, "0.00", "150.25", "21.46"),
           (13, "150.25", "paid-search", 1, 7, "150.25", "0.00", "21.46"),
           (13, "150.25", "social", 2, 7, "0.00", "0.00", "42.93"),
           (14, "99.99", "email", 2, 4, "99.99", "0.00", "49.99"),
           (14, "99.99", "referral", 1, 4, "0.00", "99.99", "25.00"),
           (14, "99.99", "social", 1, 4, "0.00", "0.00", "25.00"),
           (15, "42.00", "email", 1, 2, "42.00", "0.00", "21.00"),
           (15, "42.00", "organic", 1, 2, "0.00", "42.00", "21.00")])

    check("by channel, all three models come to 2628.07 with 449.00 unattributed, over by 0.00, while the join "
          "comes to 6459.74, over by 3831.67, and credits affiliate 462.34 where every model gives it nothing",
          lambda: q(db, "05-channel-totals.sql"),
          [("affiliate", "0.00", "0.00", "0.00", "462.34"),
           ("display", "0.00", "0.00", "21.47", "367.25"),
           ("email", "381.48", "362.34", "373.63", "1682.66"),
           ("organic", "240.00", "192.25", "162.46", "589.60"),
           ("paid-search", "242.60", "274.49", "163.66", "888.09"),
           ("referral", "1254.99", "1349.99", "1277.49", "1444.97"),
           ("social", "60.00", "0.00", "180.36", "1024.83"),
           ("(unattributed)", "449.00", "449.00", "449.00", None),
           ("(total)", "2628.07", "2628.07", "2628.07", "6459.74"),
           ("(over revenue)", "0.00", "0.00", "0.00", "3831.67")])

    def cents_of(text):
        whole, part = text.lstrip("-").split(".")
        return (-1 if text.startswith("-") else 1) * (int(whole) * 100 + int(part))

    def consistent(conn):
        # The reports checked against each other rather than against numbers
        # written down.
        credit = q(conn, "04-credit-by-conversion.sql")
        per_conversion, per_channel = {}, {}
        for conversion, revenue, channel, _, _, first, last, linear in credit:
            sums = per_conversion.setdefault(conversion, [cents_of(revenue), 0, 0, 0])
            line = per_channel.setdefault(channel, [0, 0, 0])
            for k, value in enumerate((first, last, linear)):
                sums[k + 1] += cents_of(value)
                line[k] += cents_of(value)
        adds_back = all(s[0] == s[1] == s[2] == s[3] for s in per_conversion.values())
        rows = q(conn, "05-channel-totals.sql")
        totals = {r[0]: r[1:] for r in rows}
        lines = [r for r in rows if r[0] not in ("(total)", "(over revenue)")]
        lines_match = (set(per_channel) <= set(totals)
                       and all(tuple(cents_of(v) for v in r[1:4]) == tuple(per_channel.get(r[0], [0, 0, 0]))
                               for r in lines))
        revenue = cents_of(q(conn, "01-log-shape.sql")[0][5])
        added = [sum(cents_of(r[k]) for r in lines if r[k] is not None) for k in range(1, 5)]
        totals_match = ([cents_of(v) for v in totals["(total)"]] == added
                        and [cents_of(v) for v in totals["(over revenue)"]] == [a - revenue for a in added])
        joined = {r[0]: r[3] for r in q(conn, "02-naive-join.sql")}
        join_match = (set(joined) <= set(totals)
                      and all(r[4] == joined.get(r[0], None if r[0] == "(unattributed)" else "0.00")
                              for r in rows if r[0] != "(over revenue)"))
        windows = q(conn, "03-touch-windows.sql")
        touched = dict(conn.execute("SELECT customer, COUNT(*) FROM touches GROUP BY customer").fetchall())
        pairs_match = (all(sum(r[5:9]) == touched.get(r[1], 0) for r in windows)
                       and sum(sum(r[5:9]) for r in windows) == q(conn, "02-naive-join.sql")[-1][1])
        counted = {r[0]: r[4] for r in credit}
        window_match = all(counted[r[0]] == r[5] for r in windows)
        return adds_back, lines_match, totals_match, join_match, pairs_match, window_match

    check("on the sample, every conversion's credit adds back to its revenue under all three models; query 05 "
          "has a line for every channel query 04 credits, each line query 04 added up, a (total) that adds up "
          "the lines and an (over revenue) that is that less query 01's revenue, with query 02 as its join "
          "column; and query 03 puts every touch by a converting customer into exactly one of its four counts "
          "for each of their conversions, the counts adding up to the join's pairs, with as many in the window "
          "as query 04 counts",
          lambda: consistent(db), (True, True, True, True, True, True))

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

    def printed(conn, name, row):
        # One row of a report as print_table lays it out, below the rule.
        headers, rows = run_query(conn, SQL_DIR / name)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            print_table(headers, rows)
        return out.getvalue().splitlines()[2 + row]

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
            (Path(folder) / "nothing").mkdir()
            for target in (Gone(folder), Path(folder) / "nothing", Path(folder) / "not_there"):
                err = io.StringIO()
                try:
                    with contextlib.redirect_stderr(err):
                        run_all(db, target)
                    results.append((0, ""))
                except SystemExit as stop:
                    results.append((stop.code, err.getvalue().strip()))
        return results

    check("all five reports print as tables, with their column names, a rule as wide as each column, how many "
          "rows each prints and the first of them; a missing value prints as a blank cell, in the middle of a "
          "row and at its end; and a query file that fails, has no query result, is not UTF-8 or is gone by "
          "the time it is read, or a folder named like one, stops them with a one-line message, as does a "
          "query folder that is empty or not there",
          lambda: [reports(), printed(db, "03-touch-windows.sql", 2), printed(db, "05-channel-totals.sql", 7),
                   broken_reports()],
          [[("=== 01-log-shape.sql ===",
             "touches  channels  customers_touched  conversions  customers_converting  revenue",
             "-------  --------  -----------------  -----------  --------------------  -------", 1,
             "40       7         11                 15           11                    2628.07"),
            ("=== 02-naive-join.sql ===", "channel      pairs  conversions  credited",
             "-----------  -----  -----------  --------", 8, "affiliate    4      4            462.34"),
            ("=== 03-touch-windows.sql ===",
             "conversion  customer  converted_at      previous          lookback_from     in_window  after  "
             "earlier  too_old  first_touch  last_touch",
             "----------  --------  ----------------  ----------------  ----------------  ---------  -----  "
             "-------  -------  -----------  -----------", 15,
             "1           CU-1001   2026-03-10 14:30                    2026-02-08 14:30  3          3      "
             "0        0        email        paid-search"),
            ("=== 04-credit-by-conversion.sql ===",
             "conversion  revenue  channel         touches  in_window  first_touch  last_touch  linear",
             "----------  -------  --------------  -------  ---------  -----------  ----------  -------", 32,
             "1           100.00   email           1        3          100.00       0.00        33.34"),
            ("=== 05-channel-totals.sql ===", "line            first_touch  last_touch  linear   naive_join",
             "--------------  -----------  ----------  -------  ----------", 10,
             "affiliate       0.00         0.00        0.00     462.34")],
           "3           CU-1007   2026-03-18 12:00                    2026-02-16 12:00  0          0      "
           "0        2",
           "(unattributed)  449.00       449.00      449.00",
           [(2, '01-broken.sql: did not run: near "SELEC": syntax error'),
            (2, "01-empty.sql: did not run: has no query result to print"),
            (2, "01-ansi.sql: is not UTF-8 text"),
            (2, "01-folder.sql: is a folder, not a query file"),
            (2, "01-gone.sql: No such file or directory"),
            (2, "nothing: holds no query files"),
            (2, "not_there: holds no query files")]])

    # Logs built for cases the sample does not reach on its own. None of them
    # goes through the loader.
    edges = new_db(
        [(1, "E1", "email", "2025-12-16 09:00"), (2, "E1", "social", "2025-12-16 08:59"),
         (3, "E1", "display", "2026-01-15 09:00"), (4, "E1", "organic", "2026-01-15 09:01"),
         (5, "E2", "referral", "2028-01-31 00:10"), (6, "E2", "paid-search", "2028-01-31 00:09"),
         (7, "E3", "social", "2026-03-02 10:00"), (8, "E3", "email", "2026-03-03 10:00"),
         (9, "E4", "podcast", "2026-03-01 12:00")],
        [(1, "E1", "2026-01-15 09:00", 1001), (2, "E1", "2026-02-14 09:00", 2000),
         (3, "E2", "2028-03-01 00:10", 500), (4, "E3", "2026-03-01 10:00", 999),
         (5, "E5", "2026-03-05 12:00", 50000)])
    check("across a change of year and a leap February, a touch exactly 30 days before counts and one a minute "
          "earlier does not; a touch at the moment of a conversion counts toward it and not toward the next "
          "one, even when that next one comes exactly 30 days later; touches only after a conversion leave it "
          "unattributed; a channel only a customer who never converted touched still gets its line; and when "
          "the revenue the join drops outweighs what it counts twice, it comes in under the revenue, with a "
          "minus sign",
          lambda: [q(edges, "03-touch-windows.sql"), q(edges, "04-credit-by-conversion.sql"),
                   q(edges, "05-channel-totals.sql")],
          [[(1, "E1", "2026-01-15 09:00", None, "2025-12-16 09:00", 2, 1, 0, 1, "email", "display"),
            (2, "E1", "2026-02-14 09:00", "2026-01-15 09:00", "2026-01-15 09:00", 1, 0, 3, 0,
             "organic", "organic"),
            (3, "E2", "2028-03-01 00:10", None, "2028-01-31 00:10", 1, 0, 0, 1, "referral", "referral"),
            (4, "E3", "2026-03-01 10:00", None, "2026-01-30 10:00", 0, 2, 0, 0, None, None),
            (5, "E5", "2026-03-05 12:00", None, "2026-02-03 12:00", 0, 0, 0, 0, None, None)],
           [(1, "10.01", "display", 1, 2, "0.00", "10.01", "5.01"),
            (1, "10.01", "email", 1, 2, "10.01", "0.00", "5.00"),
            (2, "20.00", "organic", 1, 1, "20.00", "20.00", "20.00"),
            (3, "5.00", "referral", 1, 1, "5.00", "5.00", "5.00"),
            (4, "9.99", "(unattributed)", 0, 0, "9.99", "9.99", "9.99"),
            (5, "500.00", "(unattributed)", 0, 0, "500.00", "500.00", "500.00")],
           [("display", "0.00", "10.01", "5.01", "30.01"),
            ("email", "10.01", "0.00", "5.00", "40.00"),
            ("organic", "20.00", "20.00", "20.00", "30.01"),
            ("paid-search", "0.00", "0.00", "0.00", "5.00"),
            ("podcast", "0.00", "0.00", "0.00", "0.00"),
            ("referral", "5.00", "5.00", "5.00", "5.00"),
            ("social", "0.00", "0.00", "0.00", "40.00"),
            ("(unattributed)", "509.99", "509.99", "509.99", None),
            ("(total)", "545.00", "545.00", "545.00", "150.02"),
            ("(over revenue)", "0.00", "0.00", "0.00", "-394.98")]])

    def reversed_logs():
        # The sample again, stored in the opposite order in tables with no key
        # and no index, so nothing hands the rows back in order unless a query
        # sorts them.
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE touches (touch_id INTEGER, customer TEXT, channel TEXT, touched_at TEXT)")
        conn.execute("CREATE TABLE conversions (conversion_id INTEGER, customer TEXT, converted_at TEXT, "
                     "revenue_cents INTEGER)")
        touches, conversions = load(TOUCHES_CSV, CONVERSIONS_CSV)
        conn.executemany("INSERT INTO touches VALUES (?, ?, ?, ?)", list(reversed(touches)))
        conn.executemany("INSERT INTO conversions VALUES (?, ?, ?, ?)", list(reversed(conversions)))
        return [q(conn, path.name) == q(db, path.name) for path in sorted(SQL_DIR.glob("*.sql"))]

    # Touch ids and conversion ids that run against time: the sort has to be
    # on the moment, with the id only settling a tie within one minute.
    backwards = new_db(
        [(9, "B1", "email", "2026-06-01 10:00"), (8, "B1", "social", "2026-06-02 10:00"),
         (7, "B1", "paid-search", "2026-06-03 10:00"), (5, "B1", "display", "2026-06-04 12:00"),
         (6, "B1", "organic", "2026-06-04 12:00"), (3, "B1", "referral", "2026-06-10 10:00"),
         (4, "B1", "email", "2026-06-12 10:00"), (2, "B1", "email", "2026-06-15 10:00")],
        [(2, "B1", "2026-06-05 08:00", 12345), (1, "B1", "2026-06-20 08:00", 6789)])
    check("with touch ids and conversion ids running against time, the previous conversion, the first touch "
          "and the last touch are still found by time, in the channel totals too, and of two touches in one "
          "minute the higher id is the later; a last touch on a channel with two touches in the window still "
          "takes the revenue; and the sample stored in the opposite order, in tables with no key and no "
          "index, gives the same five reports",
          lambda: [q(backwards, "03-touch-windows.sql"), q(backwards, "04-credit-by-conversion.sql"),
                   q(backwards, "05-channel-totals.sql"), reversed_logs()],
          [[(1, "B1", "2026-06-20 08:00", "2026-06-05 08:00", "2026-05-21 08:00", 3, 0, 5, 0, "referral",
             "email"),
            (2, "B1", "2026-06-05 08:00", None, "2026-05-06 08:00", 5, 3, 0, 0, "email", "organic")],
           [(1, "67.89", "email", 2, 3, "0.00", "67.89", "45.26"),
            (1, "67.89", "referral", 1, 3, "67.89", "0.00", "22.63"),
            (2, "123.45", "display", 1, 5, "0.00", "0.00", "24.69"),
            (2, "123.45", "email", 1, 5, "123.45", "0.00", "24.69"),
            (2, "123.45", "organic", 1, 5, "0.00", "123.45", "24.69"),
            (2, "123.45", "paid-search", 1, 5, "0.00", "0.00", "24.69"),
            (2, "123.45", "social", 1, 5, "0.00", "0.00", "24.69")],
           [("display", "0.00", "0.00", "24.69", "191.34"),
            ("email", "123.45", "67.89", "69.95", "574.02"),
            ("organic", "0.00", "123.45", "24.69", "191.34"),
            ("paid-search", "0.00", "0.00", "24.69", "191.34"),
            ("referral", "67.89", "0.00", "22.63", "191.34"),
            ("social", "0.00", "0.00", "24.69", "191.34"),
            ("(unattributed)", "0.00", "0.00", "0.00", None),
            ("(total)", "191.34", "191.34", "191.34", "1530.72"),
            ("(over revenue)", "0.00", "0.00", "0.00", "1339.38")],
           [True] * 5])

    # Seven channels share six cents, so every share cuts down to nothing and
    # the cents go by name; a conversion worth nothing credits nothing; and a
    # channel with three of four touches on 0.99 is owed 0.7425, which has to
    # be cut from 297 quarters of a cent, not taken as three 24-cent quarters.
    tiny = new_db([(n, "T1", channel, f"2026-07-01 1{n}:00") for n, channel in
                   enumerate(["social", "referral", "paid-search", "organic", "email", "display", "affiliate"],
                             1)]
                  + [(8, "T2", "email", "2026-07-02 09:00"), (9, "T2", "social", "2026-07-02 09:30")]
                  + [(10, "T3", "email", "2026-07-03 09:00"), (11, "T3", "social", "2026-07-03 09:10"),
                     (12, "T3", "email", "2026-07-03 09:20"), (13, "T3", "email", "2026-07-03 09:30")],
                  [(1, "T1", "2026-07-01 20:00", 6), (2, "T2", "2026-07-02 10:00", 0),
                   (3, "T3", "2026-07-03 10:00", 99)])
    check("when the revenue is smaller than the number of channels every share cuts down to nothing and the "
          "leftover cents go by name, a conversion worth nothing credits nothing, and a channel with three of "
          "four touches is cut down from its whole share, all adding up the same",
          lambda: [q(tiny, "04-credit-by-conversion.sql"), q(tiny, "05-channel-totals.sql")[-3:]],
          [[(1, "0.06", "affiliate", 1, 7, "0.00", "0.06", "0.01"),
            (1, "0.06", "display", 1, 7, "0.00", "0.00", "0.01"),
            (1, "0.06", "email", 1, 7, "0.00", "0.00", "0.01"),
            (1, "0.06", "organic", 1, 7, "0.00", "0.00", "0.01"),
            (1, "0.06", "paid-search", 1, 7, "0.00", "0.00", "0.01"),
            (1, "0.06", "referral", 1, 7, "0.00", "0.00", "0.01"),
            (1, "0.06", "social", 1, 7, "0.06", "0.00", "0.00"),
            (2, "0.00", "email", 1, 2, "0.00", "0.00", "0.00"),
            (2, "0.00", "social", 1, 2, "0.00", "0.00", "0.00"),
            (3, "0.99", "email", 3, 4, "0.99", "0.99", "0.74"),
            (3, "0.99", "social", 1, 4, "0.00", "0.00", "0.25")],
           [("(unattributed)", "0.00", "0.00", "0.00", None),
            ("(total)", "1.05", "1.05", "1.05", "4.38"),
            ("(over revenue)", "0.00", "0.00", "0.00", "3.33")]])

    # The costliest logs found within the loader's limits. 50000 customers
    # with one touch and one conversion each is the most rows with one pair
    # each; 25000 customers with two touches before two conversions is the
    # most pairs with the most windows; and one customer with 50000 touches,
    # each on a channel of its own, before two conversions, beside 49998
    # conversions no touch reached, is the costliest found for queries 03, 04
    # and 05.
    def stamp(minutes):
        return (datetime(2026, 1, 1) + timedelta(minutes=minutes)).strftime(MOMENT)

    channels = ["affiliate", "display", "email", "organic", "paid-search", "referral", "social"]
    widest = new_db([(n + 1, f"C{n}", channels[n % 7], stamp(n)) for n in range(MOST_TOUCHES)],
                    [(n + 1, f"C{n}", stamp(n + 60), 99999999) for n in range(MOST_CONVERSIONS)])
    paired = new_db([(2 * c + k + 1, f"C{c}", channels[(2 * c + k) % 7], stamp(k))
                     for c in range(25000) for k in range(2)],
                    [(2 * c + k + 1, f"C{c}", stamp(10 + k), 99999999) for c in range(25000) for k in range(2)])
    spread = new_db([(n + 1, "C1", f"c{n}", stamp(n % 40000)) for n in range(MOST_TOUCHES)],
                    [(1, "C1", stamp(40000), 99999999), (2, "C1", stamp(40001), 99999999)]
                    + [(n + 3, f"U{n}", stamp(n), 99999999) for n in range(MOST_CONVERSIONS - 2)])

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
        check("50000 customers with a touch and a conversion each, 25000 with two touches before two conversions, "
              "and one customer with 50000 touches on 50000 channels beside 49998 conversions no touch reached "
              "all run through every query inside the step budget, and a query that would run for ever is "
              "stopped by it",
              lambda: [[ends(conn, path.name) for path in sorted(SQL_DIR.glob("*.sql"))]
                       for conn in (widest, paired, spread)] + [endless(tmp)],
              [[(1, (50000, 7, 50000, 50000, 50000, "49999999500.00"),
                 (50000, 7, 50000, 50000, 50000, "49999999500.00")),
                (8, ("affiliate", 7143, 7143, "7142999928.57"), ("(total)", 50000, 50000, "49999999500.00")),
                (50000, (1, "C0", "2026-01-01 01:00", None, "2025-12-02 01:00", 1, 0, 0, 0, "affiliate",
                         "affiliate"),
                 (50000, "C49999", "2026-02-04 18:19", None, "2026-01-05 18:19", 1, 0, 0, 0, "referral",
                  "referral")),
                (50000, (1, "999999.99", "affiliate", 1, 1, "999999.99", "999999.99", "999999.99"),
                 (50000, "999999.99", "referral", 1, 1, "999999.99", "999999.99", "999999.99")),
                (10, ("affiliate", "7142999928.57", "7142999928.57", "7142999928.57", "7142999928.57"),
                 ("(over revenue)", "0.00", "0.00", "0.00", "0.00"))],
               [(1, (50000, 7, 25000, 50000, 25000, "49999999500.00"),
                 (50000, 7, 25000, 50000, 25000, "49999999500.00")),
                (8, ("affiliate", 14286, 14286, "14285999857.14"), ("(total)", 100000, 50000, "99999999000.00")),
                (50000, (1, "C0", "2026-01-01 00:10", None, "2025-12-02 00:10", 2, 0, 0, 0, "affiliate",
                         "display"),
                 (50000, "C24999", "2026-01-01 00:11", "2026-01-01 00:10", "2025-12-02 00:11", 0, 0, 2, 0, None,
                  None)),
                (75000, (1, "999999.99", "affiliate", 1, 2, "999999.99", "0.00", "500000.00"),
                 (50000, "999999.99", "(unattributed)", 0, 0, "999999.99", "999999.99", "999999.99")),
                (10, ("affiliate", "3571999964.28", "3570999964.29", "3571500000.00", "14285999857.14"),
                 ("(over revenue)", "0.00", "0.00", "0.00", "49999999500.00"))],
               [(1, (50000, 50000, 1, 50000, 49999, "49999999500.00"),
                 (50000, 50000, 1, 50000, 49999, "49999999500.00")),
                (50001, ("c0", 2, 2, "1999999.98"), ("(total)", 100000, 2, "99999999000.00")),
                (50000, (1, "C1", "2026-01-28 18:40", None, "2025-12-29 18:40", 50000, 0, 0, 0, "c0", "c39999"),
                 (50000, "U49997", "2026-02-04 17:17", None, "2026-01-05 17:17", 0, 0, 0, 0, None, None)),
                (99999, (1, "999999.99", "c0", 1, 50000, "999999.99", "0.00", "20.00"),
                 (50000, "999999.99", "(unattributed)", 0, 0, "999999.99", "999999.99", "999999.99")),
                (50003, ("c0", "999999.99", "0.00", "20.00", "1999999.98"),
                 ("(over revenue)", "0.00", "0.00", "0.00", "49999999500.00"))],
               "stopped after 200000 thousand steps"])

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

        thead = ",".join(TOUCH_COLUMNS) + "\n"
        chead = ",".join(CONVERSION_COLUMNS) + "\n"
        small = thead + "1,KIT,email,2026-04-01 10:00\n2,KIT,social,2026-04-02 10:00\n"
        csmall = chead + "1,KIT,2026-04-03 10:00,25.00\n"

        def touch_log(name, content):
            return rejection(load_touches, csv_file(name, content))

        def conversion_log(name, content):
            return rejection(load_conversions, csv_file(name, content))

        def sized(result):
            code, loaded = result
            return (code, len(loaded)) if code == 0 else result

        check("the included bad touch log is refused for a date that does not exist, naming its row; a touch_id "
              "or conversion_id listed twice, a touch logged twice and a customer converting twice in one minute "
              "are refused by name, while two channels in one minute, and two customers converting in one "
              "minute, load",
              lambda: [rejection(load, HERE / "data" / "invalid-touches.csv", CONVERSIONS_CSV),
                       touch_log("twice_id.csv", small + "2,KIT,display,2026-04-02 11:00\n"),
                       touch_log("again.csv", small + "3,KIT,social,2026-04-02 10:00\n"),
                       touch_log("same_minute.csv", small + "3,KIT,display,2026-04-02 10:00\n"),
                       conversion_log("twice_id.csv", csmall + "1,BOX,2026-04-03 11:00,5.00\n"),
                       conversion_log("twice_moment.csv", csmall + "2,KIT,2026-04-03 10:00,5.00\n"),
                       conversion_log("shared_minute.csv", csmall + "2,BOX,2026-04-03 10:00,5.00\n")],
              [(2, "invalid-touches.csv row 25: touched_at '2026-04-31 09:30' is not a date and time written like "
                   "2026-04-15 14:00, from 1970-01-01 00:00 to 2200-12-31 23:59"),
               (2, "twice_id.csv row 4: touch_id 2 appears twice; one row per touch"),
               (2, "again.csv row 4: touch 3 repeats touch 2 (KIT, social, 2026-04-02 10:00); a touch logged "
                   "twice would be credited twice"),
               (0, [(1, "KIT", "email", "2026-04-01 10:00"), (2, "KIT", "social", "2026-04-02 10:00"),
                    (3, "KIT", "display", "2026-04-02 10:00")]),
               (2, "twice_id.csv row 3: conversion_id 1 appears twice; one row per conversion"),
               (2, "twice_moment.csv row 3: KIT converts twice at 2026-04-03 10:00, as conversions 1 and 2; one "
                   "conversion per customer per minute, with the revenue added together"),
               (0, [(1, "KIT", "2026-04-03 10:00", 2500), (2, "BOX", "2026-04-03 10:00", 500)])])

        bad_ids = ["0", "007", "-1", "1.0", "1e3", "", "1000000000", "one", "\u0661"]
        customers = ["kit", "KIT 2", "KIT--2", "-KIT", "KIT-", "A" * 25, "", "CAF\u00c9", "\uff2b\uff29\uff34"]
        channels = ["Email", "paid search", "paid_search", "paid--search", "-email", "email-", "a" * 25, "",
                    "caf\u00e9", "\uff45mail"]
        check("a touch_id or conversion_id of 0, with a leading zero, a sign, a point or an exponent, blank, past "
              "nine digits, a word or an Arabic-Indic digit is refused; a customer code in lower case, with a "
              "space, a doubled or outer hyphen, over 24 characters, blank, accented or in fullwidth letters is "
              "refused, in either log; a channel in capitals, with a space, an underscore, a doubled or outer "
              "hyphen, over 24 characters, blank, accented or in fullwidth letters is refused; and the largest "
              "id, a 24-character code and a 24-character channel load",
              lambda: [touch_log(f"tid{k}.csv", thead + f'"{raw}",KIT,email,2026-04-01 10:00\n')
                       for k, raw in enumerate(bad_ids)]
                      + [conversion_log(f"cid{k}.csv", chead + f'"{raw}",KIT,2026-04-03 10:00,25.00\n')
                         for k, raw in enumerate(bad_ids)]
                      + [touch_log(f"who{k}.csv", thead + f'1,"{raw}",email,2026-04-01 10:00\n')
                         for k, raw in enumerate(customers)]
                      + [conversion_log(f"cwho{k}.csv", chead + f'1,"{raw}",2026-04-03 10:00,25.00\n')
                         for k, raw in enumerate(customers)]
                      + [touch_log(f"via{k}.csv", thead + f'1,KIT,"{raw}",2026-04-01 10:00\n')
                         for k, raw in enumerate(channels)]
                      + [touch_log("widest.csv", thead + "999999999,ABCDEFGH-1234567-ABCDEFG,abcdefgh-1234567-abcdefg,"
                                                         "2026-04-01 10:00\n")],
              [(2, f"tid{k}.csv row 2: touch_id {raw!r} is not a whole number from 1 to 999999999 with no "
                   "leading zero") for k, raw in enumerate(bad_ids)]
              + [(2, f"cid{k}.csv row 2: conversion_id {raw!r} is not a whole number from 1 to 999999999 with "
                     "no leading zero") for k, raw in enumerate(bad_ids)]
              + [(2, f"who{k}.csv row 2: customer {raw!r} is not a customer code: capital letters and digits, "
                     "joined by single hyphens, at most 24 characters") for k, raw in enumerate(customers)]
              + [(2, f"cwho{k}.csv row 2: customer {raw!r} is not a customer code: capital letters and digits, "
                     "joined by single hyphens, at most 24 characters") for k, raw in enumerate(customers)]
              + [(2, f"via{k}.csv row 2: channel {raw!r} is not a channel name: small letters and digits, joined "
                     "by single hyphens, at most 24 characters") for k, raw in enumerate(channels)]
              + [(0, [(999999999, "ABCDEFGH-1234567-ABCDEFG", "abcdefgh-1234567-abcdefg", "2026-04-01 10:00")])])

        moments = ["2026-04-31 09:30", "2026-02-29 10:00", "2026-04-15 24:00", "2026-04-15 14:60",
                   "2026-04-15T14:00", "2026-04-15 14:00:00", "2026-04-15", "2026-4-15 14:00", "2026-04-15  14:00",
                   "1969-12-31 23:59", "2201-01-01 00:00", "", "15/04/2026 14:00",
                   "\uff12\uff10\uff12\uff16-04-15 14:00"]
        amounts = ["-5.00", "5", "5.0", "5.000", "05.00", "1000000.00", "1e3", "", "5,00", "$5.00", ".50",
                   "\u0661\u0660.\u0660\u0660", "1\u0660.\u0660\u0660"]
        check("a moment on a day that does not exist, at 24:00 or minute 60, with a T, with seconds, with no time, "
              "without leading zeros, with two spaces, before 1970 or after 2200, blank, written day first or in "
              "fullwidth digits is refused, in either log; revenue that is negative, whole, to one or three "
              "places, zero-padded, seven digits, in exponent form, blank, with a comma, a dollar sign or no "
              "digit before the point, or with Arabic-Indic digits in it is refused; and the first and last "
              "minutes allowed, a leap day, 0.00 and 999999.99 load",
              lambda: [touch_log(f"when{k}.csv", thead + f'1,KIT,email,"{raw}"\n') for k, raw in enumerate(moments)]
                      + [conversion_log(f"cwhen{k}.csv", chead + f'1,KIT,"{raw}",25.00\n')
                         for k, raw in enumerate(moments)]
                      + [conversion_log(f"amount{k}.csv", chead + f'1,KIT,2026-04-03 10:00,"{raw}"\n')
                         for k, raw in enumerate(amounts)]
                      + [touch_log("bounds.csv", thead + "1,KIT,email,1970-01-01 00:00\n2,KIT,email,2028-02-29 10:00\n"
                                                         "3,KIT,email,2200-12-31 23:59\n"),
                         conversion_log("extremes.csv", chead + "1,KIT,2026-04-03 10:00,0.00\n"
                                                                "2,KIT,2026-04-04 10:00,999999.99\n")],
              [(2, f"when{k}.csv row 2: touched_at {raw!r} is not a date and time written like 2026-04-15 14:00, "
                   "from 1970-01-01 00:00 to 2200-12-31 23:59") for k, raw in enumerate(moments)]
              + [(2, f"cwhen{k}.csv row 2: converted_at {raw!r} is not a date and time written like "
                     "2026-04-15 14:00, from 1970-01-01 00:00 to 2200-12-31 23:59") for k, raw in enumerate(moments)]
              + [(2, f"amount{k}.csv row 2: revenue {raw!r} is not an amount from 0.00 to 999999.99 written like "
                     "149.99") for k, raw in enumerate(amounts)]
              + [(0, [(1, "KIT", "email", "1970-01-01 00:00"), (2, "KIT", "email", "2028-02-29 10:00"),
                      (3, "KIT", "email", "2200-12-31 23:59")]),
                 (0, [(1, "KIT", "2026-04-03 10:00", 0), (2, "KIT", "2026-04-04 10:00", 99999999)])])

        check("rows are counted past blank lines and a line of spaces, and a stray quote is named by its own row, "
              "in a data row or in the header; rows with too many or too few fields, a line of commas, a tab, "
              "text after a closing quote, a quote left open, a field past the parser's limit, and a bad, renamed "
              "or reordered header, in either log, also one found after a blank line, written as one quoted field "
              "or with a trailing comma, are refused, and a long value or header is cut short in the message, by "
              "one character as well as by many",
              lambda: [touch_log("rows.csv", small + "\n   \n\n3,kit,email,2026-04-03 10:00\n"),
                       touch_log("quote.csv", small + '3,"KIT,email,2026-04-03 10:00\n4,KIT",email,2026-04-04 10:00\n'),
                       touch_log("unclosed.csv", small + '3,"KIT,email,2026-04-03 10:00\n'),
                       touch_log("wide.csv", small + "3,KIT,email,2026-04-03 10:00,extra\n"),
                       touch_log("narrow.csv", small + "3,KIT,email\n"),
                       touch_log("commas.csv", small + ",,,\n"),
                       touch_log("tab.csv", small + "3,KIT\t,email,2026-04-03 10:00\n"),
                       touch_log("after.csv", small + '3,"KIT"x,email,2026-04-03 10:00\n'),
                       touch_log("huge_field.csv", small + "3," + "A" * 200000 + ",email,2026-04-03 10:00\n"),
                       touch_log("header.csv", 'touch_id,"customer"x,channel,touched_at\n'),
                       touch_log("open_header.csv", '"touch_id,customer,channel,touched_at\n'),
                       touch_log("renamed.csv", "touch_id,customer,source,touched_at\n"),
                       touch_log("reordered.csv", "customer,touch_id,channel,touched_at\n"),
                       touch_log("late_renamed.csv", "\ntouch_id,customer,source,touched_at\n"),
                       touch_log("quoted_header.csv", '"touch_id,customer,channel,touched_at"\n'),
                       touch_log("comma_header.csv", "touch_id,customer,channel,touched_at,\n"),
                       conversion_log("amount_header.csv", "conversion_id,customer,converted_at,amount\n"),
                       touch_log("long_header.csv", "touch_id,customer,channel,touched_at" + "x" * 100 + "\n"),
                       touch_log("over_header.csv", "touch_id,customer,channel,touched_at" + "x" * 45 + "\n"),
                       touch_log("long_value.csv", small + "3," + "B" * 100 + ",email,2026-04-03 10:00\n"),
                       touch_log("just_over.csv", small + "3," + "C" * 41 + ",email,2026-04-03 10:00\n")],
              [(2, "rows.csv row 7: customer 'kit' is not a customer code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "quote.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "unclosed.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "wide.csv row 4: has more fields than the header"),
               (2, "narrow.csv row 4: has fewer fields than the header"),
               (2, "commas.csv row 4: touch_id '' is not a whole number from 1 to 999999999 with no leading zero"),
               (2, "tab.csv row 4: customer 'KIT\\t' is not a customer code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "after.csv row 4: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "huge_field.csv row 4: has a field over 131072 characters long"),
               (2, "header.csv row 1: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "open_header.csv row 1: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "renamed.csv row 1: expected columns 'touch_id,customer,channel,touched_at', "
                   "got 'touch_id,customer,source,touched_at'"),
               (2, "reordered.csv row 1: expected columns 'touch_id,customer,channel,touched_at', "
                   "got 'customer,touch_id,channel,touched_at'"),
               (2, "late_renamed.csv row 2: expected columns 'touch_id,customer,channel,touched_at', "
                   "got 'touch_id,customer,source,touched_at'"),
               (2, "quoted_header.csv row 1: expected columns 'touch_id,customer,channel,touched_at', "
                   "got '\"touch_id,customer,channel,touched_at\"'"),
               (2, "comma_header.csv row 1: expected columns 'touch_id,customer,channel,touched_at', "
                   "got 'touch_id,customer,channel,touched_at,'"),
               (2, "amount_header.csv row 1: expected columns 'conversion_id,customer,converted_at,revenue', "
                   "got 'conversion_id,customer,converted_at,amount'"),
               (2, "long_header.csv row 1: expected columns 'touch_id,customer,channel,touched_at', "
                   "got 'touch_id,customer,channel,touched_at" + "x" * 44 + "' and 56 more characters"),
               (2, "over_header.csv row 1: expected columns 'touch_id,customer,channel,touched_at', "
                   "got 'touch_id,customer,channel,touched_at" + "x" * 44 + "' and 1 more character"),
               (2, "long_value.csv row 4: customer '" + "B" * 40 + "' and 60 more characters is not a customer "
                   "code: capital letters and digits, joined by single hyphens, at most 24 characters"),
               (2, "just_over.csv row 4: customer '" + "C" * 40 + "' and 1 more character is not a customer "
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
            lines, _ = open_csv(path, Dropped(text), TOUCH_COLUMNS)
            return list(records(path, lines, TOUCH_COLUMNS))

        def capped(text):
            return len(list(read_lines(Path(tmp) / "cap.csv", io.StringIO(text))))

        far_down = "".join(f"{n + 1},C{n},email,2026-04-01 10:00\n" for n in range(20000))
        conversions_far_down = "".join(f"{n + 1},C{n},2026-04-01 10:00,1.00\n" for n in range(20000))
        check("an empty file, one of blank lines, one with only a header, in either log, also after a blank line, "
              "one that is not UTF-8 from its first line or only far down, or holds only part of a byte-order "
              "mark, a folder, a read that gives way before the header or partway through, and a line past "
              "1000000 characters, with or without a byte-order mark, are refused, a line of exactly 1000000 "
              "passing with either; while a byte-order mark, blank lines before the header, spaces around "
              "unquoted fields, in the header too, and a line holding one empty quoted field, which is passed "
              "over like a blank one, load, and rows are counted the same with Windows line endings",
              lambda: [touch_log("empty.csv", ""),
                       conversion_log("empty_conversions.csv", ""),
                       touch_log("blank_only.csv", "\n  \n\n"),
                       conversion_log("blank_conversions.csv", "\n  \n\n"),
                       touch_log("bare.csv", thead),
                       conversion_log("bare_conversions.csv", chead),
                       touch_log("late_bare.csv", "\n" + thead),
                       rejection(load_touches, byte_file("latin1.csv", thead.encode("utf-8")[:-1] + b"\xc9\n")),
                       rejection(load_touches, byte_file("late_latin1.csv", (thead + far_down).encode("utf-8")
                                                         + b"20001,CAF\xc9,email,2026-04-01 10:00\n")),
                       rejection(load_touches, byte_file("part_mark.csv", b"\xef\xbb")),
                       rejection(load_touches, Path(tmp)),
                       rejection(dropped, ""),
                       rejection(dropped, small),
                       touch_log("long_line.csv", small + "," * 1000001 + "\n"),
                       rejection(capped, "x" * 1000001 + "\n"),
                       rejection(capped, "\ufeff" + "x" * 1000001 + "\r\n"),
                       rejection(capped, "x" * 1000000 + "\r\n"),
                       rejection(capped, "\ufeff" + "x" * 1000000 + "\r\n"),
                       touch_log("windows.csv", (small + "3,kit,email,2026-04-03 10:00\n").replace("\n", "\r\n")),
                       touch_log("marked.csv", "\ufeff touch_id , customer , channel , touched_at \n"
                                               " 1 , KIT , email , 2026-04-01 10:00 \n2,KIT,social,2026-04-02 10:00\n"),
                       touch_log("leading.csv", "\n  \n" + small),
                       touch_log("quoted_blank.csv", small + '""\n')],
              [(2, "empty.csv: is empty"),
               (2, "empty_conversions.csv: is empty"),
               (2, "blank_only.csv: is empty"),
               (2, "blank_conversions.csv: is empty"),
               (2, "bare.csv row 1: no data rows after the header"),
               (2, "bare_conversions.csv row 1: no data rows after the header"),
               (2, "late_bare.csv row 2: no data rows after the header"),
               (2, "latin1.csv: is not UTF-8 text"),
               (2, "late_latin1.csv: is not UTF-8 text"),
               (2, "part_mark.csv: is not UTF-8 text"),
               (2, f"{Path(tmp).name}: is a folder, not a file"),
               (2, "dropped.csv: Input/output error"),
               (2, "dropped.csv: Input/output error"),
               (2, "long_line.csv row 4: runs past 1000000 characters on one line"),
               (2, "cap.csv row 1: runs past 1000000 characters on one line"),
               (2, "cap.csv row 1: runs past 1000000 characters on one line"),
               (0, 1),
               (0, 1),
               (2, "windows.csv row 4: customer 'kit' is not a customer code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (0, [(1, "KIT", "email", "2026-04-01 10:00"), (2, "KIT", "social", "2026-04-02 10:00")]),
               (0, [(1, "KIT", "email", "2026-04-01 10:00"), (2, "KIT", "social", "2026-04-02 10:00")]),
               (0, [(1, "KIT", "email", "2026-04-01 10:00"), (2, "KIT", "social", "2026-04-02 10:00")])])

        def stamps(count):
            return [(datetime(2026, 1, 1) + timedelta(minutes=n)).strftime(MOMENT) for n in range(count)]

        def touch_rows(customers, per_customer):
            at = stamps(per_customer)
            return "".join(f"{c * per_customer + k + 1},C{c},email,{at[k]}\n"
                           for c in range(customers) for k in range(per_customer))

        def conversion_rows(customers, per_customer):
            at = stamps(per_customer)
            return "".join(f"{c * per_customer + k + 1},C{c},{at[k]},1.00\n"
                           for c in range(customers) for k in range(per_customer))

        # One customer with 317 touches and 316 conversions pairs up 100172
        # times, and 400 with 250 exactly 100000; 25000 customers with two of
        # each is 100000 too, with both logs at their limit.
        check("a log of more than 50000 touches or 50000 conversions is stopped as it is read, before a bad byte "
              "further down, and logs whose touches and conversions pair up more than 100000 times by customer "
              "are refused, while logs of exactly 50000 rows each that pair up exactly 100000 times load",
              lambda: [rejection(load_touches, byte_file("too_many.csv", (thead + touch_rows(MOST_TOUCHES + 1, 1)
                                                                            + far_down).encode("utf-8")
                                                         + b"20001,CAF\xc9,email,2026-04-01 10:00\n")),
                       rejection(load_conversions, byte_file("too_many.csv",
                                                             (chead + conversion_rows(MOST_CONVERSIONS + 1, 1)
                                                              + conversions_far_down).encode("utf-8")
                                                             + b"1,CAF\xc9,2026-04-01 10:00,1.00\n")),
                       rejection(load, csv_file("pair_touches.csv", thead + touch_rows(1, 317)),
                                 csv_file("pair_conversions.csv", chead + conversion_rows(1, 316))),
                       rejection(lambda *paths: [len(rows) for rows in load(*paths)],
                                 csv_file("tall_touches.csv", thead + touch_rows(1, 400)),
                                 csv_file("tall_conversions.csv", chead + conversion_rows(1, 250))),
                       rejection(lambda *paths: [len(rows) for rows in load(*paths)],
                                 csv_file("full_touches.csv", thead + touch_rows(25000, 2)),
                                 csv_file("full_conversions.csv", chead + conversion_rows(25000, 2)))],
              [(2, f"too_many.csv row {MOST_TOUCHES + 2}: the log runs past 50000 touches"),
               (2, f"too_many.csv row {MOST_CONVERSIONS + 2}: the log runs past 50000 conversions"),
               (2, "pair_conversions.csv: these conversions and the touches in pair_touches.csv pair up 100172 "
                   "times by customer, more than the 100000 the queries work through"),
               (0, [400, 250]),
               (0, [50000, 50000])])

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

        own_touches = csv_file("own_touches.csv", TOUCHES_CSV.read_text(encoding="utf-8"))
        own_conversions = csv_file("own_conversions.csv", CONVERSIONS_CSV.read_text(encoding="utf-8"))
        copied = csv_file("\u6f22\u5b57-touches.csv",
                          (HERE / "data" / "invalid-touches.csv").read_text(encoding="utf-8"))

        def cli(*argv):
            return rejection(settings, [str(a) for a in argv])

        def main_check():
            # main itself, on a file name the Windows codepage cannot hold. It
            # stops at the missing file, and the message has to come out as
            # UTF-8. Then main on a pair of logs of your own, which prints the
            # reports. Neither command line has --test, so no suite is started.
            saved = sys.argv, sys.stdout, sys.stderr
            err, out = io.BytesIO(), io.BytesIO()
            name = "\u6f22\u5b57.csv"
            sys.argv = ["run.py", "--touches", str(Path(tmp) / name), "--conversions", str(own_conversions)]
            sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="\n")
            sys.stderr = io.TextIOWrapper(err, encoding="cp1252", newline="\n")
            try:
                try:
                    main()
                    stopped = "main returned"
                except SystemExit as stop:
                    sys.stderr.flush()
                    stopped = stop.code, name in err.getvalue().decode("utf-8")
                # A file the loader refuses, rather than the command line.
                refused = io.BytesIO()
                sys.stderr = io.TextIOWrapper(refused, encoding="cp1252", newline="\n")
                sys.argv = ["run.py", "--touches", str(copied), "--conversions", str(own_conversions)]
                try:
                    main()
                    loader = "main returned"
                except SystemExit as stop:
                    sys.stderr.flush()
                    loader = stop.code, refused.getvalue().decode("utf-8").strip()
                sys.argv = ["run.py", "--touches", str(own_touches), "--conversions", str(own_conversions)]
                sys.stdout = io.TextIOWrapper(out, encoding="cp1252", newline="\n")
                main()
                sys.stdout.flush()
                lines = out.getvalue().decode("utf-8").splitlines()
                return stopped, loader, lines[0], len(lines)
            finally:
                sys.argv, sys.stdout, sys.stderr = saved

        spelled = HERE / "data" / ".." / "data"
        check("on the command line, one log without the other, a file that is not there, a name with a wildcard "
              "in it and a test run on any files other than the samples are refused, while the samples are picked "
              "by default or spelled another way and a pair of your own is taken; output and messages are written "
              "as UTF-8 by the helper that sets them up, which leaves alone a stream it cannot switch, and main's "
              "own messages come out as UTF-8, from the command line and from the loader alike, while on a pair "
              "of your own it prints all five reports",
              lambda: [cli("--touches", own_touches),
                       cli("--conversions", own_conversions),
                       cli("--touches", Path(tmp) / "not_there.csv", "--conversions", own_conversions),
                       cli("--touches", own_touches, "--conversions", Path(tmp) / "data*.csv"),
                       cli("--test", "--touches", own_touches, "--conversions", CONVERSIONS_CSV),
                       cli("--test", "--touches", TOUCHES_CSV, "--conversions", own_conversions),
                       cli("--test"),
                       cli(),
                       cli("--test", "--touches", spelled / "touches.csv", "--conversions",
                           spelled / "conversions.csv"),
                       cli("--touches", own_touches, "--conversions", own_conversions),
                       utf8_check(),
                       main_check()],
              [(2, "run.py: error: --touches and --conversions go together; give both or neither"),
               (2, "run.py: error: --touches and --conversions go together; give both or neither"),
               (2, f"run.py: error: --touches: '{Path(tmp) / 'not_there.csv'}' is not a file"),
               (2, f"run.py: error: --conversions: '{Path(tmp) / 'data*.csv'}' is not a file"),
               (2, "run.py: error: --test checks hand-computed answers for the sample files; run it without "
                   "--touches and --conversions"),
               (2, "run.py: error: --test checks hand-computed answers for the sample files; run it without "
                   "--touches and --conversions"),
               (0, (True, (TOUCHES_CSV, CONVERSIONS_CSV))),
               (0, (False, (TOUCHES_CSV, CONVERSIONS_CSV))),
               (0, (True, (spelled / "touches.csv", spelled / "conversions.csv"))),
               (0, (False, (own_touches, own_conversions))),
               (("\u6f22\u5b57.csv\n", "\u6f22\u5b57.csv\n"), "\u6f22\u5b57.csv\n"),
               ((2, True), (2, "\u6f22\u5b57-touches.csv row 25: touched_at '2026-04-31 09:30' is not a date and "
                                "time written like 2026-04-15 14:00, from 1970-01-01 00:00 to 2200-12-31 23:59"),
                "=== 01-log-shape.sql ===", 86)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def settings(argv):
    # Reads the command line and settles which files to load. It never runs
    # a query or the suite, so the suite can check it directly.
    parser = argparse.ArgumentParser(prog="run.py", description="Run the attribution queries against a touch "
                                                 "log and a conversions log, the samples by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--touches", type=Path, default=None, help="path to an alternate touch log CSV")
    parser.add_argument("--conversions", type=Path, default=None,
                        help="path to the conversions log CSV that goes with it")
    args = parser.parse_args(argv)
    given = [value is not None for value in (args.touches, args.conversions)]
    # The two logs only make sense together, so a touch log of your own never
    # picks up the sample conversions.
    if any(given) and not all(given):
        parser.error("--touches and --conversions go together; give both or neither")
    paths = (args.touches or TOUCHES_CSV, args.conversions or CONVERSIONS_CSV)
    for flag, path in zip(("--touches", "--conversions"), paths):
        try:
            found = path.is_file()
        except OSError:
            # Python 3.7 raises here for a name Windows cannot hold, such as
            # one with a wildcard in it.
            found = False
        if not found:
            if all(given):
                parser.error(f"{flag}: '{path}' is not a file")
            parser.error(f"the sample file '{path}' is missing or is not a file")
    samples = (TOUCHES_CSV, CONVERSIONS_CSV)
    if args.test and any(p.resolve() != s.resolve() for p, s in zip(paths, samples)):
        parser.error("--test checks hand-computed answers for the sample files; "
                     "run it without --touches and --conversions")
    return args.test, paths


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
    test, paths = settings(sys.argv[1:])
    db = new_db(*load(*paths))
    if test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
