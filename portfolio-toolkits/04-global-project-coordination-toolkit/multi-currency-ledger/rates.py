"""Exchange-rate configuration for the Multi-Currency Consultant Ledger.

The base currency is the single currency every invoice is converted into before
it is reconciled against the grant total. Each rate is the number of base-currency
units that one unit of the foreign currency is worth.

    base_amount = foreign_amount * EXCHANGE_RATES[foreign_currency]

These rates are illustrative and meant to be edited by hand. Replace them with the
rates your finance team publishes for the reconciliation period. All values are
Decimal so the conversion math stays exact.
"""

from decimal import Decimal

BASE_CURRENCY = "USD"

# Units of base currency (USD) per 1 unit of the foreign currency.
EXCHANGE_RATES = {
    "USD": Decimal("1"),
    "EUR": Decimal("1.08"),
    "GBP": Decimal("1.27"),
    "JPY": Decimal("0.0067"),
}
