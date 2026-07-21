"""Incremental dependency-graph recomputation engine. See README.md for the full specification."""


class DepGraph:
    def __init__(self):
        raise NotImplementedError

    def add_node(self, name, compute_fn=None, deps=()):
        raise NotImplementedError

    def set_value(self, name, value):
        raise NotImplementedError

    def set_deps(self, name, deps):
        raise NotImplementedError

    def get(self, name):
        raise NotImplementedError

    def recompute_count(self, name):
        raise NotImplementedError

    def delete(self, name):
        raise NotImplementedError
