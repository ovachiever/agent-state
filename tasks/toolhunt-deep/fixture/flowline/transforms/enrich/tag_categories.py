"""Enrichment transform: size category from a `units` field"""


def tag_categories(rows):
    """Return new rows with a 'category' key added (size category from a `units` field)."""
    enriched = []
    for row in rows:
        updated = dict(row)
        updated['category'] = "bulk" if float(row.get("units", 0) or 0) >= 100 else "retail"
        enriched.append(updated)
    return enriched
