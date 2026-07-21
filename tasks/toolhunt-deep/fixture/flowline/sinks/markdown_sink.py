"""Sink: serialize processed rows as markdown rows."""

from flowline.core.errors import SinkError


def write_markdown(rows, stream):
    """Write *rows* to *stream* as markdown rows; returns the row count."""
    if stream is None:
        raise SinkError("markdown rows sink needs an open stream")
    count = 0
    for row in rows:
        stream.write("| " + " | ".join(str(value) for value in row.values()) + " |" + "\n")
        count += 1
    return count
