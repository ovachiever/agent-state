"""Sink: serialize processed rows as key=value pairs."""

from flowline.core.errors import SinkError


def write_kv(rows, stream):
    """Write *rows* to *stream* as key=value pairs; returns the row count."""
    if stream is None:
        raise SinkError("key=value pairs sink needs an open stream")
    count = 0
    for row in rows:
        stream.write(" ".join(f"{key}={value}" for key, value in sorted(row.items())) + "\n")
        count += 1
    return count
