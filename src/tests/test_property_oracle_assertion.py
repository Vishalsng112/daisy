# Feature: daisy-codebase-rewrite, Property 8: Oracle assertion loading
"""Property test: Oracle assertion loading.

**Validates: Requirements 4.2**

For any ground-truth assertion data stored as a JSON list of strings in
``oracle_assertions.json``, the Oracle Assertion Strategy SHALL return
each string wrapped in its own inner list → [[a1], [a2], ...].

Strategy: generate random list[str], write as JSON to a temp folder's
``oracle_assertions.json``, create OracleAssertionStrategy, call _do_infer
with dataset_folder kwarg, verify returned data matches the wrapping contract.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings
from hypothesis import strategies as st

from src.daisy.assertion_inference.oracle_strategy import OracleAssertionStrategy


# --- Hypothesis strategies ---

assertion_strings_st = st.lists(
    st.text(min_size=0, max_size=200),
    min_size=0,
    max_size=50,
)


# --- Property test ---

@settings(max_examples=100)
@given(assertions=assertion_strings_st)
def test_oracle_assertion_loading_roundtrip(assertions: list[str]) -> None:
    """Write JSON list of strings to oracle_assertions.json, load via OracleAssertionStrategy, verify each wrapped in inner list."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        oracle_file = tmp_path / "oracle_assertions.json"
        oracle_file.write_text(json.dumps(assertions), encoding="utf-8")

        strategy = OracleAssertionStrategy(
            dataset_path=tmp_path,
            cache_dir=None,
        )

        result = strategy._do_infer(
            method_text_with_placeholders="method Foo() { }",
            error_output="",
            dataset_folder=str(tmp_path),
        )

        expected = [[a] for a in assertions]
        assert result == expected, f"Expected {expected}, got {result}"
