# Feature: daisy-codebase-rewrite, Property 11: Behavioral equivalence with current pipeline
"""Property test: zip_with_empty_indexed behavioral equivalence.

**Validates: Requirements 13.1, 15.3**

For any list[list[str]] of assertion candidates, the new
zip_with_empty_indexed (src/daisy/verification/parallel_combo.py)
SHALL produce identical output to the original implementation in
src/llm/llm_pipeline.py.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings
from hypothesis import strategies as st

# New implementation
from src.daisy.verification.parallel_combo import (
    zip_with_empty_indexed as new_zip_with_empty_indexed,
)


# Original implementation copied verbatim from src/llm/llm_pipeline.py
# (cannot import directly — old module has unresolvable transitive deps)
def old_zip_with_empty_indexed(
    assertions: list[list[str]],
) -> tuple[list[list[str]], list[list[int]]]:
    """Exact copy of src/llm/llm_pipeline.py::zip_with_empty_indexed."""
    n = len(assertions)
    if not assertions:
        return [], []

    min_len = min(map(len, assertions))

    zipped_vals = [list(row) for row in zip(*(lst[:min_len] for lst in assertions))]
    zipped_inds = [[i] * n for i in range(min_len)]

    leftover_vals: list[list[str]] = []
    leftover_inds: list[list[int]] = []

    if n != 1:
        for list_idx, lst in enumerate(assertions):
            for item_idx, val in enumerate(lst):
                v_row = [val if i == list_idx else "" for i in range(n)]
                i_row = [item_idx if i == list_idx else -1 for i in range(n)]
                leftover_vals.append(v_row)
                leftover_inds.append(i_row)

    return zipped_vals + leftover_vals, zipped_inds + leftover_inds

# --- Hypothesis strategies ---

# Generate list of lists of strings: 1-5 positions, 1-10 candidates each
candidates_st = st.lists(
    st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
            min_size=1,
            max_size=30,
        ),
        min_size=1,
        max_size=10,
    ),
    min_size=1,
    max_size=5,
)


# --- Property test ---


@settings(max_examples=100)
@given(candidates=candidates_st)
def test_zip_with_empty_indexed_behavioral_equivalence(
    candidates: list[list[str]],
) -> None:
    """New zip_with_empty_indexed produces identical output to old implementation."""
    old_vals, old_inds = old_zip_with_empty_indexed(candidates)
    new_vals, new_inds = new_zip_with_empty_indexed(candidates)

    assert old_vals == new_vals, (
        f"Values differ.\nOld: {old_vals}\nNew: {new_vals}"
    )
    assert old_inds == new_inds, (
        f"Indices differ.\nOld: {old_inds}\nNew: {new_inds}"
    )


@settings(max_examples=100)
@given(candidates=candidates_st)
def test_zip_with_empty_indexed_output_structure(
    candidates: list[list[str]],
) -> None:
    """Both values and indices lists have same length; each row has len == n positions."""
    vals, inds = new_zip_with_empty_indexed(candidates)
    n = len(candidates)

    # vals and inds same length
    assert len(vals) == len(inds)

    # each row has n elements
    for row in vals:
        assert len(row) == n
    for row in inds:
        assert len(row) == n


def test_zip_with_empty_indexed_empty_input_equivalence() -> None:
    """Empty input produces identical empty output from both implementations."""
    old_vals, old_inds = old_zip_with_empty_indexed([])
    new_vals, new_inds = new_zip_with_empty_indexed([])
    assert old_vals == new_vals == []
    assert old_inds == new_inds == []
