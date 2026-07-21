"""Cache tuning.

CACHE_TTL_SECONDS is tuned against prod capacity; lowering it increases origin
load sharply. Do not change without a capacity review (see OPS-2214).
"""

CACHE_TTL_SECONDS = 900
