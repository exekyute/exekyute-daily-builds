"""Tests for core.py, the logic both front ends share.

These use Python's built-in `unittest`, so there is nothing to install. Run them
from the project folder with:

    python -m unittest discover tests

Each test states what it expects in plain English. Tests are the safety net that
lets you change core.py later and instantly see if you broke something. Every
test that needs files makes them in its own temporary folder, so samples/,
samples_work/ and your own folders are never read or changed.
"""

import csv
import os
import sys
import tempfile
import unittest

# Make sure we can import core.py, which lives one folder up from this file.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core  # noqa: E402  (import after the path tweak above)
import generate_samples  # noqa: E402  (only its lists are used; nothing is written)

# The sample lookup table, keyed the way core.load_lookup keys it.
LOOKUP = {
    number.zfill(core.IO_PAD): company
    for number, company in generate_samples.COMPANIES
}

# The 12 messy names generate_samples.py makes.
SAMPLE_NAMES = [name for name, _ in generate_samples.SAMPLE_FILES]

# What one run makes of those 12 names with the sample lookup table, in the
# order plan_renames works through them. None means the file is skipped.
SAMPLE_PLAN = [
    ("12345-Acme-IO-signed.pdf", "Acme-Corporation_IO-12345.pdf"),
    ("13579_UMBRELLA_FINAL.pdf", "Umbrella-Media_IO-13579.pdf"),
    ("Globex IO#67890 (copy).pdf", "Globex-Inc_IO-67890.pdf"),
    ("IO 12345 Acme Corp.pdf", "Acme-Corporation_IO-12345-2.pdf"),
    ("IO#99001 Initrode Partners v1.pdf", "Initrode_IO-99001.pdf"),
    ("IO24680 initech the agency.pdf", "Initech-LLC_IO-24680.pdf"),
    ("Initech_IO_24680.pdf", "Initech-LLC_IO-24680-2.pdf"),
    ("acme_insertionorder_12345_FINAL_v2.pdf", "Acme-Corporation_IO-12345-3.pdf"),
    ("initrode 99001 io.pdf", "Initrode_IO-99001-2.pdf"),
    ("insertion order 67890 globex draft.pdf", "Globex-Inc_IO-67890-2.pdf"),
    ("scanned_document_final.pdf", None),
    ("umbrella media io 13579.pdf", "Umbrella-Media_IO-13579-2.pdf"),
]


class TempFolderCase(unittest.TestCase):
    """Gives each test a fresh temporary folder, removed when the test ends."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = temp.name
        self.folder = os.path.join(self.root, "ios")
        os.mkdir(self.folder)
        # The undo log sits beside the folder, not in it, the way the front
        # ends keep it next to the script.
        self.log_path = os.path.join(self.root, core.UNDO_LOG_NAME)

    def make_files(self, names):
        # Each file holds its own name, so a test can tell which original
        # ended up under which new name.
        for name in names:
            with open(os.path.join(self.folder, name), "w", encoding="utf-8") as f:
                f.write(name)

    def files(self):
        """{file name: contents} for everything in the folder right now."""
        out = {}
        for name in sorted(os.listdir(self.folder)):
            with open(os.path.join(self.folder, name), encoding="utf-8") as f:
                out[name] = f.read()
        return out

    def planned(self, lookup=LOOKUP):
        """{old name: new name} from one plan_renames run (None = skipped)."""
        plan = core.plan_renames(self.folder, lookup)
        return {item.old_name: item.new_name for item in plan}


class TestExtractIoNumber(unittest.TestCase):
    def test_io_label_before_the_number(self):
        self.assertEqual(core.extract_io_number("IO 12345 Acme Corp.pdf"), "12345")
        self.assertEqual(core.extract_io_number("Globex IO#67890 (copy).pdf"), "67890")
        self.assertEqual(core.extract_io_number("Initech_IO_24680.pdf"), "24680")
        self.assertEqual(core.extract_io_number("IO24680 initech the agency.pdf"), "24680")

    def test_io_label_after_the_number(self):
        self.assertEqual(core.extract_io_number("initrode 99001 io.pdf"), "99001")
        # Two digits are too short for a bare number, so this one needs the label.
        self.assertEqual(core.extract_io_number("Hooli 42 IO.pdf"), "00042")

    def test_bare_number_without_a_label(self):
        self.assertEqual(
            core.extract_io_number("acme_insertionorder_12345_FINAL_v2.pdf"), "12345")
        self.assertEqual(core.extract_io_number("13579_UMBRELLA_FINAL.pdf"), "13579")
        # Here the IO is not next to the number, so only the bare number rule finds it.
        self.assertEqual(core.extract_io_number("12345-Acme-IO-signed.pdf"), "12345")

    def test_short_number_is_padded_when_labelled(self):
        self.assertEqual(core.extract_io_number("IO 42 Hooli.pdf"), "00042")

    def test_bare_number_needs_three_digits(self):
        # Without an IO label, 1 or 2 digits are a version or a copy number.
        self.assertIsNone(core.extract_io_number("contract_v2.pdf"))
        self.assertIsNone(core.extract_io_number("contract draft 2.pdf"))
        self.assertIsNone(core.extract_io_number("contract draft 12.pdf"))
        self.assertEqual(core.extract_io_number("contract draft 123.pdf"), "00123")

    def test_no_number_at_all(self):
        self.assertIsNone(core.extract_io_number("scanned_document_final.pdf"))

    def test_every_sample_name_gives_the_io_number_it_was_made_with(self):
        for name, number in generate_samples.SAMPLE_FILES:
            with self.subTest(name=name):
                self.assertEqual(core.extract_io_number(name), number or None)


class TestSlugifyCompany(unittest.TestCase):
    def test_spaces_become_hyphens(self):
        self.assertEqual(core.slugify_company("Acme Corporation"), "Acme-Corporation")

    def test_punctuation_is_dropped(self):
        self.assertEqual(core.slugify_company("Globex Inc."), "Globex-Inc")


class TestLoadLookup(TempFolderCase):
    def write_table(self, rows):
        path = os.path.join(self.root, "companies.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["io_number", "company"])
            writer.writerows(rows)
        return path

    def test_reads_the_sample_table(self):
        path = self.write_table(generate_samples.COMPANIES)
        self.assertEqual(core.load_lookup(path), LOOKUP)

    def test_pads_io_numbers_and_skips_half_empty_rows(self):
        path = self.write_table([
            (" 42 ", " Hooli "),
            ("", "No Number Inc"),
            ("777", ""),
        ])
        self.assertEqual(core.load_lookup(path), {"00042": "Hooli"})

    def test_a_missing_table_gives_an_empty_lookup(self):
        missing = os.path.join(self.root, "companies.csv")
        self.assertEqual(core.load_lookup(missing), {})


class TestResolveCompany(unittest.TestCase):
    def test_lookup_table_wins(self):
        self.assertEqual(
            core.resolve_company("12345", "IO 12345 Acme Corp.pdf", LOOKUP),
            "Acme Corporation")

    def test_guess_from_the_name_when_not_in_the_table(self):
        self.assertEqual(
            core.resolve_company("99001", "IO#99001 Initrode Partners v1.pdf", LOOKUP),
            "Initrode")
        self.assertEqual(
            core.resolve_company("13579", "umbrella media io 13579.pdf", {}),
            "Umbrella Media")

    def test_nothing_left_to_guess_from(self):
        self.assertIsNone(core.resolve_company("55555", "IO 55555.pdf", LOOKUP))


class TestBuildNewName(unittest.TestCase):
    def test_company_then_io_number(self):
        self.assertEqual(
            core.build_new_name("Acme Corporation", "12345", ".pdf"),
            "Acme-Corporation_IO-12345.pdf")
        self.assertEqual(
            core.build_new_name("Globex Inc.", "00042", ".pdf"),
            "Globex-Inc_IO-00042.pdf")


class TestPlanRenames(TempFolderCase):
    def test_the_readme_example(self):
        self.make_files([
            "IO 12345 Acme Corp.pdf",
            "acme_insertionorder_12345_FINAL_v2.pdf",
            "Globex IO#67890 (copy).pdf",
            "Initech_IO_24680.pdf",
            "scanned_document_final.pdf",
        ])
        self.assertEqual(self.planned(), {
            "IO 12345 Acme Corp.pdf": "Acme-Corporation_IO-12345.pdf",
            "acme_insertionorder_12345_FINAL_v2.pdf": "Acme-Corporation_IO-12345-2.pdf",
            "Globex IO#67890 (copy).pdf": "Globex-Inc_IO-67890.pdf",
            "Initech_IO_24680.pdf": "Initech-LLC_IO-24680.pdf",
            "scanned_document_final.pdf": None,
        })

    def test_every_sample_file(self):
        self.assertEqual(sorted(SAMPLE_NAMES), [old for old, _ in SAMPLE_PLAN])
        self.make_files(SAMPLE_NAMES)
        plan = core.plan_renames(self.folder, LOOKUP)
        self.assertEqual([(item.old_name, item.new_name) for item in plan], SAMPLE_PLAN)
        statuses = [item.status for item in plan]
        self.assertEqual(statuses.count(core.STATUS_OK), 11)
        self.assertEqual(statuses.count(core.STATUS_NO_IO), 1)

    def test_a_file_without_an_io_number_is_skipped(self):
        self.make_files(["scanned_document_final.pdf"])
        (item,) = core.plan_renames(self.folder, LOOKUP)
        self.assertEqual(item.status, core.STATUS_NO_IO)
        self.assertIsNone(item.new_name)
        self.assertIsNone(item.io_number)

    def test_a_file_without_a_company_is_skipped(self):
        self.make_files(["IO 55555.pdf"])
        (item,) = core.plan_renames(self.folder, LOOKUP)
        self.assertEqual(item.status, core.STATUS_NO_COMPANY)
        self.assertIsNone(item.new_name)
        self.assertEqual(item.io_number, "55555")

    def test_the_extension_is_lower_cased(self):
        self.make_files(["Initech_IO_24680.PDF"])
        self.assertEqual(self.planned(), {"Initech_IO_24680.PDF": "Initech-LLC_IO-24680.pdf"})

    def test_a_new_name_never_lands_on_a_file_already_in_the_folder(self):
        # The clean name is already taken by a file from an earlier run, and
        # the messy name sorts first, so it is planned before that file.
        self.make_files(["12345-Acme-IO-signed.pdf", "Acme-Corporation_IO-12345.pdf"])
        self.assertEqual(self.planned(), {
            "12345-Acme-IO-signed.pdf": "Acme-Corporation_IO-12345-2.pdf",
            "Acme-Corporation_IO-12345.pdf": None,
        })

    def test_the_suffix_counts_past_every_name_already_taken(self):
        self.make_files([
            "Acme-Corporation_IO-12345.pdf",
            "Acme-Corporation_IO-12345-2.pdf",
            "IO 12345 Acme Corp.pdf",
        ])
        self.assertEqual(self.planned(), {
            "Acme-Corporation_IO-12345.pdf": None,
            "Acme-Corporation_IO-12345-2.pdf": None,
            "IO 12345 Acme Corp.pdf": "Acme-Corporation_IO-12345-3.pdf",
        })


class TestSecondRun(TempFolderCase):
    def test_a_second_run_leaves_every_renamed_file_in_place(self):
        self.make_files(SAMPLE_NAMES)
        core.apply_renames(self.folder, core.plan_renames(self.folder, LOOKUP))
        after_first_run = self.files()

        plan = core.plan_renames(self.folder, LOOKUP)
        renames = [(item.old_name, item.new_name)
                   for item in plan if item.status == core.STATUS_OK]
        self.assertEqual(renames, [])
        statuses = [item.status for item in plan]
        self.assertEqual(statuses.count(core.STATUS_ALREADY_CLEAN), 11)
        self.assertEqual(statuses.count(core.STATUS_NO_IO), 1)
        self.assertEqual(core.apply_renames(self.folder, plan), [])
        self.assertEqual(self.files(), after_first_run)

    def test_a_clean_name_with_a_suffix_is_left_alone(self):
        self.make_files(["Globex-Inc_IO-67890-2.pdf"])
        self.assertEqual(self.planned(), {"Globex-Inc_IO-67890-2.pdf": None})
        (item,) = core.plan_renames(self.folder, LOOKUP)
        self.assertEqual(item.status, core.STATUS_ALREADY_CLEAN)


class TestApplyAndUndo(TempFolderCase):
    def test_apply_moves_each_file_to_its_planned_name(self):
        self.make_files(SAMPLE_NAMES)
        entries = core.apply_renames(self.folder, core.plan_renames(self.folder, LOOKUP))
        self.assertEqual(entries, [[new, old] for old, new in SAMPLE_PLAN if new])
        # Each renamed file still holds the name it started with, and the
        # skipped file has not moved.
        expected = {new: old for old, new in SAMPLE_PLAN if new}
        expected["scanned_document_final.pdf"] = "scanned_document_final.pdf"
        self.assertEqual(self.files(), expected)

    def test_undo_puts_every_name_back(self):
        self.make_files(SAMPLE_NAMES)
        entries = core.apply_renames(self.folder, core.plan_renames(self.folder, LOOKUP))
        core.write_undo_log(self.log_path, self.folder, entries)
        self.assertEqual(core.undo(self.log_path), 11)
        self.assertEqual(self.files(), {name: name for name in SAMPLE_NAMES})
        self.assertFalse(os.path.exists(self.log_path))

    def test_undo_skips_a_renamed_file_that_is_gone(self):
        self.make_files(SAMPLE_NAMES)
        entries = core.apply_renames(self.folder, core.plan_renames(self.folder, LOOKUP))
        core.write_undo_log(self.log_path, self.folder, entries)
        os.remove(os.path.join(self.folder, "Initrode_IO-99001.pdf"))
        self.assertEqual(core.undo(self.log_path), 10)
        self.assertNotIn("IO#99001 Initrode Partners v1.pdf", self.files())

    def test_undo_without_a_log_raises(self):
        with self.assertRaises(FileNotFoundError):
            core.undo(self.log_path)


if __name__ == "__main__":
    unittest.main()
