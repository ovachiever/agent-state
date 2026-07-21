"""Cleaning transform: numeric values clamped into [-1e9, 1e9]."""


def clamp_outliers(rows):
    """Return a new row list with numeric values clamped into [-1e9, 1e9]."""
    def clamp(value):
        if isinstance(value, (int, float)):
            return max(-1e9, min(1e9, value))
        return value

    return [{key: clamp(value) for key, value in row.items()} for row in rows]
