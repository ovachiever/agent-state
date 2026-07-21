"""Enrichment transform: fraction of non-empty fields"""


def score_quality(rows):
    """Return new rows with a 'quality' key added (fraction of non-empty fields)."""
    enriched = []
    for row in rows:
        updated = dict(row)
        updated['quality'] = round(sum(1 for value in row.values() if value not in (None, "")) / max(1, len(row)), 3)
        enriched.append(updated)
    return enriched
