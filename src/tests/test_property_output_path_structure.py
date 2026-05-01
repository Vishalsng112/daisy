# Feature: daisy-codebase-rewrite, Property 10: Output path structure preservation
"""Property test: output path structure preservation.

**Validates: Requirements 6.3, 13.2**

For any valid model_name, prog_folder, group_id strings, the cache layer
SHALL construct paths matching:
  {cache_dir}/{model_name}/{prog_folder}/{group_id}/localization/localization_raw_response.txt
  {cache_dir}/{model_name}/{prog_folder}/{group_id}/assertions_list/assertions_parsed.json

Strategy:
- Generate random model_name, prog_folder, group_id strings
- Construct cache_key as "{model_name}/{prog_folder}/{group_id}"
- Create concrete PositionInferer with cache_dir set to a tmp dir
- Verify _cache_path(cache_key) matches expected localization path
- Create concrete AssertionInferer with same cache_dir
- Verify _cache_path(cache_key) matches expected assertions path
"""

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings
from hypothesis import strategies as st

from src.daisy.position_inference.base import PositionInferer
from src.daisy.assertion_inference.base import AssertionInferer


# --- Concrete stubs (ABCs can't be instantiated directly) ---

class _StubPositionInferer(PositionInferer):
    def _do_infer(self, method_text: str, error_output: str, **kwargs: Any) -> list[int]:
        return []


class _StubAssertionInferer(AssertionInferer):
    def _do_infer(
        self, method_text_with_placeholders: str, error_output: str, **kwargs: Any
    ) -> list[list[str]]:
        return []


# --- Strategies ---

# Safe path-component strings: non-empty, no slashes/dots/null bytes
_path_component_st = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-",
    min_size=1,
    max_size=30,
)


# --- Property test ---

@settings(max_examples=100)
@given(
    model_name=_path_component_st,
    prog_folder=_path_component_st,
    group_id=_path_component_st,
)
def test_output_path_structure_preservation(
    model_name: str,
    prog_folder: str,
    group_id: str,
    tmp_path_factory,
) -> None:
    """Cache paths match {cache_dir}/{model}/{prog}/{group}/{subdir}/{file}."""
    cache_dir = tmp_path_factory.mktemp("cache")
    cache_key = f"{model_name}/{prog_folder}/{group_id}"

    # --- PositionInferer path ---
    pos_inferer = _StubPositionInferer(name="test", cache_dir=cache_dir)
    pos_path = pos_inferer._cache_path(cache_key)

    expected_pos = (
        cache_dir / model_name / prog_folder / group_id
        / "localization" / "localization_raw_response.txt"
    )
    assert pos_path == expected_pos, (
        f"PositionInferer path mismatch.\n"
        f"  Expected: {expected_pos}\n"
        f"  Got:      {pos_path}"
    )

    # Verify subdir is "localization/"
    assert pos_path.parent.name == "localization"
    # Verify group_id is grandparent
    assert pos_path.parent.parent.name == group_id

    # --- AssertionInferer path ---
    assert_inferer = _StubAssertionInferer(name="test", cache_dir=cache_dir)
    assert_path = assert_inferer._cache_path(cache_key)

    expected_assert = (
        cache_dir / model_name / prog_folder / group_id
        / "assertions_list" / "assertions_parsed.json"
    )
    assert assert_path == expected_assert, (
        f"AssertionInferer path mismatch.\n"
        f"  Expected: {expected_assert}\n"
        f"  Got:      {assert_path}"
    )

    # Verify subdir is "assertions_list/"
    assert assert_path.parent.name == "assertions_list"
    # Verify group_id is grandparent
    assert assert_path.parent.parent.name == group_id

    # --- Both share the same base prefix ---
    pos_base = pos_path.parent.parent  # {cache_dir}/{model}/{prog}/{group}
    assert_base = assert_path.parent.parent
    assert pos_base == assert_base, (
        f"Base path mismatch between inferers.\n"
        f"  Position base: {pos_base}\n"
        f"  Assertion base: {assert_base}"
    )
