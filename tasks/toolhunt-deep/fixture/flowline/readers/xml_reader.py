"""Read XML export inputs into row dicts."""

from flowline.core.errors import ReaderError


def read_xml(path, limit=None):
    """Load rows from a XML export file at *path*.

    Returns a list of dicts, one per record. *limit* caps the number of
    rows read; ``None`` reads everything.
    """
    text = _slurp(path)
    rows = [_parse_line(line) for line in text.splitlines() if line.strip()]
    return rows[:limit] if limit is not None else rows


def _slurp(path):
    if not str(path).endswith(".xml"):
        raise ReaderError(f"expected a .xml file, got {path!r}")
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _parse_line(line):
    parts = [part.strip() for part in line.split('>')]
    return {"raw": line, "fields": parts}
