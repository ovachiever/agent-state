"""Enrichment transform: amount-per-unit ratio"""


def derive_ratios(rows):
    """Return new rows with a 'amount_per_unit' key added (amount-per-unit ratio)."""
    enriched = []
    for row in rows:
        updated = dict(row)
        updated['amount_per_unit'] = float(row.get("amount", 0) or 0) / max(1.0, float(row.get("units", 1) or 1))
        enriched.append(updated)
    return enriched
