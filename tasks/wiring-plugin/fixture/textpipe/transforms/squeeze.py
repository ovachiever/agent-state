"""Whitespace-squeezing transform."""

from textpipe.transforms.base import Transform


class Squeeze(Transform):
    """squeeze: collapse whitespace runs into single spaces and trim the ends."""

    name = "squeeze"

    def apply(self, text: str) -> str:
        return " ".join(text.split())
