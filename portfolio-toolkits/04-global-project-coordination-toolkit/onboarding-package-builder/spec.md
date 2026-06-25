# Spec: Contractor Onboarding Package Builder

## Purpose

Build a personalized onboarding folder for an international contractor. Given a contractor's region
and role, the tool resolves the required compliance documents from editable rule tables and copies
those templates from a master directory into a vendor folder named after the contractor. This models
managing contractor onboarding and making sure the right regional compliance documents are collected
and filed.

## Inputs

- `--region`: the contractor's region code (one of `AMER`, `APAC`, `EMEA`).
- `--role`: the contractor's role (one of `consultant`, `field-officer`, `translator`).
- `--name`: the contractor's full name, used to name the vendor folder.

Provide all three arguments, or provide none and the tool prompts for each one. The rule tables and
the supported regions and roles live in `requirements.py`.

## Validation rules

- The region must be one of the supported codes. An unknown region is rejected with the list of
  supported codes.
- The role must be one of the supported roles. An unknown role is rejected with the list of supported
  roles.
- The contractor name must be non-blank and must contain at least one letter or number, so it can be
  turned into a folder-safe slug. A name of only symbols is rejected.

## Logic

1. Validate and normalize the region, role, and name. The name becomes a lowercase hyphenated slug
   (for example `Amara Okafor` becomes `amara-okafor`).
2. Resolve the required documents as base documents plus region documents plus role documents, in
   that order, with duplicates removed.
3. If the vendor folder already exists, stop and report it. Nothing is copied, so existing files are
   never overwritten.
4. Otherwise create the folder and copy each required template from the master directory into it.
5. If a required template is not present in the master directory, record it as missing and continue.
   One missing template never stops the rest of the package from being built.

## Outputs

- A manifest printed to the screen: contractor, region, role, and the target folder path.
- A markdown table listing every required document and whether it was copied or missing.
- A summary line counting how many of the required documents were copied.
- A populated vendor folder under `output/<contractor-slug>/`.

## Edge cases

- An unknown region or role (rejected before any folder is created).
- A name with no letters or numbers (rejected, no empty folder created).
- A required template missing from the master directory (reported, build continues).
- Re-running for a contractor whose folder already exists (reported, nothing overwritten).

## Sample data design

The master `templates/` directory holds synthetic placeholder documents. The rule tables in
`requirements.py` are seeded so the documented runs exercise every path:

- **EMEA + consultant** resolves a full set of seven documents, all present, copied cleanly.
- **APAC + field-officer** resolves seven documents, but `field-safety-briefing.md` is deliberately
  not in the master directory, so it is reported as a missing template while the other six copy.
- **Re-running EMEA + consultant** for the same contractor reports the existing folder and copies
  nothing.
- **An unknown region** such as `MARS` is rejected with the list of supported regions.

The `output/` folder ships empty (only a `.gitkeep`). Vendor folders are generated at run time and are
not committed.
