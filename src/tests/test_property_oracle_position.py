# Feature: daisy-codebase-rewrite, Property 5: Oracle position loading
"""Property test: Oracle position loading.

**Validates: Requirements 2.5**

For any ground-truth position data stored as a JSON list of ints in
``oracle_fix_position.txt``, the Oracle Position Strategy SHALL return
exactly that list of integers.

Strategy: generate random list[int], write as JSON to a temp folder's
``oracle_fix_position.txt``, create OraclePositionStrategy, call _do_infer
with dataset_folder kwarg, verify returned positions match exactly.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings
from hypothesis import strategies as st

from src.daisy.position_inference.oracle_strategy import OraclePositionStrategy


# --- Hypothesis strategies ---

positions_st = st.lists(
    st.integers(min_value=0, max_value=10_000),
    min_size=0,
    max_size=50,
)


# --- Property test ---

@settings(max_examples=100)
@given(positions=positions_st)
def test_oracle_position_loading_roundtrip(positions: list[int]) -> None:
    """Write JSON list of ints to oracle_fix_position.txt, load via OraclePositionStrategy, verify match."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        oracle_file = tmp_path / "oracle_fix_position.txt"
        oracle_file.write_text(json.dumps(positions), encoding="utf-8")

        strategy = OraclePositionStrategy(
            dataset_path=tmp_path,
            cache_dir=None,
        )

        result = strategy._do_infer(
            method_text="method Foo() { }",
            error_output="",
            dataset_folder=str(tmp_path),
        )

        assert result == positions, f"Expected {positions}, got {result}"
