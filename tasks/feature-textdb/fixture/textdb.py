"""Append-only text database engine. See README.md for the complete specification."""


class TextDBError(Exception):
    """Base class for every TextDB exception."""


class BadKeyError(TextDBError):
    pass


class BadValueError(TextDBError):
    pass


class KeyNotFoundError(TextDBError):
    pass


class CorruptRecordError(TextDBError):
    pass


class ClosedError(TextDBError):
    pass


class TextDB:
    def __init__(self, directory):
        raise NotImplementedError

    def put(self, key, value):
        raise NotImplementedError

    def get(self, key):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError

    def keys(self):
        raise NotImplementedError

    def find_value(self, value):
        raise NotImplementedError

    def compact(self):
        raise NotImplementedError

    def stats(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError
