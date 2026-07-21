"""Enrichment transform: split a `codes` CSV field into a list"""


def expand_codes(rows):
    """Return new rows with a 'code_list' key added (split a `codes` CSV field into a list)."""
    enriched = []
    for row in rows:
        updated = dict(row)
        updated['code_list'] = str(row.get("codes", "")).split(",") if row.get("codes") else []
        enriched.append(updated)
    return enriched
