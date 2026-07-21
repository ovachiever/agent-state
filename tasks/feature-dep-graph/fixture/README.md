# DepGraph Specification

Implement `DepGraph` in `depgraph.py`. Standard library only.

An incremental computation engine: named nodes hold values. **Source** nodes
get their values from `set_value`. **Computed** nodes derive theirs by calling
a compute function on the values of other nodes. Results are memoized; `get`
recomputes only what is stale, and only what the requested node needs.

## Constructor

```python
DepGraph()
```

## Node kinds

- **Source**: created with `compute_fn=None`. Must have empty `deps`. Holds
  whatever `set_value` last assigned; has no value at all until the first
  `set_value`.
- **Computed**: created with a callable `compute_fn`. Its value is
  `compute_fn(*dep_values)`, where `dep_values` are the values of its
  dependencies in the exact order `deps` was given. A computed node may have
  zero deps (its compute_fn is then called with no arguments).

## Methods

### `add_node(name, compute_fn=None, deps=())`
- Registers a new node. `deps` is a sequence of names of nodes that must
  already exist in the graph.
- `ValueError` if: `name` is already a node; any dep is not an existing node
  (note this means a node can never be added depending on itself); `deps`
  contains the same name twice; `compute_fn is None` and `deps` is non-empty.
- A new computed node starts dirty (never computed, recompute count 0).

### `set_value(name, value)`
- Assigns a **source** node's value and marks every transitive dependent of
  `name` dirty. Marking happens even if `value` equals the node's current
  value — dirtiness is structural, never inferred by comparing values.
- `KeyError` if `name` is not a node; `ValueError` if `name` is a computed
  node.

### `set_deps(name, deps)`
- Replaces a **computed** node's dependency list.
- `KeyError` if `name` is not a node. `ValueError` if `name` is a source; if
  any dep is unknown or duplicated (same rules as `add_node`); or if the new
  deps would create a cycle — i.e. `name` is reachable from any of the new
  deps by following dependency edges (listing `name` itself is the trivial
  case).
- On success: the deps are replaced (order significant), the node and all of
  its transitive dependents become dirty, and the old dependency edges are
  dropped (a former dep no longer counts this node as a dependent). The
  memoized value and the recompute count are untouched until a later `get`
  forces recomputation.

### `get(name)`
- `KeyError` if `name` is not a node.
- For a source: returns its value (`ValueError` if it was never set).
- For a computed node, let CLOSURE be the node plus everything it
  transitively depends on:
  - If any source in CLOSURE was never set: `ValueError`, and no compute
    function is called at all.
  - Otherwise recompute exactly the dirty nodes in CLOSURE — each exactly
    once, in dependency order (a node recomputes only after all of its deps
    are current). A recompute calls `compute_fn(*dep_values)`, stores the
    result, clears the node's dirty flag, and increments its recompute count.
  - Clean nodes are served from the memo; their compute_fn is NOT called.
    Dirty nodes outside CLOSURE are left alone — they stay dirty until some
    `get` actually needs them.
- Returns the node's value.

### `recompute_count(name) -> int`
- How many times this node's compute_fn has ever been invoked. Always 0 for
  source nodes. `KeyError` if `name` is not a node.

### `delete(name)`
- `KeyError` if `name` is not a node; `ValueError` if any node lists `name`
  as a dependency (the graph is unchanged).
- Otherwise removes the node and unregisters it from its deps' dependent
  sets. The name becomes reusable: a later `add_node(name, ...)` creates a
  completely fresh node (dirty, recompute count 0).

## Error discipline

- `KeyError`: the method's primary `name` argument names no existing node.
- `ValueError`: every other rejection (bad or unknown deps, wrong node kind,
  cycles, unset sources, deleting a depended-on node).

## Atomicity

Any call that raises must leave the graph exactly as it was — no partially
registered node, no half-wired edges, no changed deps, no new dirty marks,
no count changes. In particular: an `add_node` rejected for an unknown dep
must not leave `name` behind or registered as anyone's dependent; a
`set_deps` rejected for a cycle must leave the old deps fully in effect and
nothing dirtied.

## Recompute semantics

- Diamonds recompute shared work once: with `b` and `c` both depending on
  `a`, and `d` depending on `b` and `c`, a single `get("d")` after `a`
  changes recomputes each of `b`, `c`, `d` exactly once.
- No value cutoff: if a recompute yields a value equal to the old one,
  dependents recompute anyway. Value equality never short-circuits dirtiness.
