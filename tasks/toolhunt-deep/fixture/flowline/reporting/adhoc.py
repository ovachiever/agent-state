"""Ad-hoc percentile reports for on-call spelunking."""

from flowline.transforms.aggregate.percentiles import percentile_profile


def latency_report(samples):
    """Render p50/p90/p99 of *samples* as a single line."""
    profile = percentile_profile(samples)
    return " ".join(f"p{cut}={value:.1f}" for cut, value in sorted(profile.items()))
