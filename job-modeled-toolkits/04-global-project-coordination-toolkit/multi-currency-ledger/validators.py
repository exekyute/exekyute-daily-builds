"""Input validation for the Multi-Currency Consultant Ledger.

Each function returns a cleaned value or raises InvalidInvoice with a plain,
specific message. The loader and logic layers catch these so a single bad row is
reported and counted instead of crashing the whole run.
"""

from decimal import Decimal, InvalidOperation

from rates import EXCHANGE_RATES


class InvalidInvoice(Exception):
    """Raised when an invoice row fails a validation rule."""


def validate_invoice_id(raw):
    """An invoice id must be present and non-blank."""
    invoice_id = (raw or "").strip()
    if not invoice_id:
        raise InvalidInvoice("invoice id is blank")
    return invoice_id


def validate_currency(raw):
    """A currency code must exist in the editable exchange-rate dictionary."""
    currency = (raw or "").strip().upper()
    if not currency:
        raise InvalidInvoice("currency is blank")
    if currency not in EXCHANGE_RATES:
        raise InvalidInvoice(f"unknown currency '{currency}'")
    return currency


def validate_amount(raw):
    """An amount must be numeric and greater than zero."""
    text = (raw or "").strip()
    if not text:
        raise InvalidInvoice("amount is blank")
    try:
        amount = Decimal(text)
    except InvalidOperation:
        raise InvalidInvoice(f"amount '{text}' is not a number")
    if amount <= 0:
        raise InvalidInvoice(f"amount '{text}' is not greater than zero")
    return amount
