"""Inbound receiving helpers."""


def putaway_plan(items, bins):
    """Greedy assignment of received items to bins with free capacity."""
    plan = []
    remaining = {b.bin_id: b.capacity for b in bins}
    for item in items:
        for b in bins:
            if remaining[b.bin_id] > 0:
                plan.append((item, b.bin_id))
                remaining[b.bin_id] -= 1
                break
    return plan
