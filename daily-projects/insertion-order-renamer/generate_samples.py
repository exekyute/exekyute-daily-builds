"""Create synthetic sample data for the Insertion Order renamer.

Running this script (re)creates two things in the project folder:

  1. companies.csv  - a small lookup table mapping an IO number to the clean,
                      official name of the company (the media buyer / agency /
                      advertiser) that sent you the insertion order.
  2. samples/       - a folder of messy, inconsistently named IO files, the kind
                      that pile up when many different senders each name files
                      their own way.

Everything here is made up. There is no real client data anywhere in this repo.

The sample files are tiny but real, openable PDFs. We build them by hand out of
plain bytes so the project needs nothing beyond the Python standard library.
The PDF content does not matter to the renamer (it only ever looks at file
names), but real PDFs make the demo feel less like a trick.

Run it with:

    python generate_samples.py
"""

import csv
import os

# ---------------------------------------------------------------------------
# Where things go. We use paths relative to THIS file so the script works no
# matter what folder you run it from.
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES_DIR = os.path.join(HERE, "samples")
LOOKUP_PATH = os.path.join(HERE, "companies.csv")

# ---------------------------------------------------------------------------
# The lookup table. IO number -> official sender name.
# Notice that 99001 is deliberately NOT here, so the tool has to fall back to
# guessing the company from the file name for that one.
# ---------------------------------------------------------------------------
COMPANIES = [
    ("12345", "Acme Corporation"),
    ("67890", "Globex Inc"),
    ("24680", "Initech LLC"),
    ("13579", "Umbrella Media"),
]

# ---------------------------------------------------------------------------
# The messy file names. This is the variety the parser has to cope with.
# Each tuple is (messy filename, IO number to stamp inside the PDF for realism).
# The last two are intentional problem cases:
#   - initrode 99001 io.pdf      has an IO number that is NOT in the lookup
#   - scanned_document_final.pdf has no IO number at all
# ---------------------------------------------------------------------------
SAMPLE_FILES = [
    ("IO 12345 Acme Corp.pdf", "12345"),
    ("acme_insertionorder_12345_FINAL_v2.pdf", "12345"),
    ("12345-Acme-IO-signed.pdf", "12345"),
    ("Globex IO#67890 (copy).pdf", "67890"),
    ("insertion order 67890 globex draft.pdf", "67890"),
    ("Initech_IO_24680.pdf", "24680"),
    ("IO24680 initech the agency.pdf", "24680"),
    ("umbrella media io 13579.pdf", "13579"),
    ("13579_UMBRELLA_FINAL.pdf", "13579"),
    ("initrode 99001 io.pdf", "99001"),
    ("IO#99001 Initrode Partners v1.pdf", "99001"),
    ("scanned_document_final.pdf", ""),
]


def make_pdf_bytes(text):
    """Return the bytes of a minimal, valid, single-page PDF showing `text`.

    This hand-builds the smallest PDF that real viewers will open. You do not
    need to understand the format to use the renamer. The short version: a PDF
    is a list of numbered "objects"; at the end, a cross-reference table records
    the byte offset of each one. We assemble the objects, then measure where
    each landed so the table is correct.
    """
    # Escape characters that are special inside a PDF text string.
    safe = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")

    # Build the page's drawing instructions, then measure their exact byte
    # length. The /Length entry must match this exactly, so we compute it rather
    # than guess it.
    content = b"BT /F1 14 Tf 20 60 Td (" + safe.encode("latin-1", "replace") + b") Tj ET"

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 120] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i
        out += body
        out += b"\nendobj\n"

    xref_pos = len(out)
    out += b"xref\n"
    out += b"0 %d\n" % (len(objects) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % (len(objects) + 1)
    out += b"startxref\n%d\n%%%%EOF" % xref_pos
    return bytes(out)


def write_lookup():
    with open(LOOKUP_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["io_number", "company"])
        writer.writerows(COMPANIES)
    print("Wrote lookup table: companies.csv (%d senders)" % len(COMPANIES))


def write_samples():
    os.makedirs(SAMPLES_DIR, exist_ok=True)
    for filename, io_number in SAMPLE_FILES:
        label = "Insertion Order %s" % io_number if io_number else "Insertion Order"
        path = os.path.join(SAMPLES_DIR, filename)
        with open(path, "wb") as f:
            f.write(make_pdf_bytes(label))
    print("Wrote %d sample files into samples/" % len(SAMPLE_FILES))


def main():
    write_lookup()
    write_samples()
    print("Done. Try:  python rename_cli.py preview")


if __name__ == "__main__":
    main()
