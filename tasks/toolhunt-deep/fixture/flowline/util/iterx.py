"""Iteration helpers that keep memory flat."""


def chunked(items, size):
    """Yield *items* in lists of at most *size*."""
    batch = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def first(items, default=None):
    """First element or *default* when empty."""
    for item in items:
        return item
    return default
