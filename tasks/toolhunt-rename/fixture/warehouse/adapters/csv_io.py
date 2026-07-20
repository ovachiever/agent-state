"""CSV import for SKU master data."""

import csv

from warehouse.core.models import Sku


def load_skus(path):
    skus = []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            skus.append(
                Sku(
                    sku_id=row["sku_id"],
                    description=row["description"],
                    daily_demand=float(row["daily_demand"]),
                    lead_time_days=float(row["lead_time_days"]),
                    safety_stock=float(row["safety_stock"]),
                )
            )
    return skus
