"""Cleaning transform: currency symbols stripped from string values."""


def strip_currency(rows):
    """Return a new row list with currency symbols stripped from string values."""
    symbols = "$€£¥"
    return [
        {key: value.strip(symbols) if isinstance(value, str) else value for key, value in row.items()}
        for row in rows
    ]
