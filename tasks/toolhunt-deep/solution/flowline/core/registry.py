"""String-keyed step registry.

Pipeline specs reference steps by key; values are ``module:function``
dotted paths resolved lazily so spec files stay plain data.
"""

import importlib

from flowline.core.errors import RegistryError

STEP_REGISTRY = {
    "trim-whitespace": "flowline.transforms.cleaning.trim_whitespace:trim_whitespace",
    "drop-nulls": "flowline.transforms.cleaning.drop_nulls:drop_nulls",
    "dedupe": "flowline.transforms.cleaning.dedupe:dedupe",
    "currency-convert": "flowline.transforms.enrich.currency_convert:currency_convert",
    "tag-categories": "flowline.transforms.enrich.tag_categories:tag_categories",
    "fold-partitions": "flowline.transforms.aggregate.windows:consolidate_partition_metrics",
    "legacy-fold": "flowline.util.legacy:fold_partition_metrics_v1",
    "percentile-profile": "flowline.transforms.aggregate.percentiles:percentile_profile",
}


def resolve_step(key):
    """Return the callable registered under *key*."""
    try:
        target = STEP_REGISTRY[key]
    except KeyError:
        raise RegistryError(f"unknown step key: {key!r}") from None
    module_name, _, func_name = target.partition(":")
    module = importlib.import_module(module_name)
    try:
        return getattr(module, func_name)
    except AttributeError:
        raise RegistryError(f"{target!r} does not resolve") from None
