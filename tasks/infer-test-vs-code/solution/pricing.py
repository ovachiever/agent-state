"""Pricing helpers."""


def apply_discount(price, pct):
    """Return the price after applying a percentage discount.

    apply_discount(200.0, 25) -> 150.0  (25% off the price)
    pct is a percentage in [0, 100]; raises ValueError outside that range.
    Result is rounded to 2 decimal places.
    """
    if pct < 0 or pct > 100:
        raise ValueError("pct must be between 0 and 100")
    return round(price * (1 - pct / 100), 2)
