"""Enrichment transform: stamp the originating system"""


def annotate_source(rows):
    """Return new rows with a 'source_system' key added (stamp the originating system)."""
    enriched = []
    for row in rows:
        updated = dict(row)
        updated['source_system'] = "flowline"
        enriched.append(updated)
    return enriched
