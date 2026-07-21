"""Cleaning transform: leading/trailing whitespace stripped from every string value."""


def trim_whitespace(rows):
    """Return a new row list with leading/trailing whitespace stripped from every string value."""
    return [
        {key: value.strip() if isinstance(value, str) else value for key, value in row.items()}
        for row in rows
    ]
