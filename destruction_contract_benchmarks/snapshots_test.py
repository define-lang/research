from __future__ import annotations

import random

import pytest

from destruction_contract_benchmarks import snapshots, workloads


@pytest.mark.parametrize("variant", snapshots.FACTORIES)
def test_callee_precedence_and_independent_callers(variant: str):
    occupied = snapshots.Occupancy(1, 123)
    initial = {("parent",): occupied, ("parent", "empty"): snapshots.EMPTY}
    original = snapshots.FACTORIES[variant](initial)
    first = original.with_caller(
        {("parent",): snapshots.ERROR, ("parent", "first"): occupied}
    )
    second = original.with_caller({("parent", "second"): snapshots.ERROR})
    assert dict(original.items()) == initial
    assert dict(original.with_caller(initial).items()) == initial
    assert dict(first.items()) == initial | {("parent", "first"): occupied}
    assert dict(second.items()) == initial | {("parent", "second"): snapshots.ERROR}
    assert original.get(("absent",)) is None
    assert first.get(("parent", "empty")) is snapshots.EMPTY
    assert second.get(("parent", "second")) is snapshots.ERROR
    assert first.nearest_occupied_parent(("parent", "missing", "child")) == occupied
    assert first.nearest_occupied_parent(("unknown", "child")) is None


@pytest.mark.parametrize("variant", snapshots.FACTORIES)
def test_retained_versions_match_flat_oracle(variant: str):
    workload = workloads.generate(
        workloads.Configuration(16, 80, 3, 4, 20, caller_shape="branching"), 1_482
    )
    histories = [snapshots.FACTORIES[variant](workload.initial)]
    expected = [workload.initial.copy()]
    for caller in workload.callers:
        next_expected = caller.knowledge | expected[caller.callee]
        expected.append(next_expected)
        histories.append(histories[caller.callee].with_caller(caller.knowledge))
    for actual, oracle in zip(histories, expected, strict=True):
        assert dict(actual.items()) == oracle
        for position, occupancy in oracle.items():
            assert actual.get(position) == occupancy
        assert actual.get(("missing",)) is None


@pytest.mark.parametrize("variant", snapshots.FACTORIES)
def test_dense_batches_and_compaction(variant: str):
    randomizer = random.Random(87)  # noqa: S311 - Reproduce failures across test runs.
    snapshot = snapshots.FACTORIES[variant]({})
    expected: dict[snapshots.Position, snapshots.Occupancy] = {}
    retained: list[snapshots.Snapshot] = []
    oracles: list[dict[snapshots.Position, snapshots.Occupancy]] = []
    for batch in range(40):
        caller: dict[snapshots.Position, snapshots.Occupancy] = {}
        for _ in range(100):
            position = ("parent", str(randomizer.randrange(1_000)), "child")
            caller[position] = snapshots.Occupancy(batch % 3, batch)
        expected = caller | expected
        snapshot = snapshot.with_caller(caller)
        retained.append(snapshot)
        oracles.append(expected)
    for actual, oracle in zip(retained, oracles, strict=True):
        assert dict(actual.items()) == oracle


def test_position_tree_shares_child_state():
    initial = snapshots.PositionTree.from_values(
        {("parent",): snapshots.Occupancy(1, 1), ("parent", "child"): snapshots.EMPTY}
    )
    child_view = initial.at_particle(("parent",))
    assert child_view.top is initial.top.children["parent"]
    assert child_view.get(("child",)) is snapshots.EMPTY
    extended = initial.with_caller({("other",): snapshots.Occupancy(1, 2)})
    assert extended.top.children["parent"] is child_view.top


@pytest.mark.parametrize("variant", snapshots.FACTORIES)
def test_large_base_sparse_additions_and_unchanged_versions(variant: str):
    initial = {(str(index),): snapshots.EMPTY for index in range(512)}
    original = snapshots.FACTORIES[variant](initial)
    history = [original]
    expected = initial.copy()
    for index in range(512, 1_200):
        position = (str(index),)
        expected[position] = snapshots.Occupancy(1, index)
        history.append(history[-1].with_caller({position: expected[position]}))
    assert dict(history[-1].items()) == expected
    assert dict(original.items()) == initial
    assert dict(history[-1].with_caller(expected).items()) == expected
    assert dict(original.with_caller(initial).items()) == initial
    assert dict(history[1].with_caller({("512",): snapshots.ERROR}).items()) == (
        initial | {("512",): snapshots.Occupancy(1, 512)}
    )
