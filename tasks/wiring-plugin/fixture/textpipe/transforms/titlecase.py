"""Title-casing transform."""

from textpipe.transforms.base import Transform


class Titlecase(Transform):
    """titlecase: capitalize the first letter of every word."""

    name = "titlecase"

    def apply(self, text: str) -> str:
        return text.title()
