"""Event counter."""


class Counter:
    """Accumulates numeric samples.

    add(value): record a sample. Every finite numeric value is recorded,
    including zero and negatives.
    count(): number of samples recorded.
    total(): sum of recorded samples.
    """

    def __init__(self):
        self._values = []

    def add(self, value):
        if value > 0:
            self._values.append(value)

    def count(self):
        return len(self._values)

    def total(self):
        return sum(self._values)
