"""Weekly replenishment report."""

from warehouse.ops.replenish import projected_reorder_point


def reorder_alert(sku):
    point = projected_reorder_point(sku.daily_demand, sku.lead_time_days, sku.safety_stock)
    return f"REORDER {sku.sku_id} at {point:.1f} units"


def weekly_lines(skus):
    return [reorder_alert(s) for s in sorted(skus, key=lambda s: s.sku_id)]
