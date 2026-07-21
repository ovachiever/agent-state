"""Cleaning transform: string values lower-cased for stable joins."""


def normalize_case(rows):
    """Return a new row list with string values lower-cased for stable joins."""
    return [
        {key: value.lower() if isinstance(value, str) else value for key, value in row.items()}
        for row in rows
    ]
