# Feature: daisy-codebase-rewrite, Property 4: LAUREL output parsing
"""Property test: LAUREL output parsing.

**Validates: Requirements 2.3**

For any method text with LAUREL placeholder tags inserted at various
positions, _parse_output SHALL extract the correct 0-based line numbers
of the original code lines where tags were placed.

Strategy: generate a list of regular code lines, pick random positions
to insert LAUREL assertion tags, build the combined output, call
_parse_output, verify returned line numbers match expected positions.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.daisy.position_inference.laurel_strategy import (
    LAURELPositionStrategy,
    LAUREL_ASSERTION_TAG,
)


# --- Hypothesis strategies ---

# Generate a non-empty list of regular code lines (no tag substring)
# Characters that Python splitlines() treats as line breaks
_LINE_BREAK_CHARS = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"

_code_line_st = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters="<>" + _LINE_BREAK_CHARS,
    ),
    min_size=1,
    max_size=80,
).filter(lambda s: LAUREL_ASSERTION_TAG not in s)

_code_lines_st = st.lists(_code_line_st, min_size=1, max_size=50)


@st.composite
def laurel_output_st(draw):
    """Build LAUREL output: code lines with tags inserted at random positions.

    Returns (output_string, expected_0based_positions).

    _parse_output algorithm: for each tag at output idx, with added_lines
    tags seen so far (incremented before recording), position = idx - added_lines.

    We insert tag lines *after* code lines at chosen positions so that
    the formula yields the expected original line index.

    If tag is inserted after code_lines[i], it appears at output index
    (i + tags_before_i + 1). At that point added_lines = tags_before_i + 1.
    So position = (i + tags_before_i + 1) - (tags_before_i + 1) = i. ✓
    """
    code_lines = draw(_code_lines_st)
    n = len(code_lines)

    # Pick unique sorted positions (0-based original line indices)
    positions = draw(
        st.lists(
            st.integers(min_value=0, max_value=n - 1),
            min_size=0,
            max_size=min(n, 20),
            unique=True,
        )
    )
    positions = sorted(positions)
    pos_set = set(positions)

    # Build output: code line, then tag if this position is selected
    result_lines: list[str] = []
    for i, line in enumerate(code_lines):
        result_lines.append(line)
        if i in pos_set:
            result_lines.append(LAUREL_ASSERTION_TAG)

    output = "\n".join(result_lines)
    return output, positions


# --- Property test ---


@settings(max_examples=100)
@given(data=laurel_output_st())
def test_laurel_parse_output_extracts_correct_positions(data):
    """Tags inserted at known positions → _parse_output returns those positions."""
    output, expected_positions = data

    result = LAURELPositionStrategy._parse_output(output)

    assert result == expected_positions, (
        f"Expected {expected_positions}, got {result}"
    )


@settings(max_examples=100)
@given(code_lines=_code_lines_st)
def test_laurel_parse_output_no_tags_returns_empty(code_lines):
    """Output with no tags → empty list."""
    output = "\n".join(code_lines)
    result = LAURELPositionStrategy._parse_output(output)
    assert result == [], f"Expected [], got {result}"
