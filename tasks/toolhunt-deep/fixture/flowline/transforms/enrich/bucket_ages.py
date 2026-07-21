"""Enrichment transform: coarse age bucket from an `age` field"""


def bucket_ages(rows):
    """Return new rows with a 'age_bucket' key added (coarse age bucket from an `age` field)."""
    enriched = []
    for row in rows:
        updated = dict(row)
        updated['age_bucket'] = "minor" if float(row.get("age", 0) or 0) < 18 else "adult"
        enriched.append(updated)
    return enriched
