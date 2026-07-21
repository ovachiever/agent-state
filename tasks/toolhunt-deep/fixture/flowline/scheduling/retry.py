"""Bounded retry helper for flaky deliveries."""


def with_retry(func, attempts=3):
    """Call *func* until it stops raising, at most *attempts* times."""
    last_error = None
    for _ in range(max(1, attempts)):
        try:
            return func()
        except Exception as error:  # noqa: BLE001, deliberate catch-all
            last_error = error
    raise last_error
