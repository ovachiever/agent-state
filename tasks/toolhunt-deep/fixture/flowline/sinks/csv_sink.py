"""Sink: serialize processed rows as CSV."""

from flowline.core.errors import SinkError


def write_csv(rows, stream):
    """Write *rows* to *stream* as CSV; returns the row count."""
    if stream is None:
        raise SinkError("CSV sink needs an open stream")
    count = 0
    for row in rows:
        stream.write(",".join(str(value) for value in row.values()) + "\n")
        count += 1
    return count
