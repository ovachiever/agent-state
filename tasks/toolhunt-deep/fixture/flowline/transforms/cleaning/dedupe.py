"""Cleaning transform: exact duplicate rows collapsed, first occurrence wins."""


def dedupe(rows):
    """Return a new row list with exact duplicate rows collapsed, first occurrence wins."""
    seen = set()
    unique = []
    for row in rows:
        key = tuple(sorted(row.items()))
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique
