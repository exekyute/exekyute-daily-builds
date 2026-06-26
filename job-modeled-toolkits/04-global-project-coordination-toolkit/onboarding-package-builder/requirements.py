"""Onboarding rules for the Contractor Onboarding Package Builder.

These are plain, editable rule tables. Every contractor receives the base
documents. On top of that they receive the documents required for their region
and the documents required for their role. The required document set for a
contractor is the base set plus the region set plus the role set.

Each value is the file name of a template in the master `templates/` directory.
To change what a region or role requires, edit the lists below.
"""

# Documents every contractor receives, regardless of region or role.
BASE_DOCUMENTS = [
    "code-of-conduct.md",
    "data-privacy-agreement.md",
    "bank-details-form.md",
    "tax-form.md",
]

# Extra documents required by region.
REGION_DOCUMENTS = {
    "EMEA": ["regional-compliance-emea.md", "gdpr-data-notice.md"],
    "AMER": ["regional-compliance-amer.md"],
    "APAC": ["regional-compliance-apac.md"],
}

# Extra documents required by role.
ROLE_DOCUMENTS = {
    "consultant": ["consultant-sow-template.md"],
    "translator": ["translator-nda.md"],
    "field-officer": ["safeguarding-policy.md", "field-safety-briefing.md"],
}


def known_regions():
    """Return the sorted list of supported region codes."""
    return sorted(REGION_DOCUMENTS)


def known_roles():
    """Return the sorted list of supported role codes."""
    return sorted(ROLE_DOCUMENTS)
