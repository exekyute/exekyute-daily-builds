"""Create the synthetic compliance log this tool reads.

Run this once to write data/compliance_log.csv. Every entry is made up. There is
no real site or compliance data anywhere.

The dates are chosen around a reference "today" of 2026-06-06 so that a single run
lands at least one item in every urgency band. When you test the tool, pass that
same date with --today 2026-06-06 and the dashboard will match the README:

  - one item already overdue,
  - one item due exactly today (the zero-day boundary),
  - one item due in 4 days (clearly DUE SOON),
  - one item due in exactly 14 days (the DUE SOON / UPCOMING boundary),
  - two items further out (UPCOMING),
  - one completed item,
  - one row with a slash-format date (rejected),
  - one row with a blank site (rejected),
  - one duplicate site and requirement (reported),
  - one row with an unknown status (kept, but reported and treated as open).

Ridge Site has activity in the aggregator's ledger but no deadline here, so the
cross-check flags it as a compliance gap.
"""

import csv
import os

DATA_FOLDER = os.path.join(os.path.dirname(__file__), "data")
LOG_PATH = os.path.join(DATA_FOLDER, "compliance_log.csv")

HEADER = ["site", "requirement", "due_date", "status"]

ROWS = [
    # site, requirement, due_date, status
    ["North Site", "Stormwater permit renewal", "2026-05-20", "open"],       # overdue
    ["Harbor Site", "Air quality self-report", "2026-06-06", "open"],        # due today
    ["Harbor Site", "Spill kit inspection", "2026-06-10", "open"],           # due soon (4 days)
    ["North Site", "Hazardous waste manifest filing", "2026-06-20", "open"], # due soon (14 days)
    ["North Site", "Noise monitoring report", "2026-07-15", "pending"],      # unknown status -> open
    ["Harbor Site", "Annual compliance audit", "2026-08-01", "open"],        # upcoming
    ["North Site", "Q1 emissions report", "2026-04-15", "complete"],         # complete
    ["Harbor Site", "Tank integrity test", "06/01/2026", "open"],            # bad date -> rejected
    ["", "Safety checklist sign-off", "2026-07-01", "open"],                 # blank site -> rejected
    ["North Site", "Stormwater permit renewal", "2026-05-20", "open"],       # duplicate -> reported
]


def main():
    if not os.path.isdir(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)

    with open(LOG_PATH, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(HEADER)
        writer.writerows(ROWS)

    print(f"Wrote {LOG_PATH}")
    print("Now run:  python monitor_cli.py --today 2026-06-06")


if __name__ == "__main__":
    main()
