"""Monthly rollups assembled from the weekly digests."""


def month_header(year, month):
    """Stable section header for a monthly report."""
    return f"== {year:04d}-{month:02d} =="


def combine_weeks(weekly_lines):
    """Join weekly digest lines into one monthly block."""
    return "\n".join(line for line in weekly_lines if line)
