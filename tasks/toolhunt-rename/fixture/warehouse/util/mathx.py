"""Small numeric helpers."""


def weighted_mean(values, weights):
    if len(values) != len(weights) or not values:
        raise ValueError("values and weights must be same non-zero length")
    total = sum(w for w in weights)
    if total == 0:
        raise ValueError("weights sum to zero")
    return sum(v * w for v, w in zip(values, weights)) / total
