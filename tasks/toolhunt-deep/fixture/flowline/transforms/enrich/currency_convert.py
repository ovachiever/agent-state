"""Enrichment transform: convert `amount` to cents"""


def currency_convert(rows):
    """Return new rows with a 'amount_cents' key added (convert `amount` to cents)."""
    enriched = []
    for row in rows:
        updated = dict(row)
        updated['amount_cents'] = int(round(float(row.get("amount", 0) or 0) * 100))
        enriched.append(updated)
    return enriched
