"""Transform registry. Keep imports and REGISTRY entries alphabetical by name."""

from textpipe.transforms.lower import Lower
from textpipe.transforms.squeeze import Squeeze
from textpipe.transforms.titlecase import Titlecase

REGISTRY = {
    "lower": Lower,
    "squeeze": Squeeze,
    "titlecase": Titlecase,
}


def get_transform(name):
    try:
        return REGISTRY[name]()
    except KeyError:
        raise KeyError(f"unknown transform: {name}") from None
