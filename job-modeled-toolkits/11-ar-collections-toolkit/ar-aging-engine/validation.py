"""Row parsing and validation for the AR Aging and Late-Fee Engine.

This module turns raw CSV fields into Invoice objects and rejects anything that
does not meet the rules. It holds no business math (no aging, no fees) and no
command-line handling, so the rules can be tested on their own.

A row that fails any rule raises RowError with a plain-language reason. The CLI
catches that, records the reason, and keeps processing the remaining rows.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from aging import Invoice

# The exact header the input CSV must start with.
INPUT_HEADER = ["invoice_number", "customer", "issue_date", "due_date", "amount"]


class RowError(Exception):
    """Raised when a CSV row fails a validation rule."""


def parse_date(label, value):
    """Parse a YYYY-MM-DD string into a date, or raise RowError."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise RowError(f"{label} is not a valid YYYY-MM-DD date: {value!r}")


def parse_amount(value):
    """Parse a positive money string into a Decimal, or raise RowError."""
    try:
        amount = Decimal(value)
    except InvalidOperation:
        raise RowError(f"amount is not a number: {value!r}")
    if amount <= 0:
        raise RowError(f"amount must be greater than 0: {value!r}")
    return amount


def validate_header(header):
    """Confirm the CSV header matches the expected columns, or raise RowError."""
    cleaned = [field.strip() for field in header]
    if cleaned != INPUT_HEADER:
        raise RowError(
            "unexpected header: expected "
            f"{','.join(INPUT_HEADER)} but found {','.join(cleaned)}"
        )


def validate_row(fields, seen_numbers):
    """Validate one raw row and return an Invoice, or raise RowError.

    ``seen_numbers`` is a set of invoice numbers already accepted; it is used to
    reject duplicates. On success the new invoice number is added to the set.
    """
    if len(fields) != len(INPUT_HEADER):
        raise RowError(f"expected {len(INPUT_HEADER)} fields, got {len(fields)}")

    invoice_number, customer, issue_s, due_s, amount_s = (f.strip() for f in fields)

    if not invoice_number:
        raise RowError("missing invoice_number")
    if invoice_number in seen_numbers:
        raise RowError(f"duplicate invoice_number: {invoice_number}")
    if not customer:
        raise RowError("missing customer")

    issue_date = parse_date("issue_date", issue_s)
    due_date = parse_date("due_date", due_s)
    if due_date < issue_date:
        raise RowError("due_date is before issue_date")

    amount = parse_amount(amount_s)

    seen_numbers.add(invoice_number)
    return Invoice(
        invoice_number=invoice_number,
        customer=customer,
        issue_date=issue_date,
        due_date=due_date,
        amount=amount,
    )
