"""Sink: serialize processed rows as SQL inserts."""

from flowline.core.errors import SinkError


def write_sql_inserts(rows, stream):
    """Write *rows* to *stream* as SQL inserts; returns the row count."""
    if stream is None:
        raise SinkError("SQL inserts sink needs an open stream")
    count = 0
    for row in rows:
        stream.write("INSERT INTO rows VALUES (" + ", ".join(repr(str(value)) for value in row.values()) + ");" + "\n")
        count += 1
    return count
