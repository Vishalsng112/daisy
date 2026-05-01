# Feature: daisy-codebase-rewrite, Property 1: Cache hit returns cached data without inference
"""Property test: cache hit returns cached data without calling _do_infer.

**Validates: Requirements 1.3, 3.3, 6.2**

For any PositionInferer or AssertionInferer with cache_dir set and a
pre-existing cache file, calling the inference method SHALL return the
cached data and SHALL NOT invoke _do_infer.

Strategies:
- PositionInferer: random list[int] cached, verify _do_infer call count == 0
- AssertionInferer: random list[list[str]] cached, verify _do_infer call count == 0
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


# --- Concrete subclasses with call counters ---

class CountingPositionInferer(PositionInferer):
    """Concrete PositionInferer that counts _do_infer calls."""

    def __init__(self, cache_dir: Path | None = None):
        super().__init__(name="counting-position", cache_dir=cache_dir)
        self.do_infer_count = 0

    def _do_infer(self, method_text: str, error_output: str, **kwargs: Any) -> list[int]:
        self.do_infer_count += 1
        return [999]  # sentinel — should never be returned on cache hit


class CountingAssertionInferer(AssertionInferer):
    """Concrete AssertionInferer that counts _do_infer calls."""

    def __init__(self, cache_dir: Path | None = None):
        super().__init__(name="counting-assertion", cache_dir=cache_dir)
        self.do_infer_count = 0

    def _do_infer(
        self, method_text_with_placeholders: str, error_output: str, **kwargs: Any
    ) -> list[list[str]]:
        self.do_infer_count += 1
        return [["SENTINEL"]]  # should never be returned on cache hit


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
@given(cached_positions=position_data_st, cache_key=cache_key_st)
def test_position_cache_hit_returns_cached_no_infer(
    cached_positions: list[int], cache_key: str, tmp_path_factory
) -> None:
    """Pre-populated position cache → return cached data, _do_infer NOT called."""
    cache_dir = tmp_path_factory.mktemp("pos_cache")
    inferer = CountingPositionInferer(cache_dir=cache_dir)

    # Pre-populate cache file
    cache_file = inferer._cache_path(cache_key)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cached_positions))

    # Call infer_positions — should hit cache
    result = inferer.infer_positions("method text", "error output", cache_key=cache_key)

    assert result == cached_positions, f"Expected {cached_positions}, got {result}"
    assert inferer.do_infer_count == 0, f"_do_infer called {inferer.do_infer_count} times, expected 0"


@settings(max_examples=100)
@given(cached_assertions=assertion_data_st, cache_key=cache_key_st)
def test_assertion_cache_hit_returns_cached_no_infer(
    cached_assertions: list[list[str]], cache_key: str, tmp_path_factory
) -> None:
    """Pre-populated assertion cache → return cached data, _do_infer NOT called."""
    cache_dir = tmp_path_factory.mktemp("assert_cache")
    inferer = CountingAssertionInferer(cache_dir=cache_dir)

    # Pre-populate cache file
    cache_file = inferer._cache_path(cache_key)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cached_assertions))

    # Call infer_assertions — should hit cache
    result = inferer.infer_assertions(
        "method with placeholders", "error output", cache_key=cache_key
    )

    assert result == cached_assertions, f"Expected {cached_assertions}, got {result}"
    assert inferer.do_infer_count == 0, f"_do_infer called {inferer.do_infer_count} times, expected 0"
