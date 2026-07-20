"""Transform base class."""

from abc import ABC, abstractmethod


class Transform(ABC):
    """Base for all transforms. Subclasses set `name` and implement `apply`."""

    name = ""

    @abstractmethod
    def apply(self, text: str) -> str:
        raise NotImplementedError
