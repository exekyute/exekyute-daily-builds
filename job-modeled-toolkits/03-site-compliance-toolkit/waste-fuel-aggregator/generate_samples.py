"""Create the synthetic monthly site files this tool reads.

Run this once to fill the data/ folder with example spreadsheets. Every file is
made up. There is no real site or operational data anywhere.

The samples are designed so that a single aggregation run exercises every branch
of the logic at least once:
  - a clean file with the "standard" column names,
  - a file that uses completely different column names (to test normalisation),
  - a row with a negative quantity (rejected),
  - a row with a blank site (rejected),
  - a row with a bad month like 2026-13 (rejected),
  - a duplicate site and month across two files (the later one is reported),
  - a boundary value of 0.00,
  - a file missing a required column entirely (the whole file is skipped).
"""

import csv
import os

DATA_FOLDER = os.path.join(os.path.dirname(__file__), "data")


def _write(name, header, rows):
    """Write one CSV file into the data folder."""
    path = os.path.join(DATA_FOLDER, name)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  wrote {name}")


def _clear_old_samples():
    """Remove any .csv already in the data folder so a re-run starts clean."""
    if not os.path.isdir(DATA_FOLDER):
        return
    for name in os.listdir(DATA_FOLDER):
        if name.lower().endswith(".csv"):
            os.remove(os.path.join(DATA_FOLDER, name))


def main():
    if not os.path.isdir(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    _clear_old_samples()

    print("Writing sample site files into data/ ...")

    # Files are numbered in the order they were "received" that month. The
    # aggregator reads them in this order, so when a site resends a month the
    # original (lower number) is kept and the resend is reported as a duplicate.

    # 1. North Site: the "standard" headers. Includes a 0.00 boundary row.
    _write(
        "01-north-site.csv",
        ["Site", "Month", "Waste (tons)", "Fuel (gal)"],
        [
            ["North Site", "2026-01", "12.5", "340.0"],
            ["North Site", "2026-02", "0.00", "0.00"],
        ],
    )

    # 2. Harbor Site: different header spellings, to test normalisation.
    #    The February row has a negative fuel value and is rejected.
    _write(
        "02-harbor-site.csv",
        ["Location", "Reporting Month", "Waste Tonnage", "Diesel Gallons"],
        [
            ["Harbor Site", "2026-01", "8.2", "210.5"],
            ["Harbor Site", "2026-02", "9.1", "-5.0"],
        ],
    )

    # 3. Ridge Site: another header style, plus two deliberately bad rows.
    _write(
        "03-ridge-site.csv",
        ["Facility", "period", "waste_tons", "Fuel Used"],
        [
            ["Ridge Site", "2026-01", "4.0", "75.0"],
            ["", "2026-01", "1.0", "10.0"],          # blank site, rejected
            ["Ridge Site", "2026-13", "2.0", "20.0"],  # bad month, rejected
        ],
    )

    # 4. A second North Site file that repeats January, to test deduplication.
    _write(
        "04-north-site-resend.csv",
        ["Site", "Month", "Waste (tons)", "Fuel (gal)"],
        [
            ["North Site", "2026-01", "99.0", "99.0"],  # duplicate, reported
        ],
    )

    # 5. Depot Site: missing the waste column entirely, so the file is skipped.
    _write(
        "05-depot-site.csv",
        ["Site", "Month", "Fuel (gal)"],
        [
            ["Depot Site", "2026-01", "50.0"],
        ],
    )

    print("Done. Now run:  python aggregate_cli.py")


if __name__ == "__main__":
    main()
