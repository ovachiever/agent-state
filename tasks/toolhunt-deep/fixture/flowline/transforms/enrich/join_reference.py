"""Enrichment transform: attach the static plan tier"""


def join_reference(rows):
    """Return new rows with a 'plan_tier' key added (attach the static plan tier)."""
    enriched = []
    for row in rows:
        updated = dict(row)
        updated['plan_tier'] = {"p1": "gold", "p2": "silver"}.get(str(row.get("plan", "")), "bronze")
        enriched.append(updated)
    return enriched
