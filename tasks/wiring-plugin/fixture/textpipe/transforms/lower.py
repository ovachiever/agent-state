"""Lowercase transform."""

from textpipe.transforms.base import Transform


class Lower(Transform):
    """lower: convert text to lowercase."""

    name = "lower"

    def apply(self, text: str) -> str:
        return text.lower()
