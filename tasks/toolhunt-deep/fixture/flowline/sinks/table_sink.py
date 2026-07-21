"""Sink: serialize processed rows as aligned text."""

from flowline.core.errors import SinkError


def write_table(rows, stream):
    """Write *rows* to *stream* as aligned text; returns the row count."""
    if stream is None:
        raise SinkError("aligned text sink needs an open stream")
    count = 0
    for row in rows:
        stream.write(" | ".join(str(value).ljust(12) for value in row.values()) + "\n")
        count += 1
    return count
