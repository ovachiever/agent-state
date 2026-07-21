"""Enrichment transform: coarse region from a `country` field"""


def geo_lookup(rows):
    """Return new rows with a 'region' key added (coarse region from a `country` field)."""
    enriched = []
    for row in rows:
        updated = dict(row)
        updated['region'] = "emea" if str(row.get("country", "")).upper() in ("DE", "FR", "GB") else "other"
        enriched.append(updated)
    return enriched
