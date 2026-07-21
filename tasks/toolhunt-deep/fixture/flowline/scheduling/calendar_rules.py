"""Business-calendar rules layered on top of cron schedules."""

WEEKEND = (5, 6)


def is_business_day(weekday_index):
    """Monday=0 ... Sunday=6; weekends are not business days."""
    return weekday_index not in WEEKEND


def next_business_day(weekday_index):
    """Index of the next business day after *weekday_index*."""
    candidate = (weekday_index + 1) % 7
    while not is_business_day(candidate):
        candidate = (candidate + 1) % 7
    return candidate
