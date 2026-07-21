"""Minimal five-field cron expression parsing."""

FIELDS = ("minute", "hour", "day", "month", "weekday")


def parse_cron(expression):
    """Split a cron expression into a field dict; `*` means every."""
    parts = expression.split()
    if len(parts) != len(FIELDS):
        raise ValueError(f"expected {len(FIELDS)} cron fields, got {len(parts)}")
    return dict(zip(FIELDS, parts))


def is_wildcard(field_value):
    """True when a cron field matches every slot."""
    return field_value in ("*", "*/1")
