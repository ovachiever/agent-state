"""Enrichment transform: stable short id from the row repr"""


def hash_ids(rows):
    """Return new rows with a 'row_id' key added (stable short id from the row repr)."""
    enriched = []
    for row in rows:
        updated = dict(row)
        updated['row_id'] = format(abs(hash(tuple(sorted(str(item) for item in row.items())))) % 10**8, "08d")
        enriched.append(updated)
    return enriched
