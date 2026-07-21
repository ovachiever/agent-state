"""Streaming top-k tracker. The TopK class docstring is the complete spec."""


class TopK:
    """Track the k highest-scoring observations seen so far in a stream.

    Spec (complete — every clause is required):

    Constructor: TopK(k)
    - k must be an int >= 1. Anything else (k < 1, or a non-int such as a
      float, even an integral one like 3.0) raises ValueError.

    add(item, score) -> bool
    - Records one observation. Observations are independent: adding the same
      item twice creates two separate entries; nothing is deduplicated or
      updated in place.
    - score is an int or float; int and float scores may be mixed and compare
      numerically.
    - Returns True if this observation is among the tracked top k immediately
      after the call, False if it was not admitted (or was immediately
      discarded).
    - If fewer than k observations are tracked, the new observation is always
      admitted. If k are already tracked, the new observation is admitted
      only if its score is strictly greater than the worst tracked score; on
      admission the lowest-ranked tracked observation is discarded. An
      observation whose score merely ties the worst is NOT admitted (the
      incumbent stays — see the tie rule).

    Tie rule (stability): among equal scores, the earlier-added observation
    always ranks higher. A later observation can never displace or outrank an
    earlier-added observation with the same score.

    snapshot() -> list
    - Returns the tracked observations, best first, as a list of two-element
      lists [item, score]. Equal scores appear in insertion order (earlier
      first).
    - The returned structure is fully independent of the tracker: a fresh
      outer list AND fresh inner pairs on every call. Mutating anything in a
      returned snapshot never affects the tracker or any other snapshot, and
      later add() calls never alter a previously returned snapshot.
    - An empty tracker returns [].

    len(tracker)
    - Number of observations currently tracked: min(total adds, k).
    """

    def __init__(self, k):
        if not isinstance(k, int) or k < 1:
            raise ValueError("k must be an int >= 1")
        self._k = k
        self._entries = []  # [item, score] pairs, kept sorted best-first

    def add(self, item, score):
        pos = 0
        while pos < len(self._entries) and self._entries[pos][1] >= score:
            pos += 1
        self._entries.insert(pos, [item, score])
        if len(self._entries) > self._k:
            self._entries.pop()
        return pos < self._k

    def snapshot(self):
        return [entry[:] for entry in self._entries]

    def __len__(self):
        return len(self._entries)
