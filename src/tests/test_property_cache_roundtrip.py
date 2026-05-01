# Feature: daisy-codebase-rewrite, Property 2: Cache round-trip preserves data
"""Property test: cache round-trip preserves data.

**Validates: Requirements 1.4, 3.4**

For any base class instance with cache_dir set and empty cache, calling the
inference method SHALL invoke _do_infer, write the result to cache, and a
subsequent call with the same key SHALL return identical data from cache
without invoking _do_infer again.

Tested for BOTH PositionInferer and AssertionInferer.
"""

import sys
import json
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings
from hypothesis import strategies as st

from src.daisy.position_inference.base import PositionInferer
from src.daisy.assertion_inference.base import AssertionInferer


# --- Concrete subclasses that return generated data ---


class StubPositionInferer(PositionInferer):
    """Returns pre-set data from _do_infer and counts calls."""

    def __init__(self, return_data: list[int], cache_dir: Path | None = None):
        super().__init__(name="stub-position", cache_dir=cache_dir)
        self._return_data = return_data
        self.do_infer_count = 0

    def _do_infer(self, method_text: str, error_output: str, **kwargs: Any) -> list[int]:
        self.do_infer_count += 1
        return self._return_data


class StubAssertionInferer(AssertionInferer):
    """Returns pre-set data from _do_infer and counts calls."""

    def __init__(self, return_data: list[list[str]], cache_dir: Path | None = None):
        super().__init__(name="stub-assertion", cache_dir=cache_dir)
        self._return_data = return_data
        self.do_infer_count = 0

    def _do_infer(
        self, method_text_with_placeholders: str, error_output: str, **kwargs: Any
    ) -> list[list[str]]:
        self.do_infer_count += 1
        return self._return_data


# --- Strategies ---

position_data_st = st.lists(st.integers(min_value=0, max_value=1000), min_size=0, max_size=20)

assertion_data_st = st.lists(
    st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
            min_size=1,
            max_size=40,
        ),
        min_size=1,
        max_size=5,
    ),
    min_size=0,
    max_size=10,
)

cache_key_st = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
    min_size=1,
    max_size=20,
)


# --- Property tests ---


@settings(max_examples=100)
@given(generated_positions=position_data_st, cache_key=cache_key_st)
def test_position_cache_roundtrip(
    generated_positions: list[int], cache_key: str, tmp_path_factory
) -> None:
    """Empty cache → _do_infer called once, result cached. Second call → no _do_infer, same data."""
    cache_dir = tmp_path_factory.mktemp("pos_rt")
    inferer = StubPositionInferer(return_data=generated_positions, cache_dir=cache_dir)

    # First call: cache miss → _do_infer called, result written
    result1 = inferer.infer_positions("method text", "error output", cache_key=cache_key)
    assert result1 == generated_positions, f"First call: expected {generated_positions}, got {result1}"
    assert inferer.do_infer_count == 1, f"Expected 1 _do_infer call, got {inferer.do_infer_count}"

    # Verify cache file written
    cache_file = inferer._cache_path(cache_key)
    assert cache_file.exists(), "Cache file not written after first call"
    assert json.loads(cache_file.read_text()) == generated_positions

    # Second call: cache hit → _do_infer NOT called, identical data
    result2 = inferer.infer_positions("method text", "error output", cache_key=cache_key)
    assert result2 == generated_positions, f"Second call: expected {generated_positions}, got {result2}"
    assert inferer.do_infer_count == 1, f"Expected still 1 _do_infer call, got {inferer.do_infer_count}"


@settings(max_examples=100)
@given(generated_assertions=assertion_data_st, cache_key=cache_key_st)
def test_assertion_cache_roundtrip(
    generated_assertions: list[list[str]], cache_key: str, tmp_path_factory
) -> None:
    """Empty cache → _do_infer called once, result cached. Second call → no _do_infer, same data."""
    cache_dir = tmp_path_factory.mktemp("assert_rt")
    inferer = StubAssertionInferer(return_data=generated_assertions, cache_dir=cache_dir)

    # First call: cache miss → _do_infer called, result written
    result1 = inferer.infer_assertions(
        "method with placeholders", "error output", cache_key=cache_key
    )
    assert result1 == generated_assertions, f"First call: expected {generated_assertions}, got {result1}"
    assert inferer.do_infer_count == 1, f"Expected 1 _do_infer call, got {inferer.do_infer_count}"

    # Verify cache file written
    cache_file = inferer._cache_path(cache_key)
    assert cache_file.exists(), "Cache file not written after first call"
    assert json.loads(cache_file.read_text()) == generated_assertions

    # Second call: cache hit → _do_infer NOT called, identical data
    result2 = inferer.infer_assertions(
        "method with placeholders", "error output", cache_key=cache_key
    )
    assert result2 == generated_assertions, f"Second call: expected {generated_assertions}, got {result2}"
    assert inferer.do_infer_count == 1, f"Expected still 1 _do_infer call, got {inferer.do_infer_count}"
