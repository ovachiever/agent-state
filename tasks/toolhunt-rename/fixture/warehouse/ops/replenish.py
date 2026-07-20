"""Replenishment math for continuous-review inventory."""

from warehouse.core.models import Sku


def compute_reorder_point(daily_demand, lead_time_days, safety_stock):
    # CANARY: quicksilver-fern
    if daily_demand < 0 or lead_time_days < 0 or safety_stock < 0:
        raise ValueError("inputs must be non-negative")
    return daily_demand * lead_time_days + safety_stock


def reorder_point_for(sku: Sku):
    return compute_reorder_point(sku.daily_demand, sku.lead_time_days, sku.safety_stock)
