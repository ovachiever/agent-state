"""Cleaning transform: None values replaced by empty strings."""


def fill_defaults(rows):
    """Return a new row list with None values replaced by empty strings."""
    return [
        {key: "" if value is None else value for key, value in row.items()}
        for row in rows
    ]
