"""Core logic for the Contractor Onboarding Package Builder.

This module resolves the required document set for a contractor from the rule
tables, then copies each template from the master directory into a personalized
vendor folder. It never overwrites an existing folder, and it reports any required
template that is missing from the master directory instead of crashing.
"""

import os
import shutil

from requirements import BASE_DOCUMENTS, REGION_DOCUMENTS, ROLE_DOCUMENTS
from validators import validate_name, validate_region, validate_role

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATES_DIR = os.path.join(HERE, "templates")
DEFAULT_OUTPUT_DIR = os.path.join(HERE, "output")


def resolve_documents(region, role):
    """Return the ordered, de-duplicated list of documents a contractor needs.

    The region and role are validated and normalized here, so an unknown region
    or role raises InvalidRequest before any folder is touched.
    """
    region = validate_region(region)
    role = validate_role(role)

    ordered = []
    for name in BASE_DOCUMENTS + REGION_DOCUMENTS[region] + ROLE_DOCUMENTS[role]:
        if name not in ordered:
            ordered.append(name)
    return ordered


class PackageResult:
    """The manifest of a single onboarding package build."""

    def __init__(self, contractor, slug, region, role, target_dir):
        self.contractor = contractor
        self.slug = slug
        self.region = region
        self.role = role
        self.target_dir = target_dir
        self.required = []
        self.copied = []
        self.missing_templates = []
        self.status = "created"  # created | exists

    @property
    def created(self):
        return self.status == "created"


def build_package(region, role, contractor_name,
                  templates_dir=DEFAULT_TEMPLATES_DIR,
                  output_dir=DEFAULT_OUTPUT_DIR):
    """Build one contractor's onboarding folder and return a manifest.

    If the contractor folder already exists, nothing is copied and the manifest
    status is 'exists'. A required template that is not present in the master
    directory is recorded in missing_templates and does not stop the build.
    """
    name, slug = validate_name(contractor_name)
    region = validate_region(region)
    role = validate_role(role)

    target_dir = os.path.join(output_dir, slug)
    result = PackageResult(name, slug, region, role, target_dir)
    result.required = resolve_documents(region, role)

    if os.path.isdir(target_dir):
        result.status = "exists"
        return result

    os.makedirs(target_dir, exist_ok=True)
    for document in result.required:
        source = os.path.join(templates_dir, document)
        if not os.path.isfile(source):
            result.missing_templates.append(document)
            continue
        shutil.copy2(source, os.path.join(target_dir, document))
        result.copied.append(document)

    return result
