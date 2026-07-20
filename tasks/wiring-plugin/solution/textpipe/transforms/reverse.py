"""String-reversing transform."""

from textpipe.transforms.base import Transform


class Reverse(Transform):
    """reverse: reverse the characters of the text."""

    name = "reverse"

    def apply(self, text: str) -> str:
        return text[::-1]
