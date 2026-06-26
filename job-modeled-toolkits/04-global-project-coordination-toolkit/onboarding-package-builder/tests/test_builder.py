"""Unit tests for the Contractor Onboarding Package Builder logic and validation."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from builder import build_package, resolve_documents  # noqa: E402
from validators import (  # noqa: E402
    InvalidRequest,
    slugify,
    validate_name,
    validate_region,
    validate_role,
)

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(os.path.dirname(HERE), "templates")


class ValidationTests(unittest.TestCase):
    def test_region_is_uppercased(self):
        self.assertEqual(validate_region("emea"), "EMEA")

    def test_unknown_region_rejected(self):
        with self.assertRaises(InvalidRequest):
            validate_region("MARS")

    def test_unknown_role_rejected(self):
        with self.assertRaises(InvalidRequest):
            validate_role("astronaut")

    def test_blank_name_rejected(self):
        with self.assertRaises(InvalidRequest):
            validate_name("   ")

    def test_symbols_only_name_rejected(self):
        with self.assertRaises(InvalidRequest):
            validate_name("!!!")

    def test_slugify(self):
        self.assertEqual(slugify("Amara Okafor"), "amara-okafor")
        self.assertEqual(slugify("  O'Brien,  Sean "), "o-brien-sean")


class ResolveDocumentsTests(unittest.TestCase):
    def test_emea_consultant_full_set(self):
        docs = resolve_documents("EMEA", "consultant")
        self.assertEqual(
            docs,
            [
                "code-of-conduct.md",
                "data-privacy-agreement.md",
                "bank-details-form.md",
                "tax-form.md",
                "regional-compliance-emea.md",
                "gdpr-data-notice.md",
                "consultant-sow-template.md",
            ],
        )

    def test_no_duplicate_documents(self):
        docs = resolve_documents("APAC", "field-officer")
        self.assertEqual(len(docs), len(set(docs)))


class BuildPackageTests(unittest.TestCase):
    def test_clean_build_copies_all(self):
        with tempfile.TemporaryDirectory() as out:
            result = build_package(
                "EMEA", "consultant", "Amara Okafor",
                templates_dir=TEMPLATES_DIR, output_dir=out,
            )
            self.assertEqual(result.status, "created")
            self.assertEqual(len(result.missing_templates), 0)
            self.assertEqual(len(result.copied), len(result.required))
            for document in result.required:
                self.assertTrue(
                    os.path.isfile(os.path.join(out, "amara-okafor", document))
                )

    def test_missing_template_reported_not_fatal(self):
        with tempfile.TemporaryDirectory() as out:
            result = build_package(
                "APAC", "field-officer", "Kenji Tanaka",
                templates_dir=TEMPLATES_DIR, output_dir=out,
            )
            self.assertEqual(result.status, "created")
            self.assertIn("field-safety-briefing.md", result.missing_templates)
            self.assertIn("safeguarding-policy.md", result.copied)

    def test_existing_folder_not_overwritten(self):
        with tempfile.TemporaryDirectory() as out:
            first = build_package(
                "EMEA", "consultant", "Amara Okafor",
                templates_dir=TEMPLATES_DIR, output_dir=out,
            )
            self.assertEqual(first.status, "created")
            second = build_package(
                "EMEA", "consultant", "Amara Okafor",
                templates_dir=TEMPLATES_DIR, output_dir=out,
            )
            self.assertEqual(second.status, "exists")
            self.assertEqual(len(second.copied), 0)

    def test_unknown_region_raises_before_build(self):
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaises(InvalidRequest):
                build_package(
                    "MARS", "consultant", "Amara Okafor",
                    templates_dir=TEMPLATES_DIR, output_dir=out,
                )


if __name__ == "__main__":
    unittest.main()
