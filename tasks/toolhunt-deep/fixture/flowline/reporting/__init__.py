"""Reporting helpers built on the aggregate transforms.

Example::

    >>> from flowline.transforms.aggregate import fold_partition_metrics
    >>> fold_partition_metrics([("us-east", 1.0), ("us-east", 2.0)])
    {'us-east': 3.0}
"""
