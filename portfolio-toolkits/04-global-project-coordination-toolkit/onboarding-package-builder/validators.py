"""Input validation for the Contractor Onboarding Package Builder.

Each function returns a cleaned value or raises InvalidRequest with a plain,
specific message. The CLI and logic layers catch these so a bad request is
reported clearly instead of crashing or building an empty folder.
"""

import re

from requirements import REGION_DOCUMENTS, ROLE_DOCUMENTS, known_regions, known_roles


class InvalidRequest(Exception):
    """Raised when a region, role, or contractor name fails validation."""


def validate_region(raw):
    """A region must be present and one of the supported codes."""
    region = (raw or "").strip().upper()
    if not region:
        raise InvalidRequest("region is blank")
    if region not in REGION_DOCUMENTS:
        raise InvalidRequest(
            f"unknown region '{region}'. Supported: {', '.join(known_regions())}"
        )
    return region


def validate_role(raw):
    """A role must be present and one of the supported codes."""
    role = (raw or "").strip().lower()
    if not role:
        raise InvalidRequest("role is blank")
    if role not in ROLE_DOCUMENTS:
        raise InvalidRequest(
            f"unknown role '{role}'. Supported: {', '.join(known_roles())}"
        )
    return role


def slugify(name):
    """Turn a contractor name into a lowercase, hyphenated folder-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug


def validate_name(raw):
    """A contractor name must be present and yield a non-empty slug."""
    name = (raw or "").strip()
    if not name:
        raise InvalidRequest("contractor name is blank")
    slug = slugify(name)
    if not slug:
        raise InvalidRequest(
            f"contractor name '{name}' has no letters or numbers to build a folder name"
        )
    return name, slug
