"""Run the SDD construction on many circuits and record the results.

From the repository root, run for example
`uv run --frozen --python 3.14 python circuit_treewidth_sdd/experiments.py random`.
The recorded outputs are in `results/`, and README.md describes them.
"""

from __future__ import annotations

import random

import click
import sdd_construction as sc


def random_circuit(
    rng: random.Random, num_inputs: int, num_gates: int, window: int, max_fan_in: int
) -> sc.Circuit:
    """Return a random circuit whose wires come from the last `window` vertices.

    Small windows give circuits of small treewidth. Gates are AND or OR with
    one to max_fan_in wires, each negated at random, so NOT gates occur too.
    Inputs are used early when possible, and the output is the last gate.
    """
    gates: list[tuple[str, list[tuple[int, bool]]]] = []
    unused = list(range(num_inputs))
    for index in range(num_gates):
        vertex = num_inputs + index
        low = max(0, vertex - window)
        fan_in = min(rng.randint(1, max_fan_in), vertex - low)
        sources: set[int] = set()
        if unused and rng.random() < 0.6:
            sources.add(unused.pop(0))
        while len(sources) < fan_in:
            sources.add(rng.randrange(low, vertex))
        unused = [x for x in unused if x not in sources]
        op = rng.choice(["and", "or"])
        gates.append((op, [(source, rng.random() < 0.5) for source in sorted(sources)]))
    return sc.Circuit(num_inputs, gates, num_inputs + num_gates - 1)


def first_use_order(circuit: sc.Circuit) -> list[int]:
    """Return all vertices with each input placed just before its first use."""
    first_use: dict[int, int] = {}
    for index, (_, wires) in enumerate(circuit.gates):
        for v, _ in wires:
            first_use.setdefault(v, circuit.num_inputs + index)

    def key(v: int) -> tuple[int, int]:
        if v < circuit.num_inputs:
            return (first_use.get(v, circuit.num_vertices), 0)
        return (v, 1)

    return sorted(range(circuit.num_vertices), key=key)


def tree_pipeline(circuit: sc.Circuit, *, split: bool) -> dict[str, int]:
    """Run gate splitting or its clique variant, normalization, leaf donation, and the SDD construction."""
    rtd, instance, decomposition_width = (
        sc.split_rtd(circuit) if split else sc.moral_rtd(circuit)
    )
    sc.check_rtd(instance, rtd)
    width_normalized = sc.width(rtd)
    vtree = sc.donate_leaves(rtd, instance.output)
    sdd, _ = sc.build_and_check_sdd(instance, vtree)
    return {
        "inputs": circuit.num_inputs,
        "gates": len(circuit.gates),
        "k": decomposition_width,
        "width_normalized": width_normalized,
        "width_final": sc.width(vtree),
        "sdd_size": sdd.size(),
        "decision_nodes": sdd.decision_count(),
        "bound": sc.size_bound(vtree),
    }


def path_pipeline(
    circuit: sc.Circuit, order: list[int], *, attach_last: bool, split: bool
) -> dict[str, int]:
    """Run the construction on a path decomposition, giving a left-linear vtree."""
    if split:
        vtree, instance, decomposition_width = sc.split_rtd(
            circuit, order=order, path=True, attach_last=attach_last
        )
    else:
        vtree, instance, decomposition_width = sc.moral_rtd(
            circuit, order=order, path=True, attach_last=attach_last
        )
    for node in sc.all_nodes(vtree):
        if not node.is_leaf():
            sc.check(sc.right(node).is_leaf(), "the vtree must be left-linear")
    sdd, _ = sc.build_and_check_sdd(instance, vtree)
    return {
        "inputs": circuit.num_inputs,
        "gates": len(circuit.gates),
        "pw": decomposition_width,
        "width_final": sc.width(vtree),
        "sdd_size": sdd.size(),
        "decision_nodes": sdd.decision_count(),
        "bound": sc.size_bound(vtree),
    }


def nonconstant_circuits(
    seed: int, count: int, max_inputs: int, max_fan_in: int
) -> list[tuple[int, sc.Circuit]]:
    """Return random circuits that do not compute a constant, with their windows."""
    rng = random.Random(seed)  # noqa: S311 - reproducible test inputs, not secrets
    result = []
    while len(result) < count:
        num_inputs = rng.randint(2, max_inputs)
        num_gates = rng.randint(num_inputs, 2 * num_inputs + 6)
        window = rng.randint(2, 7)
        circuit = random_circuit(rng, num_inputs, num_gates, window, max_fan_in)
        function = circuit.evaluate_all()[circuit.output]
        if function not in (0, (1 << (1 << num_inputs)) - 1):
            result.append((window, circuit))
    return result


@click.group()
def main() -> None:
    """Experiments for the circuit treewidth SDD construction."""


@main.command("random")
@click.option("--seed", default=20261031, help="Random seed.")
@click.option("--count", default=1000, help="Number of random circuits.")
@click.option("--max-inputs", default=10, help="Largest number of inputs.")
@click.option("--max-fan-in", default=3, help="Largest gate fan-in.")
@click.option(
    "--split/--clique",
    default=False,
    help="Use gate splitting (Lemma 7.1) or the clique variant.",
)
def random_command(
    seed: int, count: int, max_inputs: int, max_fan_in: int, *, split: bool
) -> None:
    """Check the tree construction on random circuits of small treewidth."""
    largest_k = 0
    for index, (window, circuit) in enumerate(
        nonconstant_circuits(seed, count, max_inputs, max_fan_in)
    ):
        result = tree_pipeline(circuit, split=split)
        largest_k = max(largest_k, result["k"])
        fields = " ".join(f"{key}={value}" for key, value in result.items())
        click.echo(f"circuit={index} window={window} {fields}")
    click.echo(
        f"all checks passed for {count} circuits; largest decomposition width {largest_k}"
    )


@main.command("path")
@click.option("--seed", default=20261101, help="Random seed.")
@click.option("--count", default=1000, help="Number of random circuits.")
@click.option("--max-inputs", default=10, help="Largest number of inputs.")
@click.option("--max-fan-in", default=3, help="Largest gate fan-in.")
@click.option(
    "--split/--clique",
    default=False,
    help="Use gate splitting (Lemma 7.1) or the clique variant.",
)
def path_command(
    seed: int, count: int, max_inputs: int, max_fan_in: int, *, split: bool
) -> None:
    """Check the left-linear construction on random circuits with path decompositions."""
    rng = random.Random(seed)  # noqa: S311 - reproducible test inputs, not secrets
    largest_pw = 0
    for index, (window, circuit) in enumerate(
        nonconstant_circuits(seed, count, max_inputs, max_fan_in)
    ):
        attach_last = rng.random() < 0.5
        result = path_pipeline(
            circuit, first_use_order(circuit), attach_last=attach_last, split=split
        )
        largest_pw = max(largest_pw, result["pw"])
        fields = " ".join(f"{key}={value}" for key, value in result.items())
        click.echo(f"circuit={index} window={window} {fields}")
    click.echo(
        f"all checks passed for {count} circuits; largest path decomposition width {largest_pw}"
    )


def index_circuit(address_bits: int) -> tuple[sc.Circuit, list[int]]:
    """Return the multiplexer x[y] and a vertex order for a path decomposition.

    Inputs 0 .. 2^m - 1 are the data bits x and the next m inputs are the
    address bits y. The order lists y, then for each q the data bit x[q]
    followed by the gates that test y = q and fold x[q] into the result.
    """
    data = 1 << address_bits
    num_inputs = data + address_bits
    gates: list[tuple[str, list[tuple[int, bool]]]] = []
    order = list(range(data, num_inputs))

    def add(op: str, wires: list[tuple[int, bool]]) -> int:
        gates.append((op, wires))
        vertex = num_inputs + len(gates) - 1
        order.append(vertex)
        return vertex

    result = None
    for q in range(data):
        order.append(q)
        address = [(data + j, not (q >> j) & 1) for j in range(address_bits)]
        test = add("and", [address[0], (q, False)])
        for literal in address[1:]:
            test = add("and", [(test, False), literal])
        result = test if result is None else add("or", [(result, False), (test, False)])
    return sc.Circuit(num_inputs, gates, num_inputs + len(gates) - 1), order


@main.command("index")
@click.option("--max-address-bits", default=3, help="Largest address width m.")
def index_command(max_address_bits: int) -> None:
    """Compare SDD sizes for the multiplexer with the data bits deepest."""
    for address_bits in range(1, max_address_bits + 1):
        circuit, order = index_circuit(address_bits)
        vtree, instance, pw = sc.moral_rtd(circuit, order=order, path=True)
        sdd, _ = sc.build_and_check_sdd(instance, vtree)
        function = instance.values[instance.output]
        inputs = sc.vtree_inputs_in_order(vtree)
        n = circuit.num_inputs
        canonical_same = sc.canonical_sdd_size(function, n, vtree)
        obdd = sc.canonical_sdd_size(
            function, n, sc.linear_vtree(inputs, right_linear=True)
        )
        click.echo(
            f"m={address_bits} n={n} pw={pw} width_final={sc.width(vtree)} constructed_sdd={sdd.size()} "
            f"canonical_sdd_same_vtree={canonical_same} obdd_same_order_as_sdd={obdd} order={inputs}"
        )


@main.command("scaling")
@click.option("--seed", default=20261102, help="Random seed.")
@click.option("--per-size", default=5, help="Circuits per number of inputs.")
@click.option("--max-inputs", default=13, help="Largest number of inputs.")
def scaling_command(seed: int, per_size: int, max_inputs: int) -> None:
    """Report SDD size per input for circuits of bounded width as n grows."""
    rng = random.Random(seed)  # noqa: S311 - reproducible test inputs, not secrets
    for num_inputs in range(4, max_inputs + 1):
        sizes = []
        widths = []
        made = 0
        while made < per_size:
            circuit = random_circuit(rng, num_inputs, 2 * num_inputs, 3, 2)
            function = circuit.evaluate_all()[circuit.output]
            if function in (0, (1 << (1 << num_inputs)) - 1):
                continue
            result = tree_pipeline(circuit, split=False)
            sizes.append(result["sdd_size"])
            widths.append(result["width_final"])
            made += 1
        click.echo(
            f"n={num_inputs} max_width_final={max(widths)} mean_sdd_size={sum(sizes) / len(sizes):.1f} "
            f"mean_size_per_input={sum(sizes) / len(sizes) / num_inputs:.1f} max_sdd_size={max(sizes)}"
        )


if __name__ == "__main__":
    main()
