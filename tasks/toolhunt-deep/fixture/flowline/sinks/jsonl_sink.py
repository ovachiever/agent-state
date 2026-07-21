"""Sink: serialize processed rows as JSON lines."""

from flowline.core.errors import SinkError


def write_jsonl(rows, stream):
    """Write *rows* to *stream* as JSON lines; returns the row count."""
    if stream is None:
        raise SinkError("JSON lines sink needs an open stream")
    count = 0
    for row in rows:
        stream.write(__import__('json').dumps(row, sort_keys=True) + "\n")
        count += 1
    return count
