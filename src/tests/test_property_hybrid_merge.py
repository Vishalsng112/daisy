# Feature: daisy-codebase-rewrite, Property 6: HYBRID merge preserves order and uniqueness
"""Property test: HYBRID merge preserves order and uniqueness.

**Validates: Requirements 2.6**

For any two lists of integers (LAUREL_BETTER positions and LLM positions),
the HYBRID merge SHALL produce a list containing all LAUREL_BETTER positions
first in original order, followed by LLM positions not already present,
with no duplicates from the merge.

Strategy: generate two random lists of ints, create stub inferers returning
those lists, create HybridPositionStrategy, call _do_infer, verify properties.
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings
from hypothesis import strategies as st

from src.daisy.position_inference.base import PositionInferer
from src.daisy.position_inference.hybrid_strategy import HybridPositionStrategy


# --- Stub inferer that returns a fixed list ---

class StubPositionInferer(PositionInferer):
    """Returns a predetermined list of positions."""

    def __init__(self, positions: list[int]):
        super().__init__(name="stub", cache_dir=None)
        self._positions = positions

    def _do_infer(self, method_text: str, error_output: str, **kwargs: Any) -> list[int]:
        return list(self._positions)


# --- Hypothesis strategies ---

positions_st = st.lists(
    st.integers(min_value=0, max_value=10_000),
    min_size=0,
    max_size=30,
)


# --- Property test ---

@settings(max_examples=100)
@given(laurel_positions=positions_st, llm_positions=positions_st)
def test_hybrid_merge_preserves_order_and_uniqueness(
    laurel_positions: list[int],
    llm_positions: list[int],
) -> None:
    """HYBRID merge: laurel first in order, unique llm after, no duplicates."""
    laurel_stub = StubPositionInferer(laurel_positions)
    llm_stub = StubPositionInferer(llm_positions)

    hybrid = HybridPositionStrategy(
        laurel_better_inferer=laurel_stub,
        llm_inferer=llm_stub,
        cache_dir=None,
    )

    result = hybrid._do_infer(
        method_text="method Foo() { }",
        error_output="error: assertion might not hold",
    )

    # Expected: laurel_positions + [p for p in llm_positions if p not in laurel_positions]
    expected = laurel_positions + [p for p in llm_positions if p not in laurel_positions]

    # 1. Result matches expected merge logic
    assert result == expected, f"Expected {expected}, got {result}"

    # 2. All laurel positions appear first, in original order
    laurel_len = len(laurel_positions)
    assert result[:laurel_len] == laurel_positions

    # 3. Remaining elements are LLM positions not in laurel set
    laurel_set = set(laurel_positions)
    tail = result[laurel_len:]
    for p in tail:
        assert p not in laurel_set, f"Duplicate {p} found in tail (already in laurel)"

    # 4. No element from laurel_positions appears in the tail
    #    (the merge filters out LLM positions already in laurel, but does NOT
    #    deduplicate within LLM's own list — that's the input's business)
    for p in tail:
        assert p not in laurel_set, f"LLM position {p} duplicates a laurel position"
