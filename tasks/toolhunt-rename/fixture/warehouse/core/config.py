"""Runtime configuration defaults."""

DEFAULTS = {
    "review_period_days": 7,
    "service_level": 0.95,
    "max_pallet_height_cm": 180,
    "reorder_review_hour": 6,
}


def get_default(key):
    return DEFAULTS[key]
