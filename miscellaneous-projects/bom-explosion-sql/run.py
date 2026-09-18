"""Load a bill of materials into SQLite and run the explosion queries.

Usage:
    python run.py                                                  run every query in sql/
    python run.py --test                                           run the assertion suite
    python run.py --bom b.csv --orders o.csv --stock s.csv         load a different set of files
"""

import argparse
import contextlib
import csv
import io
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
BOM_CSV = HERE / "data" / "bom.csv"
ORDERS_CSV = HERE / "data" / "orders.csv"
STOCK_CSV = HERE / "data" / "stock.csv"
SQL_DIR = HERE / "sql"
BOM_COLUMNS = ["parent", "child", "qty"]
ORDER_COLUMNS = ["item", "qty"]
STOCK_COLUMNS = ["part", "on_hand"]
CODE = re.compile(r"[A-Z0-9]+(?:-[A-Z0-9]+)*")
CODE_LENGTH = 24
# Limits that keep the queries small and their arithmetic exact. Every route
# down the bill is a row in the recursive queries, so the routes across all
# products are capped; and one unit of anything takes at most a million of
# any raw part, which with at most 99999 units ordered keeps every total far
# below where SQLite's whole numbers turn to floating point.
MOST_ROUTES = 100_000
MOST_PER_UNIT = 1_000_000
# A query that runs past this many thousand SQLite steps is stopped. The
# sample takes a few, and the largest bill the limits above allow takes
# about a fifth of it, so only a query that would run away reaches it.
STEP_BUDGET = 100_000


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
            # A line holding nothing but spaces is as blank as an empty one.
            if len(fields) <= 1 and not "".join(fields).strip(" "):
                start = reader.line_num + 1
                continue
            if any(ch in f for f in fields for ch in "\r\n"):
                fail(path, start, "a field runs across more than one line; "
                                  "most likely a stray quote")
            if len(fields) > len(columns):
                fail(path, start, "has more fields than the header")
            if len(fields) < len(columns):
                fail(path, start, "has fewer fields than the header")
            yield start, {k: v.strip(" ") for k, v in zip(columns, fields)}
            start = reader.line_num + 1
    except csv.Error as err:
        fail(path, start, f"cannot be parsed ({err}); most likely a stray quote")


def code(path, row_num, name, raw):
    # Part codes are matched exactly, so they are held to one plain form:
    # capital letters and digits, joined by single hyphens. A code typed in
    # lower case, or with a stray character, would otherwise be a different
    # part that nothing else refers to.
    if len(raw) > CODE_LENGTH or not CODE.fullmatch(raw):
        fail(path, row_num, f"{name} {raw!r} is not a part code: capital letters and digits, "
                            f"joined by single hyphens, at most {CODE_LENGTH} characters")
    return raw


def count(path, row_num, name, raw, lowest, digits):
    pattern = r"0|[1-9][0-9]{0,%d}" % (digits - 1) if lowest == 0 else r"[1-9][0-9]{0,%d}" % (digits - 1)
    if not re.fullmatch(pattern, raw):
        fail(path, row_num, f"{name} {raw!r} is not a whole number from {lowest} up, "
                            f"at most {digits} digits with no leading zero")
    return int(raw)


def find_loop(lines, rows):
    # Kahn's walk: take away every part with nothing left above it until none
    # remain. Parts still standing sit on a loop or below one. Every one of
    # them still has a parent standing, so stepping up from any of them must
    # come round to a part already seen, and that closes the loop.
    parents = {}
    for parent, child, _ in lines:
        parents.setdefault(child, []).append(parent)
    above = {part: 0 for line in lines for part in line[:2]}
    for _, child, _ in lines:
        above[child] += 1
    below = {}
    for parent, child, _ in lines:
        below.setdefault(parent, []).append(child)
    ready = [part for part, n in above.items() if n == 0]
    while ready:
        part = ready.pop()
        for child in below.get(part, []):
            above[child] -= 1
            if above[child] == 0:
                ready.append(child)
    standing = {part for part, n in above.items() if n > 0}
    if not standing:
        return None
    walk, seen = [min(standing)], set()
    while walk[-1] not in seen:
        seen.add(walk[-1])
        walk.append(min(p for p in parents[walk[-1]] if p in standing))
    loop = walk[walk.index(walk[-1]):]
    # loop runs upward, child to parent; each step is the line parent -> child.
    edges = [(loop[k + 1], loop[k]) for k in range(len(loop) - 1)]
    last = max(edges, key=lambda edge: rows[edge])
    # The loop written downward, parent before part, from the part the
    # reported line puts inside its own parent.
    down = list(reversed(loop))[:-1]
    at = down.index(last[1])
    circle = down[at:] + down[:at] + [last[1]]
    return last, rows[last], " -> ".join(circle)


def check_explosion(path, lines):
    # The queries walk every route down the bill as a row, so the routes are
    # counted first, one number per part, and a bill with too many is refused
    # before any route is walked. A count stops at one past the limit, which
    # keeps every number small however the bill is shaped. Only then is each
    # product walked route by route, to add up what one unit takes of each
    # raw part.
    below = {}
    for parent, child, qty in lines:
        below.setdefault(parent, []).append((child, qty))
    over = MOST_ROUTES + 1
    routes = {}
    for start in sorted(below):
        # Each part is entered once: its parts go on the stack above it, and
        # when it comes back to the top they are all counted. The loop check
        # runs first; on a loop this stops with an error rather than spinning.
        stack, entered = [start], set()
        while stack:
            top = stack[-1]
            if top in routes:
                stack.pop()
                continue
            if top not in entered:
                entered.add(top)
                stack.extend(child for child, _ in below.get(top, []) if child not in routes)
                continue
            stack.pop()
            routes[top] = min(over, sum(1 + routes[child] for child, _ in below.get(top, [])))
    children = {child for _, child, _ in lines}
    products = sorted(set(below) - children)
    if min(over, sum(routes[product] for product in products)) > MOST_ROUTES:
        fail_file(path, f"the products explode into more than {MOST_ROUTES} routes down the bill, "
                        "and the queries walk every route")
    # Every subassembly sits below a product, and every quantity is at least
    # one, so no part takes more of a raw part than the products above it;
    # checking the products covers the subassemblies too. The walk stops as
    # soon as a quantity passes the limit, since every quantity further down
    # is at least one and a raw part below is over the limit as well.
    for product in products:
        takes, stack = {}, [(product, 1)]
        while stack:
            part, qty = stack.pop()
            for child, n in below.get(part, []):
                amount = qty * n
                if child not in below:
                    takes[child] = takes.get(child, 0) + amount
                    if takes[child] > MOST_PER_UNIT:
                        too_many(path, product, child)
                elif amount > MOST_PER_UNIT:
                    raw = child
                    while raw in below:
                        raw = below[raw][0][0]
                    too_many(path, product, raw)
                else:
                    stack.append((child, amount))
    return routes


def too_many(path, product, raw):
    fail_file(path, f"one {product} takes more than {MOST_PER_UNIT} of {raw}, "
                    "the most the queries allow per unit")


def load_bom(path):
    lines, rows = [], {}
    reader = read_csv(path, BOM_COLUMNS)
    for i, row in records(path, reader, BOM_COLUMNS):
        parent = code(path, i, "parent", row["parent"])
        child = code(path, i, "child", row["child"])
        if parent == child:
            fail(path, i, f"{parent} lists itself as one of its own parts")
        if (parent, child) in rows:
            fail(path, i, f"{parent} -> {child} appears twice; one line per parent and part, "
                          "with the quantities added together")
        qty = count(path, i, "qty", row["qty"], 1, 5)
        rows[(parent, child)] = i
        lines.append((parent, child, qty))
        # Every line ends at least one route of its own down from a product,
        # so a bill past the route limit in lines is past it in routes too.
        # Stopping here keeps a huge file from being held in memory.
        if len(lines) > MOST_ROUTES:
            fail(path, i, f"the bill runs past {MOST_ROUTES} lines, and every line adds a route "
                          "the queries walk")
    if not lines:
        fail(path, 1, "no data rows after the header")
    loop = find_loop(lines, rows)
    if loop:
        (parent, child), line, circle = loop
        fail(path, line, f"{parent} -> {child} closes the loop {circle}; "
                         "an assembly cannot contain itself")
    return lines, check_explosion(path, lines)


def load_orders(path, bom_path, lines, routes):
    assemblies = {parent for parent, _, _ in lines}
    rows, seen = [], set()
    reader = read_csv(path, ORDER_COLUMNS)
    for i, row in records(path, reader, ORDER_COLUMNS):
        item = code(path, i, "item", row["item"])
        if item not in assemblies:
            fail(path, i, f"{item} has no parts listed in {Path(bom_path).name}, so there is "
                          "nothing to build it from")
        if item in seen:
            fail(path, i, f"{item} is on the plan twice; one line per item, with the units added together")
        seen.add(item)
        rows.append((item, count(path, i, "qty", row["qty"], 1, 5)))
    if not rows:
        fail(path, 1, "no data rows after the header")
    # Queries 04 and 05 walk every route down from each item on the plan.
    if min(MOST_ROUTES + 1, sum(routes[item] for item, _ in rows)) > MOST_ROUTES:
        fail_file(path, f"the items on the plan explode into more than {MOST_ROUTES} routes down the "
                        "bill, and the queries walk every route")
    return rows


def load_stock(path, bom_path, lines):
    assemblies = {parent for parent, _, _ in lines}
    raw = {child for _, child, _ in lines} - assemblies
    rows, seen = [], set()
    reader = read_csv(path, STOCK_COLUMNS)
    for i, row in records(path, reader, STOCK_COLUMNS):
        part = code(path, i, "part", row["part"])
        if part in assemblies:
            fail(path, i, f"{part} is an assembly; stock is counted for raw parts only")
        if part not in raw:
            fail(path, i, f"{part} is not a part in {Path(bom_path).name}")
        if part in seen:
            fail(path, i, f"{part} is counted twice; one line per part")
        seen.add(part)
        rows.append((part, count(path, i, "on_hand", row["on_hand"], 0, 12)))
    missing = sorted(raw - seen)
    if missing:
        fail_file(path, f"raw part {missing[0]} has no line; count every raw part, at 0 if there are none")
    return rows


def load(bom_path, orders_path, stock_path):
    lines, routes = load_bom(bom_path)
    return lines, load_orders(orders_path, bom_path, lines, routes), load_stock(stock_path, bom_path, lines)


def new_db(bom, orders, stock):
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE bom (parent TEXT NOT NULL, child TEXT NOT NULL, qty INTEGER NOT NULL, "
               "PRIMARY KEY (parent, child))")
    db.execute("CREATE TABLE orders (item TEXT PRIMARY KEY, qty INTEGER NOT NULL)")
    db.execute("CREATE TABLE stock (part TEXT PRIMARY KEY, on_hand INTEGER NOT NULL)")
    db.executemany("INSERT INTO bom VALUES (?, ?, ?)", bom)
    db.executemany("INSERT INTO orders VALUES (?, ?)", orders)
    db.executemany("INSERT INTO stock VALUES (?, ?)", stock)
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
        # check instead of stopping the suite.
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

    check("three products, eight subassemblies and sixteen raw parts on 40 lines, and 31 units on the plan",
          lambda: q(db, "01-bom-shape.sql"),
          [(3, 8, 16, 40, 4, 31)])

    union_rows = [
        ("CARGO-BIKE", "BEARING", 2), ("CARGO-BIKE", "BOLT-M5", 10), ("CARGO-BIKE", "BRAKE-PAD", 4),
        ("CARGO-BIKE", "CABLE", 2), ("CARGO-BIKE", "CHAIN", 1), ("CARGO-BIKE", "CRANK", 2),
        ("CARGO-BIKE", "FORK", 1), ("CARGO-BIKE", "FRAME-TUBES", 1), ("CARGO-BIKE", "HUB-SHELL", 1),
        ("CARGO-BIKE", "RIM-20", 1), ("CARGO-BIKE", "RIM-26", 1), ("CARGO-BIKE", "SPINDLE", 1),
        ("CARGO-BIKE", "SPOKE", 60), ("CARGO-BIKE", "TYRE-20", 1), ("CARGO-BIKE", "TYRE-26", 1),
        ("CITY-BIKE", "BEARING", 6), ("CITY-BIKE", "BOLT-M5", 4), ("CITY-BIKE", "BRAKE-PAD", 4),
        ("CITY-BIKE", "CABLE", 2), ("CITY-BIKE", "CHAIN", 1), ("CITY-BIKE", "CRANK", 2),
        ("CITY-BIKE", "FORK", 1), ("CITY-BIKE", "FRAME-TUBES", 1), ("CITY-BIKE", "HUB-SHELL", 2),
        ("CITY-BIKE", "RIM-26", 2), ("CITY-BIKE", "SPINDLE", 1), ("CITY-BIKE", "SPOKE", 64),
        ("CITY-BIKE", "TYRE-26", 2),
        ("KIDS-BIKE", "BEARING", 6), ("KIDS-BIKE", "BOLT-M5", 4), ("KIDS-BIKE", "BRAKE-PAD", 2),
        ("KIDS-BIKE", "CABLE", 1), ("KIDS-BIKE", "CHAIN", 1), ("KIDS-BIKE", "CRANK", 2),
        ("KIDS-BIKE", "FORK", 1), ("KIDS-BIKE", "FRAME-KIDS", 1), ("KIDS-BIKE", "HUB-SHELL", 2),
        ("KIDS-BIKE", "RIM-20", 2), ("KIDS-BIKE", "SPINDLE", 1), ("KIDS-BIKE", "SPOKE", 56),
        ("KIDS-BIKE", "TYRE-20", 2)]
    check("UNION drops a repeated route: every bike comes out short of bolts, and the cargo bike of bearings "
          "and hub shells too",
          lambda: q(db, "02-union-explosion.sql"),
          union_rows)

    check("UNION ALL counts every route, and each raw part shows how many routes reach it and how deep",
          lambda: q(db, "03-explosion.sql"),
          [("CARGO-BIKE", "BEARING", 6, 3, 3), ("CARGO-BIKE", "BOLT-M5", 14, 3, 2),
           ("CARGO-BIKE", "BRAKE-PAD", 4, 1, 2), ("CARGO-BIKE", "CABLE", 2, 1, 2),
           ("CARGO-BIKE", "CHAIN", 1, 1, 2), ("CARGO-BIKE", "CRANK", 2, 1, 2),
           ("CARGO-BIKE", "FORK", 1, 1, 2), ("CARGO-BIKE", "FRAME-TUBES", 1, 1, 2),
           ("CARGO-BIKE", "HUB-SHELL", 2, 2, 3), ("CARGO-BIKE", "RIM-20", 1, 1, 2),
           ("CARGO-BIKE", "RIM-26", 1, 1, 2), ("CARGO-BIKE", "SPINDLE", 1, 1, 3),
           ("CARGO-BIKE", "SPOKE", 60, 2, 2), ("CARGO-BIKE", "TYRE-20", 1, 1, 2),
           ("CARGO-BIKE", "TYRE-26", 1, 1, 2),
           ("CITY-BIKE", "BEARING", 6, 2, 3), ("CITY-BIKE", "BOLT-M5", 8, 2, 2),
           ("CITY-BIKE", "BRAKE-PAD", 4, 1, 2), ("CITY-BIKE", "CABLE", 2, 1, 2),
           ("CITY-BIKE", "CHAIN", 1, 1, 2), ("CITY-BIKE", "CRANK", 2, 1, 2),
           ("CITY-BIKE", "FORK", 1, 1, 2), ("CITY-BIKE", "FRAME-TUBES", 1, 1, 2),
           ("CITY-BIKE", "HUB-SHELL", 2, 1, 3), ("CITY-BIKE", "RIM-26", 2, 1, 2),
           ("CITY-BIKE", "SPINDLE", 1, 1, 3), ("CITY-BIKE", "SPOKE", 64, 1, 2),
           ("CITY-BIKE", "TYRE-26", 2, 1, 2),
           ("KIDS-BIKE", "BEARING", 6, 2, 3), ("KIDS-BIKE", "BOLT-M5", 8, 2, 2),
           ("KIDS-BIKE", "BRAKE-PAD", 2, 1, 2), ("KIDS-BIKE", "CABLE", 1, 1, 2),
           ("KIDS-BIKE", "CHAIN", 1, 1, 2), ("KIDS-BIKE", "CRANK", 2, 1, 2),
           ("KIDS-BIKE", "FORK", 1, 1, 2), ("KIDS-BIKE", "FRAME-KIDS", 1, 1, 1),
           ("KIDS-BIKE", "HUB-SHELL", 2, 1, 3), ("KIDS-BIKE", "RIM-20", 2, 1, 2),
           ("KIDS-BIKE", "SPINDLE", 1, 1, 2), ("KIDS-BIKE", "SPOKE", 56, 1, 2),
           ("KIDS-BIKE", "TYRE-20", 2, 1, 2)])

    check("the plan runs short of bearings, bolts, cables and both frames; UNION would see no shortage "
          "of bearings or bolts",
          lambda: q(db, "04-build-plan.sql"),
          [("BEARING", 150, 162, 12, 142), ("BOLT-M5", 200, 230, 30, 130), ("BRAKE-PAD", 90, 84, 0, 84),
           ("CABLE", 36, 42, 6, 42), ("CHAIN", 30, 25, 0, 25), ("CRANK", 60, 50, 0, 50),
           ("FORK", 25, 25, 0, 25), ("FRAME-KIDS", 6, 8, 2, 8), ("FRAME-TUBES", 16, 17, 1, 17),
           ("HUB-SHELL", 60, 56, 0, 51), ("RIM-20", 30, 21, 0, 21), ("RIM-26", 40, 35, 0, 35),
           ("SPINDLE", 30, 25, 0, 25), ("SPOKE", 2000, 1708, 0, 1708), ("TYRE-20", 30, 21, 0, 21),
           ("TYRE-26", 40, 35, 0, 35)])

    check("alone, every item but the kids bike could be built in full, and the rims and tyres tie on the wheels",
          lambda: q(db, "05-buildable.sql"),
          [("CARGO-BIKE", 5, 14, "BOLT-M5", 0), ("CITY-BIKE", 12, 16, "FRAME-TUBES", 0),
           ("KIDS-BIKE", 8, 6, "FRAME-KIDS", 2), ("WHEEL-26", 6, 40, "RIM-26", 0)])

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
            sections.append((lines[at], lines[at + 1], "".join(sorted(set(lines[at + 2]))), len(rows), rows[0]))
        return sections

    def broken_reports():
        results = []
        with tempfile.TemporaryDirectory() as folder:
            for name, data in (("broken", b"SELEC 1;"), ("empty", b""), ("ansi", b"-- caf\xe9\nSELECT 1;")):
                sub = Path(folder) / name
                sub.mkdir()
                (sub / f"01-{name}.sql").write_bytes(data)
                err = io.StringIO()
                try:
                    with contextlib.redirect_stderr(err):
                        run_all(db, sub)
                    results.append((0, ""))
                except SystemExit as stop:
                    results.append((stop.code, err.getvalue().strip()))
        return results

    check("all five reports print as tables, with their column names, a rule, every row and the first row "
          "as expected, and a query file that fails, has no query result, or is not UTF-8 stops them with a "
          "one-line message",
          lambda: [reports(), broken_reports()],
          [[("=== 01-bom-shape.sql ===",
             "products  subassemblies  raw_parts  bom_lines  order_lines  units_ordered", " -", 1,
             "3         8              16         40         4            31"),
            ("=== 02-union-explosion.sql ===", "product     part         per_unit", " -", 41,
             "CARGO-BIKE  BEARING      2"),
            ("=== 03-explosion.sql ===", "product     part         per_unit  routes  deepest", " -", 41,
             "CARGO-BIKE  BEARING      6         3       3"),
            ("=== 04-build-plan.sql ===", "part         on_hand  need  short_by  union_need", " -", 16,
             "BEARING      150      162   12        142"),
            ("=== 05-buildable.sql ===", "item        ordered  buildable  bottleneck   short_units", " -", 4,
             "CARGO-BIKE  5        14         BOLT-M5      0")],
          [(2, '01-broken.sql: did not run: near "SELEC": syntax error'),
           (2, "01-empty.sql: did not run: has no query result to print"),
           (2, "01-ansi.sql: is not UTF-8 text")]])

    # Bills built for cases the sample does not reach on its own. None of
    # them goes through the loader, so the last one can hold a loop.
    def bill(lines, orders, stock):
        return new_db(lines, orders, stock)

    twins = bill([("P", "A", 1), ("P", "B", 1), ("A", "X", 3), ("B", "X", 3), ("Q", "A", 1), ("Q", "B", 2)],
                 [("P", 1), ("Q", 1)], [("X", 100)])
    check("two routes that arrive with the same quantity lose one to UNION, two that differ keep both",
          lambda: [q(twins, "02-union-explosion.sql"), q(twins, "03-explosion.sql"),
                   q(twins, "04-build-plan.sql")],
          [[("P", "X", 3), ("Q", "X", 9)],
           [("P", "X", 6, 2, 2), ("Q", "X", 9, 2, 2)],
           [("X", 100, 15, 0, 12)]])

    deep = bill([("TOP", "L1", 2), ("L1", "L2", 3), ("L2", "L3", 1), ("L3", "L4", 5), ("L4", "RAW-Z", 7),
                 ("TOP", "L3", 1)],
                [("TOP", 3)], [("RAW-Z", 700)])
    # A chain of three lines whose one route runs the whole length of the
    # bill, the deepest a route can go, which the level cap has to let through.
    chain = bill([("C0", "C1", 2), ("C1", "C2", 3), ("C2", "RAW-C", 4)], [("C0", 2)], [("RAW-C", 50)])
    check("quantities multiply all the way down, a shortcut to the same part adds a route, the deepest "
          "level is the long way round, and a route as long as the bill gets through the level cap",
          lambda: [q(deep, "01-bom-shape.sql"), q(deep, "03-explosion.sql"), q(deep, "04-build-plan.sql"),
                   q(deep, "05-buildable.sql"), q(chain, "03-explosion.sql"), q(chain, "04-build-plan.sql"),
                   q(chain, "05-buildable.sql")],
          [[(1, 4, 1, 6, 1, 3)],
           [("TOP", "RAW-Z", 245, 2, 5)],
           [("RAW-Z", 700, 735, 35, 735)],
           [("TOP", 3, 2, "RAW-Z", 1)],
           [("C0", "RAW-C", 24, 1, 3)],
           [("RAW-C", 50, 48, 0, 48)],
           [("C0", 2, 2, "RAW-C", 0)]])

    ties = bill([("KIT", "NUT", 2), ("KIT", "BOLT", 4), ("KIT", "WASHER", 4), ("KIT", "AXLE", 3), ("KIT", "SUB", 1),
                 ("SUB", "PIN", 1),
                 ("OTHER", "PIN", 1), ("OTHER", "CLIP", 3)],
                [("KIT", 9), ("SUB", 4), ("OTHER", 2)],
                [("NUT", 20), ("BOLT", 40), ("WASHER", 43), ("AXLE", 31), ("PIN", 30), ("CLIP", 0)])
    # AXLE, BOLT, NUT and WASHER all run out at 10. AXLE sorts first. BOLT is
    # the one an exact ratio or the largest per unit would pick, NUT the one
    # with the least on hand, and WASHER the one with the most to spare, so
    # only the code order picks AXLE.
    check("a four-way tie for the bottleneck goes to the code that sorts first; a part with none on hand "
          "builds nothing, and a subassembly on the plan is exploded like a product",
          lambda: [q(ties, "04-build-plan.sql"), q(ties, "05-buildable.sql")],
          [[("AXLE", 31, 27, 0, 27), ("BOLT", 40, 36, 0, 36), ("CLIP", 0, 6, 6, 6), ("NUT", 20, 18, 0, 18),
            ("PIN", 30, 15, 0, 15), ("WASHER", 43, 36, 0, 36)],
           [("KIT", 9, 10, "AXLE", 0), ("OTHER", 2, 0, "CLIP", 2), ("SUB", 4, 30, "PIN", 0)]])

    # Each value is paired with its type, since 5.0 == 5 in Python and a total
    # that turned to floating point would otherwise pass.
    def typed(rows):
        return [tuple((type(v).__name__, v) for v in row) for row in rows]

    caps = bill([("HEAVY", "SUB", 1000), ("SUB", "GRAIN", 1000), ("HEAVY", "SACK", 1), ("HEAVY-TWO", "SUB", 1000)],
                [("HEAVY", 99999), ("HEAVY-TWO", 99999)],
                [("GRAIN", 999999999999), ("SACK", 0)])
    check("with a million of a part per unit and the most units the plan allows, on two items, the totals "
          "stay whole numbers",
          lambda: [typed(q(caps, "03-explosion.sql")), typed(q(caps, "04-build-plan.sql")),
                   typed(q(caps, "05-buildable.sql"))],
          [typed([("HEAVY", "GRAIN", 1000000, 1, 2), ("HEAVY", "SACK", 1, 1, 1),
                  ("HEAVY-TWO", "GRAIN", 1000000, 1, 2)]),
           typed([("GRAIN", 999999999999, 199998000000, 0, 199998000000), ("SACK", 0, 99999, 99999, 99999)]),
           typed([("HEAVY", 99999, 0, "SACK", 99999), ("HEAVY-TWO", 99999, 999999, "GRAIN", 0)])])

    # 88 products on a shared frame of 10 and 10 parts: 97680 routes, and the
    # plan adds the 20 subassemblies for 98880, near the route limit.
    near = [(a, b, 3) for a in (f"A{n}" for n in range(10)) for b in (f"B{n}" for n in range(10))]
    near += [(b, r, 7) for b in (f"B{n}" for n in range(10)) for r in (f"R{n}" for n in range(10))]
    near += [(p, a, 5) for p in (f"P{n}" for n in range(88)) for a in (f"A{n}" for n in range(10))]
    near_plan = ([(f"P{n}", 1) for n in range(88)] + [(f"A{n}", 1) for n in range(10)]
                 + [(f"B{n}", 1) for n in range(10)])
    wide = bill(near, near_plan, [(f"R{n}", 10 ** 12 - 1) for n in range(10)])
    # One product of 99999 raw parts, on the plan: one of the costliest bills
    # the loader allows for queries 04 and 05, about a fifth of the step budget.
    flat = bill([("FLAT", f"R{n}", 1) for n in range(99999)], [("FLAT", 1)],
                [(f"R{n}", 10 ** 12 - 1) for n in range(99999)])

    def first_and_count(conn, name):
        rows = q(conn, name)
        return len(rows), rows[0]

    check("one of the costliest bills the loader allows and one near the route limit run through queries 03, "
          "04 and "
          "05 inside the step budget",
          lambda: [first_and_count(wide, "03-explosion.sql"), first_and_count(wide, "04-build-plan.sql"),
                   first_and_count(wide, "05-buildable.sql"), first_and_count(flat, "04-build-plan.sql"),
                   first_and_count(flat, "05-buildable.sql")],
          [(880, ("P0", "R0", 10500, 100, 3)), (10, ("R0", 999999999999, 926170, 0, 9520)),
           (108, ("A0", 1, 4761904761, "R0", 0)), (99999, ("R0", 999999999999, 1, 0, 1)),
           (1, ("FLAT", 1, 999999999999, "R0", 0))])

    # A loop the loader would refuse, put straight into the database. The
    # level cap stops each UNION ALL walk once it has gone as deep as the bill
    # has lines. The UNION walk in query 04 carries no cap; on this loop it
    # ends because its quantities repeat and UNION drops the repeated rows.
    looped = bill([("P", "A", 1), ("A", "B", 1), ("B", "A", 1), ("B", "R", 1)], [("P", 1)], [("R", 5)])

    def endless(folder):
        path = Path(folder) / "endless.sql"
        path.write_text("WITH RECURSIVE n(i) AS (SELECT 1 UNION ALL SELECT i + 1 FROM n) "
                        "SELECT MAX(i) FROM n;", encoding="utf-8")
        try:
            return run_query(db, path)
        except sqlite3.OperationalError as err:
            return str(err)

    with tempfile.TemporaryDirectory() as tmp:
        check("a loop that gets into the database stops at the level cap in the UNION ALL walks of queries 03, "
              "04 and 05, and a query that would run for ever is stopped by the step budget",
              lambda: [q(looped, "03-explosion.sql"), q(looped, "04-build-plan.sql"), q(looped, "05-buildable.sql"),
                       endless(tmp)],
              [[("P", "R", 1, 1, 3)],
               [("R", 5, 1, 0, 1)],
               [("P", 1, 5, "R", 0)],
               f"stopped after {STEP_BUDGET} thousand steps"])

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

        bom_head = ",".join(BOM_COLUMNS) + "\n"
        order_head = ",".join(ORDER_COLUMNS) + "\n"
        stock_head = ",".join(STOCK_COLUMNS) + "\n"
        small_bom = bom_head + "KIT,NUT,2\nKIT,BOLT,1\n"
        small_orders = csv_file("small_orders.csv", order_head + "KIT,3\n")
        small_stock = csv_file("small_stock.csv", stock_head + "NUT,10\nBOLT,10\n")

        def boms(name, content):
            return rejection(load, csv_file(name, content), small_orders, small_stock)

        def plans(name, content):
            return rejection(load, csv_file("plan_bom.csv", small_bom), csv_file(name, content), small_stock)

        def stocks(name, content):
            return rejection(load, csv_file("stock_bom.csv", small_bom), small_orders, csv_file(name, content))

        def sized(result):
            code, loaded = result
            return (code, (len(loaded[0]), loaded[1], len(loaded[2]))) if code == 0 else result

        def code_message(name, row, field, raw):
            return (2, f"{name} row {row}: {field} {raw!r} is not a part code: capital letters and digits, "
                       f"joined by single hyphens, at most 24 characters")

        check("a loop in the bill is refused, naming the line that closes it and the loop itself",
              lambda: [rejection(load, HERE / "data" / "invalid-bom.csv", ORDERS_CSV, STOCK_CSV),
                       boms("three.csv", bom_head + "KIT,A,1\nA,B,1\nB,C,2\nC,A,1\nC,NUT,1\n")],
              [(2, "invalid-bom.csv row 42: HUB-ASSY -> WHEEL-20 closes the loop "
                   "WHEEL-20 -> HUB-ASSY -> WHEEL-20; an assembly cannot contain itself"),
               (2, "three.csv row 5: C -> A closes the loop A -> B -> C -> A; an assembly cannot contain itself")])

        codes = [("lower.csv", "kit"), ("space.csv", "KIT 2"), ("double.csv", "KIT--2"), ("edge.csv", "-KIT"),
                 ("trailing.csv", "KIT-"), ("long.csv", "A" * 25), ("blank.csv", "")]
        check("a part code in lower case, with a space, a doubled or outer hyphen, over 24 characters, or "
              "blank is refused, and a code of exactly 24 characters and one with two hyphens load",
              lambda: [boms(name, bom_head + f"{raw},NUT,1\n") for name, raw in codes]
                      + [rejection(load, csv_file("max_bom.csv", bom_head + "A" * 24 + ",BOLT-M5-ZN,1\n"),
                                   csv_file("max_orders.csv", order_head + "A" * 24 + ",1\n"),
                                   csv_file("max_stock.csv", stock_head + "BOLT-M5-ZN,1\n"))],
              [code_message(name, 2, "parent", raw) for name, raw in codes]
              + [(0, ([("A" * 24, "BOLT-M5-ZN", 1)], [("A" * 24, 1)], [("BOLT-M5-ZN", 1)]))])

        check("in the bill, rows are counted past blank lines, a line of spaces and a stray quote; a bad "
              "header or one in another order, text after a closing quote, a part listed in itself, a line given twice, and a "
              "quantity of zero, a fraction, a leading zero or six digits are refused",
              lambda: [boms("rows.csv", small_bom + "\n   \n\nKIT,nut,1\n"),
                       boms("quote.csv", small_bom + 'KIT,"WASHER,1\nKIT,PIN",1\n'),
                       boms("spans.csv", small_bom + 'KIT,"WAS\nHER"x,1\n'),
                       boms("header.csv", 'parent,"child"x,qty\nKIT,NUT,1\n'),
                       boms("reordered.csv", "child,parent,qty\nNUT,KIT,1\n"),
                       boms("after.csv", small_bom + 'KIT,"WASHER"x,1\n'),
                       boms("itself.csv", small_bom + "KIT,KIT,1\n"),
                       boms("twice.csv", small_bom + "KIT,NUT,3\n"),
                       boms("zero.csv", small_bom + "KIT,WASHER,0\n"),
                       boms("fraction.csv", small_bom + "KIT,WASHER,1.5\n"),
                       boms("padded.csv", small_bom + "KIT,WASHER,07\n"),
                       boms("six.csv", small_bom + "KIT,WASHER,100000\n")],
              [(2, "rows.csv row 7: child 'nut' is not a part code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "quote.csv row 4: a field runs across more than one line; most likely a stray quote"),
               (2, "spans.csv row 4: cannot be parsed (',' expected after '\"'); most likely a stray quote"),
               (2, "header.csv row 1: cannot be parsed (',' expected after '\"')"),
               (2, "reordered.csv row 1: expected columns parent,child,qty, got ['child', 'parent', 'qty']"),
               (2, "after.csv row 4: cannot be parsed (',' expected after '\"'); most likely a stray quote"),
               (2, "itself.csv row 4: KIT lists itself as one of its own parts"),
               (2, "twice.csv row 4: KIT -> NUT appears twice; one line per parent and part, "
                   "with the quantities added together"),
               (2, "zero.csv row 4: qty '0' is not a whole number from 1 up, at most 5 digits with no leading zero"),
               (2, "fraction.csv row 4: qty '1.5' is not a whole number from 1 up, "
                   "at most 5 digits with no leading zero"),
               (2, "padded.csv row 4: qty '07' is not a whole number from 1 up, at most 5 digits with no leading zero"),
               (2, "six.csv row 4: qty '100000' is not a whole number from 1 up, "
                   "at most 5 digits with no leading zero")])

        # 400 kits of one shared frame that holds 250 parts: 100800 routes on
        # 1050 lines, and a ladder of 40 rungs whose routes double at each one.
        routes_bill = (bom_head + "".join(f"BIG,K{n},1\n" for n in range(400))
                       + "".join(f"K{n},FRAME,1\n" for n in range(400))
                       + "".join(f"FRAME,R{n},1\n" for n in range(250)))
        ladder_bill = (bom_head + "".join(f"N{n},A{n},1\nN{n},B{n},1\nA{n},N{n + 1},1\nB{n},N{n + 1},1\n"
                                          for n in range(40)) + "N40,RAW,1\n")
        # A product with 50251 routes, and one of its subassemblies with 50250
        # ordered beside it.
        plan_bill = (bom_head + "TOP,MID,1\n" + "".join(f"MID,D{n},1\n" for n in range(250))
                     + "".join(f"D{n},E,1\n" for n in range(250)) + "".join(f"E,R{n},1\n" for n in range(199)))
        plan_stock = stock_head + "".join(f"R{n},0\n" for n in range(199))
        # 400 kits of a frame of 248 parts is exactly 100000 routes, which
        # loads with the product alone on the plan; one more part on the
        # product makes 100001. Two products of 200 and 201 kits are each
        # under the limit and together over it.
        exact_bill = (bom_head + "".join(f"BIG,K{n},1\n" for n in range(400))
                      + "".join(f"K{n},FRAME,1\n" for n in range(400))
                      + "".join(f"FRAME,R{n},1\n" for n in range(248)))
        exact_stock = stock_head + "".join(f"R{n},0\n" for n in range(248))
        together_bill = (bom_head + "".join(f"ONE,K{n},1\n" for n in range(200))
                         + "".join(f"TWO,K{n},1\n" for n in range(201))
                         + "".join(f"K{n},FRAME,1\n" for n in range(201))
                         + "".join(f"FRAME,R{n},1\n" for n in range(248)))

        def per_unit_message(name, product):
            return (2, f"{name}: one {product} takes more than 1000000 of NUT, the most the queries allow per unit")

        def route_message(name):
            return (2, f"{name}: the products explode into more than 100000 routes down the bill, "
                       "and the queries walk every route")

        check("a bill with more routes than the queries walk, one route over, and a ladder whose routes double "
              "at every rung; a part needed more than a million times over, by one over, only once two routes "
              "are added, three levels down, on a product that sorts after another, or at a subassembly partway "
              "down, and a chain of a thousand lines at the largest quantity; a bill of more than 100000 lines, "
              "stopped as it is read; two products each under "
              "the route limit and together over it; and a plan whose items explode past the route limit are "
              "refused, while a bill of exactly 100000 routes, a subassembly needed exactly a million times over, "
              "and a part needed exactly a million times over three levels down load",
              lambda: [boms("routes.csv", routes_bill),
                       boms("one_over.csv", exact_bill + "BIG,EXTRA,1\n"),
                       boms("ladder.csv", ladder_bill),
                       boms("per_unit.csv", bom_head + "KIT,SUB,1000\nSUB,NUT,1001\n"),
                       boms("by_one.csv", bom_head + "KIT,SUB,1000\nSUB,NUT,1000\nKIT,NUT,1\n"),
                       boms("two_routes.csv", bom_head + "KIT,A,1\nKIT,B,1\nA,X,10\nB,X,10\nX,NUT,60000\n"),
                       boms("three_levels.csv", bom_head + "KIT,A,10\nA,B,100\nB,NUT,1001\n"),
                       boms("second.csv", bom_head + "A,NUT,1\nB,SUB,1000\nSUB,NUT,1001\n"),
                       boms("partway.csv", bom_head + "KIT,C1,99999\nC1,C2,99999\nC2,NUT,1\n"),
                       boms("long_chain.csv", bom_head + "KIT,C1,99999\n"
                            + "".join(f"C{n},C{n + 1},99999\n" for n in range(1, 1000)) + "C1000,NUT,99999\n"),
                       boms("too_many_lines.csv", bom_head + "".join(f"FLAT,R{n},1\n" for n in range(100001))),
                       boms("together.csv", together_bill),
                       rejection(load, csv_file("plan_bill.csv", plan_bill),
                                 csv_file("plan_orders.csv", order_head + "TOP,1\nMID,1\n"),
                                 csv_file("plan_stock.csv", plan_stock)),
                       sized(rejection(load, csv_file("exact_routes.csv", exact_bill),
                                       csv_file("exact_orders.csv", order_head + "BIG,1\n"),
                                       csv_file("exact_stock.csv", exact_stock))),
                       rejection(load, csv_file("at_assembly.csv", bom_head + "KIT,A,1000\nA,B,1000\nB,NUT,1\n"),
                                 csv_file("at_orders.csv", order_head + "KIT,1\n"),
                                 csv_file("at_stock.csv", stock_head + "NUT,0\n")),
                       rejection(load, csv_file("exact_cap.csv", bom_head + "KIT,A,10\nA,B,100\nB,NUT,1000\n"),
                                 csv_file("cap_orders.csv", order_head + "KIT,1\n"),
                                 csv_file("cap_stock.csv", stock_head + "NUT,0\n"))],
              [route_message("routes.csv"), route_message("one_over.csv"), route_message("ladder.csv"),
               per_unit_message("per_unit.csv", "KIT"), per_unit_message("by_one.csv", "KIT"),
               per_unit_message("two_routes.csv", "KIT"), per_unit_message("three_levels.csv", "KIT"),
               per_unit_message("second.csv", "B"), per_unit_message("partway.csv", "KIT"),
               per_unit_message("long_chain.csv", "KIT"),
               (2, "too_many_lines.csv row 100002: the bill runs past 100000 lines, and every line adds a route "
                   "the queries walk"),
               route_message("together.csv"),
               (2, "plan_orders.csv: the items on the plan explode into more than 100000 routes down the bill, "
                   "and the queries walk every route"),
               (0, (1048, [("BIG", 1)], 248)),
               (0, ([("KIT", "A", 1000), ("A", "B", 1000), ("B", "NUT", 1)], [("KIT", 1)], [("NUT", 0)])),
               (0, ([("KIT", "A", 10), ("A", "B", 100), ("B", "NUT", 1000)], [("KIT", 1)], [("NUT", 0)]))])

        check("on the plan, a raw part, an unknown code, a code in lower case, an item listed twice, a quantity "
              "of zero or six "
              "digits, and a plan with only a header are refused; in the stock count, an assembly, an unknown part, a part counted twice, a "
              "part in lower case, a negative, zero-padded or thirteen-digit count, and a raw part left out are refused",
              lambda: [plans("raw_item.csv", order_head + "NUT,1\n"),
                       plans("unknown_item.csv", order_head + "BIKE,1\n"),
                       plans("twice_item.csv", order_head + "KIT,1\nKIT,2\n"),
                       plans("zero_item.csv", order_head + "KIT,0\n"),
                       plans("six_item.csv", order_head + "KIT,100000\n"),
                       plans("bare_plan.csv", order_head),
                       plans("lower_item.csv", order_head + "kit,1\n"),
                       stocks("assembly.csv", stock_head + "KIT,1\n"),
                       stocks("unknown_part.csv", stock_head + "WASHER,1\n"),
                       stocks("twice_part.csv", stock_head + "NUT,1\nNUT,2\n"),
                       stocks("negative.csv", stock_head + "NUT,-1\n"),
                       stocks("thirteen.csv", stock_head + "NUT,1000000000000\n"),
                       stocks("padded_count.csv", stock_head + "NUT,07\n"),
                       stocks("lower_part.csv", stock_head + "nut,1\n"),
                       stocks("missing.csv", stock_head + "NUT,4\n")],
              [(2, "raw_item.csv row 2: NUT has no parts listed in plan_bom.csv, so there is nothing to build it from"),
               (2, "unknown_item.csv row 2: BIKE has no parts listed in plan_bom.csv, "
                   "so there is nothing to build it from"),
               (2, "twice_item.csv row 3: KIT is on the plan twice; one line per item, with the units added together"),
               (2, "zero_item.csv row 2: qty '0' is not a whole number from 1 up, "
                   "at most 5 digits with no leading zero"),
               (2, "six_item.csv row 2: qty '100000' is not a whole number from 1 up, "
                   "at most 5 digits with no leading zero"),
               (2, "bare_plan.csv row 1: no data rows after the header"),
               (2, "lower_item.csv row 2: item 'kit' is not a part code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "assembly.csv row 2: KIT is an assembly; stock is counted for raw parts only"),
               (2, "unknown_part.csv row 2: WASHER is not a part in stock_bom.csv"),
               (2, "twice_part.csv row 3: NUT is counted twice; one line per part"),
               (2, "negative.csv row 2: on_hand '-1' is not a whole number from 0 up, "
                   "at most 12 digits with no leading zero"),
               (2, "thirteen.csv row 2: on_hand '1000000000000' is not a whole number from 0 up, "
                   "at most 12 digits with no leading zero"),
               (2, "padded_count.csv row 2: on_hand '07' is not a whole number from 0 up, "
                   "at most 12 digits with no leading zero"),
               (2, "lower_part.csv row 2: part 'nut' is not a part code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "missing.csv: raw part BOLT has no line; count every raw part, at 0 if there are none")])

        check("rows with too many or too few fields, a line of commas, a tab, a renamed header, an empty file, "
              "one with only a header, one that is not UTF-8, and a folder are refused, while a byte-order mark, "
              "spaces around fields, and the largest counts load",
              lambda: [boms("wide.csv", small_bom + "KIT,WASHER,1,extra\n"),
                       boms("narrow.csv", small_bom + "KIT,WASHER\n"),
                       boms("commas.csv", small_bom + ",,\n"),
                       boms("tab.csv", small_bom + "KIT,WASHER\t,1\n"),
                       boms("renamed.csv", "parent,part,qty\nKIT,NUT,1\n"),
                       boms("empty.csv", ""),
                       boms("bare.csv", bom_head),
                       rejection(load, byte_file("latin1.csv", bom_head.encode("utf-8")
                                                 + "KIT,NUT,1\n".encode("utf-8") + b"KIT,\xe9,1\n"),
                                 small_orders, small_stock),
                       (lambda code, message: (code, message.startswith(Path(tmp).name + ": ")))(
                           *rejection(load, Path(tmp), small_orders, small_stock)),
                       rejection(load, csv_file("bom_bom.csv", "\ufeff" + small_bom),
                                 csv_file("spaced_orders.csv", order_head + " KIT , 99999 \n"),
                                 csv_file("big_stock.csv", stock_head + "NUT,999999999999\nBOLT,0\n"))],
              [(2, "wide.csv row 4: has more fields than the header"),
               (2, "narrow.csv row 4: has fewer fields than the header"),
               (2, "commas.csv row 4: parent '' is not a part code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "tab.csv row 4: child 'WASHER\\t' is not a part code: capital letters and digits, "
                   "joined by single hyphens, at most 24 characters"),
               (2, "renamed.csv row 1: expected columns parent,child,qty, got ['parent', 'part', 'qty']"),
               (2, "empty.csv: is empty"),
               (2, "bare.csv row 1: no data rows after the header"),
               (2, "latin1.csv: is not UTF-8 text"),
               (2, True),
               (0, ([("KIT", "NUT", 2), ("KIT", "BOLT", 1)], [("KIT", 99999)],
                    [("NUT", 999999999999), ("BOLT", 0)]))])

        def utf8_check():
            # Output written in the Windows codepage cannot hold these
            # characters; after utf8_output it goes out as UTF-8.
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
                return out.getvalue().decode("utf-8"), err.getvalue().decode("utf-8")
            finally:
                sys.stdout, sys.stderr = saved

        other = [csv_file(name, Path(sample).read_text(encoding="utf-8"))
                 for name, sample in (("other_bom.csv", BOM_CSV), ("other_orders.csv", ORDERS_CSV),
                                      ("other_stock.csv", STOCK_CSV))]

        def cli(*argv):
            return rejection(settings, [str(a) for a in argv])

        def main_check():
            # main itself, on a file name the Windows codepage cannot hold. It
            # stops at the missing file, and the message has to come out as
            # UTF-8. The command line has no --test, so no suite is started.
            saved = sys.argv, sys.stdout, sys.stderr
            err = io.BytesIO()
            name = "\u6f22\u5b57.csv"
            sys.argv = ["run.py", "--bom", str(Path(tmp) / name), "--orders", str(other[1]), "--stock", str(other[2])]
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

        check("on the command line, files given without the other two, a file that is not there, and a test "
              "run on any file other than the sample are refused, while the sample is picked by default or spelled "
              "another way, three files of your own are taken, and output and messages, from main itself too, "
              "are written as UTF-8",
              lambda: [cli("--bom", other[0]),
                       cli("--orders", other[1], "--stock", other[2]),
                       cli("--bom", Path(tmp) / "not_there.csv", "--orders", other[1], "--stock", other[2]),
                       cli("--test", "--bom", other[0], "--orders", ORDERS_CSV, "--stock", STOCK_CSV),
                       cli("--test", "--bom", BOM_CSV, "--orders", other[1], "--stock", STOCK_CSV),
                       cli("--test", "--bom", BOM_CSV, "--orders", ORDERS_CSV, "--stock", other[2]),
                       cli("--test"),
                       cli(),
                       utf8_check(),
                       cli("--test", "--bom", HERE / "data" / ".." / "data" / "bom.csv", "--orders", ORDERS_CSV,
                           "--stock", STOCK_CSV),
                       cli("--bom", other[0], "--orders", other[1], "--stock", other[2]),
                       main_check()],
              [(2, "run.py: error: --bom, --orders and --stock go together; give all three or none"),
               (2, "run.py: error: --bom, --orders and --stock go together; give all three or none"),
               (2, f"run.py: error: --bom: '{Path(tmp) / 'not_there.csv'}' is not a file"),
               (2, "run.py: error: --test checks hand-computed answers for the sample files; "
                   "run it without --bom, --orders and --stock"),
               (2, "run.py: error: --test checks hand-computed answers for the sample files; "
                   "run it without --bom, --orders and --stock"),
               (2, "run.py: error: --test checks hand-computed answers for the sample files; "
                   "run it without --bom, --orders and --stock"),
               (0, (True, (BOM_CSV, ORDERS_CSV, STOCK_CSV))),
               (0, (False, (BOM_CSV, ORDERS_CSV, STOCK_CSV))),
               ("\u6f22\u5b57.csv\n", "\u6f22\u5b57.csv\n"),
               (0, (True, (HERE / "data" / ".." / "data" / "bom.csv", ORDERS_CSV, STOCK_CSV))),
               (0, (False, tuple(other))),
               (2, True)])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def settings(argv):
    # Reads the command line and settles which files to load. It never runs
    # a query or the suite, so the suite can check it directly.
    parser = argparse.ArgumentParser(prog="run.py", description="Run the explosion queries against a bill of "
                                                 "materials, the sample by default.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--bom", type=Path, default=None, help="path to an alternate bill of materials CSV")
    parser.add_argument("--orders", type=Path, default=None, help="path to the build plan for that bill")
    parser.add_argument("--stock", type=Path, default=None, help="path to the stock count for that bill")
    args = parser.parse_args(argv)
    given = [value is not None for value in (args.bom, args.orders, args.stock)]
    # The three files only make sense together, so a bill of your own never
    # picks up the sample plan or stock.
    if any(given) and not all(given):
        parser.error("--bom, --orders and --stock go together; give all three or none")
    paths = (args.bom or BOM_CSV, args.orders or ORDERS_CSV, args.stock or STOCK_CSV)
    for flag, path in zip(("--bom", "--orders", "--stock"), paths):
        if not path.is_file():
            if all(given):
                parser.error(f"{flag}: '{path}' is not a file")
            parser.error(f"the sample file '{path}' is missing")
    samples = (BOM_CSV, ORDERS_CSV, STOCK_CSV)
    if args.test and any(p.resolve() != s.resolve() for p, s in zip(paths, samples)):
        parser.error("--test checks hand-computed answers for the sample files; "
                     "run it without --bom, --orders and --stock")
    return args.test, paths


def utf8_output():
    # Output is written as UTF-8, since a file name in a message can hold
    # characters that the Windows console codepage cannot print.
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


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
