"""Load customer records from a web shop and a till into SQLite and run the dedupe queries.

Usage:
    python run.py                          run every query in sql/
    python run.py --test                   run the assertion suite
    python run.py --customers other.csv    load a different file
"""

import argparse
import contextlib
import csv
import datetime
import io
import re
import sqlite3
import sys
import tempfile
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
CUSTOMERS_CSV = HERE / "data" / "customers.csv"
SQL_DIR = HERE / "sql"
COLUMNS = ["source", "record_no", "full_name", "email", "phone", "address", "opt_in", "updated_on"]
SOURCES = ("web", "pos")
FIRST_DAY = datetime.date(1970, 1, 1)
NAME_LENGTH, EMAIL_LENGTH, PHONE_LENGTH, ADDRESS_LENGTH = 50, 60, 25, 60
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
# The queries take these six characters out of a phone number and keep what
# is left, so a number may hold nothing else besides its digits.
PHONE_SEPARATORS = " -.()+"
# Punctuation a name may hold besides letters. The queries collapse runs of
# spaces with a trick that uses < and >, and build keys with |, so none of
# those can appear in a name.
NAME_PUNCTUATION = " '\u2019-."
ADDRESS_PUNCTUATION = " '\u2019-.,#/0123456789"
# Invisible characters that belong in names, of people and of streets: the
# zero-width joiner and non-joiner that Persian and Sinhala spelling needs,
# and the marks that set writing direction around a name in Arabic or Hebrew.
NAME_MARKS = {"\u200c", "\u200d", "\u200e", "\u200f", "\u061c"}
# Characters that count as letters or marks and show nothing: the combining
# grapheme joiner, the Hangul fillers and the Khmer inherent vowels.
BLANK_MARKS = {"\u034f", "\u115f", "\u1160", "\u17b4", "\u17b5", "\u3164", "\uffa0"}
# The queries sort and rank every record several times over. The costliest
# file found within the loader's limits takes under a third of the step
# budget below, on SQLite 3.31, 3.34 and 3.50 alike.
MOST_RECORDS = 20_000
# A line of the file may hold at most this many characters. A real row holds
# a hundred or so.
LINE_CAP = 1_000_000
# A query that runs past this many thousand SQLite steps is stopped. The
# sample takes under fifty and the costliest file found within the limits
# about 31000, so only a query that would run away reaches it.
STEP_BUDGET = 100_000


def fail(path, row_num, message):
    print(f"{Path(path).name} row {row_num}: {message}", file=sys.stderr)
    sys.exit(2)


def fail_file(path, message):
    print(f"{Path(path).name}: {message}", file=sys.stderr)
    sys.exit(2)


def shown(raw):
    # A value is cut short in a message, so one enormous field cannot flood
    # the screen.
    if len(raw) <= 40:
        return repr(raw)
    over = len(raw) - 40
    return f"{raw[:40]!r} and {over} more character" + ("" if over == 1 else "s")


def read_lines(path, handle):
    # Hands the file over a line at a time, reading at most LINE_CAP + 3
    # characters of any line: the cap, a byte-order mark and a CRLF ending.
    # A longer line is refused, so one enormous line is never held in memory
    # whole, and load() stops a file far past the record limit as it reads.
    # The byte-order mark that Excel puts on its CSV exports is dropped here.
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
    # No field of the file runs across lines, so a quote left open is caught
    # on its own row and nothing is held past the end of a line. strict,
    # because the lenient parser folds text that follows a closing quote back
    # into the field and hands over a garbled row without a word.
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


def source_of(path, row_num, raw):
    if raw not in SOURCES:
        fail(path, row_num, f"source {shown(raw)} is not web or pos")
    return raw


def record_no_of(path, row_num, raw):
    if not re.fullmatch(r"[1-9][0-9]{0,8}", raw):
        fail(path, row_num, f"record_no {shown(raw)} is not a whole number from 1 up, "
                            "at most 9 digits with no leading zero")
    return int(raw)


def spelled(path, row_num, column, raw, length, allowed, what):
    # NFC first, so an accent typed as a separate combining mark is the same
    # text as the accented letter typed as one character. Letters and marks
    # from any script pass, besides the punctuation allowed. NFC takes time
    # that grows with the square of a long run of marks, and no character
    # stands for more than four under it, so a value over four times the
    # limit is too long whatever NFC makes of it and is refused unread.
    if len(raw) > 4 * length:
        fail(path, row_num, f"{column} {shown(raw)} runs past {length} characters")
    value = unicodedata.normalize("NFC", raw)
    if len(value) > length:
        fail(path, row_num, f"{column} {shown(value)} runs past {length} characters")
    bad = next((ch for ch in value if ch in BLANK_MARKS
                or not (unicodedata.category(ch)[0] in "LM" or ch in allowed or ch in NAME_MARKS)), None)
    if bad is not None:
        fail(path, row_num, f"{column} {shown(value)} holds U+{ord(bad):04X}; {what}")
    return value


def name_of(path, row_num, raw):
    if not raw:
        fail(path, row_num, "full_name is blank")
    value = spelled(path, row_num, "full_name", raw, NAME_LENGTH, NAME_PUNCTUATION,
                    "a name holds letters, spaces, hyphens, apostrophes and full stops")
    if not any(unicodedata.category(ch)[0] == "L" for ch in value):
        fail(path, row_num, f"full_name {shown(value)} holds no letters")
    return value


def email_of(path, row_num, raw):
    # Kept as typed, capitals and all. Query 01 matches it in lower case,
    # which is exact for the plain ASCII an address is held to here.
    if not raw:
        return None
    if len(raw) > EMAIL_LENGTH or not EMAIL.fullmatch(raw):
        fail(path, row_num, f"email {shown(raw)} is not an email address written like name@example.com, "
                            f"at most {EMAIL_LENGTH} characters")
    return raw


def phone_of(path, row_num, raw):
    # Kept as typed. Ten digits whose first, the start of a North American
    # area code, is 2 to 9, or eleven with a 1 in front, and nothing else
    # but the separators the queries take out.
    if not raw:
        return None
    digits = "".join(ch for ch in raw if "0" <= ch <= "9")
    number = digits[1:] if len(digits) == 11 and digits[0] == "1" else digits
    if (len(raw) > PHONE_LENGTH or any(ch not in PHONE_SEPARATORS and not "0" <= ch <= "9" for ch in raw)
            or len(number) != 10 or number[0] in "01"):
        fail(path, row_num, f"phone {shown(raw)} is not a phone number: ten digits, the first 2 to 9, with or "
                            "without a 1 in front, and only spaces, hyphens, dots, brackets or a plus sign "
                            f"besides, at most {PHONE_LENGTH} characters")
    return raw


def address_of(path, row_num, raw):
    if not raw:
        return None
    value = spelled(path, row_num, "address", raw, ADDRESS_LENGTH, ADDRESS_PUNCTUATION,
                    "an address holds letters, the digits 0 to 9, spaces and , . ' - # /")
    if not any(unicodedata.category(ch)[0] == "L" or "0" <= ch <= "9" for ch in value):
        fail(path, row_num, f"address {shown(value)} holds no letters or digits")
    return value


def opt_in_of(path, row_num, raw):
    if raw not in ("yes", "no"):
        fail(path, row_num, f"opt_in {shown(raw)} is not yes or no")
    return raw


def day_of(path, row_num, raw, latest):
    # The queries compare dates as text, which puts them in order only when
    # every one is written the same way.
    day = None
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
        try:
            day = datetime.date(int(raw[:4]), int(raw[5:7]), int(raw[8:]))
        except ValueError:
            day = None
    if day is None or day < FIRST_DAY:
        fail(path, row_num, f"updated_on {shown(raw)} is not a date written like 2026-02-20, "
                            f"from {FIRST_DAY} on")
    # A record dated ahead would win every ranking by date. A date written
    # in UTC can run a day ahead of the local one, and no more.
    if day > latest:
        fail(path, row_num, f"updated_on {raw} is later than tomorrow, {latest}; a record cannot have been "
                            "updated after it was exported")
    return raw


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
    latest = datetime.date.today() + datetime.timedelta(days=1)
    rows, seen = [], {}
    with handle:
        lines, header_line = open_csv(path, handle, COLUMNS)
        for i, row in records(path, lines, COLUMNS):
            source = source_of(path, i, row["source"])
            record_no = record_no_of(path, i, row["record_no"])
            if (source, record_no) in seen:
                fail(path, i, f"{source} {record_no} appears twice, first on row {seen[source, record_no]}; "
                              "a source uses each record number once")
            seen[source, record_no] = i
            rows.append((source, record_no, name_of(path, i, row["full_name"]), email_of(path, i, row["email"]),
                         phone_of(path, i, row["phone"]), address_of(path, i, row["address"]),
                         opt_in_of(path, i, row["opt_in"]), day_of(path, i, row["updated_on"], latest)))
            # The file is read a line at a time, so a file far past the limit
            # is never read to the end.
            if len(rows) > MOST_RECORDS:
                fail(path, i, f"the file runs past {MOST_RECORDS} records")
    if not rows:
        fail(path, header_line, "no data rows after the header")
    return rows


def new_db(rows):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE customers (source TEXT NOT NULL, record_no INTEGER NOT NULL, full_name TEXT NOT NULL, "
               "email TEXT, phone TEXT, address TEXT, opt_in TEXT NOT NULL, updated_on TEXT NOT NULL, "
               "PRIMARY KEY (source, record_no))")
    db.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
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
            raise sqlite3.OperationalError(f"stopped after {STEP_BUDGET * 1000} steps")
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


QUERIES = ["01-match-keys.sql", "02-max-per-column.sql", "03-survivor-row.sql", "04-survivor-fields.sql",
           "05-approaches.sql"]


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

    check("six ways of matching: email alone joins the Boudreaus and lumps 8 records with no email into one "
          "customer, the number alone joins them too and lumps 3 with no number, the name alone joins two "
          "Sarah MacLeans with different numbers, blank numbers matched joins two John MacDonalds, and the "
          "match key makes 21 customers with none of those",
          lambda: q(db, "01-match-keys.sql"),
          [("each record alone", 33, 0, 0, 0, 0),
           ("email, lower case", 20, 7, 2, 1, 1),
           ("phone number, digits only", 18, 13, 2, 0, 1),
           ("name, lower case, spaces collapsed", 19, 12, 0, 1, 1),
           ("name and number, blank numbers matched", 20, 12, 0, 0, 1),
           ("name and number, blank numbers apart", 21, 11, 0, 0, 0)])

    check("MAX() per column builds 7 of the 11 merged customers from values no one record holds, the date "
          "aside, Mary Ellen Doucet's from three, and SELECT DISTINCT keeps every record but the second of Priya "
          "Nair's two",
          lambda: q(db, "02-max-per-column.sql"),
          [(2, 2, "Ben Kowalski", "bkowalski@example.net", "902-555-0152", "61 Prince St, Truro", "yes",
            "2026-05-30", "no"),
           (2, 2, "Colin O'Brien", "colin.obrien@example.com", "902-555-0123", "5 Park St, Kentville", "no",
            "2025-09-14", "yes"),
           (2, 2, "Fiona Chisholm", "fchisholm@example.com", "902-555-0165", "19 Elm Street, New Glasgow", "yes",
            "2026-03-07", "no"),
           (2, 2, "Graham MacKinnon", "gmackinnon@example.com", "9025550102", "22 Main St, Antigonish", "yes",
            "2026-04-18", "no"),
           (2, 2, "Hugh Cameron", "hugh.cameron@example.com", "902-555-0108", "9 Hill St, Pictou", "yes",
            "2025-10-05", "no"),
           (2, 2, "keisha downey", "kdowney@example.com", "902-555-0172", "77 Lake Dr, Dartmouth", "yes",
            "2024-03-19", "no"),
           (3, 3, "mary ellen  doucet", "medoucet@example.net", "902.555.0114", "7 Pleasant St, Truro", "yes",
            "2026-02-20", "no"),
           (2, 2, "Nadia Haddad", "nadia.haddad@example.com", "902-555-0189", "4 Front St, Wolfville", "yes",
            "2026-01-11", "yes"),
           (2, 1, "Priya Nair", "priya.nair@example.com", "902-555-0131", "5 Oak Ave, Wolfville", "yes",
            "2025-08-30", "yes"),
           (2, 2, "Sarah Maclean", "smaclean@example.com", "902-555-0161", "40 Queen St, Truro", "yes",
            "2025-11-20", "no"),
           (2, 2, "\u00c9milie Th\u00e9riault", "etheriault@example.com", "902-555-0156",
            "12 Comeau Rd, Meteghan", "no", "2025-02-27", "yes")])

    check("one whole record per customer, 21 in all: newest first, then the web shop on a same-day tie, as "
          "for Fiona Chisholm and Priya Nair, then the lower number, as for Hugh Cameron; Graham MacKinnon's "
          "kept record has no email or address",
          lambda: q(db, "03-survivor-row.sql"),
          [("Ahmad Karimi", "ahmad.karimi@example.com", "+1 902 555 0144", "6 Mill St, Bridgewater", "no",
            "2025-07-08", "web 1017", 1, "only record"),
           ("Ben Kowalski", "ben.kowalski@example.com", "902-555-0152", None, "yes", "2026-05-30", "web 1014", 2,
            "newest"),
           ("COLIN O'BRIEN", "colin.obrien@example.com", "902-555-0123", "5 Park St, Kentville", "no",
            "2025-09-14", "pos 3004", 2, "newest"),
           ("Dan Boudreau", "boudreaus@example.com", "(902) 555-0147", "3 Shore Rd, Pictou", "yes", "2024-08-17",
            "pos 3001", 1, "only record"),
           ("Fiona Chisholm", "fchisholm@example.com", "902-555-0165", "19 Elm St, New Glasgow", "yes",
            "2026-03-07", "web 1010", 2, "same day, web shop"),
           ("Grace Sampson", None, "902-555-0195", "28 King St, Truro", "no", "2026-06-28", "pos 3002", 1,
            "only record"),
           ("GRAHAM MACKINNON", None, "9025550102", None, "no", "2026-04-18", "pos 3003", 2, "newest"),
           ("Hugh Cameron", "Hugh.Cameron@example.com", "902-555-0108", "9 Hill St, Pictou", "yes", "2025-10-05",
            "web 1008", 2, "same day, lower number"),
           ("John MacDonald", "jmacdonald@example.org", None, "31 George St, Sydney", "yes", "2025-05-20",
            "web 1012", 1, "only record"),
           ("John MacDonald", "john.macd@example.com", None, "8 Water St, Yarmouth", "no", "2025-12-01",
            "web 1015", 1, "only record"),
           ("keisha downey", None, "1-902-555-0172", "77 Lake Dr, Dartmouth", "yes", "2024-03-19", "pos 3014", 2,
            "newest"),
           ("Liam Fraser", None, None, "9 Mill Rd, Stellarton", "no", "2025-03-30", "pos 3012", 1, "only record"),
           ("Marie Boudreau", "Boudreaus@example.com", "902-555-0147", "3 Shore Rd, Pictou", "yes", "2025-04-12",
            "web 1001", 1, "only record"),
           ("Mary Ellen Doucet", "medoucet@example.net", "902-555-0114", "114 Robie St, Truro", "no",
            "2026-02-20", "web 1019", 3, "newest"),
           ("Nadia Haddad", "nadia.haddad@example.com", "902-555-0189", "4 Front St, Wolfville", "yes",
            "2026-01-11", "web 1013", 2, "newest"),
           ("Oliver Chen", "oliver.chen@example.com", "902.555.0119", "50 Young St, Halifax", "yes", "2024-02-15",
            "web 1011", 1, "only record"),
           ("Priya Nair", "priya.nair@example.com", "902-555-0131", "5 Oak Ave, Wolfville", "yes", "2025-08-30",
            "web 1006", 2, "same day, web shop"),
           ("Sarah MacLean", "smaclean@example.com", "902-555-0161", "40 Queen St, Truro", "yes", "2025-11-20",
            "web 1005", 2, "newest"),
           ("SARAH MACLEAN", None, "902-555-0178", "12 College St, Antigonish", "yes", "2024-12-12", "pos 3010",
            1, "only record"),
           ("Tom\u00e1s Ortega", "tomas.ortega@example.com", "902 555 0137", "15 Bay Rd, Lunenburg", "yes",
            "2024-06-21", "web 1016", 1, "only record"),
           ("\u00c9milie  Th\u00e9riault", "etheriault@example.com", "902-555-0156", "12 Comeau Rd, Meteghan",
            "no", "2025-02-27", "pos 3008", 2, "newest")])

    check("field by field, each value beside the record it came from: Graham MacKinnon's email and address "
          "from the web shop with the till's newer no, Ben Kowalski's address from the till, and Fiona "
          "Chisholm's no from the till winning a same-day tie against the web shop's yes",
          lambda: q(db, "04-survivor-fields.sql"),
          [("Ahmad Karimi", "web 1017", "ahmad.karimi@example.com", "web 1017", "+1 902 555 0144", "web 1017",
            "6 Mill St, Bridgewater", "web 1017", "no", "web 1017"),
           ("Ben Kowalski", "web 1014", "ben.kowalski@example.com", "web 1014", "902-555-0152", "web 1014",
            "61 Prince St, Truro", "pos 3005", "yes", "web 1014"),
           ("Colin O'Brien", "web 1003", "colin.obrien@example.com", "pos 3004", "902-555-0123", "pos 3004",
            "5 Park St, Kentville", "pos 3004", "no", "pos 3004"),
           ("Dan Boudreau", "pos 3001", "boudreaus@example.com", "pos 3001", "(902) 555-0147", "pos 3001",
            "3 Shore Rd, Pictou", "pos 3001", "yes", "pos 3001"),
           ("Fiona Chisholm", "web 1010", "fchisholm@example.com", "web 1010", "902-555-0165", "web 1010",
            "19 Elm St, New Glasgow", "web 1010", "no", "pos 3013"),
           ("Grace Sampson", "pos 3002", None, None, "902-555-0195", "pos 3002", "28 King St, Truro", "pos 3002",
            "no", "pos 3002"),
           ("Graham MacKinnon", "web 1002", "gmackinnon@example.com", "web 1002", "9025550102", "pos 3003",
            "22 Main St, Antigonish", "web 1002", "no", "pos 3003"),
           ("Hugh Cameron", "web 1008", "Hugh.Cameron@example.com", "web 1008", "902-555-0108", "web 1008",
            "9 Hill St, Pictou", "web 1008", "yes", "web 1008"),
           ("John MacDonald", "web 1012", "jmacdonald@example.org", "web 1012", None, None,
            "31 George St, Sydney", "web 1012", "yes", "web 1012"),
           ("John MacDonald", "web 1015", "john.macd@example.com", "web 1015", None, None,
            "8 Water St, Yarmouth", "web 1015", "no", "web 1015"),
           ("Keisha Downey", "web 1018", "kdowney@example.com", "web 1018", "1-902-555-0172", "pos 3014",
            "77 Lake Dr, Dartmouth", "pos 3014", "yes", "pos 3014"),
           ("Liam Fraser", "pos 3012", None, None, None, None, "9 Mill Rd, Stellarton", "pos 3012", "no",
            "pos 3012"),
           ("Marie Boudreau", "web 1001", "Boudreaus@example.com", "web 1001", "902-555-0147", "web 1001",
            "3 Shore Rd, Pictou", "web 1001", "yes", "web 1001"),
           ("Mary Ellen Doucet", "web 1019", "medoucet@example.net", "web 1019", "902-555-0114", "web 1019",
            "114 Robie St, Truro", "web 1019", "no", "web 1019"),
           ("Nadia Haddad", "web 1013", "nadia.haddad@example.com", "web 1013", "902-555-0189", "web 1013",
            "4 Front St, Wolfville", "web 1013", "yes", "web 1013"),
           ("Oliver Chen", "web 1011", "oliver.chen@example.com", "web 1011", "902.555.0119", "web 1011",
            "50 Young St, Halifax", "web 1011", "yes", "web 1011"),
           ("Priya Nair", "web 1006", "priya.nair@example.com", "web 1006", "902-555-0131", "web 1006",
            "5 Oak Ave, Wolfville", "web 1006", "yes", "web 1006"),
           ("Sarah MacLean", "web 1005", "smaclean@example.com", "web 1005", "902-555-0161", "web 1005",
            "40 Queen St, Truro", "web 1005", "yes", "web 1005"),
           ("SARAH MACLEAN", "pos 3010", None, None, "902-555-0178", "pos 3010", "12 College St, Antigonish",
            "pos 3010", "yes", "pos 3010"),
           ("Tom\u00e1s Ortega", "web 1016", "tomas.ortega@example.com", "web 1016", "902 555 0137", "web 1016",
            "15 Bay Rd, Lunenburg", "web 1016", "yes", "web 1016"),
           ("\u00c9milie Th\u00e9riault", "web 1007", "etheriault@example.com", "pos 3008", "902-555-0156",
            "pos 3008", "12 Comeau Rd, Meteghan", "pos 3008", "no", "pos 3008")])

    check("side by side: DISTINCT keeps 32 of 33 rows with 10 customers still doubled, MAX() builds 7 rows no "
          "record holds, the date aside, and says yes for 3 customers whose newest answer is no, the whole "
          "record leaves 4 known values blank and keeps 1 yes over a same-day no, and field by field fills every "
          "blank, its per-field rules making 4 customers no single record holds",
          lambda: q(db, "05-approaches.sql"),
          [("as loaded", 33, 11, 0, 10, 4),
           ("select distinct", 32, 10, 0, 10, 4),
           ("max() per column", 21, 0, 7, 0, 3),
           ("whole record", 21, 0, 0, 4, 1),
           ("field by field", 21, 0, 4, 0, 0)])

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

    def blank_cell():
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            print_table(["full_name", "email"], [("Grace Sampson", None), ("Oliver Chen", "oliver@example.com")])
        return out.getvalue().splitlines()

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
          "rows each prints and the first of them, and a query file that fails, has no query result, is not "
          "UTF-8 or is gone by the time it is read, or a folder named like one, stops them with a one-line "
          "message; a blank value prints as a blank cell",
          lambda: [reports(), broken_reports(), blank_cell()],
          [[("=== 01-match-keys.sql ===",
             "match_on                                customers  merged  two_names  two_numbers  no_number",
             "--------------------------------------  ---------  ------  ---------  -----------  ---------", 6,
             "each record alone                       33         0       0          0            0"),
            ("=== 02-max-per-column.sql ===",
             "records  distinct_rows  full_name           email                     phone         address"
             "                     opt_in  updated_on  in_a_record",
             "-------  -------------  ------------------  ------------------------  ------------  "
             "--------------------------  ------  ----------  -----------", 11,
             "2        2              Ben Kowalski        bkowalski@example.net     902-555-0152  61 Prince St, Truro"
             "         yes     2026-05-30  no"),
            ("=== 03-survivor-row.sql ===",
             "full_name          email                     phone            address                    opt_in  "
             "updated_on  kept      records  won_on",
             "-----------------  ------------------------  ---------------  -------------------------  ------  "
             "----------  --------  -------  ----------------------", 21,
             "Ahmad Karimi       ahmad.karimi@example.com  +1 902 555 0144  6 Mill St, Bridgewater     no      "
             "2025-07-08  web 1017  1        only record"),
            ("=== 04-survivor-fields.sql ===",
             "full_name          name_from  email                     email_from  phone            phone_from  "
             "address                    address_from  opt_in  opt_in_from",
             "-----------------  ---------  ------------------------  ----------  ---------------  ----------  "
             "-------------------------  ------------  ------  -----------", 21,
             "Ahmad Karimi       web 1017   ahmad.karimi@example.com  web 1017    +1 902 555 0144  web 1017    "
             "6 Mill St, Bridgewater     web 1017      no      web 1017"),
            ("=== 05-approaches.sql ===",
             "approach          rows_kept  duplicates_left  in_no_record  blanks_known  yes_over_no",
             "----------------  ---------  ---------------  ------------  ------------  -----------", 5,
             "as loaded         33         11               0             10            4")],
           [(2, '01-broken.sql: did not run: near "SELEC": syntax error'),
            (2, "01-empty.sql: did not run: has no query result to print"),
            (2, "01-ansi.sql: is not UTF-8 text"),
            (2, "01-folder.sql: is a folder, not a query file"),
            (2, "01-gone.sql: No such file or directory")],
           ["full_name      email", "-------------  ------------------", "Grace Sampson",
            "Oliver Chen    oliver@example.com"]])

    # Logs built for cases the sample does not reach on its own. None of them
    # goes through the loader, and every value in them is one it accepts.
    def every(conn):
        return [q(conn, name) for name in QUERIES]

    # Each pair differs in one way the match key has to see through: letter
    # case, a run of two or three spaces, and each of the six characters taken
    # out of a phone number, alone, then a leading 1 and all of them at once.
    # The last three pairs have to stay apart: two records with no number,
    # an e with an accent in lower case against a capital one, and one name
    # at two numbers.
    pairs = [("Ann Lee", "902-555-0101", "ANN LEE", "902-555-0101"),
             ("Bo  Chan", "902-555-0102", "Bo Chan", "902-555-0102"),
             ("Cy   Dunn", "902-555-0103", "Cy Dunn", "902-555-0103"),
             ("Di Eng", "902 555 0104", "Di Eng", "9025550104"),
             ("Ed Fox", "902-555-0105", "Ed Fox", "9025550105"),
             ("Flo Gray", "902.555.0106", "Flo Gray", "9025550106"),
             ("Gus Hill", "(9025550107", "Gus Hill", "9025550107"),
             ("Hal Ives", "902)5550108", "Hal Ives", "9025550108"),
             ("Ida Jay", "+9025550109", "Ida Jay", "9025550109"),
             ("Jo Kerr", "19025550110", "Jo Kerr", "9025550110"),
             ("Kai Lam", "+1 (902) 555-0111", "Kai Lam", "902.555.0111"),
             ("Lu Moss", None, "Lu Moss", None),
             ("\u00e9lise Roy", "902-555-0112", "\u00c9LISE ROY", "902-555-0112"),
             ("Mo Nash", "902-555-0113", "Mo Nash", "902-555-0114")]
    variants = new_db([row for n, (name_a, phone_a, name_b, phone_b) in enumerate(pairs, 1)
                       for row in (("web", n, name_a, None, phone_a, None, "yes", "2026-01-01"),
                                   ("pos", n, name_b, None, phone_b, None, "yes", "2026-01-02"))])

    def key_counts(conn):
        # What each query makes of the pairs: 01's row for the match key,
        # 02's records, distinct rows and in_a_record for each merged pair,
        # and how many records or rows each of the others comes to.
        reports = every(conn)
        return (reports[0][-1], [(r[0], r[1], r[-1]) for r in reports[1]], [r[7] for r in reports[2]],
                len(reports[3]), [r[1] for r in reports[4]])

    check("every query joins records that differ only in letter case, a run of spaces, or any of the six "
          "characters a phone number may hold besides digits, alone or together, with a leading 1 or without; "
          "and keeps apart two records with no number, one name at two numbers, and \u00e9 against \u00c9, "
          "since lower() folds only A to Z; with no email or address on any record, the MAX() row of each pair "
          "is still one of its records",
          lambda: key_counts(variants),
          (("name and number, blank numbers apart", 17, 11, 0, 0, 0), [(2, 2, "yes")] * 11,
           [2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1, 1], 17, [28, 27, 17, 17, 17]))

    ties = new_db([("pos", 5, "Tia Web", None, "902-555-0201", None, "yes", "2026-01-10"),
                   ("web", 9, "Tia Web", None, "902-555-0201", None, "yes", "2026-01-10"),
                   ("web", 100, "Uma Two", "uma@b.example.com", "902-555-0202", "2 B St, Truro", "no",
                    "2026-01-10"),
                   ("web", 99, "Uma Two", "uma@a.example.com", "902-555-0202", "1 A St, Truro", "yes",
                    "2026-01-10"),
                   ("web", 7, "Val Old", "val@a.example.com", "902-555-0203", None, "yes", "2025-01-01"),
                   ("pos", 8, "VAL OLD", "val@b.example.com", "902-555-0203", None, "yes", "2026-01-01"),
                   ("web", 11, "Wes Opt", None, "902-555-0204", None, "yes", "2026-02-02"),
                   ("pos", 12, "Wes Opt", None, "902-555-0204", None, "no", "2026-02-02"),
                   ("pos", 13, "Wes Opt", None, "902-555-0204", None, "yes", "2026-02-02"),
                   ("pos", 15, "Xia Opt", None, "902-555-0205", None, "yes", "2026-02-02"),
                   ("web", 14, "Xia Opt", None, "902-555-0205", None, "no", "2026-02-02"),
                   ("pos", 21, "YAN FOUR", None, "902 555 0206", None, "yes", "2026-05-01"),
                   ("pos", 22, "YAN FOUR", "yan@new.example.com", "902-555-0206", None, "no", "2026-04-01"),
                   ("web", 23, "Yan Four", "yan@old.example.com", "(902) 555-0206", "1 Old Rd, Truro", "yes",
                    "2025-01-01"),
                   ("web", 24, "yan four", None, "902.555.0206", None, "no", "2026-03-01"),
                   ("pos", 30, "Zed Tie", "zed@pos.example.com", "902-555-0207", "3 Tie Rd, Truro", "yes",
                    "2026-06-01"),
                   ("web", 31, "Zed Tie", "zed@web.example.com", "902-555-0207", None, "yes", "2026-06-01")])
    check("on the same day the web shop wins over a lower till number for the whole record and for name, "
          "email, phone and consent, and record 99 wins over record 100 for the whole record and for every "
          "field but consent, a newer till record wins over an older web one, a same-day no beats "
          "every yes for consent whichever source gives it, one customer's fields come from four different "
          "records, the web shop's name beside the till's newer email makes a record neither holds, a MAX() row "
          "matching a record in all but its yes is no record, and records differing only in consent are two rows "
          "to SELECT DISTINCT",
          lambda: [q(ties, "02-max-per-column.sql"), q(ties, "03-survivor-row.sql"), q(ties, "04-survivor-fields.sql"),
                   q(ties, "05-approaches.sql")],
          [[(2, 1, "Tia Web", None, "902-555-0201", None, "yes", "2026-01-10", "yes"),
            (2, 2, "Uma Two", "uma@b.example.com", "902-555-0202", "2 B St, Truro", "yes", "2026-01-10", "no"),
            (2, 2, "Val Old", "val@b.example.com", "902-555-0203", None, "yes", "2026-01-01", "no"),
            (3, 2, "Wes Opt", None, "902-555-0204", None, "yes", "2026-02-02", "yes"),
            (2, 2, "Xia Opt", None, "902-555-0205", None, "yes", "2026-02-02", "yes"),
            (4, 4, "yan four", "yan@old.example.com", "902.555.0206", "1 Old Rd, Truro", "yes", "2026-05-01", "no"),
            (2, 2, "Zed Tie", "zed@web.example.com", "902-555-0207", "3 Tie Rd, Truro", "yes", "2026-06-01", "no")],
           [("Tia Web", None, "902-555-0201", None, "yes", "2026-01-10", "web 9", 2, "same day, web shop"),
            ("Uma Two", "uma@a.example.com", "902-555-0202", "1 A St, Truro", "yes", "2026-01-10", "web 99", 2,
             "same day, lower number"),
            ("VAL OLD", "val@b.example.com", "902-555-0203", None, "yes", "2026-01-01", "pos 8", 2, "newest"),
            ("Wes Opt", None, "902-555-0204", None, "yes", "2026-02-02", "web 11", 3, "same day, web shop"),
            ("Xia Opt", None, "902-555-0205", None, "no", "2026-02-02", "web 14", 2, "same day, web shop"),
            ("YAN FOUR", None, "902 555 0206", None, "yes", "2026-05-01", "pos 21", 4, "newest"),
            ("Zed Tie", "zed@web.example.com", "902-555-0207", None, "yes", "2026-06-01", "web 31", 2,
             "same day, web shop")],
           [("Tia Web", "web 9", None, None, "902-555-0201", "web 9", None, None, "yes", "web 9"),
            ("Uma Two", "web 99", "uma@a.example.com", "web 99", "902-555-0202", "web 99", "1 A St, Truro",
             "web 99", "no", "web 100"),
            ("Val Old", "web 7", "val@b.example.com", "pos 8", "902-555-0203", "pos 8", None, None, "yes",
             "pos 8"),
            ("Wes Opt", "web 11", None, None, "902-555-0204", "web 11", None, None, "no", "pos 12"),
            ("Xia Opt", "web 14", None, None, "902-555-0205", "web 14", None, None, "no", "web 14"),
            ("yan four", "web 24", "yan@new.example.com", "pos 22", "902 555 0206", "pos 21", "1 Old Rd, Truro",
             "web 23", "yes", "pos 21"),
            ("Zed Tie", "web 31", "zed@web.example.com", "web 31", "902-555-0207", "web 31", "3 Tie Rd, Truro",
             "pos 30", "yes", "web 31")],
           [("as loaded", 17, 7, 0, 6, 4),
            ("select distinct", 15, 6, 0, 6, 3),
            ("max() per column", 7, 0, 4, 0, 3),
            ("whole record", 7, 0, 0, 3, 2),
            ("field by field", 7, 0, 4, 0, 0)]])

    sample = load(CUSTOMERS_CSV)
    check("loaded backwards, or with the till's records first, the sample gives the same five reports, so no "
          "tie is left to the order the records arrive in",
          lambda: [every(new_db(rows)) == every(db) for rows in (sample[::-1], sample[19:] + sample[:19])],
          [True, True])

    # The costliest shape found within the loader's limits: 20000 records,
    # each its own customer, every one with an email and an address, and every
    # number written with a +1 in front, which the key has to take off.
    def letters(n):
        out = ""
        for _ in range(4):
            out, n = chr(97 + n % 26) + out, n // 26
        return out.capitalize()

    def filler(n):
        return ("web", n + 1, f"Kim {letters(n)}", f"k{n}@example.com",
                f"+1 (902) {200 + n // 10000:03d}-{n % 10000:04d}", f"{n + 1} Main St, Truro", "no", "2026-01-01")

    widest = new_db([filler(n) for n in range(MOST_RECORDS)])

    def ends(conn, name):
        rows = q(conn, name)
        return (len(rows), rows[0], rows[-1]) if rows else (0,)

    def endless(folder):
        path = Path(folder) / "endless.sql"
        path.write_text("WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) "
                        "SELECT MAX(i) FROM n;", encoding="utf-8")
        try:
            return run_query(db, path)
        except sqlite3.OperationalError as err:
            return str(err)

    with tempfile.TemporaryDirectory() as tmp:
        check("20000 records, each its own customer with an email, an address and a +1 number, run through every "
              "query inside the step budget, and a query that would run for ever is stopped by it",
              lambda: [ends(widest, name) for name in QUERIES] + [endless(tmp)],
              [(6, ("each record alone", 20000, 0, 0, 0, 0), ("name and number, blank numbers apart", 20000, 0, 0,
                                                              0, 0)),
               (0,),
               (20000, ("Kim Aaaa", "k0@example.com", "+1 (902) 200-0000", "1 Main St, Truro", "no", "2026-01-01",
                        "web 1", 1, "only record"),
                ("Kim Bdpf", "k19999@example.com", "+1 (902) 201-9999", "20000 Main St, Truro", "no", "2026-01-01",
                 "web 20000", 1, "only record")),
               (20000, ("Kim Aaaa", "web 1", "k0@example.com", "web 1", "+1 (902) 200-0000", "web 1",
                        "1 Main St, Truro", "web 1", "no", "web 1"),
                ("Kim Bdpf", "web 20000", "k19999@example.com", "web 20000", "+1 (902) 201-9999", "web 20000",
                 "20000 Main St, Truro", "web 20000", "no", "web 20000")),
               (5, ("as loaded", 20000, 0, 0, 0, 0), ("field by field", 20000, 0, 0, 0, 0)),
               "stopped after 100000000 steps"])

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

        head = ",".join(COLUMNS) + "\n"
        base = {"source": "web", "record_no": "1", "full_name": "Ann Lee", "email": "ann@example.com",
                "phone": "902-555-0101", "address": "1 Main St, Truro", "opt_in": "yes", "updated_on": "2026-01-01"}
        loaded = ("web", 1, "Ann Lee", "ann@example.com", "902-555-0101", "1 Main St, Truro", "yes", "2026-01-01")
        small = head + "web,1,Ann Lee,,902-555-0101,,yes,2026-01-01\npos,1,ANN LEE,,9025550101,,no,2026-01-02\n"
        small_rows = [("web", 1, "Ann Lee", None, "902-555-0101", None, "yes", "2026-01-01"),
                      ("pos", 1, "ANN LEE", None, "9025550101", None, "no", "2026-01-02")]

        def logs(name, content):
            return rejection(load, csv_file(name, content))

        def one(name, **change):
            # The base record with some fields changed, written the way a CSV
            # writer quotes them.
            out = io.StringIO()
            csv.writer(out, lineterminator="\n").writerow([change.get(c, base[c]) for c in COLUMNS])
            return logs(name, head + out.getvalue())

        def sized(result):
            code, rows = result
            return (code, len(rows)) if code == 0 else result

        check("the included bad file is refused for a phone number typed with a letter O for a zero, and a "
              "record listed twice is refused with the row it first appeared on",
              lambda: [rejection(load, HERE / "data" / "invalid-customers.csv"),
                       logs("twice.csv", small + "web,1,Bo Chan,,902-555-0102,,yes,2026-01-03\n")],
              [(2, "invalid-customers.csv row 21: phone '(902) 555-O147' is not a phone number: ten digits, the "
                   "first 2 to 9, with or without a 1 in front, and only spaces, hyphens, dots, brackets or a plus "
                   "sign besides, at most 25 characters"),
               (2, "twice.csv row 4: web 1 appears twice, first on row 2; a source uses each record number once")])

        name_rule = "a name holds letters, spaces, hyphens, apostrophes and full stops"
        address_rule = "an address holds letters, the digits 0 to 9, spaces and , . ' - # /"
        bad_names = [("Ann Lee 2", 0x32), ("Ann <Lee>", 0x3C), ("Ann Lee>", 0x3E), ("Ann|Lee", 0x7C),
                     ("Lee, Ann", 0x2C), ("Ann\u00a0Lee", 0xA0), ("Ann\tLee", 0x09), ("Ann\u200bLee", 0x200B),
                     *[(f"An{chr(mark)}n Lee", mark) for mark in (0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x3164,
                                                                   0xFFA0)]]
        good_names = ["d'Entremont", "O\u2019Brien", "Mary-Ellen St. Clair", "Ann   Lee", "Ali\u200creza Stone",
                      "Mina\u200d Rao", "\u200fLev Adler", "\u200eOren Katz", "Nour\u061c Haddad",
                      "\u674e\u5c0f\u9f99", "\u0905\u0928\u093f\u0932 Rao", "N" * 50]
        good_addresses = ["Unit #4/12 St. Mary\u2019s-Bay Rd", "1" * 60]
        # Marks of two classes, alternating, which NFC puts in order: 200
        # characters are normalized and then refused, 201 are refused unread.
        marks = ["a" + "\u0316\u0315" * 99 + "\u0316", "a" + "\u0316\u0315" * 100]
        check("a name holding a digit, a < or >, a bar, a comma, a non-breaking space, a tab, a zero-width space, "
              "the combining grapheme joiner, a Hangul filler or a Khmer inherent vowel, one with no letters, one "
              "past 50 characters once NFC has joined what it can, a blank one, one over four times that limit, "
              "refused unread so a long run of combining marks never reaches NFC, and an address holding a "
              "semicolon, a non-breaking space or an Arabic-Indic digit, "
              "with no letters or digits, or past 60 characters are refused; while apostrophes straight or curly, "
              "hyphens, full stops, runs of spaces, the zero-width joiner and non-joiner, all three direction "
              "marks, other scripts with their vowel marks, a name of 50 characters, an accent typed as a separate "
              "mark, an address with # and / in it or of 60 characters, and a blank address load, each as typed but "
              "for NFC, which joins an accent typed as a separate mark to its letter",
              lambda: [one(f"name{k}.csv", full_name=raw) for k, (raw, _) in enumerate(bad_names)]
                      + [one("dashes.csv", full_name="--"), one("long_name.csv", full_name="N" * 51),
                         one("no_name.csv", full_name="   "),
                         one("marks200.csv", full_name=marks[0]), one("marks201.csv", full_name=marks[1]),
                         one("semicolon.csv", address="1 Main St; Truro"),
                         one("nbsp.csv", address="1 Main St\u00a0Truro"),
                         one("arabic_digit.csv", address="\u0661 Main St"), one("hashes.csv", address="#/#"),
                         one("long_address.csv", address="1" * 61)]
                      + [one(f"good{k}.csv", full_name=raw) for k, raw in enumerate(good_names)]
                      + [one(f"good_address{k}.csv", address=raw) for k, raw in enumerate(good_addresses)]
                      + [one("accent.csv", full_name="Rene\u0301 Aucoin", address="12 Rue d'E\u0301glise, Arichat"),
                         one("no_address.csv", address="")],
              [(2, f"name{k}.csv row 2: full_name {raw!r} holds U+{mark:04X}; {name_rule}")
               for k, (raw, mark) in enumerate(bad_names)]
              + [(2, "dashes.csv row 2: full_name '--' holds no letters"),
                 (2, "long_name.csv row 2: full_name '" + "N" * 40 + "' and 11 more characters runs past 50 "
                     "characters"),
                 (2, "no_name.csv row 2: full_name is blank"),
                 (2, "marks200.csv row 2: full_name 'a" + "\u0316" * 39 + "' and 160 more characters runs past 50 "
                     "characters"),
                 (2, "marks201.csv row 2: full_name 'a" + "\u0316\u0315" * 19 + "\u0316' and 161 more characters "
                     "runs past 50 characters"),
                 (2, f"semicolon.csv row 2: address '1 Main St; Truro' holds U+003B; {address_rule}"),
                 (2, f"nbsp.csv row 2: address '1 Main St\\xa0Truro' holds U+00A0; {address_rule}"),
                 (2, f"arabic_digit.csv row 2: address '\u0661 Main St' holds U+0661; {address_rule}"),
                 (2, "hashes.csv row 2: address '#/#' holds no letters or digits"),
                 (2, "long_address.csv row 2: address '" + "1" * 40 + "' and 21 more characters runs past 60 "
                     "characters")]
              + [(0, [loaded[:2] + (raw,) + loaded[3:]]) for raw in good_names]
              + [(0, [loaded[:5] + (raw,) + loaded[6:]]) for raw in good_addresses]
              + [(0, [loaded[:2] + ("Ren\u00e9 Aucoin",) + loaded[3:5] + ("12 Rue d'\u00c9glise, Arichat",)
                      + loaded[6:]]),
                 (0, [loaded[:5] + (None,) + loaded[6:]])])

        bad_emails = ["ann@", "@example.com", "ann@example", "ann lee@example.com", "ann@exa_mple.com",
                      "\u00e9@example.com", "ann@@example.com", "a" * 49 + "@example.com"]
        bad_phones = ["902-555-O101", "555-0101", "1902555010", "0902555010", "29025550101", "902/555/0101",
                      "902-555-0101 x2", "+44 20 7946 0958", "902" + " " * 16 + "5550101", "1 012 555 0101",
                      "+1 112 555 0101"]
        good_phones = ["+1 (902) 555-0101", "1.902.555.0101", "9025550101", "902" + " " * 15 + "5550101"]
        check("an email with no name or no domain, a domain with no dot or an underscore, a space, an accent, two "
              "@ signs or past 60 characters, and a phone number with a letter, too few or too many digits, a "
              "first digit of 1 or 0 after any leading 1, a slash, an extension, or past 25 characters are "
              "refused; while an email in capitals, which is kept as typed, one of 60 characters, and numbers "
              "written with a plus sign, brackets, dots, a leading 1 or enough spacing to bring the number to 25 "
              "characters load, as do a blank email and phone",
              lambda: [one(f"email{k}.csv", email=raw) for k, raw in enumerate(bad_emails)]
                      + [one(f"phone{k}.csv", phone=raw) for k, raw in enumerate(bad_phones)]
                      + [one("capitals.csv", email="Ann.Lee+Shop@Example.CO.uk"),
                         one("sixty.csv", email="a" * 48 + "@example.com")]
                      + [one(f"good_phone{k}.csv", phone=raw) for k, raw in enumerate(good_phones)]
                      + [one("blanks.csv", email="", phone="")],
              [(2, f"email{k}.csv row 2: email {shown(raw)} is not an email address written like name@example.com, "
                   "at most 60 characters") for k, raw in enumerate(bad_emails)]
              + [(2, f"phone{k}.csv row 2: phone {raw!r} is not a phone number: ten digits, the first 2 to 9, "
                     "with or without a 1 in front, and only spaces, hyphens, dots, brackets or a plus sign "
                     "besides, at most 25 characters") for k, raw in enumerate(bad_phones)]
              + [(0, [loaded[:3] + ("Ann.Lee+Shop@Example.CO.uk",) + loaded[4:]]),
                 (0, [loaded[:3] + ("a" * 48 + "@example.com",) + loaded[4:]])]
              + [(0, [loaded[:4] + (raw,) + loaded[5:]]) for raw in good_phones]
              + [(0, [loaded[:3] + (None, None) + loaded[5:]])])

        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        after = tomorrow + datetime.timedelta(days=1)
        bad_codes = [("source", "WEB", "source 'WEB' is not web or pos"),
                     ("source", "shop", "source 'shop' is not web or pos"),
                     ("source", "", "source '' is not web or pos"),
                     *[("record_no", raw, f"record_no {raw!r} is not a whole number from 1 up, at most 9 digits "
                                          "with no leading zero")
                       for raw in ("0", "007", "12.0", "1234567890", "-5", "")],
                     *[("opt_in", raw, f"opt_in {raw!r} is not yes or no") for raw in ("Yes", "y", "", "true")],
                     *[("updated_on", raw, f"updated_on {raw!r} is not a date written like 2026-02-20, from "
                                           "1970-01-01 on")
                       for raw in ("2026-2-20", "2026-02-5", "2026-02-30", "20/02/2026", "1969-12-31", "",
                                   "2026-02-20 10:00")],
                     ("updated_on", after.isoformat(), f"updated_on {after} is later than tomorrow, {tomorrow}; a "
                                                       "record cannot have been updated after it was exported")]
        check("a source other than web or pos, a record number that is 0, padded, a fraction, ten digits long, "
              "negative or blank, an opt_in other than yes or no, and a date written another way, that does not "
              "exist, before 1970 or later than tomorrow are refused; while a record from the till with a "
              "nine-digit number, a no, and dates of 1970-01-01 and tomorrow load",
              lambda: [one(f"code{k}.csv", **{column: raw}) for k, (column, raw, _) in enumerate(bad_codes)]
                      + [one("till.csv", source="pos", record_no="999999999", opt_in="no",
                             updated_on="1970-01-01"),
                         one("tomorrow.csv", updated_on=tomorrow.isoformat())],
              [(2, f"code{k}.csv row 2: {message}") for k, (_, _, message) in enumerate(bad_codes)]
              + [(0, [("pos", 999999999) + loaded[2:6] + ("no", "1970-01-01")]),
                 (0, [loaded[:7] + (tomorrow.isoformat(),)])])

        check("rows are counted past blank lines and a line of spaces, and a stray quote is named by its own row, "
              "in a data row or in the header; rows with too many or too few fields, a line of commas, a tab, "
              "text after a closing quote, a quote left open, a field past the parser's limit, and a bad, renamed "
              "or reordered header, also one written as one quoted field or with a trailing comma, are refused, "
              "and a long value or header is cut short in the message, by one character as well as by many",
              lambda: [logs("rows.csv", small + "\n   \n\nweb,2,Bo Chan,,902-555-0102,,maybe,2026-01-01\n"),
                       logs("quote.csv", small + 'web,2,"Bo Chan\nweb,3,Cy",,,,yes,2026-01-01\n'),
                       logs("unclosed.csv", small + 'web,2,"Bo Chan\n'),
                       logs("wide.csv", small + "web,2,Bo Chan,,,,yes,2026-01-01,extra\n"),
                       logs("narrow.csv", small + "web,2,Bo Chan\n"),
                       logs("commas.csv", small + ",,,,,,,\n"),
                       logs("tab.csv", small + "web\t,2,Bo Chan,,,,yes,2026-01-01\n"),
                       logs("after.csv", small + 'web,2,"Bo Chan"x,,,,yes,2026-01-01\n'),
                       logs("huge_field.csv", small + "web,2," + "B" * 200000 + ",,,,yes,2026-01-01\n"),
                       logs("header.csv", 'source,"record_no"x\n'),
                       logs("open_header.csv", '"source,record_no\n'),
                       logs("renamed.csv", head.replace("opt_in", "marketing") + small.split("\n", 1)[1]),
                       logs("reordered.csv", head.replace("email,phone", "phone,email")),
                       logs("late_renamed.csv", "\n" + head.replace("full_name", "name")),
                       logs("quoted_header.csv", '"' + head.rstrip("\n") + '"\n'),
                       logs("comma_header.csv", head.rstrip("\n") + ",\n"),
                       logs("long_value.csv", small + "web,2,Bo Chan,,,,yes," + "9" * 100 + "\n"),
                       logs("just_over.csv", small + "web,2,Bo Chan,,,,yes," + "9" * 41 + "\n")],
              [(2, "rows.csv row 7: opt_in 'maybe' is not yes or no"),
               (2, "quote.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "unclosed.csv row 4: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "wide.csv row 4: has more fields than the header"),
               (2, "narrow.csv row 4: has fewer fields than the header"),
               (2, "commas.csv row 4: source '' is not web or pos"),
               (2, "tab.csv row 4: source 'web\\t' is not web or pos"),
               (2, "after.csv row 4: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "huge_field.csv row 4: has a field over 131072 characters long"),
               (2, "header.csv row 1: cannot be parsed (',' expected after '\"'); a quoted field has to end at its "
                   "closing quote"),
               (2, "open_header.csv row 1: cannot be parsed (unexpected end of data); a quote is left open "
                   "at the end of the line, and no field can run onto the next"),
               (2, "renamed.csv row 1: expected columns '" + ",".join(COLUMNS) + "', got 'source,record_no,"
                   "full_name,email,phone,a' and 27 more characters"),
               (2, "reordered.csv row 1: expected columns '" + ",".join(COLUMNS) + "', got 'source,record_no,"
                   "full_name,phone,email,a' and 24 more characters"),
               (2, "late_renamed.csv row 2: expected columns '" + ",".join(COLUMNS) + "', got 'source,record_no,"
                   "name,email,phone,addres' and 19 more characters"),
               (2, "quoted_header.csv row 1: expected columns '" + ",".join(COLUMNS) + "', got '\"source,"
                   "record_no,full_name,email,phone,' and 26 more characters"),
               (2, "comma_header.csv row 1: expected columns '" + ",".join(COLUMNS) + "', got 'source,record_no,"
                   "full_name,email,phone,a' and 25 more characters"),
               (2, "long_value.csv row 4: updated_on '" + "9" * 40 + "' and 60 more characters is not a date "
                   "written like 2026-02-20, from 1970-01-01 on"),
               (2, "just_over.csv row 4: updated_on '" + "9" * 40 + "' and 1 more character is not a date "
                   "written like 2026-02-20, from 1970-01-01 on")])

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
            lines, _ = open_csv(path, Dropped(text), COLUMNS)
            return list(records(path, lines, COLUMNS))

        def capped(text):
            return len(list(read_lines(Path(tmp) / "cap.csv", io.StringIO(text))))

        def valid(n):
            return f"{SOURCES[n % 2]},{n + 1},Kim {letters(n)},,902-{200 + n // 10000:03d}-{n % 10000:04d},,yes," \
                   "2026-01-01\n"

        far_down = "".join(valid(n) for n in range(5000))
        check("an empty file, one of blank lines, one with only a header, also after a blank line, one that is "
              "not UTF-8 from its first line or only far down, or holds only part of a byte-order mark, a folder, "
              "a read that gives way before the header or partway through, and a line past 1000000 characters "
              "are refused, a line of exactly 1000000 passing; while a byte-order mark, blank lines before the "
              "header, spaces around unquoted fields, in the header too, and a line holding one empty quoted field, "
              "which is passed over like a blank one, load",
              lambda: [logs("empty.csv", ""),
                       logs("blank_only.csv", "\n  \n\n"),
                       logs("bare.csv", head),
                       logs("late_bare.csv", "\n" + head),
                       rejection(load, byte_file("latin1.csv", head.replace("updated", "updat\xe9d").encode("latin-1")
                                                 + b"web,1,Ann Lee,,,,yes,2026-01-01\n")),
                       rejection(load, byte_file("late_latin1.csv", (head + far_down).encode("utf-8")
                                                 + b"web,99999,Ren\xe9,,,,yes,2026-01-01\n")),
                       rejection(load, byte_file("part_mark.csv", b"\xef\xbb")),
                       rejection(load, Path(tmp)),
                       rejection(dropped, ""),
                       rejection(dropped, small),
                       logs("long_line.csv", small + "," * 1000001 + "\n"),
                       rejection(capped, "x" * 1000001 + "\n"),
                       rejection(capped, "x" * 1000000 + "\r\n"),
                       logs("marked.csv", "\ufeff " + head.replace(",", " , ").rstrip("\n") + " \n web , 1 , "
                                          "Ann Lee , , 902-555-0101 , , yes , 2026-01-01 \n"
                                          + small.split("\n", 2)[2]),
                       logs("leading.csv", "\n  \n" + small),
                       logs("quoted_blank.csv", small + '""\n')],
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
               (0, small_rows),
               (0, small_rows),
               (0, small_rows)])

        spread = head + "".join(valid(n) for n in range(MOST_RECORDS))
        check("a file of more than 20000 records is stopped as it is read, before a bad byte further down, "
              "while one of exactly 20000 loads",
              lambda: [rejection(load, byte_file("too_many.csv", (spread + valid(MOST_RECORDS) + far_down)
                                                 .encode("utf-8") + b"web,99999,Ren\xe9,,,,yes,2026-01-01\n")),
                       sized(logs("at_limit.csv", spread))],
              [(2, f"too_many.csv row {MOST_RECORDS + 2}: the file runs past {MOST_RECORDS} records"),
               (0, MOST_RECORDS)])

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

        other = csv_file("other.csv", CUSTOMERS_CSV.read_text(encoding="utf-8"))

        def cli(*argv):
            return rejection(settings, [str(a) for a in argv])

        def main_check():
            # main itself, on a file name the Windows codepage cannot hold. It
            # stops at the missing file, and the message has to come out as
            # UTF-8. The command line has no --test, so no suite is started.
            saved = sys.argv, sys.stdout, sys.stderr
            err = io.BytesIO()
            name = "\u6f22\u5b57.csv"
            sys.argv = ["run.py", "--customers", str(Path(tmp) / name)]
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

        check("on the command line, a file that is not there, a name with a wildcard in it and a test run on any "
              "file other than the sample are refused, while the sample is picked by default or spelled another "
              "way and a file of your own is taken; output and messages are written as UTF-8 by the helper that "
              "sets them up, which leaves alone a stream it cannot switch, and main's own messages come out as "
              "UTF-8",
              lambda: [cli("--customers", Path(tmp) / "not_there.csv"),
                       cli("--customers", Path(tmp) / "data*.csv"),
                       cli("--test", "--customers", other),
                       cli("--test"),
                       cli(),
                       cli("--test", "--customers", HERE / "data" / ".." / "data" / "customers.csv"),
                       cli("--customers", other),
                       utf8_check(),
                       main_check()],
              [(2, f"run.py: error: --customers: '{Path(tmp) / 'not_there.csv'}' is not a file"),
               (2, f"run.py: error: --customers: '{Path(tmp) / 'data*.csv'}' is not a file"),
               (2, "run.py: error: --test checks hand-computed answers for the sample file; "
                   "run it without --customers"),
               (0, (True, CUSTOMERS_CSV)),
               (0, (False, CUSTOMERS_CSV)),
               (0, (True, HERE / "data" / ".." / "data" / "customers.csv")),
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
    parser = argparse.ArgumentParser(prog="run.py", description="Run the dedupe queries against customer "
                                                 "records, the sample by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--customers", type=Path, default=None, help="path to an alternate customer CSV")
    args = parser.parse_args(argv)
    path = args.customers or CUSTOMERS_CSV
    try:
        found = path.is_file()
    except OSError:
        # Python 3.7 raises here for a name Windows cannot hold, such as one
        # with a wildcard in it.
        found = False
    if not found:
        if args.customers is not None:
            parser.error(f"--customers: '{path}' is not a file")
        parser.error(f"the sample file '{path}' is missing")
    if args.test and path.resolve() != CUSTOMERS_CSV.resolve():
        parser.error("--test checks hand-computed answers for the sample file; run it without --customers")
    return args.test, path


def utf8_output():
    # Output is written as UTF-8, since a name in a report or a file name in
    # a message can hold characters that the Windows console codepage cannot
    # print. A stream with no way to switch, as under IDLE, is left as it is.
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
