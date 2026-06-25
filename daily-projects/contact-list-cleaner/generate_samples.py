"""Create synthetic sample data for the Contact List Cleaner.

Running this script (re)creates one thing in the project folder:

  samples/contacts_messy.csv  - a small, deliberately messy contact list of the
                                kind you get when you export from several places
                                and paste them together.

Everything here is made up. There is no real contact data anywhere in this repo,
so it is safe to commit and share. The names are the usual fictional companies
(Acme, Globex, Initech, Umbrella, Initrode).

The mess is on purpose. Each row exercises something the cleaner has to handle:
duplicate people, three spellings of one email, a phone in every format, a couple
of genuine contradictions, and one phone number that is too short to be real.

Run it with:

    python generate_samples.py
"""

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(HERE, "samples")
MESSY_PATH = os.path.join(SAMPLES_DIR, "contacts_messy.csv")

# Each tuple is one row: (name, email, phone, company, title). The comments call
# out what each block is testing. Order is shuffled-ish on purpose so duplicates
# are not always next to each other, just like a real export.
SAMPLE_ROWS = [
    # Same person, matched by email, typed three different ways. The second row
    # has no company or title but does have a phone, so it donates the phone to
    # the merged record while the others donate the company and title.
    ("Jane Doe", "Jane@Acme.com", "", "Acme Corporation", "Marketing Lead"),
    ("  jane doe ", " jane@acme.com ", "(555) 123-4567", "", ""),
    ("Jane Doe", "Jane Doe <jane@acme.com>", "555.123.4567", "Acme Corporation", "Marketing Lead"),

    # Matched by PHONE only (no email on either row), in two formats. The titles
    # disagree, which should surface as a conflict, not get silently dropped.
    ("Bob Smith", "", "+1 555 234 5678", "Globex Inc", "Buyer"),
    ("Robert Smith", "", "5552345678", "Globex Inc", "Senior Buyer"),

    # Matched by NAME only (no email, no phone). Identical, so a clean merge.
    ("Carol King", "", "", "Initech LLC", "Coordinator"),
    ("carol king", "", "", "Initech LLC", "Coordinator"),

    # Same email, but the company disagrees: a real conflict to put in the report.
    ("Dave Lee", "dave@umbrella.com", "(555) 345-6789", "Umbrella Media", "Analyst"),
    ("Dave Lee", "DAVE@umbrella.com", "", "Umbrella Corp", ""),

    # A phone that is too short to be a real number: flagged, not formatted.
    ("Frank Stone", "frank@initrode.com", "555-12", "Initrode Partners", "Owner"),

    # Clean, unique singletons. Their phones cover the rest of the format zoo so
    # the cleaner's reformatting gets a thorough workout.
    ("Grace Hopper", "grace@globex.com", "(555) 456-7890", "Globex Inc", "CTO"),
    ("Henry Ford", "henry@initech.com", "5554567891", "Initech LLC", "Operations"),
    ("Ivy Chen", "ivy@acme.com", "+1 (555) 567-8902", "Acme Corporation", "Designer"),
    ("  JAMES   BOND ", "james@globex.com", "555 678 9013", "Globex Inc", "Field Agent"),
    ("Karen Page", "karen@umbrella.com", "(555) 789-0124", "Umbrella Media", "Counsel"),
    ("Leo Marsh", "leo@initrode.com", "5557890125", "Initrode Partners", "Scout"),
    # No email: this one stands alone, keyed by its (unique) phone number.
    ("Mona Reyes", "", "555.890.1267", "Acme Corporation", "Curator"),
    ("Otto Frank", "OTTO@INITECH.COM", "+1 (555) 901-2378", "Initech LLC", "Archivist"),
]


def write_samples():
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    with open(MESSY_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "email", "phone", "company", "title"])
        writer.writerows(SAMPLE_ROWS)
    print("Wrote %d messy rows into samples/contacts_messy.csv" % len(SAMPLE_ROWS))


def main():
    write_samples()
    print("Done. Try:  python clean_cli.py preview")


if __name__ == "__main__":
    main()
