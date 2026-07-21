"""Deterministic backoff schedules (no jitter: tests need stable timing)."""


def exponential_backoff(attempt, base_seconds=1.0, cap_seconds=60.0):
    """Delay before retry *attempt* (0-indexed), capped at *cap_seconds*."""
    return min(cap_seconds, base_seconds * (2 ** attempt))


def backoff_schedule(attempts, base_seconds=1.0):
    """The full delay sequence for *attempts* retries."""
    return [exponential_backoff(i, base_seconds) for i in range(attempts)]
