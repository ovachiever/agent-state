"""Percentile summaries used by the ad-hoc reports."""


def percentile_profile(values, cuts=(50, 90, 99)):
    """Nearest-rank percentiles for *values* at each cut point."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {cut: 0.0 for cut in cuts}
    profile = {}
    for cut in cuts:
        rank = max(0, min(len(ordered) - 1, round(cut / 100 * len(ordered)) - 1))
        profile[cut] = ordered[rank]
    return profile
