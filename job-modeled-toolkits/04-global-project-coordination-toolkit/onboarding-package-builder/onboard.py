"""Command-line entry point for the Contractor Onboarding Package Builder.

Asks for (or accepts as arguments) a contractor's region, role, and name, resolves
the required compliance documents from the rule tables, copies them from the master
templates directory into a personalized vendor folder, and prints a manifest of what
was copied and where.

Example
-------
    python onboard.py --region EMEA --role consultant --name "Amara Okafor"
    python onboard.py            (prompts for region, role, and name)
"""

import argparse
import sys

from builder import build_package
from requirements import known_regions, known_roles
from validators import InvalidRequest, validate_name, validate_region, validate_role


def prompt_for_request():
    """Ask for region, role, and name at the prompt, re-asking on bad input."""
    region = _prompt(
        f"Region ({', '.join(known_regions())}): ", validate_region
    )
    role = _prompt(
        f"Role ({', '.join(known_roles())}): ", validate_role
    )
    name = _prompt("Contractor name: ", lambda value: validate_name(value)[0])
    return region, role, name


def _prompt(label, validator):
    """Prompt until the validator accepts the input, then return the clean value."""
    while True:
        try:
            return validator(input(label))
        except InvalidRequest as error:
            print(f"  {error}")


def print_manifest(result):
    """Print the build manifest in plain language."""
    print(
        f"Contractor: {result.contractor} | Region: {result.region} | "
        f"Role: {result.role}"
    )
    print(f"Folder: {result.target_dir}")
    print()

    if result.status == "exists":
        print(
            "This contractor folder already exists. Nothing was copied, so existing "
            "files are left untouched. Remove the folder to rebuild it."
        )
        print(f"Required documents on record: {len(result.required)}")
        return

    print("| Document | Status |")
    print("| --- | --- |")
    for document in result.required:
        status = "copied" if document in result.copied else "MISSING TEMPLATE"
        print(f"| {document} | {status} |")
    print()

    print(
        f"Copied {len(result.copied)} of {len(result.required)} required document(s)."
    )
    if result.missing_templates:
        print(
            "Missing from the master templates directory: "
            + ", ".join(result.missing_templates)
        )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a contractor's regional onboarding document package."
    )
    parser.add_argument("--region", help=f"one of: {', '.join(known_regions())}")
    parser.add_argument("--role", help=f"one of: {', '.join(known_roles())}")
    parser.add_argument("--name", help="contractor full name")
    args = parser.parse_args(argv)

    if args.region and args.role and args.name:
        region, role, name = args.region, args.role, args.name
    elif any([args.region, args.role, args.name]):
        print(
            "Error: provide all of --region, --role, and --name, "
            "or none of them to be prompted.",
            file=sys.stderr,
        )
        return 1
    else:
        region, role, name = prompt_for_request()

    try:
        result = build_package(region, role, name)
    except InvalidRequest as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    print_manifest(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
