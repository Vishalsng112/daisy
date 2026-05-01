# Feature: daisy-codebase-rewrite, Property 9: Cache miss error reports exact missing entries
"""Property test: cache miss error reports exact missing entries.

**Validates: Requirements 9.3**

For any dataset with N assertion groups where M < N have cached results,
ResultsReader.check_all_cached() SHALL report exactly the N-M missing
entries by their group identifiers (prog_folder/group_id).

Strategy:
- Generate N unique (prog_folder, group_id) pairs
- Pick M < N to be "cached" (create their localization cache files)
- Call check_all_cached(), verify missing list has exactly N-M entries
  matching the uncached group IDs
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from src.analysis.results_reader import ResultsReader


# --- Strategies ---

# Safe path-component strings (no slashes, no dots, non-empty)
_path_component_st = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789_",
    min_size=1,
    max_size=20,
)

# Generate a unique list of (prog_folder, group_id) tuples
_group_st = st.tuples(_path_component_st, _path_component_st)

_groups_list_st = st.lists(
    _group_st,
    min_size=2,
    max_size=30,
    unique=True,
)

# Model name
_model_name_st = _path_component_st


# --- Property test ---

@settings(max_examples=100)
@given(
    model_name=_model_name_st,
    groups=_groups_list_st,
    data=st.data(),
)
def test_cache_miss_reports_exact_missing_entries(
    model_name: str,
    groups: list[tuple[str, str]],
    data: st.DataObject,
    tmp_path_factory,
) -> None:
    """N groups, cache M < N → missing list has exactly N-M uncached IDs."""
    n = len(groups)
    # Pick M: at least 0, at most N-1 (so there's always ≥1 missing)
    m = data.draw(st.integers(min_value=0, max_value=n - 1), label="cached_count")

    cached_groups = set(range(m))
    expected_missing: set[str] = set()

    results_dir = tmp_path_factory.mktemp("results")
    reader = ResultsReader(results_dir)

    # Create cache files for the first M groups
    for i, (prog_folder, group_id) in enumerate(groups):
        if i in cached_groups:
            loc_file = (
                results_dir / model_name / prog_folder / group_id
                / "localization" / "localization_raw_response.txt"
            )
            loc_file.parent.mkdir(parents=True, exist_ok=True)
            loc_file.write_text("[1, 2, 3]")
        else:
            expected_missing.add(f"{prog_folder}/{group_id}")

    # Call check_all_cached
    missing = reader.check_all_cached(model_name, groups)

    # Verify count
    assert len(missing) == n - m, (
        f"Expected {n - m} missing, got {len(missing)}"
    )

    # Verify exact set match
    assert set(missing) == expected_missing, (
        f"Missing set mismatch.\n"
        f"  Expected: {sorted(expected_missing)}\n"
        f"  Got:      {sorted(missing)}"
    )
