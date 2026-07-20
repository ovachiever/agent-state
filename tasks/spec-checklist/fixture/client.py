"""Meter ingest client. See README.md for the full specification of each function."""


def parse_reading(line):
    """See README section 1."""
    raise NotImplementedError


def validate_id(meter_id):
    """See README section 2."""
    raise NotImplementedError


def batch_stats(readings):
    """See README section 3."""
    raise NotImplementedError


def render_row(reading):
    """See README section 4."""
    raise NotImplementedError


def chunk(items, size):
    """See README section 5."""
    raise NotImplementedError


def dedupe_latest(readings):
    """See README section 6."""
    raise NotImplementedError


def parse_window(s):
    """See README section 7."""
    raise NotImplementedError


def to_csv(readings):
    """See README section 8."""
    raise NotImplementedError
