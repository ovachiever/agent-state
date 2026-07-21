"""Cleaning transform: numeric-looking strings coerced to floats."""


def coerce_types(rows):
    """Return a new row list with numeric-looking strings coerced to floats."""
    def coerce(value):
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return value
        return value

    return [{key: coerce(value) for key, value in row.items()} for row in rows]
