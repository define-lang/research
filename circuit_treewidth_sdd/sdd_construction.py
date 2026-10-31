"""Build and check SDDs for circuits of small treewidth.

This module carries out, on small examples, every step of the construction in
`circuit-treewidth-sdd-proof.md`:

1. a circuit and a tree decomposition of its graph (Section 7 of the proof);
2. gate splitting, which gives a relational tree decomposition (RTD) whose
   relations are gate constraints (Lemma 7.1);
3. normalization to a full binary tree whose leaves are the inputs
   (Lemma 7.2);
4. leaf donation, which gives the shape conditions (S1) and (S2) (Lemma 6.1);
5. the SDD built from pair cells and joins (Theorem 5.1).

Every property that the proof claims for an intermediate object is checked by
brute force over all input assignments, and the final SDD is checked to be a
valid SDD for the vtree that computes the circuit. Boolean functions over the
n inputs are Python integers used as bitsets: bit a is the value at the
assignment whose i-th input is bit i of a.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field


class CheckFailedError(Exception):
    """A property that the proof claims was found to be false."""


def check(condition: bool, message: str) -> None:  # noqa: FBT001
    """Raise CheckFailedError with the message unless the condition holds."""
    if not condition:
        raise CheckFailedError(message)


def input_bitsets(num_inputs: int) -> list[int]:
    """Return, for each input, its value on all assignments as a bitset."""
    size = 1 << num_inputs
    result = []
    for i in range(num_inputs):
        bits = 0
        for a in range(size):
            if (a >> i) & 1:
                bits |= 1 << a
        result.append(bits)
    return result


# ---------------------------------------------------------------------------
# Circuits
# ---------------------------------------------------------------------------


@dataclass
class Circuit:
    """A Boolean circuit with AND and OR gates of any fan-in and negated wires.

    Vertices 0 .. num_inputs - 1 are the inputs. Gate i is vertex
    num_inputs + i, and its wires come from earlier vertices only. A NOT gate
    is an AND gate with one negated wire.
    """

    num_inputs: int
    gates: list[tuple[str, list[tuple[int, bool]]]]
    output: int

    @property
    def num_vertices(self) -> int:
        """Inputs plus gates."""
        return self.num_inputs + len(self.gates)

    def evaluate_all(self) -> list[int]:
        """Return, for every vertex, its value on all assignments as a bitset."""
        full = (1 << (1 << self.num_inputs)) - 1
        values = input_bitsets(self.num_inputs)
        for op, wires in self.gates:
            literals = [
                full ^ values[v] if negated else values[v] for v, negated in wires
            ]
            values.append(combine(op, literals, full))
        return values

    def wire_graph(self) -> dict[int, set[int]]:
        """Return the undirected graph whose edges are the circuit's wires."""
        adjacency: dict[int, set[int]] = {v: set() for v in range(self.num_vertices)}
        for index, (_, wires) in enumerate(self.gates):
            gate = self.num_inputs + index
            for v, _ in wires:
                adjacency[gate].add(v)
                adjacency[v].add(gate)
        return adjacency


def combine(op: str, literals: list[int], full: int) -> int:
    """Return the AND or OR of bitsets; the empty AND is true, the empty OR false."""
    if op == "and":
        result = full
        for literal in literals:
            result &= literal
        return result
    if op == "or":
        result = 0
        for literal in literals:
            result |= literal
        return result
    raise ValueError(op)


# ---------------------------------------------------------------------------
# Trees, bags, and relations
# ---------------------------------------------------------------------------


def valuations(bag: tuple[int, ...]) -> range:
    """Return the valuations of a bag, as integers over the bag's positions."""
    return range(1 << len(bag))


def value_in(valuation: int, bag: tuple[int, ...], vertex: int) -> int:
    """Return the value of a vertex in a valuation of a bag."""
    return (valuation >> bag.index(vertex)) & 1


def project(valuation: int, bag: tuple[int, ...], target: tuple[int, ...]) -> int:
    """Restrict a valuation of bag to the vertices of target, all in bag."""
    result = 0
    for j, vertex in enumerate(target):
        result |= value_in(valuation, bag, vertex) << j
    return result


def join(
    left: set[int],
    left_bag: tuple[int, ...],
    right: set[int],
    right_bag: tuple[int, ...],
) -> tuple[set[int], tuple[int, ...]]:
    """Return the natural join of two relations and its bag."""
    common = tuple(v for v in left_bag if v in right_bag)
    union = tuple(sorted(set(left_bag) | set(right_bag)))
    by_common: dict[int, list[int]] = {}
    for r in right:
        by_common.setdefault(project(r, right_bag, common), []).append(r)
    result = set()
    for valuation in left:
        for r in by_common.get(project(valuation, left_bag, common), []):
            combined = 0
            for j, vertex in enumerate(union):
                if vertex in left_bag:
                    bit = value_in(valuation, left_bag, vertex)
                else:
                    bit = value_in(r, right_bag, vertex)
                combined |= bit << j
            result.add(combined)
    return result, union


def project_relation(
    relation: set[int], bag: tuple[int, ...], target: tuple[int, ...]
) -> set[int]:
    """Project a relation onto a subset of its bag."""
    return {project(valuation, bag, target) for valuation in relation}


def restrict_relation(
    relation: set[int],
    bag: tuple[int, ...],
    constraint: set[int],
    constraint_bag: tuple[int, ...],
) -> set[int]:
    """Keep the valuations whose restriction to constraint_bag is in constraint."""
    return {
        valuation
        for valuation in relation
        if project(valuation, bag, constraint_bag) in constraint
    }


def extend_relation(
    relation: set[int], bag: tuple[int, ...], new_bag: tuple[int, ...]
) -> set[int]:
    """Return the cylinder of the relation over a larger bag."""
    positions = [new_bag.index(v) for v in bag]
    free = [j for j, v in enumerate(new_bag) if v not in bag]
    extras = []
    for combination in range(1 << len(free)):
        bits = 0
        for i, j in enumerate(free):
            bits |= ((combination >> i) & 1) << j
        extras.append(bits)
    result = set()
    for valuation in relation:
        placed = 0
        for i, j in enumerate(positions):
            placed |= ((valuation >> i) & 1) << j
        for bits in extras:
            result.add(placed | bits)
    return result


def relation_from_constraints(
    bag: tuple[int, ...], constraints: list[tuple[set[int], tuple[int, ...]]]
) -> set[int]:
    """Return the valuations of bag that satisfy every constraint, by joining them."""
    relation, current = {0}, ()
    for constraint, constraint_bag in constraints:
        relation, current = join(relation, current, constraint, constraint_bag)
    return extend_relation(relation, current, bag)


@dataclass(eq=False)
class Node:
    """A node of a rooted tree decomposition, and of the final vtree.

    In a vtree, a node has no children (a leaf for input `leaf_input`) or
    exactly two (left, then right).
    """

    bag: tuple[int, ...]
    relation: set[int]
    children: list[Node] = field(default_factory=list)
    leaf_input: int | None = None

    def is_leaf(self) -> bool:
        """Return whether the node has no children."""
        return not self.children


def all_nodes(root: Node) -> list[Node]:
    """Return the nodes of the tree in preorder, left before right."""
    result = []
    stack = [root]
    while stack:
        node = stack.pop()
        result.append(node)
        stack.extend(reversed(node.children))
    return result


def parent_map(root: Node) -> dict[Node, Node | None]:
    """Return each node's parent."""
    parents: dict[Node, Node | None] = {root: None}
    for node in all_nodes(root):
        for child in node.children:
            parents[child] = node
    return parents


def add_vertices(node: Node, vertices: set[int]) -> None:
    """Add vertices to a node's bag, extending its relation as a cylinder."""
    new_bag = tuple(sorted(set(node.bag) | vertices))
    node.relation = extend_relation(node.relation, node.bag, new_bag)
    node.bag = new_bag


def left(node: Node) -> Node:
    """Return the left child."""
    return node.children[0]


def right(node: Node) -> Node:
    """Return the right child."""
    return node.children[1]


def width(root: Node) -> int:
    """Return the largest bag size minus one."""
    return max(len(node.bag) for node in all_nodes(root)) - 1


@dataclass
class Instance:
    """The vertices' values on all assignments, and the output vertex.

    The values define the solution of every input assignment; `check_rtd`
    checks that it is the only one.
    """

    num_inputs: int
    values: dict[int, int]
    output: int

    @property
    def full(self) -> int:
        """The bitset of all assignments."""
        return (1 << (1 << self.num_inputs)) - 1


# ---------------------------------------------------------------------------
# Tree decompositions of the wire graph
# ---------------------------------------------------------------------------


def elimination_decomposition(
    adjacency: dict[int, set[int]], order: list[int] | None = None
) -> tuple[list[frozenset[int]], list[int | None]]:
    """Return bags and parent links of a tree decomposition by elimination.

    Without an order, vertices are eliminated greedily by minimum fill-in.
    """
    graph = {v: set(neighbors) for v, neighbors in adjacency.items()}
    eliminated: list[int] = []
    bags: dict[int, frozenset[int]] = {}

    def fill(u: int) -> tuple[int, int, int]:
        neighbors = graph[u]
        missing = sum(
            1 for a, b in itertools.combinations(neighbors, 2) if b not in graph[a]
        )
        return (missing, len(neighbors), u)

    while graph:
        v = order[len(eliminated)] if order is not None else min(graph, key=fill)
        neighbors = graph[v]
        bags[v] = frozenset(neighbors | {v})
        for a, b in itertools.combinations(neighbors, 2):
            graph[a].add(b)
            graph[b].add(a)
        for a in neighbors:
            graph[a].discard(v)
        del graph[v]
        eliminated.append(v)
    position = {v: i for i, v in enumerate(eliminated)}
    parents: list[int | None] = []
    for v in eliminated:
        later = [u for u in bags[v] if u != v]
        parents.append(
            position[min(later, key=lambda u: position[u])] if later else None
        )
    roots = [i for i, parent in enumerate(parents) if parent is None]
    for extra_root in roots[:-1]:
        parents[extra_root] = roots[-1]
    return [bags[v] for v in eliminated], parents


def path_decomposition(
    adjacency: dict[int, set[int]], order: list[int]
) -> tuple[list[frozenset[int]], list[int | None]]:
    """Return the path decomposition of a vertex order, rooted at its last bag.

    Bag i holds vertex i of the order and every earlier vertex that has a
    neighbor at position i or later.
    """
    position = {v: i for i, v in enumerate(order)}
    last_neighbor = {
        v: max([position[v]] + [position[u] for u in adjacency[v]]) for v in order
    }
    bags = [
        frozenset({v} | {u for u in order[:i] if last_neighbor[u] >= i})
        for i, v in enumerate(order)
    ]
    parents: list[int | None] = [i + 1 for i in range(len(order) - 1)]
    parents.append(None)
    return bags, parents


def check_tree_decomposition(adjacency: dict[int, set[int]], root: Node) -> int:
    """Check that the tree is a tree decomposition of the graph; return its width."""
    nodes = all_nodes(root)
    parents = parent_map(root)
    for v, neighbors in adjacency.items():
        holders = [node for node in nodes if v in node.bag]
        check(bool(holders), f"vertex {v} must be in a bag")
        tops = [
            node
            for node in holders
            if parents[node] is None or v not in parents[node].bag
        ]
        check(len(tops) == 1, f"bags containing {v} must be connected")
        for u in neighbors:
            check(
                any(u in node.bag for node in holders), f"edge {v}-{u} must be in a bag"
            )
    return width(root)


def tree_from_decomposition(
    bags: list[frozenset[int]], parents: list[int | None], root_vertex: int
) -> Node:
    """Return the decomposition as a rooted tree of nodes with empty relations.

    The root is the given root if its bag holds root_vertex, and otherwise a
    bag that does.
    """
    nodes = [Node(tuple(sorted(bag)), set()) for bag in bags]
    adjacency: dict[int, list[int]] = {i: [] for i in range(len(nodes))}
    for i, parent in enumerate(parents):
        if parent is not None:
            adjacency[i].append(parent)
            adjacency[parent].append(i)
    roots = [
        i
        for i, parent in enumerate(parents)
        if parent is None and root_vertex in bags[i]
    ]
    root_index = (
        roots[0]
        if roots
        else next(i for i, bag in enumerate(bags) if root_vertex in bag)
    )
    seen = {root_index}
    stack = [root_index]
    while stack:
        i = stack.pop()
        for j in adjacency[i]:
            if j not in seen:
                seen.add(j)
                nodes[i].children.append(nodes[j])
                stack.append(j)
    return nodes[root_index]


def binarize(node: Node) -> None:
    """Split nodes with three or more children into chains of copies.

    Copies get the full relation. Leaves are listed first, so that a node
    with a leaf child keeps a leaf child after splitting.
    """
    for child in node.children:
        binarize(child)
    node.children.sort(key=lambda child: not child.is_leaf())
    while len(node.children) > 2:
        copy = Node(node.bag, set(valuations(node.bag)), node.children[1:])
        node.children = [node.children[0], copy]
        binarize(copy)


# ---------------------------------------------------------------------------
# Lemma 7.1: gate splitting
# ---------------------------------------------------------------------------


def gate_relation(
    op: str, here: int, sources: list[tuple[int, bool]]
) -> tuple[set[int], tuple[int, ...]]:
    """Return the relation "here = op(sources)" over its scope.

    A source may repeat; a source equal to here is not allowed.
    """
    scope = tuple(sorted({here} | {s for s, _ in sources}))
    relation = set()
    for valuation in valuations(scope):
        literals = [
            value_in(valuation, scope, s) ^ int(negated) for s, negated in sources
        ]
        expected = int(all(literals)) if op == "and" else int(any(literals))
        if value_in(valuation, scope, here) == expected:
            relation.add(valuation)
    return relation, scope


def split_gates(circuit: Circuit, tree: Node) -> tuple[Node, Instance]:
    """Return the RTD of Lemma 7.1 on a binary tree decomposition of the wires.

    For each gate g and each node t whose bag holds g there is a new vertex
    g@t, the AND or OR of the wires assigned to t and of g@t' for the children
    t' of t whose bags hold g. The value of g is g@top(g), where top(g) is the
    highest node holding g. The new bags hold the inputs of the old bag and,
    for each gate g of the old bag, g@t, g@top(g), and g@t' for its children.
    """
    n = circuit.num_inputs
    full = (1 << (1 << n)) - 1
    nodes = all_nodes(tree)
    parents = parent_map(tree)
    top: dict[int, Node] = {}
    for node in nodes:
        for v in node.bag:
            if v >= n and (parents[node] is None or v not in parents[node].bag):
                top[v] = node
    assigned: dict[Node, list[tuple[int, int, bool]]] = {node: [] for node in nodes}
    for index, (_, wires) in enumerate(circuit.gates):
        gate = n + index
        for source, negated in wires:
            home = next(
                node for node in nodes if gate in node.bag and source in node.bag
            )
            assigned[home].append((gate, source, negated))
    number = {node: i for i, node in enumerate(nodes)}
    split_vertex: dict[tuple[int, int], int] = {}
    next_vertex = circuit.num_vertices
    for node in nodes:
        for v in node.bag:
            if v >= n:
                split_vertex[v, number[node]] = next_vertex
                next_vertex += 1

    def hat(v: int) -> int:
        return v if v < n else split_vertex[v, number[top[v]]]

    gate_values = circuit.evaluate_all()
    values: dict[int, int] = {x: gate_values[x] for x in range(n)}
    for node in reversed(nodes):
        for v in node.bag:
            if v < n:
                continue
            op = circuit.gates[v - n][0]
            literals = [
                full ^ gate_values[source] if negated else gate_values[source]
                for gate, source, negated in assigned[node]
                if gate == v
            ]
            literals += [
                values[split_vertex[v, number[child]]]
                for child in node.children
                if v in child.bag
            ]
            values[split_vertex[v, number[node]]] = combine(op, literals, full)
    for v in range(n, circuit.num_vertices):
        check(values[hat(v)] == gate_values[v], "g@top(g) must equal the gate's value")
    new_nodes: dict[Node, Node] = {}
    for node in nodes:
        bag = {v for v in node.bag if v < n}
        constraints = []
        for v in node.bag:
            if v < n:
                continue
            here = split_vertex[v, number[node]]
            sources = [
                (hat(source), negated)
                for gate, source, negated in assigned[node]
                if gate == v
            ]
            sources += [
                (split_vertex[v, number[child]], False)
                for child in node.children
                if v in child.bag
            ]
            bag |= {here, hat(v)} | {s for s, _ in sources}
            constraints.append((circuit.gates[v - n][0], here, sources))
        bag_tuple = tuple(sorted(bag))
        constraint_relations = [
            gate_relation(op, here, sources) for op, here, sources in constraints
        ]
        new_nodes[node] = Node(
            bag_tuple, relation_from_constraints(bag_tuple, constraint_relations)
        )
    for node in nodes:
        new_nodes[node].children = [new_nodes[child] for child in node.children]
    return new_nodes[tree], Instance(n, values, hat(circuit.output))


# ---------------------------------------------------------------------------
# Lemma 7.2: normalization to a vtree
# ---------------------------------------------------------------------------


def attach_input_leaves(
    root: Node, num_inputs: int, *, attach_last: bool = False
) -> None:
    """Hang a leaf with bag {x} below a node holding x, for every input x.

    The leaf goes below the first node in preorder that holds x (the one
    nearest the root), or the last one with attach_last.
    """
    nodes = all_nodes(root)
    for x in range(num_inputs):
        homes = [node for node in nodes if x in node.bag]
        home = homes[-1] if attach_last else homes[0]
        home.children.append(Node((x,), {0, 1}, leaf_input=x))


def message(
    node: Node, parent_bag: tuple[int, ...]
) -> tuple[set[int], tuple[int, ...]]:
    """Project the relations of a subtree onto its interface with the parent."""
    relation, bag = set(node.relation), node.bag
    for child in node.children:
        child_message, child_interface = message(child, node.bag)
        relation = restrict_relation(relation, bag, child_message, child_interface)
    interface = tuple(v for v in node.bag if v in parent_bag)
    return project_relation(relation, bag, interface), interface


def has_input(node: Node) -> bool:
    """Return whether an input leaf lies in the subtree."""
    return node.leaf_input is not None or any(
        has_input(child) for child in node.children
    )


def prune_dead_subtrees(node: Node) -> None:
    """Fold subtrees without input leaves into their parents' relations."""
    kept = []
    for child in node.children:
        if has_input(child):
            prune_dead_subtrees(child)
            kept.append(child)
        else:
            child_message, interface = message(child, node.bag)
            node.relation = restrict_relation(
                node.relation, node.bag, child_message, interface
            )
    node.children = kept


def chain_relation(
    chain: list[Node], bottom: Node, keep: tuple[int, ...]
) -> tuple[set[int], tuple[int, ...]]:
    """Join the relations of a chain and of the node below it, then project to keep.

    keep must contain the bottom node's bag.
    """
    relation, bag = set(bottom.relation), bottom.bag
    for node in reversed(chain):
        relation, bag = join(relation, bag, node.relation, node.bag)
        needed = tuple(v for v in bag if v in keep or v in node.bag)
        relation = project_relation(relation, bag, needed)
        bag = needed
    target = tuple(sorted(keep))
    return project_relation(relation, bag, target), target


def contract_unary_chains(root: Node, output: int) -> Node:
    """Remove nodes with exactly one child, keeping every needed vertex.

    A maximal chain of one-child nodes above an input leaf is folded into the
    node above the chain, whose bag gains that input. Any other maximal chain
    is folded into the node below it, whose bag gains the chain's interface
    with the node above. The root is treated as if its parent's bag were
    {output}.
    """
    parents = parent_map(root)

    def interface_above(top: Node) -> tuple[int, ...]:
        above = parents[top]
        if above is None:
            return tuple(v for v in top.bag if v == output)
        return tuple(v for v in top.bag if v in above.bag)

    for leaf in [node for node in all_nodes(root) if node.is_leaf()]:
        chain = []
        current = parents[leaf]
        while current is not None and len(current.children) == 1:
            chain.append(current)
            current = parents[current]
        if not chain:
            continue
        if current is None:
            raise CheckFailedError("a circuit with one input is not supported")
        chain.reverse()
        keep = tuple(sorted(set(interface_above(chain[0])) | set(leaf.bag)))
        relation, bag = chain_relation(chain, leaf, keep)
        add_vertices(current, set(leaf.bag))
        current.relation = restrict_relation(
            current.relation, current.bag, relation, bag
        )
        current.children = [
            leaf if child is chain[0] else child for child in current.children
        ]
        parents[leaf] = current

    def rebuild(node: Node) -> Node:
        chain = []
        current = node
        while len(current.children) == 1:
            chain.append(current)
            current = current.children[0]
        children = [rebuild(child) for child in current.children]
        if not chain:
            current.children = children
            return current
        keep = tuple(sorted(set(current.bag) | set(interface_above(chain[0]))))
        relation, bag = chain_relation(chain, current, keep)
        return Node(bag, relation, children)

    return rebuild(root)


def normalize(root: Node, instance: Instance, *, attach_last: bool = False) -> Node:
    """Return an RTD on a full binary tree whose leaves are the inputs (Lemma 7.2)."""
    attach_input_leaves(root, instance.num_inputs, attach_last=attach_last)
    prune_dead_subtrees(root)
    binarize(root)
    root = contract_unary_chains(root, instance.output)
    check(instance.output in root.bag, "the output must stay in the root's bag")
    return root


def split_rtd(
    circuit: Circuit,
    *,
    order: list[int] | None = None,
    path: bool = False,
    attach_last: bool = False,
) -> tuple[Node, Instance, int]:
    """Return a normalized RTD built by gate splitting, and the wire graph's width.

    With path, the decomposition is the path decomposition of the given order
    and the result is a caterpillar with each leaf child on the right.
    attach_last is passed to `attach_input_leaves`.
    """
    graph = circuit.wire_graph()
    if path:
        if order is None:
            raise ValueError("a path decomposition needs an order")
        bags, parents = path_decomposition(graph, order)
        # Theorem 1.2: the output joins every bag, so the path is rooted at its end.
        bags = [bag | {circuit.output} for bag in bags]
    else:
        bags, parents = elimination_decomposition(graph, order)
    tree = tree_from_decomposition(bags, parents, circuit.output)
    binarize(tree)
    decomposition_width = check_tree_decomposition(graph, tree)
    root, instance = split_gates(circuit, tree)
    root = normalize(root, instance, attach_last=attach_last)
    if path:
        orient_leaf_children_right(root)
    return root, instance, decomposition_width


def moral_rtd(
    circuit: Circuit,
    *,
    order: list[int] | None = None,
    path: bool = False,
    attach_last: bool = False,
) -> tuple[Node, Instance, int]:
    """Return a normalized RTD whose vertices are the circuit's own vertices.

    This variant decomposes the graph in which each gate and its wire sources
    form a clique, so that every gate constraint fits one bag. It keeps bags
    small for fan-in 2 and is used for the bulk experiments; `split_rtd` is
    the construction of Lemma 7.1. With path, the decomposition is the path
    decomposition of the given order, and the result is a caterpillar with
    each leaf child on the right. attach_last is passed to
    `attach_input_leaves`. Returns the RTD, the instance, and the width of
    the decomposition of that graph.
    """
    n = circuit.num_inputs
    graph: dict[int, set[int]] = {v: set() for v in range(circuit.num_vertices)}
    scopes = []
    for index, (op, wires) in enumerate(circuit.gates):
        gate = n + index
        scope = {gate} | {v for v, _ in wires}
        for u, v in itertools.combinations(sorted(scope), 2):
            graph[u].add(v)
            graph[v].add(u)
        scopes.append((scope, gate_relation(op, gate, wires)))
    if path:
        if order is None:
            raise ValueError("a path decomposition needs an order")
        bags, parents = path_decomposition(graph, order)
        # Theorem 1.2: the output joins every bag, so the path is rooted at its end.
        bags = [bag | {circuit.output} for bag in bags]
    else:
        bags, parents = elimination_decomposition(graph, order)
    tree = tree_from_decomposition(bags, parents, circuit.output)
    decomposition_width = check_tree_decomposition(graph, tree)
    nodes = all_nodes(tree)
    assigned: dict[Node, list[tuple[set[int], tuple[int, ...]]]] = {
        node: [] for node in nodes
    }
    for scope, constraint in scopes:
        home = next(node for node in nodes if scope <= set(node.bag))
        assigned[home].append(constraint)
    for node in nodes:
        node.relation = relation_from_constraints(node.bag, assigned[node])
    values = dict(enumerate(circuit.evaluate_all()))
    instance = Instance(n, values, circuit.output)
    root = normalize(tree, instance, attach_last=attach_last)
    if path:
        orient_leaf_children_right(root)
    return root, instance, decomposition_width


# ---------------------------------------------------------------------------
# Checking RTD properties
# ---------------------------------------------------------------------------


@dataclass
class Analysis:
    """Per-node data used by the checks and by the SDD construction."""

    instance: Instance
    root: Node
    parents: dict[Node, Node | None]
    inputs_below: dict[Node, int]
    cells: dict[Node, dict[int, int]]
    state: dict[Node, list[int]]


def input_mask(node: Node) -> int:
    """Return the inputs at the leaves below node, as a bitmask over inputs."""
    if node.leaf_input is not None:
        return 1 << node.leaf_input
    mask = 0
    for child in node.children:
        mask |= input_mask(child)
    return mask


def check_rtd(instance: Instance, root: Node) -> Analysis:
    """Check that root is an RTD on a vtree for the instance, and analyze it.

    Checks the definition in Section 3 of the proof: leaves are exactly the
    inputs with bags {x}; internal nodes have two children; every vertex's
    bags are connected; the output is in the root's bag; and every input
    assignment has exactly one solution, namely the instance's values. Also
    computes Q_t(sigma) for every node t and valuation sigma; a missing sigma
    means the empty set.
    """
    n = instance.num_inputs
    size = 1 << n
    full = instance.full
    values = instance.values
    nodes = all_nodes(root)
    parents = parent_map(root)
    leaf_inputs = sorted(
        node.leaf_input
        for node in nodes
        if node.is_leaf() and node.leaf_input is not None
    )
    check(leaf_inputs == list(range(n)), "leaves must be exactly the inputs")
    for node in nodes:
        if node.is_leaf():
            check(
                node.leaf_input is not None and node.bag == (node.leaf_input,),
                "leaf bag must be {x}",
            )
            check(node.relation == {0, 1}, "leaf relation must be trivial")
        else:
            check(len(node.children) == 2, "internal nodes must have two children")
    check(instance.output in root.bag, "output must be in the root bag")
    holders: dict[int, list[Node]] = {}
    for node in nodes:
        for v in node.bag:
            holders.setdefault(v, []).append(node)
    for v, nodes_with_v in holders.items():
        tops = [
            node
            for node in nodes_with_v
            if parents[node] is None or v not in parents[node].bag
        ]
        check(len(tops) == 1, f"bags containing vertex {v} must be connected")
    state: dict[Node, list[int]] = {}
    for node in nodes:
        states = []
        for a in range(size):
            s = 0
            for j, v in enumerate(node.bag):
                s |= ((values[v] >> a) & 1) << j
            states.append(s)
        state[node] = states
        check(
            all(s in node.relation for s in states),
            "the instance's values must satisfy every relation",
        )
    # Count solutions per assignment, saturating at two, bottom-up (Lemma 4.2).
    cells: dict[Node, dict[int, int]] = {}
    twos: dict[Node, dict[int, int]] = {}
    for node in reversed(nodes):
        cells[node], twos[node] = {}, {}
        if node.is_leaf():
            x = node.leaf_input
            cells[node] = {0: full ^ values[x], 1: values[x]}
            twos[node] = {0: 0, 1: 0}
            continue
        sums = []
        for child in node.children:
            shared = tuple(v for v in child.bag if v in node.bag)
            by_projection: dict[int, tuple[int, int]] = {}
            for tau, tau_one in cells[child].items():
                if tau_one == 0:
                    continue
                key = project(tau, child.bag, shared)
                child_one, child_two = by_projection.get(key, (0, 0))
                child_two |= twos[child][tau] | (child_one & tau_one)
                child_one |= tau_one
                by_projection[key] = (child_one, child_two)
            sums.append((shared, by_projection))
        for sigma in node.relation:
            one, two = full, 0
            for shared, by_projection in sums:
                child_one, child_two = by_projection.get(
                    project(sigma, node.bag, shared), (0, 0)
                )
                one, two = one & child_one, (two & child_one) | (one & child_two)
            cells[node][sigma], twos[node][sigma] = one, two
    total_one, total_two = 0, 0
    for sigma, sigma_one in cells[root].items():
        total_two |= twos[root][sigma] | (total_one & sigma_one)
        total_one |= sigma_one
    check(
        total_one == full and total_two == 0,
        "every assignment must have exactly one solution",
    )
    inputs_below = {node: input_mask(node) for node in nodes}
    return Analysis(instance, root, parents, inputs_below, cells, state)


def check_shape(root: Node) -> None:
    """Check (S1): the root's right child is a leaf, and (S2) at every internal right child."""
    check(
        not root.is_leaf() and right(root).is_leaf(),
        "(S1): the root's right child must be a leaf",
    )
    parents = parent_map(root)
    for node in all_nodes(root):
        parent = parents[node]
        if parent is None or node.is_leaf() or right(parent) is not node:
            continue
        below = set(node.bag) & set(right(node).bag)
        check(below <= set(parent.bag), "(S2) must hold at every internal right child")


# ---------------------------------------------------------------------------
# Lemma 6.1: leaf donation
# ---------------------------------------------------------------------------


def make_cherries_contained(root: Node) -> None:
    """Make every cherry's bag a subset of its parent's bag (Step 1 of Lemma 6.1).

    A cherry is a node whose two children are leaves. Vertices that occur
    only in the cherry are projected out, and the cherry's two inputs are
    added to the parent's bag.
    """
    for parent in all_nodes(root):
        for child in parent.children:
            if child.is_leaf() or not all(
                grandchild.is_leaf() for grandchild in child.children
            ):
                continue
            leaf_inputs = {grandchild.leaf_input for grandchild in child.children}
            keep = tuple(
                sorted({v for v in child.bag if v in parent.bag} | leaf_inputs)
            )
            child.relation = project_relation(child.relation, child.bag, keep)
            child.bag = keep
            add_vertices(parent, leaf_inputs)


def donate_leaves(root: Node, output: int) -> Node:
    """Return the RTD of Lemma 6.1: (S1) and (S2) hold.

    Each internal node w = (a, b) consumes the rightmost leaf of a and passes
    the rightmost leaf of b upward; the root's rightmost leaf becomes the new
    root's right child.
    """
    if not root.is_leaf() and all(child.is_leaf() for child in root.children):
        if not right(root).is_leaf() or right(root).leaf_input is None:
            raise CheckFailedError("unexpected cherry root")
        return root
    make_cherries_contained(root)

    def fresh_leaf(leaf: Node) -> Node:
        return Node(leaf.bag, {0, 1}, leaf_input=leaf.leaf_input)

    def build(
        w: Node,
    ) -> tuple[Node | None, Node, list[tuple[set[int], tuple[int, ...]]]]:
        """Return the new structure S_w, the donated leaf d_w, and unplaced relations."""
        if w.is_leaf():
            return None, fresh_leaf(w), []
        a, b = w.children
        left_tree, consumed, left_pending = build(a)
        right_tree, donated, right_pending = build(b)
        bag = tuple(sorted(set(w.bag) | {consumed.leaf_input, donated.leaf_input}))
        pending = [*left_pending, *right_pending, (w.relation, w.bag)]
        if left_tree is None and right_tree is None:
            return consumed, donated, pending
        for _, pending_bag in pending:
            check(
                set(pending_bag) <= set(bag),
                "a relation must fit the bag of its new node",
            )
        relation = relation_from_constraints(bag, pending)
        if left_tree is None:
            node = Node(bag, relation, [right_tree, consumed])
        elif right_tree is None:
            node = Node(bag, relation, [left_tree, consumed])
        else:
            inner = Node(bag, set(valuations(bag)), [right_tree, consumed])
            node = Node(bag, relation, [left_tree, inner])
        return node, donated, []

    tree, donated, pending = build(root)
    check(tree is not None and not pending, "the root must not be a cherry here")
    top_bag = tuple(sorted({output, donated.leaf_input}))
    return Node(top_bag, set(valuations(top_bag)), [tree, donated])


def orient_leaf_children_right(root: Node) -> None:
    """Swap children so that a leaf child is the right child where possible."""
    for node in all_nodes(root):
        if not node.is_leaf() and left(node).is_leaf() and not right(node).is_leaf():
            node.children.reverse()


# ---------------------------------------------------------------------------
# Theorem 5.1: the SDD construction
# ---------------------------------------------------------------------------


@dataclass
class Sdd:
    """An SDD whose nodes are keyed by identity.

    A decision node's kind is ("decision", vtree node, elements), where the
    elements are (prime key, sub key) pairs.
    """

    kinds: dict[object, tuple] = field(default_factory=dict)

    def size(self) -> int:
        """Return the number of elements over all decision nodes."""
        return sum(
            len(kind[2]) for kind in self.kinds.values() if kind[0] == "decision"
        )

    def decision_count(self) -> int:
        """Return the number of decision nodes."""
        return sum(1 for kind in self.kinds.values() if kind[0] == "decision")


class Builder:
    """Build the SDD of Theorem 5.1 from an analyzed RTD.

    Witnesses are full input assignments. A pair cell or join node is created
    once per identity; the witnesses of its first request are used to build it.
    """

    def __init__(self, analysis: Analysis, accepting: set[int]) -> None:
        """Prepare the builder; accepting is the set Acc of root valuations."""
        self.analysis = analysis
        self.accepting = accepting
        self.sdd = Sdd()
        self.pending: list[tuple[object, Node, tuple[int, int], tuple[int, int]]] = []
        self.false = self.constant(0)

    def constant(self, bit: int) -> object:
        """Return the key of a constant node."""
        key = ("constant", bit)
        self.sdd.kinds[key] = ("constant", bit)
        return key

    def literal(self, x: int, bit: int) -> object:
        """Return the key of a literal node."""
        key = ("literal", x, bit)
        self.sdd.kinds[key] = ("literal", x, bit)
        return key

    def state(self, node: Node, assignment: int) -> int:
        """Return st_t(w): the solution's valuation of node's bag on assignment w."""
        return self.analysis.state[node][assignment]

    def interface(self, node: Node) -> tuple[int, ...]:
        """Return I(t): the vertices node's bag shares with its parent's bag."""
        parent = self.analysis.parents[node]
        if parent is None:
            raise CheckFailedError("the root has no interface")
        return tuple(v for v in node.bag if v in parent.bag)

    def request(
        self, kind: str, node: Node, states: tuple[int, int], witnesses: tuple[int, int]
    ) -> object:
        """Return the key of a cell or join node, scheduling its construction."""
        key = (kind, id(node), states)
        if key not in self.sdd.kinds:
            self.sdd.kinds[key] = ("pending", node)
            self.pending.append((key, node, states, witnesses))
        return key

    def cell(self, node: Node, witnesses: tuple[int, int]) -> object:
        """Return Cell_t(st_t(w0), st_t(w1))."""
        states = (self.state(node, witnesses[0]), self.state(node, witnesses[1]))
        if node.is_leaf():
            check(states[0] == states[1], "a nonempty leaf cell has one state")
            return self.literal(node.leaf_input, states[0])
        return self.request("cell", node, states, witnesses)

    def join_node(self, node: Node, witnesses: tuple[int, int]) -> object:
        """Return Join_t(st_t(w0)|I(t), st_t(w1)|I(t))."""
        shared = self.interface(node)
        states = (
            project(self.state(node, witnesses[0]), node.bag, shared),
            project(self.state(node, witnesses[1]), node.bag, shared),
        )
        if node.is_leaf():
            x = node.leaf_input
            if x not in shared:
                return self.constant(1)
            if states[0] != states[1]:
                return self.false
            return self.literal(x, states[0])
        return self.request("join", node, states, witnesses)

    def agrees(self, tau: int, child: Node, sigma: int, node: Node) -> bool:
        """Return whether a child valuation and a node valuation agree on I(child)."""
        shared = tuple(v for v in child.bag if v in node.bag)
        return project(tau, child.bag, shared) == project(sigma, node.bag, shared)

    def decide(
        self, node: Node, witnesses: tuple[int, int], sub_for
    ) -> list[tuple[object, object]]:
        """Return elements whose primes are the fibers of x_a ↦ (st_a(w0[a←x_a]), st_a(w1[a←x_a])).

        sub_for maps a fiber's state pair and new witnesses to the sub's key.
        """
        a = left(node)
        mask = self.analysis.inputs_below[a]
        fibers: dict[tuple[int, int], int] = {}
        x_a = mask
        while True:
            pair = (
                self.state(a, x_a | (witnesses[0] & ~mask)),
                self.state(a, x_a | (witnesses[1] & ~mask)),
            )
            fibers.setdefault(pair, x_a)
            if x_a == 0:
                break
            x_a = (x_a - 1) & mask
        elements = []
        for pair, representative in fibers.items():
            new_witnesses = (
                representative | (witnesses[0] & ~mask),
                representative | (witnesses[1] & ~mask),
            )
            elements.append((self.cell(a, new_witnesses), sub_for(pair, new_witnesses)))
        return elements

    def build_cell(
        self, node: Node, states: tuple[int, int], witnesses: tuple[int, int]
    ) -> list:
        """Decide a pair cell at an internal node (Lemma 5.4)."""
        a, b = node.children

        def sub_for(pair: tuple[int, int], new_witnesses: tuple[int, int]) -> object:
            if all(self.agrees(pair[i], a, states[i], node) for i in range(2)):
                return self.join_node(b, new_witnesses)
            return self.false

        return self.decide(node, witnesses, sub_for)

    def build_join(
        self, node: Node, states: tuple[int, int], witnesses: tuple[int, int]
    ) -> list:
        """Decide a join at an internal right child (Lemma 5.5)."""
        a, b = node.children
        shared = self.interface(node)
        below = tuple(v for v in a.bag if v in node.bag)
        allowed = []
        for i in range(2):
            sigmas = [
                s for s in node.relation if project(s, node.bag, shared) == states[i]
            ]
            allowed.append({project(s, node.bag, below) for s in sigmas})

        def sub_for(pair: tuple[int, int], new_witnesses: tuple[int, int]) -> object:
            if all(project(pair[i], a.bag, below) in allowed[i] for i in range(2)):
                return self.join_node(b, new_witnesses)
            return self.false

        return self.decide(node, witnesses, sub_for)

    def build(self) -> object:
        """Build the whole SDD (Lemma 5.6 at the root) and return the root's key."""
        root = self.analysis.root
        a, leaf = root.children
        y = leaf.leaf_input
        below = tuple(v for v in a.bag if v in root.bag)
        allowed = []
        for value in range(2):
            sigmas = [
                s
                for s in root.relation & self.accepting
                if y not in root.bag or value_in(s, root.bag, y) == value
            ]
            allowed.append({project(s, root.bag, below) for s in sigmas})

        def sub_for(pair: tuple[int, int], _witnesses: tuple[int, int]) -> object:
            on = [
                project(pair[value], a.bag, below) in allowed[value]
                for value in range(2)
            ]
            if on[0] and on[1]:
                return self.constant(1)
            if on[1]:
                return self.literal(y, 1)
            if on[0]:
                return self.literal(y, 0)
            return self.false

        root_key = ("root",)
        self.sdd.kinds[root_key] = (
            "decision",
            root,
            self.decide(root, (0, 1 << y), sub_for),
        )
        while self.pending:
            key, node, states, witnesses = self.pending.pop()
            if key[0] == "cell":
                elements = self.build_cell(node, states, witnesses)
            else:
                elements = self.build_join(node, states, witnesses)
            self.sdd.kinds[key] = ("decision", node, elements)
        return root_key


def subtree(node: Node) -> set[Node]:
    """Return the nodes below node, including node."""
    return set(all_nodes(node))


def check_sdd(analysis: Analysis, sdd: Sdd, root_key: object, function: int) -> None:
    """Check that sdd is an SDD for the vtree that computes function.

    Checks Darwiche's conditions at every decision node at vtree node t: each
    prime is a decision node at the left child of t or a literal of the left
    child's input, each sub is a decision node at the right child or a literal
    of its input or a constant; the primes are nonempty, mutually exclusive,
    and exhaustive. Also checks every pair cell and join against its
    definition from the RTD's cells (Definition 5.2).
    """
    full = analysis.instance.full
    values = analysis.instance.values
    functions: dict[object, int] = {}

    def respects(part: object, child: Node, *, constant_ok: bool) -> bool:
        kind = sdd.kinds[part]
        if kind[0] == "decision":
            return kind[1] is child
        if kind[0] == "literal":
            return child.leaf_input == kind[1]
        return constant_ok

    def function_of(key: object) -> int:
        if key in functions:
            return functions[key]
        kind = sdd.kinds[key]
        if kind[0] == "constant":
            result = full if kind[1] else 0
        elif kind[0] == "literal":
            result = values[kind[1]] if kind[2] else full ^ values[kind[1]]
        else:
            node, elements = kind[1], kind[2]
            union, result = 0, 0
            for prime, sub in elements:
                check(
                    respects(prime, left(node), constant_ok=False),
                    "primes must respect the left child",
                )
                check(
                    respects(sub, right(node), constant_ok=True),
                    "subs must respect the right child",
                )
                prime_function = function_of(prime)
                check(prime_function != 0, "primes must be consistent")
                check(union & prime_function == 0, "primes must be mutually exclusive")
                union |= prime_function
                result |= prime_function & function_of(sub)
            check(union == full, "primes must be exhaustive")
        functions[key] = result
        return result

    check(function_of(root_key) == function, "the SDD must compute the function")
    for key, kind in sdd.kinds.items():
        if not (isinstance(key, tuple) and key[0] in ("cell", "join")):
            continue
        node = kind[1]
        cells = analysis.cells[node]
        if key[0] == "cell":
            expected = cells.get(key[2][0], 0) & cells.get(key[2][1], 0)
        else:
            parent = analysis.parents[node]
            shared = tuple(v for v in node.bag if v in parent.bag)
            expected = full
            for state in key[2]:
                union = 0
                for sigma, cell in cells.items():
                    if project(sigma, node.bag, shared) == state:
                        union |= cell
                expected &= union
        check(
            function_of(key) == expected,
            f"every {key[0]} node must compute its definition",
        )


def size_bound(root: Node) -> int:
    """Return the bound of Theorem 5.1 on the number of elements for this RTD."""
    parents = parent_map(root)
    total = 0
    for node in all_nodes(root):
        if node.is_leaf():
            continue
        elements = (1 << len(left(node).bag)) ** 2
        parent = parents[node]
        identities = (
            (1 << len(node.bag)) ** 2 if parent is None or left(parent) is node else 0
        )
        if parent is not None and right(parent) is node:
            identities += (1 << len(set(node.bag) & set(parent.bag))) ** 2
        if parent is None:
            identities = 1
        total += identities * elements
    return total


def build_and_check_sdd(instance: Instance, vtree: Node) -> tuple[Sdd, Analysis]:
    """Check the RTD and its shape, build the SDD, and check the SDD."""
    analysis = check_rtd(instance, vtree)
    check_shape(vtree)
    accepting = {
        s for s in valuations(vtree.bag) if value_in(s, vtree.bag, instance.output) == 1
    }
    builder = Builder(analysis, accepting)
    root_key = builder.build()
    check_sdd(analysis, builder.sdd, root_key, instance.values[instance.output])
    check(
        builder.sdd.size() <= size_bound(vtree), "the SDD must be within the size bound"
    )
    return builder.sdd, analysis


# ---------------------------------------------------------------------------
# Canonical (compressed and trimmed) SDDs, for comparison
# ---------------------------------------------------------------------------


def linear_vtree(order: list[int], *, right_linear: bool) -> Node:
    """Return a linear vtree over the inputs in order.

    A right-linear vtree (every left child a leaf) gives OBDDs with the order;
    in a left-linear vtree every right child is a leaf and the first input is
    deepest.
    """
    leaves = [Node((x,), {0, 1}, leaf_input=x) for x in order]
    if right_linear:
        tree = leaves[-1]
        for leaf in reversed(leaves[:-1]):
            tree = Node((), set(), [leaf, tree])
        return tree
    tree = leaves[0]
    for leaf in leaves[1:]:
        tree = Node((), set(), [tree, leaf])
    return tree


def vtree_inputs_in_order(root: Node) -> list[int]:
    """Return the inputs at the leaves from left to right."""
    return [node.leaf_input for node in all_nodes(root) if node.leaf_input is not None]


def canonical_sdd_size(function: int, num_inputs: int, root: Node) -> int:
    """Return the number of elements of the compressed, trimmed SDD on the vtree.

    The canonical SDD is built from its semantic definition: a function is
    decomposed at the deepest vtree node whose inputs contain its support, and
    the primes are the classes of left assignments that give the same sub.
    """
    size = 1 << num_inputs
    full = (1 << size) - 1
    bits = input_bitsets(num_inputs)
    nodes = all_nodes(root)
    masks = {node: input_mask(node) for node in nodes}
    depth = {root: 0}
    for node in nodes:
        for child in node.children:
            depth[child] = depth[node] + 1

    def support(g: int) -> int:
        mask = 0
        for i in range(num_inputs):
            low = g & ~bits[i] & full
            high = g & bits[i]
            if high >> (1 << i) != low:
                mask |= 1 << i
        return mask

    def restrict(g: int, assignment_mask: int, assignment: int) -> int:
        result = 0
        for a in range(size):
            if (g >> ((a & ~assignment_mask) | assignment)) & 1:
                result |= 1 << a
        return result

    cylinders: dict[tuple[int, int], int] = {}

    def cylinder(assignment_mask: int, assignment: int) -> int:
        key = (assignment_mask, assignment)
        if key not in cylinders:
            result = 0
            for a in range(size):
                if a & assignment_mask == assignment:
                    result |= 1 << a
            cylinders[key] = result
        return cylinders[key]

    memo: dict[int, int] = {}

    def decompose(g: int) -> int:
        if g in (0, full):
            return 0
        if g in memo:
            return memo[g]
        mask = support(g)
        node = max(
            (node for node in nodes if masks[node] & mask == mask),
            key=lambda node: depth[node],
        )
        if node.is_leaf():
            memo[g] = 0
            return 0
        mask_left = masks[left(node)]
        groups: dict[int, int] = {}
        x_l = mask_left
        while True:
            residual = restrict(g, mask_left, x_l)
            groups[residual] = groups.get(residual, 0) | cylinder(mask_left, x_l)
            if x_l == 0:
                break
            x_l = (x_l - 1) & mask_left
        total = len(groups)
        for residual, prime in groups.items():
            total += decompose(prime) + decompose(residual)
        memo[g] = total
        return total

    return decompose(function)
