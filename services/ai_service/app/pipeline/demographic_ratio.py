"""Whole-number demographic shares that add up to 100."""

from __future__ import annotations


def whole_number_shares(counts: list[int]) -> list[int]:
    """
    Turn headcounts into integer percentages.

    Uses the largest-remainder method. When ``counts`` sum to a positive
    total, the returned integers sum to 100. An empty or all-zero list
    returns zeros.

    Arguments:
        counts: Non-negative headcounts, one per demographic bucket.

    Returns:
        One integer percentage per input count.
    """
    total = sum(counts)
    if not counts or total <= 0:
        return [0 for _ in counts]
    floors = [(count * 100) // total for count in counts]
    leftover = 100 - sum(floors)
    order = sorted(
        range(len(counts)),
        key=lambda index: (
            (counts[index] * 100) % total,
            counts[index],
        ),
        reverse=True,
    )
    for index in order[:leftover]:
        floors[index] += 1
    return floors
