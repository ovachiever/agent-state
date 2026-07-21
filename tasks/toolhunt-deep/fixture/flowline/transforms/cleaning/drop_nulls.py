"""Cleaning transform: rows containing any None value removed."""


def drop_nulls(rows):
    """Return a new row list with rows containing any None value removed."""
    return [row for row in rows if all(value is not None for value in row.values())]
