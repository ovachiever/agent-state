"""Cleaning transform: header keys slug-cased (spaces to underscores, lower)."""


def rename_headers(rows):
    """Return a new row list with header keys slug-cased (spaces to underscores, lower)."""
    return [
        {str(key).strip().lower().replace(" ", "_"): value for key, value in row.items()}
        for row in rows
    ]
