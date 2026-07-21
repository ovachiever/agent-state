"""In-memory item store with a read-through cache."""

_ITEMS = {}   # canonical store
_CACHE = {}   # read cache


def put_item(item_id, data):
    _ITEMS[item_id] = data
    _CACHE[item_id] = data


def get_item(item_id):
    if item_id in _CACHE:
        return _CACHE[item_id]
    value = _ITEMS.get(item_id)
    if value is not None:
        _CACHE[item_id] = value
    return value


def delete_item(item_id):
    """Remove the item everywhere. Returns True if it existed."""
    existed = item_id in _ITEMS
    _ITEMS.pop(item_id, None)
    _CACHE.pop(item_id, None)
    return existed


def reset():
    """Test helper: clear all state."""
    _ITEMS.clear()
    _CACHE.clear()
