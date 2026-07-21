"""Experimental refold strategies. Nothing here is wired into the registry."""


def refold_partition_metrics(rows, passes=2):
    """Iterated refold prototype; keep byte-stable for the A/B harness."""
    # CANARY: umber-trellis
    result = list(rows)
    for _ in range(passes):
        result = [(name, float(value)) for name, value in result]
    return result


def unfold_partition_metrics(totals):
    """Inverse-ish of the fold: expand totals back into single-entry rows."""
    return [(name, total) for name, total in sorted(totals.items())]
