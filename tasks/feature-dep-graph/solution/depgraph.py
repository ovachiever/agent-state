"""Incremental dependency-graph recomputation engine. See README.md for the full specification."""


class _Node:
    __slots__ = ("compute_fn", "deps", "dependents", "value", "has_value", "dirty", "count")

    def __init__(self, compute_fn, deps):
        self.compute_fn = compute_fn
        self.deps = list(deps)
        self.dependents = set()
        self.value = None
        self.has_value = False
        self.dirty = compute_fn is not None
        self.count = 0


class DepGraph:
    def __init__(self):
        self._nodes = {}

    def _require(self, name):
        if name not in self._nodes:
            raise KeyError(name)
        return self._nodes[name]

    def _checked_deps(self, deps):
        deps = list(deps)
        if len(set(deps)) != len(deps):
            raise ValueError("duplicate dependency")
        for d in deps:
            if d not in self._nodes:
                raise ValueError(f"unknown dependency: {d!r}")
        return deps

    def add_node(self, name, compute_fn=None, deps=()):
        if name in self._nodes:
            raise ValueError(f"node already exists: {name!r}")
        deps = self._checked_deps(deps)
        if compute_fn is None and deps:
            raise ValueError("source nodes cannot have dependencies")
        # All validation happened above: registration is atomic.
        self._nodes[name] = _Node(compute_fn, deps)
        for d in deps:
            self._nodes[d].dependents.add(name)

    def set_value(self, name, value):
        node = self._require(name)
        if node.compute_fn is not None:
            raise ValueError(f"not a source node: {name!r}")
        node.value = value
        node.has_value = True
        self._dirty_dependents(name)

    def set_deps(self, name, deps):
        node = self._require(name)
        if node.compute_fn is None:
            raise ValueError(f"not a computed node: {name!r}")
        deps = self._checked_deps(deps)
        if self._reachable_from(deps, name):
            raise ValueError("cycle")
        for d in node.deps:
            self._nodes[d].dependents.discard(name)
        node.deps = deps
        for d in deps:
            self._nodes[d].dependents.add(name)
        node.dirty = True
        self._dirty_dependents(name)

    def _reachable_from(self, starts, target):
        stack = list(starts)
        seen = set()
        while stack:
            n = stack.pop()
            if n == target:
                return True
            if n in seen:
                continue
            seen.add(n)
            stack.extend(self._nodes[n].deps)
        return False

    def _dirty_dependents(self, name):
        stack = list(self._nodes[name].dependents)
        seen = set()
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            self._nodes[n].dirty = True
            stack.extend(self._nodes[n].dependents)

    def _closure_topo(self, name):
        order = []
        seen = set()

        def visit(n):
            if n in seen:
                return
            seen.add(n)
            for d in self._nodes[n].deps:
                visit(d)
            order.append(n)

        visit(name)
        return order

    def get(self, name):
        node = self._require(name)
        order = self._closure_topo(name)
        for n in order:
            nd = self._nodes[n]
            if nd.compute_fn is None and not nd.has_value:
                raise ValueError(f"source has no value: {n!r}")
        for n in order:
            nd = self._nodes[n]
            if nd.compute_fn is not None and nd.dirty:
                args = [self._nodes[d].value for d in nd.deps]
                nd.value = nd.compute_fn(*args)
                nd.dirty = False
                nd.count += 1
        return node.value

    def recompute_count(self, name):
        return self._require(name).count

    def delete(self, name):
        node = self._require(name)
        if node.dependents:
            raise ValueError(f"node has dependents: {name!r}")
        for d in node.deps:
            self._nodes[d].dependents.discard(name)
        del self._nodes[name]
