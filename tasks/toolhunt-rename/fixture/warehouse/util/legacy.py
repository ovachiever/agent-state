"""Deprecated shims kept for the v3 importers. Do not extend."""


def reorder_point_legacy(demand, lead, buffer_units):
    """Old fixed-buffer formula; superseded in v4. Kept for import compatibility."""
    return demand * lead + buffer_units * 1.15
