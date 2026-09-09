"""Load the roster and requirement tables into SQLite and run the division queries.

Usage:
    python run.py                                   run every query in sql/
    python run.py --test                            run the assertion suite
    python run.py --holdings other.csv              load one table from elsewhere
"""

import argparse
import csv
import io
import sqlite3
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
TECHNICIANS_CSV = DATA_DIR / "technicians.csv"
JOBS_CSV = DATA_DIR / "jobs.csv"
HOLDINGS_CSV = DATA_DIR / "holdings.csv"
REQUIREMENTS_CSV = DATA_DIR / "requirements.csv"
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


def cell(path, row_num, row, column):
    if None in row:
        fail(path, row_num, "has more fields than the header")
    if any(v is None for v in row.values()):
        fail(path, row_num, "has fewer fields than the header")
    # Normalised so a decomposed accent from one export and a precomposed one
    # from another are the same code rather than two that never match.
    value = unicodedata.normalize("NFC", " ".join(row[column].split()))
    if not value:
        fail(path, row_num, f"{column} is empty")
    return value


def norm_key(text):
    # Spacing is already normalised by cell(), so letter case is what is
    # left to catch: one code arriving as HEIGHT here and height there.
    return text.casefold()


def load_entities(path, id_column, name_column):
    rows, seen = [], {}
    reader = read_csv(path, [id_column, name_column])
    for row in reader:
        i = reader.line_num
        entity_id = cell(path, i, row, id_column)
        name = cell(path, i, row, name_column)
        first = seen.get(norm_key(entity_id))
        if first is not None:
            fail(path, i, f"{id_column} {entity_id!r} repeats {first!r}; each row is one record")
        seen[norm_key(entity_id)] = entity_id
        rows.append((entity_id, name))
    if not rows:
        fail(path, 1, "no data rows after the header")
    return rows


def load_links(path, parent_column, parent_ids, parent_file, certs):
    rows, seen = [], set()
    reader = read_csv(path, [parent_column, "cert"])
    for row in reader:
        i = reader.line_num
        parent = cell(path, i, row, parent_column)
        # A link naming a record that does not exist can never produce a
        # qualified pair, since the reports join back to the roster. It would
        # still inflate the raw counts in 01 and the any-of count in 02.
        if parent not in parent_ids:
            fail(path, i, f"{parent_column} {parent!r} is not in {parent_file}; "
                          "a link to an unknown record would vanish from every join")
        cert = cell(path, i, row, "cert")
        # The division matches certification text exactly, across both files,
        # so one code spelled two ways would silently split into two codes
        # and make a job nobody can qualify for.
        first, first_file = certs.get(norm_key(cert), (None, None))
        if first is not None and first != cert:
            fail(path, i, f"cert {cert!r} matches {first!r} in {first_file} apart from letter "
                          "case; the division matches certification text exactly")
        certs[norm_key(cert)] = (cert, Path(path).name)
        if (parent, cert) in seen:
            fail(path, i, f"{parent} already lists {cert!r}; a repeated pair adds nothing")
        seen.add((parent, cert))
        rows.append((parent, cert))
    # No minimum here on purpose. An empty link table is ordinary data: a crew
    # with nothing recorded yet, or a job list where nothing is gated.
    return rows


def build_db(technicians_path, jobs_path, holdings_path, requirements_path):
    technicians = load_entities(technicians_path, "tech_id", "name")
    jobs = load_entities(jobs_path, "job_id", "job_name")
    certs = {}
    holdings = load_links(holdings_path, "tech_id",
                          {t for t, _ in technicians}, Path(technicians_path).name, certs)
    requirements = load_links(requirements_path, "job_id",
                              {j for j, _ in jobs}, Path(jobs_path).name, certs)

    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE technicians (tech_id TEXT PRIMARY KEY, name TEXT NOT NULL)")
    db.execute("CREATE TABLE jobs (job_id TEXT PRIMARY KEY, job_name TEXT NOT NULL)")
    db.execute("CREATE TABLE holdings (tech_id TEXT NOT NULL, cert TEXT NOT NULL, PRIMARY KEY (tech_id, cert))")
    db.execute("CREATE TABLE requirements (job_id TEXT NOT NULL, cert TEXT NOT NULL, PRIMARY KEY (job_id, cert))")
    db.executemany("INSERT INTO technicians VALUES (?, ?)", technicians)
    db.executemany("INSERT INTO jobs VALUES (?, ?)", jobs)
    db.executemany("INSERT INTO holdings VALUES (?, ?)", holdings)
    db.executemany("INSERT INTO requirements VALUES (?, ?)", requirements)
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

    check("all four tables loaded",
          tuple(db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                for t in ("technicians", "jobs", "holdings", "requirements")),
          (8, 4, 22, 9))

    _, shape = run_query(db, SQL_DIR / "01-roster-shape.sql")
    check("one technician holds nothing and one job requires nothing",
          shape, [(8, 4, 22, 9, 6, 6, 1, 1)])

    _, trap = run_query(db, SQL_DIR / "02-any-versus-all.sql")
    check("any-of inflates every real job and reports zero for the empty one",
          trap,
          [("J-1", "Pump overhaul", 3, 7, 2),
           ("J-2", "Tank inspection", 2, 6, 4),
           ("J-3", "Structural weld", 4, 7, 1),
           ("J-4", "Yard cleanup", 0, 0, 8)])

    _, counted = run_query(db, SQL_DIR / "03-division-by-counting.sql")
    check("counting finds seven qualified pairs",
          [(r[0], r[2], r[3]) for r in counted],
          [("J-1", "T-01", "Ada Reyes"), ("J-1", "T-02", "Bo Ellis"),
           ("J-2", "T-01", "Ada Reyes"), ("J-2", "T-03", "Cyd Marsh"),
           ("J-2", "T-04", "Dev Kaur"), ("J-2", "T-07", "Gil Sant"),
           ("J-3", "T-03", "Cyd Marsh")])
    check("the job requiring nothing never appears in the counting version",
          [r for r in counted if r[0] == "J-4"], [])

    _, absent = run_query(db, SQL_DIR / "04-division-by-absence.sql")
    check("absence finds the same seven plus the whole roster for the empty job",
          len(absent), 15)
    check("the two constructions agree on every job that requires something",
          sorted((r[0], r[2]) for r in absent if r[0] != "J-4"),
          sorted((r[0], r[2]) for r in counted))
    check("they disagree only on the job requiring nothing",
          sorted((r[0], r[2], r[4]) for r in absent if r[4] == "no"),
          sorted(("J-4", f"T-0{n}", "no") for n in range(1, 9)))
    check("the technician holding nothing qualifies for the empty job and no other",
          [(r[0], r[3]) for r in absent if r[2] == "T-08"],
          [("J-4", "Hana Ito")])

    _, near = run_query(db, SQL_DIR / "05-one-cert-away.sql")
    check("three technicians are one certification short across four pairs",
          near,
          [("J-1", "Pump overhaul", "T-03", "Cyd Marsh", "HYD"),
           ("J-2", "Tank inspection", "T-02", "Bo Ellis", "HEIGHT"),
           ("J-2", "Tank inspection", "T-06", "Fin Oduya", "CONF"),
           ("J-3", "Structural weld", "T-06", "Fin Oduya", "FORK")])
    check("nobody already qualified turns up in the near-miss list",
          sorted(set((r[0], r[2]) for r in near) & set((r[0], r[2]) for r in absent)),
          [])

    print()
    if failures:
        print(f"{failures} check(s) failed")
        sys.exit(1)
    print("all checks passed")


def main():
    parser = argparse.ArgumentParser(description="Run the division queries against the sample roster.")
    parser.add_argument("--test", action="store_true", help="run the assertion suite instead of the reports")
    parser.add_argument("--technicians", type=Path, default=TECHNICIANS_CSV, help="path to the technician roster")
    parser.add_argument("--jobs", type=Path, default=JOBS_CSV, help="path to the job list")
    parser.add_argument("--holdings", type=Path, default=HOLDINGS_CSV, help="path to the certifications held")
    parser.add_argument("--requirements", type=Path, default=REQUIREMENTS_CSV, help="path to the certifications required")
    args = parser.parse_args()
    # The loader accepts any UTF-8 name, so the reports have to be able to
    # print one. Windows consoles default to a codepage that cannot.
    sys.stdout.reconfigure(encoding="utf-8")
    defaults = (TECHNICIANS_CSV, JOBS_CSV, HOLDINGS_CSV, REQUIREMENTS_CSV)
    given = (args.technicians, args.jobs, args.holdings, args.requirements)
    # Checked here rather than at open time so the complaint names the flag.
    # An empty path argument becomes the current directory, which opens as a
    # directory and would otherwise report an error against no file at all.
    for flag, path in zip(("technicians", "jobs", "holdings", "requirements"), given):
        if not path.is_file():
            parser.error(f"--{flag}: {str(path)!r} is not a file")
    if args.test and any(g.resolve() != d.resolve() for g, d in zip(given, defaults)):
        parser.error("--test checks hand-computed answers for the sample roster; run it without a file override")

    db = build_db(*given)
    if args.test:
        run_tests(db)
    else:
        run_all(db)


if __name__ == "__main__":
    main()
