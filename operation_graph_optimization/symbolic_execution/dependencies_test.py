from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Access:
    name: str
    particle: str
    writes: bool
    after: tuple[str, ...] = ()


@dataclass
class Boundary:
    leading_reads: set[str] = field(default_factory=set)
    first_write: str | None = None
    last_write: str | None = None
    trailing_reads: set[str] = field(default_factory=set)


@dataclass
class Summary:
    particles: dict[str, Boundary] = field(default_factory=dict)
    edges: set[tuple[str, str]] = field(default_factory=set)


def singleton(access: Access):
    if access.writes:
        boundary = Boundary(first_write=access.name, last_write=access.name)
    else:
        boundary = Boundary({access.name}, trailing_reads={access.name})
    return Summary(
        {access.particle: boundary},
        {(earlier, access.name) for earlier in access.after},
    )


def compose(earlier: Summary, later: Summary):
    # Only boundary information is inspected; internal accesses remain opaque.
    result = Summary(dict(earlier.particles), earlier.edges | later.edges)
    for particle, right in later.particles.items():
        if particle not in earlier.particles:
            result.particles[particle] = right
            continue
        left = earlier.particles[particle]
        if left.last_write is not None:
            for reader in right.leading_reads:
                result.edges.add((left.last_write, reader))
        if right.first_write is not None:
            if left.trailing_reads:
                for reader in left.trailing_reads:
                    result.edges.add((reader, right.first_write))
            elif left.last_write is not None and not right.leading_reads:
                result.edges.add((left.last_write, right.first_write))

        if left.first_write is None:
            leading = left.leading_reads | right.leading_reads
            first = right.first_write
        else:
            leading = left.leading_reads
            first = left.first_write
        if right.last_write is None:
            trailing = left.trailing_reads | right.trailing_reads
            last = left.last_write
        else:
            trailing = right.trailing_reads
            last = right.last_write
        result.particles[particle] = Boundary(leading, first, last, trailing)
    return result


def summarize(accesses: list[Access]):
    result = Summary()
    for access in accesses:
        result = compose(result, singleton(access))
    return result


def conflict_oracle(accesses: list[Access]):
    # Deliberately quadratic and independent of the boundary construction.
    edges: set[tuple[str, str]] = set()
    for index, later in enumerate(accesses):
        for earlier in accesses[:index]:
            if earlier.particle == later.particle and (earlier.writes or later.writes):
                edges.add((earlier.name, later.name))
        for earlier_name in later.after:
            edges.add((earlier_name, later.name))
    return edges


def respects(order: tuple[str, ...], edges: set[tuple[str, str]]):
    indexes = {name: index for index, name in enumerate(order)}
    return all(indexes[earlier] < indexes[later] for earlier, later in edges)


def closure(names: list[str], edges: set[tuple[str, str]]):
    reachable: dict[str, set[str]] = {}
    for name in names:
        ancestors: set[str] = set()
        for earlier, later in edges:
            if later == name:
                ancestors.add(earlier)
                ancestors.update(reachable[earlier])
        reachable[name] = ancestors
    return reachable


def observations(accesses: list[Access], order: tuple[str, ...]):
    by_name = {access.name: access for access in accesses}
    storage: dict[str, str] = {}
    reads: dict[str, str] = {}
    writes: dict[str, list[str]] = {}
    for name in order:
        access = by_name[name]
        if access.writes:
            storage[access.particle] = name
            writes.setdefault(access.particle, []).append(name)
        else:
            reads[name] = storage.get(access.particle, "initial")
    # Write labels are oracle instrumentation, not runtime value versions.
    return reads, storage, writes


def test_every_schedule_of_every_four_access_two_particle_program():
    choices = (("A", False), ("A", True), ("B", False), ("B", True))
    for program in itertools.product(choices, repeat=4):
        accesses: list[Access] = []
        for index, (particle, writes) in enumerate(program):
            accesses.append(Access(str(index), particle, writes))
        summary = summarize(accesses)
        oracle = conflict_oracle(accesses)
        names = tuple(access.name for access in accesses)
        expected = observations(accesses, names)
        for order in itertools.permutations(names):
            accepted = respects(order, summary.edges)
            assert accepted == respects(order, oracle)
            assert accepted == (observations(accesses, order) == expected)


def test_nested_summaries_match_whole_program_for_random_accesses():
    generator = random.Random(114402)  # noqa: S311 - Reproducible research oracle.
    for _ in range(1000):
        accesses: list[Access] = []
        summaries: list[Summary] = []
        for index in range(24):
            prior: tuple[str, ...] = ()
            if index and generator.randrange(3) == 0:
                prior = (str(generator.randrange(index)),)
            access = Access(
                str(index),
                str(generator.randrange(5)),
                bool(generator.randrange(2)),
                prior,
            )
            accesses.append(access)
            summaries.append(singleton(access))
        while len(summaries) > 1:
            index = generator.randrange(len(summaries) - 1)
            summaries[index : index + 2] = [
                compose(summaries[index], summaries[index + 1])
            ]
        names = [access.name for access in accesses]
        assert closure(names, summaries[0].edges) == closure(
            names, conflict_oracle(accesses)
        )
        assert summaries[0].particles == summarize(accesses).particles


def test_caller_can_consume_one_callee_result_before_unrelated_work():
    caller = summarize([Access("caller.set(A)", "A", writes=True)])
    callee = summarize(
        [
            Access("callee.read(A)", "A", writes=False),
            Access("callee.write(B)", "B", writes=True, after=("callee.read(A)",)),
            Access("callee.write(C)", "C", writes=True),
        ]
    )
    later = summarize([Access("caller.read(B)", "B", writes=False)])
    result = compose(compose(caller, callee), later)
    assert result.edges == {
        ("caller.set(A)", "callee.read(A)"),
        ("callee.read(A)", "callee.write(B)"),
        ("callee.write(B)", "caller.read(B)"),
    }
    assert respects(
        (
            "caller.set(A)",
            "callee.read(A)",
            "callee.write(B)",
            "caller.read(B)",
            "callee.write(C)",
        ),
        result.edges,
    )
    assert respects(
        (
            "callee.write(C)",
            "caller.set(A)",
            "callee.read(A)",
            "callee.write(B)",
            "caller.read(B)",
        ),
        result.edges,
    )


def test_prior_caller_read_does_not_delay_callee_reads():
    result = compose(
        summarize([Access("caller.read(A)", "A", writes=False)]),
        summarize(
            [
                Access("callee.read(A)", "A", writes=False),
                Access("callee.write(A)", "A", writes=True),
            ]
        ),
    )
    assert result.edges == {
        ("caller.read(A)", "callee.write(A)"),
        ("callee.read(A)", "callee.write(A)"),
    }


def test_read_completion_releases_write_without_waiting_for_arithmetic():
    result = summarize(
        [
            Access("read(A)", "A", writes=False),
            Access(
                "write(B, captured_A_plus_one)", "B", writes=True, after=("read(A)",)
            ),
            Access("write(A)", "A", writes=True),
        ]
    )
    assert result.edges == {
        ("read(A)", "write(B, captured_A_plus_one)"),
        ("read(A)", "write(A)"),
    }


def test_repeated_calls_do_not_share_completion_or_local_particles():
    calls: list[Summary] = []
    for invocation in ("one", "two"):
        calls.append(
            summarize(
                [
                    Access(
                        f"{invocation}.write(local)", f"{invocation}.local", writes=True
                    ),
                    Access(
                        f"{invocation}.read(local)", f"{invocation}.local", writes=False
                    ),
                    Access(f"{invocation}.write(shared)", "shared", writes=True),
                ]
            )
        )
    assert compose(calls[0], calls[1]).edges == {
        ("one.write(local)", "one.read(local)"),
        ("two.write(local)", "two.read(local)"),
        ("one.write(shared)", "two.write(shared)"),
    }


def test_caller_known_destructor_is_inserted_at_destruction_not_after_caller():
    before = summarize([Access("caller.write(old)", "old", writes=True)])
    destructor = summarize(
        [
            Access("destructor.read(old)", "old", writes=False),
            Access(
                "destructor.write(shared)",
                "shared",
                writes=True,
                after=("destructor.read(old)",),
            ),
        ]
    )
    after = summarize(
        [
            Access("caller.write(replacement)", "replacement", writes=True),
            Access("caller.read(shared)", "shared", writes=False),
        ]
    )
    assert compose(compose(before, destructor), after).edges == {
        ("caller.write(old)", "destructor.read(old)"),
        ("destructor.read(old)", "destructor.write(shared)"),
        ("destructor.write(shared)", "caller.read(shared)"),
    }


def test_lifetime_end_waits_for_all_reads_but_not_unrelated_work():
    # Exclusive begin/end events reuse the conflict protocol only for this model.
    result = summarize(
        [
            Access("allocate(A)", "A", writes=True),
            Access("constructor.write(A)", "A", writes=True),
            Access("callee.read(A)", "A", writes=False),
            Access("destructor.read(A)", "A", writes=False),
            Access("release(A)", "A", writes=True),
            Access(
                "destructor.write(B)", "B", writes=True, after=("destructor.read(A)",)
            ),
        ]
    )
    assert result.edges == {
        ("allocate(A)", "constructor.write(A)"),
        ("constructor.write(A)", "callee.read(A)"),
        ("constructor.write(A)", "destructor.read(A)"),
        ("callee.read(A)", "release(A)"),
        ("destructor.read(A)", "release(A)"),
        ("destructor.read(A)", "destructor.write(B)"),
    }


def test_destructor_order_is_observable_when_symbols_are_mutable():
    accesses = [
        Access("destructor_one.write(A)", "A", writes=True),
        Access("destructor_two.write(A)", "A", writes=True),
        Access("caller.read(A)", "A", writes=False),
    ]
    first = tuple(access.name for access in accesses)
    second = (first[1], first[0], first[2])
    assert observations(accesses, first) != observations(accesses, second)
