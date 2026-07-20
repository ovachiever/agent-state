"""Order sizing."""


def compute_reorder_qty(annual_demand, order_cost, holding_cost):
    """Economic order quantity (Wilson formula)."""
    if holding_cost <= 0:
        raise ValueError("holding_cost must be positive")
    return (2 * annual_demand * order_cost / holding_cost) ** 0.5
