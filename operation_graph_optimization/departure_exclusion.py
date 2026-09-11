"""Release-wait cycle check for disjoint pairs with one departure dependency."""

from __future__ import annotations


def permits_entry(
    successors: tuple[int, ...],
    first_completed: int,
    second_started: int,
    second_completed: int,
    exclusion: int,
) -> bool:
    """Check a reverse entry in an already permitted prefix of this fragment."""
    bit = 1 << exclusion
    if first_completed & bit:
        return True
    waiting = (second_started & ~first_completed & ~second_completed) | bit
    following = successors[exclusion]
    # The existing waiting relationships are acyclic, so a newly created cycle
    # must return to this entry. No execution orders or alternative assignments
    # need to be explored for a single-successor departure dependency.
    while waiting & (1 << following):
        if following == exclusion:
            return False
        following = successors[following]
    return True
