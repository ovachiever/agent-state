"""Sink: serialize processed rows as pretty JSON."""

from flowline.core.errors import SinkError


def write_json(rows, stream):
    """Write *rows* to *stream* as pretty JSON; returns the row count."""
    if stream is None:
        raise SinkError("pretty JSON sink needs an open stream")
    count = 0
    for row in rows:
        stream.write(__import__('json').dumps(row, sort_keys=True, indent=2) + "\n")
        count += 1
    return count
