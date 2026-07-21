"""Statistics helpers."""


def median(nums):
    """Return the median of a non-empty list of numbers.

    Spec (authoritative): sort the values; odd length -> the middle value;
    even length -> the arithmetic mean of the two middle values.
    Raises ValueError on an empty list. Does not mutate the input.
    """
    if not nums:
        raise ValueError("median of empty list")
    ordered = sorted(nums)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2
