"""Read and validate individual departmental budget sheets.

Each department file is a small CSV with a `category,amount` header. The
department name is taken from the file name (for example `sales.csv` becomes
`Sales`). Column matching is case-insensitive and any extra columns are ignored.
"""

import csv
from pathlib import Path

REQUIRED_COLUMNS = ("category", "amount")


class BudgetFileError(Exception):
    """Raised when a department file cannot be read or is missing a column."""


def department_name_from_path(path):
    """Turn a file name into a display department name.

    'sales.csv' becomes 'Sales'. 'human_resources.csv' becomes 'Human Resources'.
    """
    stem = Path(path).stem
    words = stem.replace("_", " ").replace("-", " ").split()
    return " ".join(word.capitalize() for word in words)


def discover_department_files(directory):
    """Return the department CSV files in a directory, sorted by name."""
    folder = Path(directory)
    if not folder.is_dir():
        raise BudgetFileError(f"'{directory}' is not a directory.")
    return sorted(folder.glob("*.csv"))


def read_department_file(path):
    """Read one department CSV into raw category/amount string pairs.

    Returns a tuple of (department_name, rows), where each row is a dict with
    'category' and 'amount' string values. Raises BudgetFileError when a
    required column is missing.
    """
    path = Path(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        lookup = {name.strip().lower(): name for name in header}
        for column in REQUIRED_COLUMNS:
            if column not in lookup:
                found = ", ".join(header) if header else "(no columns)"
                raise BudgetFileError(
                    f"{path.name} is missing the required '{column}' column. "
                    f"Found: {found}."
                )
        category_key = lookup["category"]
        amount_key = lookup["amount"]
        rows = []
        for raw in reader:
            rows.append(
                {
                    "category": (raw.get(category_key) or "").strip(),
                    "amount": (raw.get(amount_key) or "").strip(),
                }
            )
    return department_name_from_path(path), rows
